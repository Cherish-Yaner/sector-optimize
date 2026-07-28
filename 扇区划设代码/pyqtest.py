import sys
from math import cos, sin, radians
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QPushButton, QMessageBox
from PyQt6.QtGui import QPainter, QPen, QPolygonF
from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtCore import QThread, pyqtSignal, QObject, QCoreApplication, QMetaObject

import pickle
import threading
import socket

from init import init
from scene import transfer_grid, input_action, scene_step, get_overall_observation, save_observation_to_json, scene_act, get_valid_transfers

from MARLlib.marllib import marl
from register_env import env_creator

from gridmap import GridMap
from gridize import hexize
from polygon import hexes

gbl_lock = threading.Lock()

class GridWidget(QWidget):
    def __init__(self, rows=5, cols=5):
        super().__init__()
        self.rows = rows  # 网格行数
        self.cols = cols  # 网格列数

    def paintEvent(self, event):
        # 创建绘图工具
        painter = QPainter(self)
        painter.setPen(QPen(Qt.GlobalColor.black, 1))  # 设置黑色画笔，线宽1像素

        # 获取当前窗口尺寸
        width = self.width()
        height = self.height()

        # 计算每个单元格的宽高
        cell_width = width / self.cols
        cell_height = height / self.rows

        # 绘制垂直线（列分割线）
        for i in range(self.cols + 1):
            x = i * cell_width
            painter.drawLine(QPointF(x, 0), QPointF(x, height))

        # 绘制水平线（行分割线）
        for i in range(self.rows + 1):
            y = i * cell_height
            painter.drawLine(QPointF(0, y), QPointF(width, y))

class HexGridWidget(QWidget):
    def __init__(self, rows=5, cols=5):
        super().__init__()
        self.rows = rows  # 网格行数
        self.cols = cols  # 网格列数

    def paintEvent(self, event):
        # 创建绘图工具
        painter = QPainter(self)
        painter.setPen(QPen(Qt.GlobalColor.blue, 2))  # 设置蓝色画笔，线宽2像素

        # 获取当前窗口尺寸
        width = self.width()
        height = self.height()

        # 六边形的边长（根据窗口尺寸动态调整）
        hex_size = min(width / (self.cols * 1.5), height / (self.rows * 1.5))

        # 六边形的高度和宽度
        hex_width = hex_size * 1.5
        hex_height = hex_size * (3 ** 0.5)

        # 绘制六边形网格
        for row in range(self.rows):
            for col in range(self.cols):
                # 计算六边形的中心点
                x = col * hex_width + (row % 2) * (hex_width / 2)
                y = row * hex_height * 0.75

                # 绘制六边形
                self.draw_hexagon(painter, x, y, hex_size)

    def draw_hexagon(self, painter, center_x, center_y, size):
        # 计算六边形的六个顶点
        points = []
        for i in range(6):
            angle_deg = 60 * i
            angle_rad = radians(angle_deg)
            x = center_x + size * cos(angle_rad)
            y = center_y + size * sin(angle_rad)
            points.append(QPointF(x, y))

        # 使用 QPolygonF 绘制六边形
        polygon = QPolygonF(points)
        painter.drawPolygon(polygon)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PyQt6 网格示例")
        self.setGeometry(100, 100, 700, 700)  # 窗口位置和尺寸
        
        container = QWidget()
        self.setCentralWidget(container)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(20, 20, 20, 20)


        # 创建网格部件并设置为中央部件
        self.grid_widget = GridWidget()
        self.hex_widget = HexGridWidget()

        layout.addWidget(self.hex_widget)
        # 创建按钮并添加到布局中
        self.button = QPushButton("点击我")
        self.button.clicked.connect(self.show_message)  # 连接按钮点击事件
        layout.addWidget(self.button)

    def show_message(self):
        QMessageBox.information(self, "提示", "你好，这是一个消息框！")

def input_thread(widget: GridMap):
    while True:
        try:
            cmd = input(">>> ").strip()
            if cmd == "act":
                grid_id, dom_id = input("grid_id, dom_id: ").split(",")
                scene_act(gbl_lock, int(grid_id), int(dom_id))
                widget.update()
            elif cmd == "quit":
                QMetaObject.invokeMethod(app, "quit",
                         Qt.ConnectionType.QueuedConnection)
                return
            elif cmd == "obs":
                with gbl_lock:
                    save_observation_to_json()
                    # print("observation:")
                    # print(str(get_overall_observation()))
        except Exception as e:
            print(f"[ERROR] {e}")

def tcp_listener_thread(widget: GridMap,
                        host: str = "0.0.0.0",
                        port: int = 4291,
                        backlog: int = 5):
    """在独立线程中启动一个轻量 TCP 服务器。"""
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((host, port))
    srv.listen(backlog)
    print(f"[TCP] listening on {host}:{port}")

    try:
        while True:
            conn, addr = srv.accept()
            print(f"[TCP] new connection from {addr}")
            # 对每个客户端再起一个子线程，互不阻塞
            threading.Thread(
                target=_handle_client,
                args=(conn, widget),
                daemon=True
            ).start()
    finally:
        srv.close()


def _handle_client(conn: socket.socket, widget: GridMap):
    """一次性读完整个客户端连接，按行解析命令。"""
    with conn:
        buffer = b""
        while True:
            chunk = conn.recv(1024)
            if not chunk:           # 对方关流
                break
            buffer += chunk
            while b"\n" in buffer:  # 支持粘包
                line, buffer = buffer.split(b"\n", 1)
                _dispatch_command(line.decode().strip(), widget, conn)


def _dispatch_command(cmd_line: str, widget: GridMap, conn: socket.socket):
    """将字符串命令映射到原本的业务逻辑。"""
    if not cmd_line:
        return

    # 统一大小写 & 去除多余空白
    cmd_line = cmd_line.lower().strip()
    tokens = [tok.strip() for tok in cmd_line.split(",")]

    try:
        if tokens[0] == "act":
            if len(tokens) != 3:
                raise ValueError("act 命令应为 act,<grid_id>,<dom_id>")
            grid_id, dom_id = map(int, tokens[1:])
            reward = scene_act(gbl_lock, grid_id, dom_id)
            conn.sendall(
                str(reward).encode("utf-8") + b"\n"
            )
            widget.update()

        elif tokens[0] == "obs":
            if len(tokens) != 2:
                raise ValueError("obs 命令应为 obs,<section_id>")
            section_id = int(tokens[1])
            conn.sendall(
                str(get_overall_observation(section_id)).encode("utf-8") + b"\n"
            )

        elif tokens[0] == "transfer":
            if len(tokens) != 2:
                raise ValueError("transfer 命令应为 transfer,<section_id>")
            section_id = int(tokens[1])
            conn.sendall(
                str(get_valid_transfers(section_id)).encode("utf-8") + b"\n"
            )

        elif tokens[0] == "quit":
            # 让 GUI 主线程优雅退出
            QMetaObject.invokeMethod(
                app, "quit", Qt.ConnectionType.QueuedConnection
            )

        else:
            print(f"[TCP] unknown command: {cmd_line}")

    except Exception as exc:
        print(f"[TCP-ERROR] {exc}")

def train():

    env = marl.make_env(environment_name="TBXGridEnv", map_name="default", lock=None)

    mappo = marl.algos.mappo(hyperparam_source="common")

    model = marl.build_model(env, mappo, {"core_arch": "mlp", "encode_layer": "128-128"})

    # mappo.load_checkpoint(
    #     "C:/Users/Bardi/Work/series/4-4/3-11/exp_results/mappo_mlp_default/MAPPOTrainer_TBXGridEnv_default_e0049_00000_0_2025-05-03_09-21-01/checkpoint_000001"
    # )

    mappo.fit(
        env,
        model,
        stop={'timesteps_total': 300},
        local_mode=True,
        share_policy="all",
        num_workers=0,
        checkpoint_freq=100,
        checkpoint_end=True,
        restore_path={
          'params_path': "exp_results/mappo_mlp_default/MAPPOTrainer_TBXGridEnv_default_e0049_00000_0_2025-05-03_09-21-01/params.json",
          'model_path': "exp_results/mappo_mlp_default/MAPPOTrainer_TBXGridEnv_default_e0049_00000_0_2025-05-03_09-21-01/checkpoint_000001/checkpoint-1"
        }
    )

if __name__ == "__main__":
    
    # app = QApplication(sys.argv)
    # # window = MainWindow()
    # # window.show()

    

    init()
    scene_step()

    train()

    # gridmap = GridMap([], gbl_lock=gbl_lock)
    # gridmap.show()

    # threading.Thread(target=train, daemon=True).start()
    # # threading.Thread(target=tcp_listener_thread, args=(gridmap,), daemon=True).start()

    # sys.exit(app.exec())
from PyQt6.QtWidgets import QApplication, QMainWindow, QLabel, QWidget, QVBoxLayout, QTextEdit, QTextBrowser
from PyQt6.QtCore import Qt, QPoint
import sys
import predefines

from section import Section
from polygon import HexGrid

class BulletinBoard(QTextBrowser):
    """HTML 样式的告示板，动态更新栅格和扇区信息"""
    def __init__(self):
        super().__init__()

        # 样式
        self.setStyleSheet("font-size: 16px; background-color: #f0f0f0; padding: 10px; border: 1px solid #aaa;")
        self.setFixedSize(300, 200)

        # 初始化信息
        self.grid_id = "未知"
        self.sector_id = "未知"
        self.sector_info = {}

        self.update_display()

    def set_grid_sector(self, grid_id, sector_id):
        """更新栅格和扇区编号"""
        self.grid_id = grid_id
        self.sector_id = sector_id
        self.update_display()

    def update_sector_info(self, sector_id, info):
        """更新某个扇区的信息"""
        self.sector_info[sector_id] = info
        self.update_display()

    def clear_sector_info(self):
        """清空所有扇区信息"""
        self.sector_info.clear()
        self.update_display()

    def update_display(self):
        """用 HTML 方式更新文本显示"""
        sector_details = "".join(
            f"<tr><td><b>扇区 {sid}</b></td><td>{info}</td></tr>"
            for sid, info in self.sector_info.items()
        ) or "<tr><td colspan='2'>暂无数据</td></tr>"

        html_content = f"""
        <html>
        <body>
            <h2>告示板</h2>
            <p><b>栅格：</b> #{self.grid_id}</p>
            <p><b>扇区：</b> #{self.sector_id}</p>
            <h3>扇区详情：</h3>
            <table border="1" cellspacing="0" cellpadding="5">
                <tr><th>扇区</th><th>信息</th></tr>
                {sector_details}
            </table>
        </body>
        </html>
        """
        self.setHtml(html_content)
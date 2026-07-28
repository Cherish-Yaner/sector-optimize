from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import QPainter, QPen, QFont, QBrush
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QMenu

from shapely.geometry import Polygon

from polygon import hexes, find_point_hexgrid
from section import get_grid_section, find_point_section
from scene import transfer_grid
from typing import List

from config import gbl_config

# from BulletinBoard import BulletinBoard

import predefines
import math

earth_radius = 6371.393

class GridMap(QWidget):
    def __init__(self, polygons: List[Polygon] = [], gbl_lock=None):
        super().__init__()
        self.setWindowTitle("经纬网格地图")
        self.resize(900, 600)
        self.gbl_lock = gbl_lock

        # self.dashboard = BulletinBoard()

        self.lng_min, self.lng_max = predefines.lng_min, predefines.lng_max
        self.lat_min, self.lat_max = predefines.lat_min, predefines.lat_max
        self.grid_interval = predefines.grid_interval
        

        # 按地图内平均纬度计算每经度长度
        self.parallel_cofficient = predefines.parallel_cofficient   
        self.len_per_lng = predefines.len_per_lng   
        self.len_per_lat = predefines.len_per_lat
        self.km_per_pixel = None

        self.left_padding = 50
        self.right_padding = 50
        self.up_padding = 15
        self.down_padding = 15

        self.polygons = polygons
        self.polygons += [predefines.full_area]
        self.polygons += predefines.preset_areas

    # 将经纬度坐标转换为窗口坐标
    def convertCoord(self, lng, lat) -> QPointF:
        x = self.left_padding + (lng - self.lng_min) * self.len_per_lng / self.km_per_pixel
        y = self.up_padding + (self.lat_max - lat) * self.len_per_lat / self.km_per_pixel
        return QPointF(x, y)
    
    # 将窗口坐标转换为经纬度坐标
    def revConvertCoord(self, x, y):
        lng = self.lng_min + (x - self.left_padding) * self.km_per_pixel / self.len_per_lng
        lat = self.lat_max - (y - self.up_padding) * self.km_per_pixel / self.len_per_lat
        return lng, lat

    def drawHexGrid(self, painter):
        original_pen = painter.pen()
        original_brush = painter.brush()
        for hex_grid in hexes:
            self.drawPolygon(painter, hex_grid.get_polygon(), Qt.GlobalColor.blue, 0.7)
            # draw index with red color

            if gbl_config.grid_name:
                painter.setPen(QPen(
                    predefines.area_colors[get_grid_section(hex_grid.index, self.gbl_lock)], 1
                ))
                painter.drawText(self.convertCoord(*hex_grid.get_center()) + QPointF(-9, 3), f'{hex_grid.index:03d}')
            if gbl_config.fill_color:
                brush = QBrush(predefines.area_colors[get_grid_section(hex_grid.index, self.gbl_lock)])
                painter.setBrush(brush)
                self.drawPolygon(painter, hex_grid.get_polygon())
            # if gbl_config.fill_color:
            #     painter.fillPolygon(self.convertCoord(hex_grid.get_polygon().exterior.coords))
            # draw coord
            # painter.drawText(self.convertCoord(hex_grid.get_w()[0], hex_grid.get_w()[1] - 0.1), f"{hex_grid.get_w()[0]:.1f},{hex_grid.get_w()[1]:.1f}")

            painter.setPen(original_pen)
            painter.setBrush(original_brush)

        painter.setPen(original_pen)
        painter.setBrush(original_brush)

    def drawFlightPoints(self, painter):
        for point_name, point_coord in predefines.named_flight_points_dict.items():
            painter.setPen(QPen(Qt.GlobalColor.red, 2))
            painter.drawPoint(self.convertCoord(*point_coord))
            if gbl_config.flight_point_name:
                painter.drawText(self.convertCoord(*point_coord) + QPointF(5, 5), point_name)

    def drawFlights(self, painter):
        for flight_name, flight in predefines.flights_dict.items():
            painter.setPen(QPen(Qt.GlobalColor.blue, 3))
            for i in range(len(flight) - 1):
                painter.drawLine(
                    self.convertCoord(*predefines.named_flight_points_dict[flight[i]]),
                    self.convertCoord(*predefines.named_flight_points_dict[flight[i + 1]])
                )

    def drawPolygon(self, painter, polygon: Polygon, color=Qt.GlobalColor.black, width=1):
        original_pen = painter.pen()
        painter.setPen(QPen(color, width))
        vertices = polygon.exterior.coords
        points = []
        for vertex in vertices:
            lng, lat = vertex
            points.append(self.convertCoord(lng, lat))
        painter.drawPolygon(points)
        painter.setPen(original_pen)

    def drawScaleBar(self, painter, width, height):
        scale_lengths = [5, 10, 20, 50, 100, 200]  # 可能的比例尺选项（单位：公里）
        
        # 选择一个合适的比例尺长度
        for length in scale_lengths:
            scale_length_pixels = length / self.km_per_pixel
            if 30 < scale_length_pixels < width / 5:
                break  # 找到合适的比例尺长度

        # 确定比例尺的位置（放在右下角）
        margin = 20
        start_x = width - scale_length_pixels - margin  # 右下角对齐
        start_y = height - margin

        # 绘制比例尺主线
        pen = QPen(Qt.GlobalColor.black, 2)
        painter.setPen(pen)
        painter.drawLine(QPointF(start_x, start_y), QPointF(start_x + scale_length_pixels, start_y))

        # 绘制两端的小竖线
        painter.drawLine(QPointF(start_x, start_y - 5), QPointF(start_x, start_y + 5))
        painter.drawLine(QPointF(start_x + scale_length_pixels, start_y - 5), QPointF(start_x + scale_length_pixels, start_y + 5))

        # 标注文本
        text_x = start_x + scale_length_pixels / 2 - 15  # 文字居中
        text_y = start_y - 10
        painter.drawText(QPointF(text_x, text_y), f"{length} km")

    def contextMenuEvent(self, event):
        # 获取右键点击的位置（窗口坐标）
        pos = event.pos()
        lng, lat = self.revConvertCoord(pos.x(), pos.y())

        # 创建菜单
        menu = QMenu(self)
        
        # 创建一个包含坐标的测试项
        action_text = f"测试：经度 {lng:.4f}°, 纬度 {lat:.4f}°"
        test_action = QAction(action_text, self)
        test_action.triggered.connect(lambda: self.on_test_action_triggered(lng, lat))

        idx = find_point_section(lng, lat)
        idx2 = find_point_hexgrid(lng, lat)
        if idx != -1:
            for i in range(predefines.nr_sections):
                if i == idx:
                    continue
                action_text = f"将格子 {idx2} 所属扇区从 {idx} 更改到 {i} ({str(predefines.area_colors[i])})"
                change_action = QAction(action_text, self) 
                change_action.triggered.connect(
                    lambda _, i=i: self.change_grid_section(lng, lat, i)
                )
                menu.addAction(change_action)


        menu.addAction(test_action)
        menu.exec(event.globalPos())

    def on_test_action_triggered(self, lng, lat):
        print(f"经度={lng:.4f}°, 纬度={lat:.4f}°")
    
    def change_grid_section(self, lng, lat, id_target):
        idx = find_point_section(lng, lat)
        idx2 = find_point_hexgrid(lng, lat)
        assert idx != -1 and idx2 != -1, "Invalid coordinates for changing section"
        transfer_grid(idx2, id_target, idx)
        print(f"将格子 {idx2} 所属扇区从 {idx} 更改到 {id_target}({str(predefines.area_colors[id_target])})")
        self.update()

    def mouseMoveEvent(self, event):
        pass
        # x = event.x()
        # y = event.y()
        # lng, lat = self.revConvertCoord(x, y)
        # self.statusBar().showMessage(f"经度：{lng:.2f}°，纬度：{lat:.2f}°")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        width = self.width()
        height = self.height()

        font = QFont()
        font.setPixelSize(10)
        painter.setFont(font)

        effective_width = width - self.left_padding - self.right_padding
        effective_height = height - self.up_padding - self.down_padding

        lng_range = self.lng_max - self.lng_min
        lat_range = self.lat_max - self.lat_min

        pixel_per_lng = effective_width / lng_range
        pixel_per_lat = effective_height / lat_range

        if pixel_per_lat * self.parallel_cofficient < pixel_per_lng:
            pixel_per_lng = pixel_per_lat * self.parallel_cofficient
            real_width = pixel_per_lng * lng_range + self.left_padding
            real_height = height - self.down_padding
        else:
            pixel_per_lat = pixel_per_lng / self.parallel_cofficient
            real_width = width - self.right_padding
            real_height = pixel_per_lat * lat_range + self.up_padding

        self.km_per_pixel = self.len_per_lng / pixel_per_lng

        self.drawScaleBar(painter, width, height)

        # 画六边形网格
        self.drawHexGrid(painter)

        # 画航班点
        self.drawFlightPoints(painter)

        # 画航班
        self.drawFlights(painter)

        # 画多边形
        for polygon in self.polygons:
            self.drawPolygon(painter, polygon)
        

        # 设置网格线样式
        pen = QPen(Qt.GlobalColor.black, 0, Qt.PenStyle.DashLine)
        pen_bold = QPen(Qt.GlobalColor.black, 1, Qt.PenStyle.DashLine)
        painter.setPen(pen)

        # 画经线
        lng = self.lng_min
        x = 50
        while lng <= self.lng_max + 1e-5:
            int_error = min(math.fabs(lng - int(lng)), math.fabs(lng - (int(lng) + 1)))
            if int_error < self.grid_interval / 2:
                painter.drawText(int(x) - 20, 10, f"{lng:.1f}°E")
                painter.setPen(pen_bold)
                painter.drawLine(
                    QPointF(int(x), self.up_padding), 
                    QPointF(int(x), real_height)
                )
                painter.setPen(pen)
            else:
                painter.drawLine(
                    QPointF(int(x), self.up_padding), 
                    QPointF(int(x), real_height)
                )
            lng += self.grid_interval
            x += self.grid_interval * pixel_per_lng

        # 画纬线
        lat = self.lat_max
        y = 15
        while lat >= self.lat_min - 1e-5:
            int_error = min(math.fabs(lat - int(lat)), math.fabs(lat - (int(lat) + 1)))
            if int_error < self.grid_interval / 2:
                painter.drawText(10, int(y) + 5, f"{lat:.1f}°N")
                painter.setPen(pen_bold)
                painter.drawLine(
                    QPointF(self.left_padding, int(y)), 
                    QPointF(real_width, int(y))
                )
                painter.setPen(pen)
            else:
                painter.drawLine(
                    QPointF(self.left_padding, int(y)), 
                    QPointF(real_width, int(y))
                )
            lat -= self.grid_interval
            y += self.grid_interval * pixel_per_lat
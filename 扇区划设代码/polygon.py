from dataclasses import dataclass
from shapely.geometry import Polygon, Point
from typing import Optional, Tuple, List, Dict
import numpy as np
import shapely
import math

import predefines

# @dataclass
# class Polygon:
#   def __init__(
#     self, 
#     points: list[tuple[float, float]]
#   ):
#     self.points = points
  
@dataclass
class HexGrid:
  def __init__(
    self,
    index: int,
    start: Tuple[float, float],
    coord: Tuple[int, int]
  ):
    # 西北角坐标
    self.index = index
    self.start = start
    self.section = -1
    self.flight_id = []
    self.flow = 0
    self.conflict_cnt = 0
    self.vertices = self.update_vertices()
    self.neighbors: dict[str, Optional[int]] = {
      'n': None,
      'ne': None,
      'se': None,
      's': None,
      'sw': None,
      'nw': None
    }
    self.coord = coord

  def update_vertices(
    self
  ) -> List[Tuple[float, float]]:
    return [
      # 西北 lng, lat
      (self.start[0], self.start[1]),
      # 东北 lng + hex_size, lat
      (self.start[0] + predefines.hex_size / predefines.len_per_lng, self.start[1]),
      # 东   lng + hex_size * 1.5, lat - hex_size * (sqrt(3) / 2)
      (self.start[0] + (predefines.hex_size * 1.5) / predefines.len_per_lng, self.start[1] - predefines.hex_size * ((3 ** 0.5) / 2) / predefines.len_per_lat),
      # 东南 lng + hex_size, lat - hex_size * sqrt(3)
      (self.start[0] + predefines.hex_size / predefines.len_per_lng, self.start[1] - predefines.hex_size * (3 ** 0.5) / predefines.len_per_lat),
      # 西南 lng, lat - hex_size * sqrt(3)
      (self.start[0], self.start[1] - predefines.hex_size * (3 ** 0.5) / predefines.len_per_lat),
      # 西   lng - hex_size * 0.5, lat - hex_size * (sqrt(3) / 2)
      (self.start[0] - (predefines.hex_size * 0.5) / predefines.len_per_lng, self.start[1] - predefines.hex_size * ((3 ** 0.5) / 2) / predefines.len_per_lat)
    ]

  def contains(self, point: Point) -> bool:
    # 这里其实错了，但是其实不影响，所以我不敢改。
    if point.x < self.vertices[5][0] - 1e6:
      return False
    if point.x > self.vertices[2][0] + 1e6:
      return False
    if point.y > self.vertices[0][1] + 1e6:
      return False
    if point.y < self.vertices[4][1] - 1e6:
      return False
    return self.get_polygon().contains(point)

  def intersects(self, point: Point) -> bool:
    # 这里其实错了，但是其实不影响，所以我不敢改。
    if point.x < self.vertices[5][0] - 1e6:
      return False
    if point.x > self.vertices[2][0] + 1e6:
      return False
    if point.y > self.vertices[0][1] + 1e6:
      return False
    if point.y < self.vertices[4][1] - 1e6:
      return False
    return self.get_polygon().intersects(point)
  
  def get_polygon(self) -> Polygon:
    return Polygon(self.vertices)

  def get_nw(self):
    return self.vertices[0]

  def get_ne(self):
    return self.vertices[1]

  def get_e(self):
    return self.vertices[2]
  
  def get_se(self):
    return self.vertices[3]

  def get_sw(self):
    return self.vertices[4]

  def get_w(self):
    return self.vertices[5]

  def get_center(self):
    return (
      (self.vertices[0][0] + self.vertices[3][0]) / 2,
      (self.vertices[0][1] + self.vertices[3][1]) / 2
    )

hexes: List[HexGrid] = []

coord_dict: Dict[Tuple[int, int], int] = {}
coord_lng_range : Dict[int, Tuple[float, float]] = {}
coord_lat_range : Dict[int, Tuple[float, float]] = {}

def find_a_close_coord(
  lng: float,
  lat: float
) -> Tuple[int, int]:

  initial_point = hexes[coord_dict[(0, 0)]].start

  coord_x = math.floor((lng - initial_point[0]) / (predefines.hex_size / predefines.len_per_lng * 1.5))
  coord_y = math.floor((lat - initial_point[1]) / (predefines.hex_size / predefines.len_per_lat * (3 ** 0.5) / 2))

  return (coord_x, coord_y)

def is_point_in_coord(
  lng: float,
  lat: float,
  coord: Tuple[int, int]
) -> bool:
  if coord not in coord_dict:
    return False
  hexgrid_id = coord_dict[coord]
  return hexes[hexgrid_id].contains(Point(lng, lat)) or hexes[hexgrid_id].intersects(Point(lng, lat))

def find_point_hexgrid(
  lng: float,
  lat: float
) -> int:

  close_coord = find_a_close_coord(lng, lat)
  for i in range(0, 2):
    j_start = 1 if (close_coord[0] + close_coord[1] - i) % 2 != 0 else 0
    for j in range(j_start, 3, 2):
      now_coord_0 = (close_coord[0] + i, close_coord[1] + j)
      if is_point_in_coord(lng, lat, now_coord_0):
        return (coord_dict[now_coord_0])
      if j != 0:
        now_coord_1 = (close_coord[0] + i, close_coord[1] - j)
        if is_point_in_coord(lng, lat, now_coord_1):
          return (coord_dict[now_coord_1])
      if i != 0:
        now_coord_2 = (close_coord[0] - i, close_coord[1] + j)
        if is_point_in_coord(lng, lat, now_coord_2):
          return (coord_dict[now_coord_2])
      if i != 0 and j != 0:
        now_coord_3 = (close_coord[0] - i, close_coord[1] - j)
        if is_point_in_coord(lng, lat, now_coord_3):
          return (coord_dict[now_coord_3])

  # raise ValueError("No hexgrid found for the given coordinates.")

  return -1


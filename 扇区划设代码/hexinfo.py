from shapely.geometry import Polygon, Point, LineString
import numpy as np

from polygon import find_point_hexgrid, HexGrid
from config import gbl_config
from predefines import preset_areas, nr_sections, named_flight_points_dict, flights_dict, nr_time_slices, period_time_end, period_time_start, len_per_lat, len_per_lng
from loaders.loader import Scene

def get_grid_filghts_total_length(
  hexes: list[HexGrid],
  grid_id: int
) -> float:
  res: float = 0
  # 遍历所有航班
  for fid, flight in flights_dict.items():
    # 遍历航班的所有点
    for i in range(len(flight) - 1):
      # 航班线
      line = LineString([named_flight_points_dict[flight[i]], named_flight_points_dict[flight[i + 1]]])
      hex_poly = hexes[grid_id].get_polygon()
      # 计算相交长度并相加
      if hex_poly.intersects(line):
        res_line = line.intersection(hex_poly)
        d1 = (res_line.xy[0][0] - res_line.xy[0][1]) * len_per_lng
        d2 = (res_line.xy[1][0] - res_line.xy[1][1]) * len_per_lat
        res += (d1 ** 2 + d2 ** 2) ** 0.5
  return res


class HexInfo:
  instant_flow: float = 0
  normal_inst_cnt: float = 0
  conflict_dissolution_cnt: float = 0

def scene_payload_hexgrid(
  scene_id: int,
  scene: Scene,
  
)


class HexInfoSet:

  

  def __init__(self, hexes: list[HexGrid], scene: Scene):
    self.hexes = hexes
    self.scene = scene

    

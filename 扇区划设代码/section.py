from shapely.geometry import Polygon, Point, LineString
import numpy as np
from typing import Optional, List

from polygon import hexes, find_point_hexgrid
from gridize import hexize
from config import gbl_config
from predefines import preset_areas, nr_sections, named_flight_points_dict, flights_dict, nr_time_slices, period_time_end, period_time_start, len_per_lat, len_per_lng

from loaders.loader import Scene

class SectionPayload:
  instant_flow: float
  general_inst_cnt: float
  conflict_dissolution_cnt: float
  orientation_randomness: float
  area_traffic_density: float

  def __init__(
    self,
    instant_flow: float,
    general_inst_cnt: float,
    conflict_dissolution_cnt: float,
    orientation_randomness: float,
    area_traffic_density: float
  ):
    self.instant_flow = instant_flow
    self.general_inst_cnt = general_inst_cnt
    self.conflict_dissolution_cnt = conflict_dissolution_cnt
    self.orientation_randomness = orientation_randomness
    self.area_traffic_density = area_traffic_density

  def __str__(self):
    return f"""
    instant_flow: {self.instant_flow}
    general_inst_cnt: {self.general_inst_cnt}
    conflict_dissolution_cnt: {self.conflict_dissolution_cnt}
    orientation_randomness: {self.orientation_randomness}
    area_traffic_density: {self.area_traffic_density}
    """

class Section:
  index: int
  grid_list: List[int]

  section_payload: Optional[SectionPayload]
  total_flight_length: float

  payload_mean: float
  payload_list: List[float]

  articulation_points: List[int]

  # gini_coff_mean: float
  # gini_coff_list: List[float]

  def __init__(
    self,
    index: int
  ):
    self.index = index
    self.grid_list = []
    self.section_payload = None

    self.payload_mean = 0
    self.payload_list = []

    self.articulation_points = []

    self.gini_coff_mean = 0
    self.gini_coff_list = []

  def evaluate(self):
    self.total_flight_length = get_section_filghts_total_length(self.index)
    pass

  def validate(self) -> bool:
    pass

sections: List[Section] = [Section(i) for i in range(nr_sections)]

def get_grid_section(grid_id: int, lock):

  if lock is None:
    if grid_id == -1:
      return -1

    try:
      if hexes[grid_id].section != -1:
        return hexes[grid_id].section
    except IndexError as e:
      print(f"Error: {e}, grid_id: {grid_id}, len(hexes): {len(hexes)}")
      raise e

    for section in sections:
      if grid_id in section.grid_list:
        return section.index
  else:
    with lock:
      if grid_id == -1:
        return -1

      if hexes[grid_id].section != -1:
        return hexes[grid_id].section

      for section in sections:
        if grid_id in section.grid_list:
          return section.index
    
  return -1

def find_point_section(
  lng: float,
  lat: float
) -> int:
  hex_idx = find_point_hexgrid(lng, lat)
  if hex_idx == -1:
    return -1
  return get_grid_section(hex_idx, None)

def get_section_filghts_total_length(section_id: int):
  res: float = 0
  # 遍历所有航班
  for fid, flight in flights_dict.items():
    # 遍历航班的所有点
    for i in range(len(flight) - 1):
      # 航班线
      line = LineString([named_flight_points_dict[flight[i]], named_flight_points_dict[flight[i + 1]]])
      # 遍历所有栅格
      for hex_id in sections[section_id].grid_list:
        # 生成栅格多边形
        hex_poly = hexes[hex_id].get_polygon()
        # 计算相交长度并相加
        if hex_poly.intersects(line):
          res_line = line.intersection(hex_poly)
          d1 = (res_line.xy[0][0] - res_line.xy[0][1]) * len_per_lng
          d2 = (res_line.xy[1][0] - res_line.xy[1][1]) * len_per_lat
          res += (d1 ** 2 + d2 ** 2) ** 0.5
  return res

def get_generate_sections():
  for hex_grid in hexes:
    with np.errstate(invalid="ignore"):
      hex_grid_areas_intersections = sorted([
        (i, area.intersection(hex_grid.get_polygon()))
        for i, area in enumerate(preset_areas)
      ], key=lambda x: x[1].area, reverse=True)
    # print(f'{hex_grid.get_polygon()}, {[_ for _ in preset_areas]}, {[_.intersection(hex_grid.get_polygon()) for _ in preset_areas]}')
    print(f'{hex_grid.index} in section #{hex_grid_areas_intersections[0][0]}')
    sections[hex_grid_areas_intersections[0][0]].grid_list.append(hex_grid.index)

  with open('sections.txt', 'w') as f:
    for section in sections:
      f.write(f'section #{section.index}: {section.grid_list}\n') 

if __name__ == "__main__":
  hexize()
  get_generate_sections()
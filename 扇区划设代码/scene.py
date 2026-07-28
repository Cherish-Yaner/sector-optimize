import numpy as np
import pickle
from typing import Optional
import time
from shapely.geometry import Polygon, Point, LineString


from typing import List, Set, Dict

from loaders.loader import Scene
from polygon import hexes, find_point_hexgrid
from section import SectionPayload, sections, find_point_section, get_grid_section
from predefines import preset_areas, nr_sections, named_flight_points_dict, flights_dict, nr_time_slices, len_per_lat, len_per_lng
from config import gbl_config
from utils.tarjan import compute_section_articulation_points

from dataclasses import dataclass, asdict

import math

from loaders import loader

scene_data: Optional[loader.LoaderData] = loader.LoaderData.load(gbl_config.data_name)

step_cnt = 0
with open("model/random_forest_model0113.pkl", "rb") as f:
  payload_fit_model = pickle.load(f)

with open("model/random_forest_model_0603.pkl", "rb") as f:
  payload_fit_model2 = pickle.load(f)

flights_hexes_dict: Dict[str, List[int]] = {_ : [] for _ in flights_dict.keys()}
# 这个其实可以靠现查构造，不必维护
# flights_section_dict: Dict[str, List[int]] = {_ : [] for _ in flights_dict.keys()}

def scene_init():

  sorted_hexes = sorted(
    hexes,
    key=lambda x: (x.get_center()[0], x.get_center()[1])
  )

  # for hex_grid in hexes:
  #   for fid, flight in flights_dict.items():
  #     for i in range(len(flight) - 1):
  #       line = LineString([named_flight_points_dict[flight[i]], named_flight_points_dict[flight[i + 1]]])
  #       hex_poly = hex_grid.get_polygon()


  for hex_grid in sorted_hexes:
    for fid, flight in flights_dict.items():
      for i in range(len(flight) - 1):
        line = LineString([named_flight_points_dict[flight[i]], named_flight_points_dict[flight[i + 1]]])
        hex_poly = hex_grid.get_polygon()
        # 有可能一个栅格和两条线段相交，要判重
        if hex_poly.intersects(line) and fid not in hex_grid.flight_id:
          hex_grid.flight_id.append(fid)
          flights_hexes_dict[fid].append(hex_grid.index)
          # flights_section_dict[fid].append(hex_grid.section)
          
  for fid in flights_dict.keys():
    # print all hexes in flights_hexes_dict[fid]
    print(f"flight {fid} hexes: {flights_hexes_dict[fid]}")
    # print all sections in flights_section_dict[fid]
    # print(f"flight {fid} sections: {flights_section_dict[fid]}")

  for scene_id in range(gbl_config.scene_count):
    cur_data: Scene = scene_data.scenes[scene_id]
    for item in cur_data.position_distribution_list:
      item.grid_id = find_point_hexgrid(item.lng, item.lat)
      if item.grid_id != -1:
        hexes[item.grid_id].flow += 1
    for item in cur_data.cross_adjustment_list:
      item.grid_id = find_point_hexgrid(item.lng, item.lat)
    for item in cur_data.conflict_dissolution_list:
      item.grid_id = find_point_hexgrid(item.lng, item.lat)
      if item.grid_id != -1:
        hexes[item.grid_id].conflict_cnt += item.inst_cnt + 2

  for hex_grid in hexes:
    hex_grid.flow /= gbl_config.scene_count
    hex_grid.flow /= nr_time_slices
    hex_grid.conflict_cnt /= gbl_config.scene_count


from collections import deque
from typing import List

def re_build_section(
):
  
  t = 2
  while t > 0:
    t -= 1

    # 按 payload_mean 降序排序扇区

    # sorted_ids = [sec.index for sec in sorted(
    #   sections,
    #   key=lambda s: (s.payload_mean is None, s.payload_mean),  # None 保持在最后
    #   reverse=True                                             # True 表示降序
    # )]

    sorted_ids = [
      section.index for section in sorted(
        sections,
        key=lambda s: (s.payload_mean is None, s.payload_mean),
        reverse=False
      )
    ]
    
    for section_id in sorted_ids:
      
      # 当前 section 初始格子队列
      queue = deque(sections[section_id].grid_list)
      # 避免重复入队
      visited = set(sections[section_id].grid_list)
      
      while queue:
        curr_idx = queue.popleft()
        curr_grid = hexes[curr_idx]

        for neighbor_idx in curr_grid.neighbors.values():
          if neighbor_idx is None:
            continue
          neighbor = hexes[neighbor_idx]

          # 如果已归属当前扇区，跳过
          if neighbor.section == section_id:
            continue

          # 若被航路占据，跳过
          if neighbor.flight_id:
            continue

          # 检查邻接情况
          total_valid = 0
          same_section = 0
          for adj_idx in neighbor.neighbors.values():
            if adj_idx is not None:
              total_valid += 1
              if hexes[adj_idx].section == section_id:
                same_section += 1

          # 防止边缘跳过
          if total_valid > 0 and same_section >= max(1, total_valid // 2):
            if neighbor_idx not in compute_section_articulation_points(sections[neighbor.section], hexes):
              transfer_grid(
                neighbor_idx,
                section_id,
                neighbor.section
              )
              if neighbor_idx not in visited:
                queue.append(neighbor_idx)
                visited.add(neighbor_idx)
    
    scene_step(True)


def scene_payload(
  scene_id: int
) -> List[SectionPayload]:
  res: List[SectionPayload] = [SectionPayload(0, 0, 0, 0, 0) for _ in range(nr_sections)]
  cur_data: Scene = scene_data.scenes[scene_id]
  
  instant_flow = np.zeros([nr_sections])
  normal_inst_cnt = np.zeros([nr_sections])
  conflict_dissolution_cnt = np.zeros([nr_sections])
  orientation_randomness = np.zeros([nr_sections, nr_time_slices])
  orientation_data = [[[] for _ in range(nr_time_slices)] for _ in range(nr_sections)]
  area_traffic_density = np.zeros([nr_sections, nr_time_slices])
  nc = np.zeros([nr_sections, nr_time_slices], dtype=int)
  nd = np.zeros([nr_sections, nr_time_slices], dtype=int)
  hc = np.zeros([nr_sections, nr_time_slices], dtype=float)
  hd = np.zeros([nr_sections, nr_time_slices], dtype=float)
  nn = np.zeros([nr_sections, nr_time_slices], dtype=int)

  position_dict: dict[str, list[float]] = {}

  # 三分钟位置分布
  for item in cur_data.position_distribution_list:
    # print(item)
    section_id = hexes[item.grid_id].section if item.grid_id != -1 else -1
    
    if item.ac_id not in position_dict:
      position_dict[item.ac_id] = [None for _ in range(nr_time_slices)]
    
    assert position_dict[item.ac_id][item.period_time] is None
    position_dict[item.ac_id][item.period_time] = section_id

    if section_id == -1:
      continue

    instant_flow[section_id] += 1
    nn[section_id, item.period_time] += 1
    orientation_data[section_id][item.period_time].append(item.heading)

  # 平均瞬时流量
  instant_flow /= nr_time_slices

  for ac_id, ac_history in position_dict.items():
    last: int = -1
    for i in range(len(ac_history)):
      assert ac_history[i] is not None
      if ac_history[i] != last:
        # enter
        normal_inst_cnt[ac_history[i]] += 1
        # leave
        if last != -1:
          normal_inst_cnt[last] += 1

  
  # 高度剖面调高
  for item in cur_data.cross_adjustment_list:
    # print(item)
    section_id = hexes[item.grid_id].section if item.grid_id != -1 else -1
    if section_id == -1:
      continue
    normal_inst_cnt[section_id] += 1

    if item.delta < 0:
      # nd[section_id, item.time] += 1
      hd[section_id, item.time] += -item.delta / 1000
    else:
      # nc[section_id, item.time] += 1
      hc[section_id, item.time] += item.delta / 1000

        

  # 冲突解脱
  for item in cur_data.conflict_dissolution_list:
    section_id = hexes[item.grid_id].section if item.grid_id != -1 else -1
    if section_id == -1:
      continue
    # print(item, "section", section_id)
    conflict_dissolution_cnt[section_id] += item.inst_cnt + 2

    if item.delta1 is not None:
      if item.delta1 < 0:
        nd[section_id, item.time] += 1
        hd[section_id, item.time] += -item.delta1 / 1000
      else:
        nc[section_id, item.time] += 1
        hc[section_id, item.time] += item.delta1 / 1000
    
    if item.delta2 is not None:
      if item.delta2 < 0:
        nd[section_id, item.time] += 1
        hd[section_id, item.time] += -item.delta2 / 1000
      else:
        nc[section_id, item.time] += 1
        hc[section_id, item.time] += item.delta2 / 1000

  for i in range(nr_sections):
    for j in range(nr_time_slices):
      if len(orientation_data[i][j]) == 0:
        orientation_randomness[i, j] = 0
      else:
        orientation_randomness[i, j] = np.var(orientation_data[i][j])
  
  for i in range(nr_sections):
    for j in range(nr_time_slices):
      area_traffic_density[i, j] = \
        (math.pi * (9.3 ** 2) * (nn[i, j] * 0.6 + nc[i, j] * hc[i, j] + nd[i, j] * hd[i, j])) \
        / (120 * sections[i].total_flight_length)

  orientation_randomness = np.mean(orientation_randomness, axis=1)
  area_traffic_density = np.mean(area_traffic_density, axis=1)

  # for section_id in range(nr_sections):
  #   print(f"scene {scene_id} section {section_id} instant_flow {instant_flow[section_id]} normal_inst_cnt {normal_inst_cnt[section_id]} conflict_dissolution_cnt {conflict_dissolution_cnt[section_id]} orientation_randomness {orientation_randomness[section_id]}")

  return [
    SectionPayload(
      instant_flow[i],
      normal_inst_cnt[i],
      conflict_dissolution_cnt[i],
      orientation_randomness[i],
      area_traffic_density[i]
    ) for i in range(nr_sections)
  ]

def scene_pseudo_payload():
  res: List[SectionPayload] = [SectionPayload(0, 0, 0, 0, 0) for _ in range(nr_sections)]
  
  for section_id in range(nr_sections):
    res[section_id].instant_flow = np.sum(
      [hex_grid.flow for hex_grid in hexes if hex_grid.section == section_id]
    )
    res[section_id].general_inst_cnt = 0
    res[section_id].conflict_dissolution_cnt = np.sum(
      [hex_grid.conflict_cnt for hex_grid in hexes if hex_grid.section == section_id]
    )
    res[section_id].orientation_randomness = 0
    res[section_id].area_traffic_density = 0

  return res

def scene_pseudo_val():
  res = scene_pseudo_payload()

  for section_id in range(nr_sections):

    sections[section_id].payload_mean = payload_fit_model2.predict(
      np.array([[
        res[section_id].instant_flow,
        res[section_id].conflict_dissolution_cnt
      ]])
    )[0]

    print(f"section {section_id} instant_flow {res[section_id].instant_flow} conflict_dissolution_cnt {res[section_id].conflict_dissolution_cnt}")

    sections[section_id].articulation_points = list(compute_section_articulation_points(sections[section_id], hexes))

def scene_val():
  for section in sections:
    section.evaluate()
  
  res_scenes = [
    scene_payload(scene_id)
    for scene_id in range(gbl_config.scene_count)
  ]

  for i in range(nr_sections):
    sections[i].section_payload = SectionPayload(
      instant_flow=np.mean([scene[i].instant_flow for scene in res_scenes]),
      general_inst_cnt=np.mean([scene[i].general_inst_cnt for scene in res_scenes]),
      conflict_dissolution_cnt=np.mean([scene[i].conflict_dissolution_cnt for scene in res_scenes]),
      orientation_randomness=np.mean([scene[i].orientation_randomness for scene in res_scenes]),
      area_traffic_density=np.mean([scene[i].area_traffic_density for scene in res_scenes])
    )

    indicators = np.array([[
      scene[i].instant_flow,
      scene[i].general_inst_cnt,
      scene[i].conflict_dissolution_cnt,
      scene[i].orientation_randomness,
      scene[i].area_traffic_density
    ] for scene in res_scenes])

    sections[i].payload_list = payload_fit_model.predict(indicators)
    sections[i].payload_mean = np.mean(sections[i].payload_list)

    sections[i].articulation_points = list(compute_section_articulation_points(sections[i], hexes))

    print(f"section {i} instant_flow {sections[i].section_payload.instant_flow} conflict_dissolution_cnt {sections[i].section_payload.conflict_dissolution_cnt}")
    # print(f"section {i} payload {sections[i].payload_mean}")

def scene_step(
    psuedo: bool = False
):
  global step_cnt
  step_cnt += 1
  print(f"Step {step_cnt}")

  if psuedo:
    scene_pseudo_val()
  else:
    scene_val()

  for i in range(nr_sections):
    print(f"section {i} payload {sections[i].payload_mean}")

    print(f"valid transfers: {get_valid_transfers(i)}")


def transfer_grid(
  grid_id: int,
  section_id_dom: int,
  section_id_sub: int
):
  if hexes[grid_id].section != section_id_sub:
    raise ValueError(f"grid {grid_id} not in section {section_id_sub}")
  
  sections[section_id_sub].grid_list.remove(grid_id)
  sections[section_id_dom].grid_list.append(grid_id)

  # 不要在这里维护
  # for fid in hexes[grid_id].flight_id:
  #   for i, hex_id in enumerate(flights_hexes_dict[fid]):
  #     if hex_id == grid_id:
  #       flights_section_dict[fid][i] = section_id_dom
  #       break

  hexes[grid_id].section = section_id_dom

# 检查获取栅格是否破坏了航路结构
def check_grid_flight(
  grid_id: int,
  section_id_dom: int,
  section_id_sub: int
):

  # temporary transfer
  hexes[grid_id].section = section_id_dom

  for fid in hexes[grid_id].flight_id:
    # 对于每个航路，统计每个扇区在其中的段数

    # 段数，每条航路重置
    segments: List[int] = [0 for _ in range(len(sections))]
    # 第一段
    segments[hexes[flights_hexes_dict[fid][0]].section] = 1

    for i in range(1, len(flights_hexes_dict[fid])):
      now_hex_id = flights_hexes_dict[fid][i]
      last_hex_id = flights_hexes_dict[fid][i - 1]
      # 有新的段
      if hexes[now_hex_id].section != hexes[last_hex_id].section:
        segments[hexes[now_hex_id].section] += 1

    for cnt in segments:
      # 如果有超过 1 段的扇区，说明航路被破坏了
      if cnt > 1:
        # print(f"flight {fid} section {section_id_dom} transfer grid {grid_id} break flight")
        # restore original section
        hexes[grid_id].section = section_id_sub
        return False
  
  # restore original section
  hexes[grid_id].section = section_id_sub
  return True

def get_grid_allies(
  grid_id: int,
) -> Set[int]:
  res = set()
  for _, neighbor in hexes[grid_id].neighbors.items():
    if neighbor is None:
      continue
    if hexes[neighbor].section == hexes[grid_id].section:
      res.add(neighbor)
  return res

def grid_neighbor_cnt(
  grid_id: int  
):
  res = 0
  for _, neighbor in hexes[grid_id].neighbors.items():
    if neighbor is None:
      continue
    res += 1
  return res

def grid_neighbors(
  grid_id: int  
):
  res = set()
  for _, neighbor in hexes[grid_id].neighbors.items():
    if neighbor is None:
      continue
    res.add(neighbor)
  return res

def grid_connectivity(
  grid_id: int  
) -> int:
  res: int = 0
  neighbor_ally = get_grid_allies(grid_id)
  
  if len(neighbor_ally) > 0:
    res = 1

  for neighbor in neighbor_ally:
    assert neighbor is not None
    tmpcnt: int = 0
    for neighbor2 in neighbor_ally:
      assert neighbor2 is not None
      if neighbor != neighbor2 and neighbor2 in hexes[neighbor].neighbors.values():
        tmpcnt += 1

    if tmpcnt == 2:
      res = 3
      break
    if tmpcnt == 1:
      res = 2

  if grid_neighbor_cnt(grid_id) < 5 and res < 3:
    res += 1

  return res



def valid_transfer(
  grid_id: int,
  section_id_dom: int,
  section_id_sub: int
) -> bool:
  
  # self transfer
  if section_id_dom == section_id_sub:
    return False

  # not in current section
  if hexes[grid_id].section != section_id_sub:
    return False

  # bullying
  if sections[section_id_sub].payload_mean < sections[section_id_dom].payload_mean:
    return False
  
  if grid_id in sections[section_id_sub].articulation_points:
    return False

  if not check_grid_flight(
    grid_id,
    section_id_dom,
    section_id_sub
  ):
    # print(f"grid {grid_id} section {section_id_sub} transfer to section {section_id_dom} break flight")
    return False

  # break flights
  if len(hexes[grid_id].flight_id) > 0:
    neighbor_ally = get_grid_allies(grid_id)
    for fid in hexes[grid_id].flight_id:
      tmpcnt: int = 0
      set_ally = set()
      for neighbor in neighbor_ally:
        assert neighbor is not None
        if fid in hexes[neighbor].flight_id:
          tmpcnt += 1
          set_ally.add(neighbor)
          # if grid_id == 394:
          #   print(f"grid {grid_id} flight {fid} neighbor {neighbor}")
      
      if tmpcnt > 2:
        return False

      if tmpcnt == 2:
        a, b = list(set_ally)
        if a not in grid_neighbors(b):
          return False
        
      
  # simulate transfer, check the connectivity of the grid and its neighbors
  transfer_grid(grid_id, section_id_dom, section_id_sub)

  flag: bool = True

  if grid_connectivity(grid_id) < 2:
    flag = False
  
  if flag:
    for neighbor in hexes[grid_id].neighbors.values():
      if neighbor is not None and hexes[neighbor].section == section_id_sub:
        if grid_connectivity(neighbor) < 2:
          flag = False
          break

  transfer_grid(grid_id, section_id_sub, section_id_dom)
  return flag
  
def get_valid_transfers(
  section_id: int
) -> List[int]:
  return [
    hex_grid.index 
    for hex_grid in hexes
    if valid_transfer(
      hex_grid.index,
      section_id,
      hex_grid.section
    ) is True
  ]

def get_counter_factual_info(
  grid_id: int,
  section_id_dom: int,
  section_id_sub: int
) -> float:
  # if hexes[grid_id].section != section_id_sub:
  #   raise ValueError(f"grid {grid_id} not in section {section_id_sub}")
  
  # # 备份原 payload
  # old_payload = []
  # for i in range(nr_sections):
  #   old_payload.append(sections[i].payload_mean)

  # # 模拟操作
  # transfer_grid(grid_id, section_id_dom, section_id_sub)

  # # 计算新 payload
  # scene_val()
  # new_payload = sections[section_id_dom].payload_mean
  
  # # 恢复原状
  # transfer_grid(grid_id, section_id_sub, section_id_dom)
  # for i in range(nr_sections):
  #   sections[i].payload_mean = old_payload[i]
  # return new_payload - sections[section_id_dom].payload_mean

  return hexes[grid_id].flow

@dataclass
class HexObservation:
  section_id: int
  value: float
  has_flight: bool

@dataclass
class SectionObservation:
  hex_observation: Dict[int, HexObservation]
  section_id: int
  is_self: List[bool]
  payload: List[float]

def get_hex_observation(
  section_id: int
) -> List[HexObservation]:
  res = []
  for hex_grid in hexes:
    if valid_transfer(
      hex_grid.index,
      section_id,
      hex_grid.section
    ):
      # print(f"grid {hex_grid.index} section {hex_grid.section} valid transfer")
      res.append(HexObservation(
        hex_grid.section,
        get_counter_factual_info(
          hex_grid.index,
          section_id,
          hex_grid.section
        ),
        len(hex_grid.flight_id) > 0
      ))
    else:
      res.append(HexObservation(
        hex_grid.section,
        0,
        len(hex_grid.flight_id) > 0
      ))
  return res

def get_hex_observation_tensor(
  section_id: int
) -> List[HexObservation]:
  res = []
  for hex_grid in hexes:
    if valid_transfer(
      hex_grid.index,
      section_id,
      hex_grid.section
    ):
      # print(f"grid {hex_grid.index} section {hex_grid.section} valid transfer")
      res.append([
        hex_grid.section,
        get_counter_factual_info(
          hex_grid.index,
          section_id,
          hex_grid.section
        ),
        len(hex_grid.flight_id) > 0
      ])
    else:
      res.append([
        hex_grid.section,
        0,
        len(hex_grid.flight_id) > 0
      ])
  return res

def get_section_observation(
  section_id: int,
  main_section_id: int
) -> SectionObservation:
  hex_observation = get_hex_observation(section_id)
  is_self = (section_id == main_section_id)
  payload = [section.payload_mean for section in sections]
  return SectionObservation(
    hex_observation={i: hex_observation[i] for i in range(len(hex_observation))},
    section_id=section_id,
    is_self=is_self,
    payload=payload
  )

def get_section_observation_tensor(
  section_id: int,
  main_section_id: int
) -> SectionObservation:
  hex_observation = get_hex_observation_tensor(section_id)
  is_self = (section_id == main_section_id)
  payload = [section.payload_mean for section in sections]
  return [
    hex_observation,
    section_id,
    is_self,
    payload
  ]

def get_overall_observation(
  section_id: int
):
  return [
    get_section_observation_tensor(i, section_id)
    for i in range(nr_sections)
  ]

import os, json
def save_observation_to_json(path="obs/obs.json"):
  obs = get_overall_observation()
  json_data = [asdict(section_obs) for section_obs in obs]

  os.makedirs(os.path.dirname(path), exist_ok=True)

  with open(path, "w") as f:
    json.dump(json_data, f, indent=2)
  print(f" Observation saved to {path}")

def input_action(lock):

  grid_id, section_id_dom = map(int, input("(grid_id, section_id_dom): ").split(','))

  section_id_sub = get_grid_section(grid_id, lock)

  with lock:
    transfer_grid(grid_id, section_id_dom, section_id_sub)
    scene_step(False)

  print(f"transfer grid {grid_id} from section {section_id_sub} to section {section_id_dom}")

def scene_act(
  lock,
  grid_id: int,
  section_id_dom: int
) -> float:
  
  if grid_id == len(hexes):
    print("grid_id -1, no transfer")
    return 0

  section_id_sub = get_grid_section(grid_id, lock)
  
  if not valid_transfer(
    grid_id,
    section_id_dom,
    section_id_sub
  ):
    print(f"invalid transfer grid {grid_id} from section {section_id_sub} to section {section_id_dom}")
    return -100

  original_payload = sections[section_id_dom].payload_mean

  if not lock:
    transfer_grid(grid_id, section_id_dom, section_id_sub)

    scene_step(True)
  else:
    with lock:
      transfer_grid(grid_id, section_id_dom, section_id_sub)

      scene_step(True)

  new_payload = sections[section_id_dom].payload_mean

  print(f"transfer grid {grid_id} from section {section_id_sub} to section {section_id_dom} with reward {new_payload - original_payload}")

  # [section.payload_mean for section in sections]

  return new_payload - original_payload + 10

# def valid_transfers(
#   section_id: int  
# ) -> list[int]:
  
  


#   pass
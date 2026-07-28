import numpy as np
from shapely.geometry import Polygon, Point

import pickle

import predefines
from predefines import next_direction, next_direction_rev, opposite_direction, full_area, coord_vectors
from polygon import HexGrid, hexes, coord_dict
from config import gbl_config

global_rect = Polygon([
  (predefines.lng_min, predefines.lat_max), 
  (predefines.lng_max, predefines.lat_max), 
  (predefines.lng_max, predefines.lat_min), 
  (predefines.lng_min, predefines.lat_min)])

def hexize():

  if not gbl_config.reload_hexgrid:
    print("load existing gridization result...")
    with open("hexes.pkl", "rb") as f:
      global hexes
      hexes[:] = pickle.load(f)

    for hex_grid in hexes:
      coord_dict[hex_grid.coord] = hex_grid.index
    return  

  some_point = full_area.representative_point()

  first_hex = HexGrid(
    0,
    (some_point.x, some_point.y),
    (0, 0)
  )
  hexes.append(first_hex)
  coord_dict[(0, 0)] = 0

  search_neighbors(first_hex)

  with open('hexes.txt', 'w') as f:
    for hex in hexes:
      f.write(f'hex #{hex.index}: {hex.vertices}\n{hex.neighbors}\n')
  
def search_neighbors(
  hex_grid: HexGrid
):
  print(f"searching neighbors for hex #{hex_grid.index} with coord {hex_grid.coord}...")
  # 搜索六个方向的邻居
  for direction, vector in predefines.hex_vectors.items():
    print(f"searching {direction} for hex #{hex_grid.index}...")
    # 如果是空的
    
    if hex_grid.neighbors[direction] is None:
      # 计算邻居位置
      new_hex = HexGrid(
        len(hexes),
        (
          hex_grid.start[0] + vector[0] / predefines.len_per_lng, 
          hex_grid.start[1] + vector[1] / predefines.len_per_lat
        ),
        (
          hex_grid.coord[0] + coord_vectors[direction][0], 
          hex_grid.coord[1] + coord_vectors[direction][1]
        )
      )
      # 有效
      if full_area.intersects(new_hex.get_polygon()):
        print(f"new hex #{new_hex.index}:\n{new_hex.vertices}")
        hexes.append(new_hex)
        coord_dict[new_hex.coord] = new_hex.index

        hex_grid.neighbors[direction] = new_hex.index
        
        op_direction = opposite_direction[direction]
        new_hex.neighbors[op_direction] = hex_grid.index
        
        for rev_direction, rev_coord_vec in coord_vectors.items():
          if rev_direction == op_direction:
            continue
          rev_coord = (new_hex.coord[0] + rev_coord_vec[0], new_hex.coord[1] + rev_coord_vec[1])
          if rev_coord in coord_dict:
            rev_hex = hexes[coord_dict[rev_coord]]
            new_hex.neighbors[rev_direction] = rev_hex.index
            rev_hex.neighbors[opposite_direction[rev_direction]] = new_hex.index

        # 这里到这一节 if 结束都是调试代码，不用管

        # 逆时针找新块的其他邻居
        cw_direction = next_direction[direction]            # 从当前块指向新邻居的方向
        cw_op_direction = next_direction_rev[op_direction]  # 从新块指向新邻居的方向
        cw_hex_index = hex_grid.neighbors[cw_direction]     # 新邻居 id

        assert direction == opposite_direction[op_direction]

        # 进入循环
        while cw_hex_index is not None and cw_hex_index is not hex_grid.index:
          cw_hex = hexes[cw_hex_index]
          # 找到一个邻居
          if new_hex.neighbors[cw_op_direction] is not None:
            assert new_hex.neighbors[cw_op_direction] == cw_hex.index
          new_hex.neighbors[cw_op_direction] = cw_hex.index
          # 反向设置一下，顺便把方向调整过来
          cw_direction = opposite_direction[cw_op_direction]
          if cw_hex.neighbors[cw_direction] is not None:
            assert cw_hex.neighbors[cw_direction] == new_hex.index
          cw_hex.neighbors[cw_direction] = new_hex.index

          assert cw_direction == opposite_direction[cw_op_direction]

          # 接着往下找
          cw_direction = next_direction[cw_direction]
          cw_op_direction = next_direction_rev[cw_op_direction]
          cw_hex_index = cw_hex.neighbors[cw_direction]

        # 顺时针找新块的其他邻居
        ccw_direction = next_direction_rev[direction]         # 从当前块指向新邻居的方向
        ccw_op_direction = next_direction[op_direction]       # 从新块指向新邻居的方向
        ccw_hex_id = hex_grid.neighbors[ccw_direction]        # 新邻居 id

        while ccw_hex_id is not None and ccw_hex_id is not hex_grid.index:
          ccw_hex = hexes[ccw_hex_id]
          # 找到一个邻居
          if new_hex.neighbors[ccw_op_direction] is not None:
            assert new_hex.neighbors[ccw_op_direction] == ccw_hex.index
          new_hex.neighbors[ccw_op_direction] = ccw_hex.index
          # 反向设置一下，顺便把方向调整过来
          ccw_direction = opposite_direction[ccw_op_direction]
          if ccw_hex.neighbors[ccw_direction] is not None:
            if ccw_hex.neighbors[ccw_direction] != new_hex.index:
              print(f"ccw_hex.neighbors[{ccw_direction}] = {ccw_hex.neighbors[ccw_direction]}, ccw_hex.index = {ccw_hex.index}")
              print(coord_dict)
            assert ccw_hex.neighbors[ccw_direction] == new_hex.index
          ccw_hex.neighbors[ccw_direction] = new_hex.index

          assert ccw_direction == opposite_direction[ccw_op_direction]

          # 接着往下找
          ccw_direction = next_direction_rev[ccw_direction]
          ccw_op_direction = next_direction[ccw_op_direction]
          ccw_hex_id = ccw_hex.neighbors[ccw_direction]
          
        print(f"new hex #{new_hex.index}:\n{new_hex.neighbors}")
        search_neighbors(new_hex)
      else:
        hex_grid.neighbors[direction] = None
  

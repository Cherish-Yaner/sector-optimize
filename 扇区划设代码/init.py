import os
import pickle
import sys
import time
from typing import Optional

import warnings

from config import gbl_config

from gridize import hexize
from polygon import hexes
from section import get_generate_sections, sections
from predefines import *

from scene import scene_step, scene_init, step_cnt, scene_val
from polygon import find_point_hexgrid, coord_dict, coord_lat_range, coord_lng_range, find_a_close_coord


def init():

  warnings.filterwarnings("ignore", message="X does not have valid feature names, but.*")

  sys.setrecursionlimit(2000)

  hexize()

  os.makedirs('output/cache', exist_ok=True)
  os.makedirs('output/misc', exist_ok=True)

  if gbl_config.reload_hexgrid:
    with open('output/cache/hexes.pkl', 'wb') as f:
      pickle.dump(hexes, f)

  if gbl_config.reload_sectors:
    if section_preset:
      get_generate_sections()
  else:
    print("load existing sections...")
    with open('output/cache/sections.pkl', 'rb') as f:
      global sections
      sections[:] = pickle.load(f)

  for section in sections:
    for hex_grid in section.grid_list:
      hexes[hex_grid].section = section.index
  
  with open('output/cache/sections.pkl', 'wb') as f:
    pickle.dump(sections, f)

  scene_init()
  print("scene init done")

  scene_val()
  with open('output/misc/payload.txt', 'w') as f:
    for section in sections:
      f.write(f"""section #{section.index}: \n
{section.section_payload} \n
payload_mean: {section.payload_mean} \n
payload_list: {list(section.payload_list)}\n
total_flight_length: {section.total_flight_length}\n""")

  for _ in range(1):
    scene_step(True)
  
if __name__ == "__main__":
  init()
  

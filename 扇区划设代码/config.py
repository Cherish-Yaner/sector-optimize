from dataclasses import dataclass

import json
import os
import sys

@dataclass
class Config:
  scene_count: int
  data_name: str

  reload_hexgrid: bool
  reload_sectors: bool
  reload_payload: bool

  grid_name: bool
  fill_color: bool
  flight_point_name: bool

  @staticmethod
  def load():

    with open('config.json') as f:
      data = json.load(f)
      reload_hexgrid=data['auto_reload']['hexgrid']
      reload_sectors=data['auto_reload']['sectors']
      reload_payload=data['auto_reload']['payload']
      grid_name=data['view_mode']['grid_name']
      fill_color=data['view_mode']['fill_color']
      flight_point_name=data['view_mode']['flight_point_name']
      if "reload" in sys.argv:
        if "hexgrid" in sys.argv:
          reload_hexgrid = True
        if "sectors" in sys.argv:
          reload_sectors = True
        if "payload" in sys.argv:
          reload_payload = True
        if "all" in sys.argv:
          reload_hexgrid = True
          reload_sectors = True
          reload_payload = True
      return Config(
        scene_count=data['scene_count'],
        data_name=data['data_name'],
        reload_hexgrid=reload_hexgrid,
        reload_sectors=reload_sectors,
        reload_payload=reload_payload,
        grid_name=grid_name,
        fill_color=fill_color,
        flight_point_name=flight_point_name
      )

gbl_config = Config.load()
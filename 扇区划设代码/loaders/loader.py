from dataclasses import dataclass
from typing import List

from .scene_loader import Scene
from config import gbl_config

@dataclass
class LoaderData:
  scenes: List[Scene]

  @staticmethod
  def load(name: str):
    return LoaderData(
      scenes=[Scene.load(i, name) for i in range(gbl_config.scene_count)]
    )
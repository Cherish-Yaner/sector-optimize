from dataclasses import dataclass
from typing import List

from .conflict_dissolution import ConflictDissolutionEntry, load_conflict_dissolution_from_csv
from .cross_adjustment import CrossAdjustmentEntry, load_cross_adjustment_from_csv
from .position_distribution import PositionDistributionEntry, load_position_distribution_from_csv

@dataclass
class Scene:
  scene_id: int
  conflict_dissolution_list: List[ConflictDissolutionEntry]
  cross_adjustment_list: List[CrossAdjustmentEntry]
  position_distribution_list: List[PositionDistributionEntry]

  @staticmethod
  def load(scene_id: int, name: str):
    return Scene(
      scene_id=scene_id,
      position_distribution_list=load_position_distribution_from_csv(f'{name}/position_distribution/{scene_id}.csv'),
      cross_adjustment_list=load_cross_adjustment_from_csv(f'{name}/cross_adjustment/{scene_id}.csv'),
      conflict_dissolution_list=load_conflict_dissolution_from_csv(f'{name}/conflict_dissolution/{scene_id}.csv')
    )
  
  
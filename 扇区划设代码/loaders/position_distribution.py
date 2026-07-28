from dataclasses import dataclass
from typing import List
from dataclass_csv import DataclassReader

from predefines import period_time_start, period_time_end, time_slice_length

@dataclass
class PositionDistributionEntryOriginal:
  period_time: int
  ac_id: str
  lng: float
  lat: float
  heading: float
  
@dataclass
class PositionDistributionEntry:
  period_time: int
  ac_id: str
  lng: float
  lat: float
  heading: float
  grid_id: int

def load_position_distribution_from_csv(filename: str) -> List[PositionDistributionEntryOriginal]:
  with open(filename) as f:
    reader = DataclassReader(f, PositionDistributionEntryOriginal)
    pre_res = list(reader)
    return [
      PositionDistributionEntry(
        (_.period_time - period_time_start - 1) // time_slice_length,
        _.ac_id,
        _.lng,
        _.lat,
        _.heading,
        -1
      ) for _ in pre_res 
      if _.period_time > period_time_start and _.period_time <= period_time_end
    ]

def test():
  data = load_position_distribution_from_csv('data/position_distribution/0.csv')
  print('first', data[0])
  print('second', data[1])
  print('last', data[-1])
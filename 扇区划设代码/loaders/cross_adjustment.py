from dataclasses import dataclass
from typing import List
import csv

from predefines import period_time_start, period_time_end, time_slice_length, nr_time_slices

@dataclass
class CrossAdjustmentEntry:
  time: int
  delta: int
  res_height: int
  lng: float
  lat: float
  grid_id: int
  
def load_cross_adjustment_from_csv(filename: str) -> List[CrossAdjustmentEntry]:
  try:
    with open(filename, newline='') as f:
      reader = csv.reader(f)
      res_data: List[CrossAdjustmentEntry] = []
      for row in reader:
        time = int(row[0])
        if time > period_time_start and time <= period_time_end:
          time = (time - period_time_start - 1) // time_slice_length
        elif time <= period_time_start:
          time = 0
        else:
          time = nr_time_slices - 1
        res_data.append(CrossAdjustmentEntry(
          time, 
          int(row[1]), int(row[2]), float(row[3]), float(row[4]),
          -1  
        ))
      return res_data
  except FileNotFoundError:
    return []

def test():
  data = load_cross_adjustment_from_csv('data/cross_adjustment/0.csv')
  print('first', data[0])
  print('second', data[1])
  print('last', data[-1])
  
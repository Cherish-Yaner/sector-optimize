from dataclasses import dataclass
import csv
from typing import List, Optional
import re

from predefines import period_time_start, period_time_end, time_slice_length, nr_time_slices

def extract_delta(text):
    match = re.search(r"DELTA:([-+]?\d*\.?\d+)", text)
    return (float(match.group(1))) if match else None

@dataclass
class ConflictDissolutionEntry:
  time: int
  lng: float
  lat: float
  inst_cnt: int
  inst1: Optional[str]
  inst2: Optional[str]
  delta1: Optional[float]
  delta2: Optional[float]
  flight1: Optional[str]
  flight2: Optional[str]
  grid_id: int

def load_conflict_dissolution_from_csv(filename: str) -> List[ConflictDissolutionEntry]:
  try:
    with open(filename, newline='') as f:
      reader = csv.reader(f)
      res_data: List[ConflictDissolutionEntry] = []
      for row in reader:
        time = int(row[1])      #B
        if time > period_time_start and time <= period_time_end:
          time = (time - period_time_start - 1) // time_slice_length
        elif time <= period_time_start:
          time = 0
        else:
          time = nr_time_slices - 1
        lng = float(row[3])     #D
        lat = float(row[4])     #E
        inst_cnt = int(row[5])  #F
        inst_1 = None
        inst_2 = None
        flight_1 = None
        flight_2 = None
        delta_1 = None
        delta_2 = None
        if inst_cnt == 1:
          action_1 = int(row[7])  #H
          if action_1 != 127:
            inst_1 = row[10]      #K
            delta_1 = extract_delta(inst_1)
            flight_1 = row[12]    #M
        elif inst_cnt == 2:
          action_1 = row[7]       #H
          action_2 = row[8]       #I
          if action_1 != 127:
            inst_1 = row[11]      #L
            delta_1 = extract_delta(inst_1)
            flight_1 = row[13]    #N
            if action_2 != 127:
              inst_2 = row[12]    #M
              delta_2 = extract_delta(inst_2)
              flight_2 = row[14]  #O
          elif action_2 != 127:
            inst_1 = row[12]      #M
            delta_1 = extract_delta(inst_1)
            flight_1 = row[14]    #O
        
        res_data.append(ConflictDissolutionEntry(time, lng, lat, inst_cnt, inst_1, inst_2, delta_1, delta_2, flight_1, flight_2, -1))

      return res_data
  except FileNotFoundError:
    return []

  

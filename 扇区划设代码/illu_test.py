import sys

from math import cos, sin, radians
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QPushButton, QMessageBox
from PyQt6.QtGui import QPainter, QPen, QPolygonF
from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtCore import QThread, pyqtSignal, QObject, QCoreApplication, QMetaObject

import pandas as pd

import pickle
import threading
import socket
from typing import List, Dict, Tuple, Optional, Any

from init import init
from scene import transfer_grid, input_action, scene_step, get_overall_observation, save_observation_to_json, scene_act, get_valid_transfers, transfer_grid, re_build_section

from section import get_grid_section

from register_env import env_creator

from gridmap import GridMap
from gridize import hexize
from polygon import hexes

import argparse
import os
import re
import matplotlib.pyplot as plt

gbl_lock = threading.Lock()

if __name__ == "__main__":
    
    app = QApplication(sys.argv)

    init()

    gridmap = GridMap([], gbl_lock=gbl_lock)
    gridmap.show()

    sys.exit(app.exec())
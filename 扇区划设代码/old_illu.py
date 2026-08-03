import sys

from math import cos, sin, radians
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QPushButton, QMessageBox
from PyQt6.QtGui import QPainter, QPen, QPolygonF
from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtCore import QThread, pyqtSignal, QObject, QCoreApplication, QMetaObject

import pandas as pd

from datetime import datetime

import pickle
import threading
import socket
from section import sections
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

STEP_RE = re.compile(r"^Step\s+(\d+)\b")
TRANSFER_RE = re.compile(
    r"transfer grid (\d+) from section (\d+) to section (\d+) with reward ([\d\.\-eE]+)"
)
RESET_KEYWORD = "load existing sections"
PAYLOAD_RE = re.compile(
    r"section (\d+) payload ([\d\.\-eE]+)"
)

def parse_log(path: str):

    cumulative: Dict[int, float] = {}
    # payload: Dict[int, float] = {}
    history: Dict[int, List[Tuple[int, float]]] = {}
    payload_history: Dict[int, List[Tuple[int, float]]] = {}

    overall_history: List[Dict[str, Any]] = []

    current_step: Optional[int] = None

    reset_count = 0
    processing = False

    with open(path, "rb") as fh:
        head = fh.read(4)
    encoding = "utf-16" if head.startswith(b"\xff\xfe") else "utf-8-sig"

    with open(path, encoding=encoding) as fh:

        tmp_rew_hist: Dict[str, float] = {}
        tmp_pay_hist: Dict[str, float] = {}

        for raw_line in fh:
            line = raw_line.strip()
            
            # if "transfer grid" in line.lower():        # 先用包含判断
            #     print(line)  # DEBUG: 打印出所有 transfer 行
            #     m = TRANSFER_RE.search(line)
            #     if not m:
            #         # DEBUG: 行里有关键词却没匹配成功，打印出来给我们看
            #         print(f"[未匹配] {line}")
            #         continue
            # else:
            #     continue

            # --- reset 检测 ---
            if RESET_KEYWORD in line or "load existing sectors" in line:
                # print(line)
                reset_count += 1
                cumulative.clear()
                if reset_count == 2:
                    history.clear()
                    processing = True
                elif reset_count >= 2:
                    if processing:
                        overall_history.append({
                            **tmp_rew_hist,
                            **tmp_pay_hist,
                            "step": current_step - 1 if current_step is not None else 0
                        })
                    processing = False
                continue
            # ------------------

            # Step 行
            step_match = STEP_RE.match(line)
            if step_match:
                if processing and current_step != 1:
                    overall_history.append({
                        **tmp_rew_hist,
                        **tmp_pay_hist,
                        "step": current_step - 1 if current_step is not None else 0
                    })
                current_step = int(step_match.group(1))
                for section in sections:
                    tmp_rew_hist[f"section_{section.index}_reward"] = 0.0
                continue

            if not processing:
                continue

            payload_match = PAYLOAD_RE.search(line)
            if payload_match:
                section_payload_id = int(payload_match.group(1))
                payload = float(payload_match.group(2)) 

                payload_history.setdefault(section_payload_id, []).append(
                    (current_step if current_step is not None else 0, payload)
                )

                tmp_pay_hist[f"section_{section_payload_id}_payload"] = payload
            
            
            transfer_match = TRANSFER_RE.search(line)
            if transfer_match:
                grid_id = int(transfer_match.group(1))
                src = int(transfer_match.group(2))
                dst = int(transfer_match.group(3))
                reward = float(transfer_match.group(4))

                transfer_grid(grid_id, dst, src)

                cumulative[dst] = cumulative.get(dst, 0.0) + reward + 10.0
                history.setdefault(dst, []).append(
                    (current_step if current_step is not None else 0, cumulative[dst])
                )

                tmp_rew_hist[f"section_{dst}_reward"] = reward + 10.0

    return history, payload_history, overall_history


def plot_reward(
    rew_hist: Dict[int, List[Tuple[int, float]]], 
    pay_hist: Dict[int, List[Tuple[int, float]]],
    overall_hist: List[Dict[str, Any]],
    log_path: str
) -> None:
    """绘制 PNG。"""
    if not rew_hist:
        print("no rew_hist")
        exit(1)
    
    if not pay_hist:
        print("no pay_hist")
        exit(1)
        
    # reward

    plt.figure(figsize=(8, 5))
    for section, series in sorted(rew_hist.items()):
        steps = [s for s, _ in series]
        rewards = [r for _, r in series]
        plt.plot(steps, rewards, label=f"section {section}")

    plt.xlabel("Step")
    plt.ylabel("Cumulative reward")
    plt.title("Cumulative reward")
    plt.legend()
    plt.tight_layout()

    ts = datetime.now().strftime("_%Y%m%d_%H%M%S")
    os.makedirs("output", exist_ok=True)
    base = os.path.join("output", os.path.basename(os.path.splitext(log_path)[0]))

    out_png = base + ts + ".png"
    plt.savefig(out_png, dpi=150)
    print(f"rew 已保存到: {out_png}")

    # payload

    plt.figure(figsize=(8, 5))
    for section, series in sorted(pay_hist.items()):
        steps = [s for s, _ in series]
        rewards = [r for _, r in series]
        plt.plot(steps, rewards, label=f"section {section}")

    plt.xlabel("Step")
    plt.ylabel("Payload")
    plt.title("Payload")
    plt.legend()
    plt.tight_layout()

    out_png_payload = base + ts + "_payload.png"
    plt.savefig(out_png_payload, dpi=150)
    print(f"payload 已保存到: {out_png_payload}")

    save_df = pd.DataFrame(overall_hist).fillna(0)

    cols = ["step"] + [c for c in save_df.columns if c != "step"]
    save_df = save_df[cols]

    csv_path = base + ts + "_overall.csv"
    save_df.to_csv(csv_path, index=False)
    print(f"csv 已保存到: {csv_path}")

if __name__ == "__main__":
    
    app = QApplication(sys.argv)
    # window = MainWindow()
    # window.show()

    init()
    # scene_step(True)

    # from filtering import matches
    # for i in matches:
    #     transfer_grid(i, 2, get_grid_section(i, None))

    
    parser = argparse.ArgumentParser(description="RL 日志分析脚本")
    parser.add_argument("logfile", help="日志文件路径")
    args = parser.parse_args()

    plot_reward(*parse_log(args.logfile), args.logfile)

    gridmap = GridMap([], gbl_lock=gbl_lock)
    gridmap.show()

    scene_step(True)

    re_build_section()

    scene_step(False)

    gridmap.update()

    ts = datetime.now().strftime("_%Y%m%d_%H%M%S")
    os.makedirs("output/analysis", exist_ok=True)
    img_path = os.path.join("output/analysis", "sector_distribution" + ts + ".png")
    gridmap.grab().save(img_path)
    print(f"扇区划分图已保存到: {img_path}")

    # for 

    sys.exit(app.exec())
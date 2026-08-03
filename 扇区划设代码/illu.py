import sys

from math import cos, sin, radians
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QPushButton, QMessageBox
from PyQt6.QtGui import QPainter, QPen, QPolygonF
from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtCore import QThread, pyqtSignal, QObject, QCoreApplication, QMetaObject

import numpy as np
import pandas as pd

from datetime import datetime

import pickle
import threading
import socket
from typing import List, Dict, Tuple, Optional, Any

from init import init
from scene import transfer_grid, input_action, scene_step, get_overall_observation, save_observation_to_json, scene_act, get_valid_transfers, re_build_section

from section import get_grid_section, sections

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
    r"transfer grid (\d+) from section (\d+) to section (\d+) with reward ([\d\.\-eE+]+)"
)
RESET_KEYWORD = "load existing sections"
PAYLOAD_RE = re.compile(
    r"section (\d+) payload ([\+\-]?[\d\.eE]+)"
)

nr_sections = len(sections)


def compute_cv(values):
    """变异系数 CV = σ/μ，衡量各扇区负载差距，越小越均衡。"""
    arr = np.asarray([v for v in values if v is not None], dtype=float)
    if arr.size == 0:
        return 0.0
    m = arr.mean()
    if m == 0:
        return 0.0
    return float(arr.std() / m)


def new_episode(eid: int) -> Dict[str, Any]:
    return {
        "episode": eid,
        "steps": 0,
        "cv_sum": 0.0,
        "total_reward": 0.0,
        "actions": 0,
        "step_payloads": {},
        "avg_imbalance": float("nan"),
        "snapshot": None,
        "rew_series": {i: [] for i in range(nr_sections)},
        "pay_series": {i: [] for i in range(nr_sections)},
    }


def finish_episode(cur: Dict[str, Any]) -> None:
    cur["avg_imbalance"] = cur["cv_sum"] / cur["steps"] if cur["steps"] else float("nan")
    cur["snapshot"] = [list(sec.grid_list) for sec in sections]


def parse_log(path: str):

    overall_history: List[Dict[str, Any]] = []
    episodes: List[Dict[str, Any]] = []
    cur: Optional[Dict[str, Any]] = None

    current_step: Optional[int] = None
    episode_step = 0
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

            # --- reset 检测 ---
            if RESET_KEYWORD in line or "load existing sectors" in line:
                if cur is not None and cur["steps"]:
                    finish_episode(cur)
                    episodes.append(cur)
                cur = None

                reset_count += 1
                if reset_count == 2:
                    processing = True
                elif reset_count > 2:
                    with open('output/cache/sections.pkl', 'rb') as f:
                        global sections
                        sections[:] = pickle.load(f)

                    for section in sections:
                        for hex_grid in section.grid_list:
                            hexes[hex_grid].section = section.index

                if reset_count >= 2:
                    cur = new_episode(reset_count - 1)
                episode_step = 0
                continue
            # ------------------

            # Step 行
            step_match = STEP_RE.match(line)
            if step_match:
                if processing and current_step is not None and episode_step > 2:
                    overall_history.append({
                        **tmp_rew_hist,
                        **tmp_pay_hist,
                        "step": current_step - 1,
                        "episode_step": episode_step - 1,
                        "episode": reset_count - 1
                    })

                current_step = int(step_match.group(1))
                episode_step += 1

                if cur is not None:
                    cur["steps"] += 1
                    cur["step_payloads"] = {}
                    for section in sections:
                        tmp_pay_hist[f"section_{section.index}_payload"] = section.payload_mean
                        tmp_rew_hist[f"section_{section.index}_reward"] = 0.0

                if not processing:
                    continue
                continue

            if not processing or cur is None:
                continue

            # payload 指标（用于负载均衡度评估）
            payload_match = PAYLOAD_RE.search(line)
            if payload_match:
                section_payload_id = int(payload_match.group(1))
                payload = float(payload_match.group(2))

                cur["step_payloads"][section_payload_id] = payload
                if len(cur["step_payloads"]) >= nr_sections:
                    cv = compute_cv([
                        cur["step_payloads"].get(i, 0.0)
                        for i in range(nr_sections)
                    ])
                    cur["cv_sum"] += cv

                cur["pay_series"][section_payload_id].append(
                    (current_step if current_step is not None else 0, payload)
                )
                tmp_pay_hist[f"section_{section_payload_id}_payload"] = payload
                continue

            # transfer 行
            transfer_match = TRANSFER_RE.search(line)
            if transfer_match:
                grid_id = int(transfer_match.group(1))
                src = int(transfer_match.group(2))
                dst = int(transfer_match.group(3))
                reward = float(transfer_match.group(4))

                transfer_grid(grid_id, dst, src)

                cur["total_reward"] += reward + 10.0
                cur["actions"] += 1
                cur["rew_series"][dst].append(
                    (current_step if current_step is not None else 0, cur["total_reward"])
                )
                tmp_rew_hist[f"section_{dst}_reward"] = reward + 10.0

    if cur is not None and cur["steps"]:
        finish_episode(cur)
        episodes.append(cur)

    return episodes, overall_history


def pick_best_episode(
    episodes: List[Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    """按负载均衡（avg_imbalance 最小）自动选取最优回合。"""
    valid = [
        ep for ep in episodes
        if ep["steps"] > 0 and ep["avg_imbalance"] == ep["avg_imbalance"]
    ]
    if not valid:
        return None
    return min(valid, key=lambda ep: (ep["avg_imbalance"], ep["episode"]))


def restore_episode(best: Dict[str, Any]) -> None:
    """把扇区状态恢复为指定回合结束时的快照。"""
    for sec, grids in zip(sections, best["snapshot"]):
        sec.grid_list = list(grids)
        for grid_id in grids:
            hexes[grid_id].section = sec.index


def save_overall_csv(overall_hist: List[Dict[str, Any]], log_path: str) -> Optional[str]:
    if not overall_hist:
        return None

    save_df = pd.DataFrame(overall_hist).fillna(0)
    base_cols = [c for c in ["step", "episode_step", "episode"] if c in save_df.columns]
    other_cols = [c for c in save_df.columns if c not in base_cols]
    save_df = save_df[base_cols + other_cols]

    ts = datetime.now().strftime("_%Y%m%d_%H%M%S")
    os.makedirs("output/analysis", exist_ok=True)
    csv_path = os.path.join("output/analysis", os.path.basename(os.path.splitext(log_path)[0]) + ts + "_overall.csv")
    save_df.to_csv(csv_path, index=False)
    print(f"csv 已保存到: {csv_path}")
    return csv_path


def save_episode_metrics(
    episodes: List[Dict[str, Any]],
    best: Optional[Dict[str, Any]],
    log_path: str
) -> str:
    rows = []
    for ep in episodes:
        rows.append({
            "episode": ep["episode"],
            "n_steps": ep["steps"],
            "avg_imbalance": round(ep["avg_imbalance"], 6),
            "total_reward": round(ep["total_reward"], 3),
            "actions": ep["actions"],
            "selected": 1 if best is not None and ep["episode"] == best["episode"] else 0,
        })
    save_df = pd.DataFrame(rows)
    ts = datetime.now().strftime("_%Y%m%d_%H%M%S")
    os.makedirs("output/analysis", exist_ok=True)
    csv_path = os.path.join("output/analysis", os.path.basename(os.path.splitext(log_path)[0]) + ts + "_episode_metrics.csv")
    save_df.to_csv(csv_path, index=False)
    print(f"逐回合指标已保存到: {csv_path}")
    return csv_path


if __name__ == "__main__":

    app = QApplication(sys.argv)

    init()

    parser = argparse.ArgumentParser(description="RL 日志分析脚本")
    parser.add_argument("logfile", help="日志文件路径")
    parser.add_argument("--episode", type=int, default=None,
                        help="手动指定绘制第 N 回合；默认按负载均衡最优回合自动选取")
    args = parser.parse_args()

    episodes, overall_hist = parse_log(args.logfile)

    if args.episode is not None:
        best = next((ep for ep in episodes if ep["episode"] == args.episode), None)
        if best is None:
            print(f"未找到 episode {args.episode}")
            sys.exit(1)
        used_info = f"手动指定第 {args.episode} 回合"
    else:
        best = pick_best_episode(episodes)
        used_info = "自动选取负载均衡最优回合"

    if best is None:
        print("no valid episodes")
        sys.exit(1)

    save_episode_metrics(episodes, best, args.logfile)
    save_overall_csv(overall_hist, args.logfile)

    print(f"[INFO] {used_info}：第 {best['episode']} 回合用于绘制扇区划分图 "
          f"(avg_imbalance={best['avg_imbalance']:.4f}, n_steps={best['steps']}, "
          f"total_reward={best['total_reward']:.1f}, actions={best['actions']})")

    restore_episode(best)

    gridmap = GridMap([], gbl_lock=gbl_lock)
    gridmap.show()

    scene_step(True)

    re_build_section()

    scene_step(False)

    gridmap.update()

    ts = datetime.now().strftime("_%Y%m%d_%H%M%S")
    os.makedirs("output/analysis", exist_ok=True)
    img_path = os.path.join("output/analysis", f"sector_distribution_ep{best['episode']}" + ts + ".png")
    gridmap.grab().save(img_path)
    print(f"扇区划分图已保存到: {img_path}")

    sys.exit(app.exec())
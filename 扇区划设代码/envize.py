import os
import sys
import socket
import time
import subprocess
from typing import Dict, List, Tuple
from ast import literal_eval

import gym
from gym.spaces import Dict as GymDict, Discrete, Box
import numpy as np
from ray.rllib.env.multi_agent_env import MultiAgentEnv
from marllib.envs.base_env import ENV_REGISTRY

policy_mapping_dict = {
    "all_scenario": {
        "description": "TBXGridEnv all scenarios",
        "team_prefix": ("",),
        "all_agents_one_policy": True,
        "one_agent_one_policy": True,
    },
}

HOST, PORT = "127.0.0.1", 4291
N_GRID = 1000          # 格子总数
N_AGENT = 3            # 智能体数量，与格子一一对应
HORIZON = 500          # 一个 episode 的最大轮数

from collections.abc import Iterable
def flatten(x):
    for item in x:
        if isinstance(item, (str, bytes)):
            yield item
        elif isinstance(item, Iterable):
            yield from flatten(item)
        else:
            yield item

class TBXGridEnv(MultiAgentEnv):
    """
    Turn‑based multi‑agent env that talks to a TCP server at :4291.
    每次 step 只让当前轮到的 agent 执行一次 act，随后换下一个 agent。
    """

    metadata = {"name": "TBXGridEnv-v0"}

    def __init__(self, env_config):

        try:
            self.sock = self._connect()
            self.sock.sendall(b"quit\n")
        except Exception as e:
            pass

        self.horizon = env_config["horizon"] if "horizon" in env_config else HORIZON
        self.num_agents = env_config["n_agent"] if "n_agent" in env_config else N_AGENT
        self.num_grids = env_config["n_grid"] if "n_grid" in env_config else N_GRID

        self.agents = [f"{i}" for i in range(self.num_agents)]

        subprocess.Popen("sh reload.sh >log.txt", start_new_session=True, shell=True, cwd=os.path.dirname(__file__))
        time.sleep(10)
        super().__init__()
        self.sock = self._connect()
        

        self.cur_agent = 0          # 轮到哪个 agent 行动
        self.step_cnt = 0

        # 动作空间：整数 [‑1, N_GRID‑1]
        self.action_space = gym.spaces.Discrete(self.num_grids + 1)

        obs_len = self.num_agents * self.num_grids * 3 + self.num_agents * 3
        self.observation_space = GymDict(
            {
                "obs": gym.spaces.Box(low=-1e9, high=1e9, shape=(obs_len,), dtype=np.float32),
                "state": gym.spaces.Box(low=-1e9, high=1e9, shape=(obs_len,), dtype=np.float32),
                "action_mask": gym.spaces.Box(low=-1, high=2, shape=(self.action_space.n,), dtype=np.int8),
            }
        )

    # ---------- RLlib required methods ---------- #

    def reset(self, *, seed=None, options=None):
        # 热重启服务器并刷新
        try:
            self.sock.sendall(b"quit\n")
        finally:
            self.sock.close()
        
        time.sleep()  # 等待服务器关闭

        subprocess.Popen("sh reload.sh >log.txt", start_new_session=True, shell=True, cwd=os.path.dirname(__file__))
        time.sleep(10)  # 等待服务器启动
        self.sock = self._connect()

        self.step_cnt = 0
        self.cur_agent = 0
        obs = self._get_obs(self.cur_agent)
        return {str(self.cur_agent): obs}

    def step(self, action_dict: Dict[str, int]):
        agent_id_str, act = next(iter(action_dict.items()))
        agent_id = int(agent_id_str)

        # 1. 发送动作并拿奖励
        reward = self._send_act(agent_id, act)

        # 2. 收集下一个 agent 的观测
        self.cur_agent = (self.cur_agent + 1) % N_AGENT
        obs_next = self._get_obs(self.cur_agent)

        # 3. done 判定：超过 HORIZON 或者外部自定义
        self.step_cnt += 1
        terminated = self.step_cnt >= self.horizon
        done_dict = {
            "__all__": terminated
        }
        reward_dict = {str(agent_id): reward}
        obs_dict = {str(self.cur_agent): obs_next} if not terminated else {}
        info_dict = {}

        return obs_dict, reward_dict, done_dict, info_dict

    def close(self):
        try:
            self.sock.sendall(b"quit\n")
        finally:
            self.sock.close()
        
        time.sleep(1.5)

    # ---------- Internal helpers ---------- #

    def _connect(self) -> socket.socket:
        s = socket.create_connection((HOST, PORT), timeout=10)
        s.settimeout(10)
        return s

    def _get_obs(self, i: int) -> np.ndarray:
        self.sock.sendall(f"obs,{i}\n".encode())
        raw = self._recv_line()
        obs = np.array(list(flatten(literal_eval(raw))), dtype=np.float32)

        # 合法动作
        self.sock.sendall(f"transfer,{i}\n".encode())
        txt = self._recv_line().strip()
        legal = literal_eval(txt)

        mask = np.zeros(self.action_space.n, dtype=np.int8)
        mask[N_GRID] = 1
        mask[legal] = 1

        return {"obs": obs, "state": obs, "action_mask": mask}

    def _send_act(self, i: int, act: int) -> float:
        self.sock.sendall(f"act,{act},{i}\n".encode())
        raw = self._recv_line()
        return float(raw)   # 单个 reward

    def _recv_line(self) -> str:
        data = []
        while not data or data[-1] != 10:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise ConnectionError("TCP server closed.")
            data.extend(chunk)
        return bytearray(data).decode().strip()
    
    def get_env_info(self):
        env_info = {
            "space_obs": self.observation_space,
            "space_act": self.action_space,
            "num_agents": self.num_agents,
            "episode_limit": 200,
            "policy_mapping_info": policy_mapping_dict
        }
        return env_info

ENV_REGISTRY["TBXGridEnv"] = TBXGridEnv
import os
import sys
import time
import subprocess
import pickle
from typing import Dict, List, Tuple
from ast import literal_eval

import gymnasium as gym
from gymnasium.spaces import Dict as GymDict, Discrete, Box
import numpy as np
from ray.rllib.env.multi_agent_env import MultiAgentEnv
from marllib.envs.base_env import ENV_REGISTRY

from polygon import hexes
from section import sections
from scene import transfer_grid, input_action, scene_step, get_overall_observation, save_observation_to_json, scene_act, get_valid_transfers
from init import init

policy_mapping_dict = {
    "all_scenario": {
        "description": "TBXGridEnv all scenarios",
        "team_prefix": ("",),
        "all_agents_one_policy": True,
        "one_agent_one_policy": True,
    },
}

HOST, PORT = "127.0.0.1", 4291
N_GRID = 744          # 格子总数
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
        super().__init__()

        self.horizon = env_config["horizon"] if "horizon" in env_config else HORIZON
        self.num_agents = env_config["n_agent"] if "n_agent" in env_config else N_AGENT
        self.num_grids = env_config["n_grid"] if "n_grid" in env_config else N_GRID
        self.lock = env_config["lock"] if "lock" in env_config else None

        print("horizon:", self.horizon)
        print("num_agents:", self.num_agents)
        print("num_grids:", self.num_grids)

        self.agents = [f"{i}" for i in range(self.num_agents)]
        self._agent_ids = set(self.agents)

        self.cur_agent = 0
        self.step_cnt = 0

        # 动作空间：整数 [‑1, N_GRID‑1]
        self.action_space = gym.spaces.Discrete(self.num_grids + 1)

        obs_len = self.num_agents * self.num_grids * 3 + self.num_agents * (self.num_agents + 2)
        self.observation_space = GymDict(
            {
                "obs": gym.spaces.Box(low=-1e9, high=1e9, shape=(obs_len,), dtype=np.float32),
                "state": gym.spaces.Box(low=-1e9, high=1e9, shape=(obs_len,), dtype=np.float32),
                "action_mask": gym.spaces.Box(low=-1, high=2, shape=(self.action_space.n,), dtype=np.int8),
            }
        )

    # ---------- RLlib required methods ---------- #

    def reset(self, *, seed=None, options=None):

        print("load existing sectors...")
        with open(os.path.join(os.path.dirname(__file__), 'output', 'cache', 'sections.pkl'), 'rb') as f:
            global sections
            sections[:] = pickle.load(f)

        for section in sections:
            for hex_grid in section.grid_list:
                # print("\033[1;32m" + str(hex_grid) + "\033[0m")
                hexes[hex_grid].section = section.index

        scene_step(False)

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
        self.cur_agent = (self.cur_agent + 1) % self.num_agents
        obs_next = self._get_obs(self.cur_agent)

        # 3. done 判定：超过 HORIZON 或者外部自定义
        self.step_cnt += 1
        terminated = (self.step_cnt // self.num_agents) >= self.horizon
        done_dict = {
            "__all__": terminated
        }
        reward_dict = {str(agent_id): reward}
        obs_dict = {str(self.cur_agent): obs_next} if not terminated else {}
        info_dict = {}

        return obs_dict, reward_dict, done_dict, info_dict

    def close(self):
        pass

    # ---------- Internal helpers ---------- #

    def _get_obs(self, i: int) -> np.ndarray:
        obs = list(map(float, list(flatten(get_overall_observation(i)))))

        legal = get_valid_transfers(i)

        mask = np.zeros(self.action_space.n, dtype=np.int8)
        mask[self.num_grids] = 1
        mask[legal] = 1

        return {"obs": obs, "state": obs, "action_mask": mask}

    def _send_act(self, i: int, act: int) -> float:
        return scene_act(self.lock, act, i)

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
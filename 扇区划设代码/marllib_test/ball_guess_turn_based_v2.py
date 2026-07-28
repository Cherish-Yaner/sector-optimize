# ball_guess_turn_based_v2.py  —— 球位在换手后立即改变
import numpy as np
from gymnasium.spaces import Discrete
from ray.rllib.env.multi_agent_env import MultiAgentEnv

class BallGuessTurnEnvV2(MultiAgentEnv):
    """Turn‑based，多球位版本：每次换手先随机新球位。"""
    def __init__(self, env_config=None):
        cfg = env_config or {}
        self.players    = ["player0", "player1"]
        self.positions  = 5
        self.hit_prob   = 0.8
        self.max_turns  = cfg.get("max_turns", 80)   # 动作次数而非完整回合

        self.observation_space = Discrete(self.positions)
        self.action_space      = Discrete(self.positions)

        self.reset()

    # ----- 初始化 -----
    def reset(self, *, seed=None, options=None):
        self.turn_count = 0
        self.current    = "player0"                       # 先手
        self.ball_pos   = np.random.randint(self.positions)
        obs = {self.current: self.ball_pos}
        info = {}
        return obs, info

    # ----- 每步仅当前玩家行动 -----
    def step(self, action_dict):
        player = self.current
        action = int(action_dict[player])

        # 命中判定
        reward = 1.0 if (action == self.ball_pos and np.random.rand() < self.hit_prob) else 0.0
        reward_dict = {player: reward}

        # 累计动作数并检测终局
        self.turn_count += 1
        done = self.turn_count >= self.max_turns

        # 交给另一玩家；若终局则不再生成观测
        if not done:
            # 换手前先随机新球位
            self.current  = "player1" if player == "player0" else "player0"
            self.ball_pos = np.random.randint(self.positions)
            obs_dict      = {self.current: self.ball_pos}
            term_dict     = {"__all__": False}
        else:
            obs_dict  = {}
            term_dict = {id_: True for id_ in self.players}
            term_dict["__all__"] = True

        info_dict = {}
        return obs_dict, reward_dict, term_dict, info_dict

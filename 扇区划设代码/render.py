import os
os.environ['RAY_LOCAL_MODE'] = '1'

import logging
logging.getLogger("ray.rllib").setLevel(logging.ERROR)

import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="gymnasium")
warnings.filterwarnings("ignore", category=RuntimeWarning, message="overflow encountered in reduce")


# 环境同时装了旧版 gym 0.23.1 和 gymnasium，Ray 内部 import gym 会拿到旧版，
# 导致 env 的 observation_space(gymnasium.spaces.Dict) 被判定为无效，
# 必须把 sys.modules['gym'] 换成 gymnasium（与 train.py 保持一致），否则报
# "observation_space not provided in PolicySpec" 错误
import gymnasium as gym
import sys
sys.modules['gym'] = gym

from init import init
from scene import scene_step
from MARLlib.marllib import marl

import register_env

def render():

    env = marl.make_env(
        environment_name="TBXGridEnv", 
        map_name="default", 
        lock=None,
        horizon=1000,    # 每个 episode 最多 1000 轮(3 个 agent 轮流(选取了武汉三个扇区)，共最多 3000 次 env step)
        n_agent=3,       # # 渲染分支 evaluation_num_episodes=100（run_cc.py:40-41），故render 共跑约 30 万次 env step
        n_grid=744
    )

    mappo = marl.algos.mappo(hyperparam_source="common")

    model = marl.build_model(env, mappo, {"core_arch": "mlp", "encode_layer": "128-128"})

    mappo.render(
        env,
        model,
        stop={'timesteps_total': 10},  # # timesteps_total 是累计值，restore 后已是 2001998，该条件无意义；
        # 实际停止由 run_cc.py:51-55 的 training_iteration=1 控制，即只跑 1 个训练迭代（约 4000 步采样，lr=1e-10 不更新网络）
        stop_timesteps=2,   # 会被 stop 参数覆盖；渲染内容由 run_cc.py:38-49 决定：evaluation_interval=1 + evaluation_num_episodes=100 个 episode
        local_mode=True,
        share_policy="all",
        num_workers=0,
        restore_path={
            # 网络参数  传入 train.py 中训练好的模型参数路径，进行渲染
            'params_path': "exp_results/mappo_mlp_default/MAPPOTrainer_TBXGridEnv_default_57961_00000_0_2026-07-30_11-47-10/params.json",
            # 训练状态
            'model_path': "exp_results/mappo_mlp_default/MAPPOTrainer_TBXGridEnv_default_57961_00000_0_2026-07-30_11-47-10/checkpoint_000400",
            'render': True
        }
    )

if __name__ == "__main__":
    
    init()
    scene_step()

    render()
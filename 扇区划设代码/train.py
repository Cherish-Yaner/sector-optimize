import os
os.environ['RAY_LOCAL_MODE'] = '1'

import logging
logging.getLogger("ray.rllib").setLevel(logging.ERROR)

import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="gymnasium")
warnings.filterwarnings("ignore", category=RuntimeWarning, message="overflow encountered in reduce")

import gymnasium as gym
import sys
sys.modules['gym'] = gym

from init import init
from scene import scene_step
from MARLlib.marllib import marl

import register_env

def render():

    env = marl.make_env(environment_name="TBXGridEnv", map_name="default", lock=None)

    mappo = marl.algos.mappo(hyperparam_source="common")

    model = marl.build_model(env, mappo, {"core_arch": "mlp", "encode_layer": "128-128"})

    mappo.fit(
        env,
        model,
        stop={'timesteps_total': 2000000},     # train 累计采样 200 万步才停
        stop_timesteps=2000000,
        local_mode=True,
        share_policy="all",
        num_workers=0,
        checkpoint_freq=100,
        checkpoint_end=True,
        # restore_path={    # 重新训练时不需要该路径下的参数，只有在想继续之前的模型进行训练时才需要，但是训练完200w步后，就不能再继续训练了，除非加大步数
        #     # 网络参数
        #     'params_path': "exp_results/mappo_mlp_default/MAPPOTrainer_TBXGridEnv_default_57961_00000_0_2026-07-30_11-47-10/params.json",
        #     # 训练状态
        #     'model_path': "exp_results/mappo_mlp_default/MAPPOTrainer_TBXGridEnv_default_57961_00000_0_2026-07-30_11-47-10/checkpoint_001000",
        #     'render': True
        # }     
    )

if __name__ == "__main__":
    
    init()
    scene_step()
    render()


from init import init
from scene import scene_step
from MARLlib.marllib import marl

import register_env

def render():

    env = marl.make_env(
        environment_name="TBXGridEnv", 
        map_name="default", 
        lock=None,
        horizon=1000,
        n_agent=3,
        n_grid=744
    )

    mappo = marl.algos.mappo(hyperparam_source="common")

    model = marl.build_model(env, mappo, {"core_arch": "mlp", "encode_layer": "128-128"})

    mappo.render(
        env,
        model,
        stop={'timesteps_total': 10},
        stop_timesteps=2,
        local_mode=True,
        share_policy="all",
        num_workers=0,
        restore_path={
            # 网络参数（不需要优化器参数）
          'params_path': "exp_results/mappo_mlp_default/MAPPOTrainer_TBXGridEnv_default_847b8_00000_0_2025-06-26_13-50-51/params.json",
          'render': True
        }
    )

if __name__ == "__main__":
    
    init()
    scene_step()

    render()
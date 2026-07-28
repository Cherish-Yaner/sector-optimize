from marllib.envs.base_env import ENV_REGISTRY
from marllib.envs.base_env.base_env import BaseEnv
from marllib import marl

# --- 封装 + 注册 ---
class BallGuessTurnEnvV2_MARL(BaseEnv):
    def __init__(self, env_config):
        super().__init__(BallGuessTurnEnvV2(env_config), env_config)

ENV_REGISTRY["ball_guess_turn_v2"] = BallGuessTurnEnvV2_MARL

# --- 训练脚本 ---
if __name__ == "__main__":
    env = marl.make_env(
        environment_name="ball_guess_turn_v2",
        map_name="default",
        max_turns=100        # 可自行调整
    )

    algo  = marl.algos.mappo(hyperparam_source="common")
    model = marl.build_model(env, algo, {"core_arch": "mlp", "encode_layer": "128-128"})

    # 两名玩家对称，策略共享
    algo.fit(
        env, model,
        stop={"timesteps_total": 1e5},
        share_policy="all",
        local_mode=True
    )

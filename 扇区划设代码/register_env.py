from envize_local import TBXGridEnv

def env_creator(config):
    return TBXGridEnv(config)

# from ray.tune.registry import register_env
# register_env("TBXGridEnv", env_creator)
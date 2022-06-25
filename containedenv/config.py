import os

def config_dir() -> str:
    dir_path = os.path.dirname(os.path.realpath(__file__))
    return os.path.join(os.path.dirname(dir_path), "config")

def default_config() -> str:
    return os.path.join(config_dir(), "default.yml")
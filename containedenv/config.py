import os
import yaml

def config_dir() -> str:
    dir_path = os.path.dirname(os.path.realpath(__file__))
    return os.path.join(os.path.dirname(dir_path), "config")

def default_config() -> str:
    return os.path.join(config_dir(), "default.yml")

def load_config(config:str = None):
    __config = config if config is not None else default_config()
    with open(__config, "r") as conffile:
        try:
            return yaml.safe_load(conffile)
        except yaml.YAMLError as exc:
            print(exc)
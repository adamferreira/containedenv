import os
import yaml

def config_dir() -> str:
    dir_path = os.path.dirname(os.path.realpath(__file__))
    return os.path.join(os.path.dirname(dir_path), "config")

def default_config() -> str:
    return os.path.join(config_dir(), ".hidden.yaml")

def load_config(config:str = None):
    __config = config if config is not None else default_config()
    with open(__config, "r") as conffile:
        try:
            return yaml.safe_load(conffile)
        except yaml.YAMLError as exc:
            print(exc)

def appname(config) -> str:
    return config["app"]["name"]

def user(config) -> str:
    return config["app"]["user"]

def imagename(config) -> str:
    return f"containedenv:{appname(config)}"

def containername(config) -> str:
    return f"{appname(config)}_cnt"

def get_github_credentials(user:str, token:str) -> str:
	# git config --global credential.helper 'store --file ~/.my-credentials'
	return f"https://{user}:{token}@github.com"
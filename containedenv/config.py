import os
import yaml
from typing import Optional, List, Dict
from dataclasses import dataclass, field
from dataclasses_json import dataclass_json, DataClassJsonMixin


@dataclass_json
@dataclass
class AppContainer(DataClassJsonMixin):
    # User name within the container
    user:str
    # Name of the container to be creater
    name:str

@dataclass_json
@dataclass
class GithubProfile(DataClassJsonMixin):
    user:str
    mail:str
    token:Optional[str] = None


@dataclass_json
@dataclass
class Project(DataClassJsonMixin):
    scmprofile:Optional[str] = None
    workspace:Optional[str] = "$PROJECTS"
    requires:Optional[List[str]] = None
    image:Optional[List[str]] = None
    sources:Optional[List[str]] = None
    container:Optional[List[str]] = None



@dataclass_json
@dataclass
class Config(DataClassJsonMixin):
    app:AppContainer
    projects:Optional[List[Project]] = field(default_factory=list)
    github_profile:Optional[GithubProfile] = None
    
    def from_dict(d):
        config = Config.from_dict(d)
        # Set project names
        for projname, proj in config.projects:
            setattr(proj, "name", projname)
        return config


def config_dir() -> str:
    dir_path = os.path.dirname(os.path.realpath(__file__))
    return os.path.join(os.path.dirname(dir_path), "config")

def default_config() -> str:
    return os.path.join(config_dir(), "test.yml")

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
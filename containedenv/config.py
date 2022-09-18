import argparse
import os
import yaml
from argparse import Namespace
from typing import Optional, List, Dict
from dataclasses import dataclass, field
from dataclasses_json import dataclass_json, DataClassJsonMixin


@dataclass_json
@dataclass
class AppContainer(DataClassJsonMixin):
    # User name within the container
    user:str
    # Name of the container to be created
    name:str

@dataclass_json
@dataclass
class GithubProfile(DataClassJsonMixin):
    # Github Username
    user:str
    # Github email for user
    mail:str
    # Github access token
    token:Optional[str] = None


@dataclass_json
@dataclass
class Package(DataClassJsonMixin):
    # Package name in the configuration
    name:str
    # 'Package' required for this package
    requires:Optional[List[str]] = field(default_factory=list)
    # (Priority 1) Package(s) name(s) in apt repository
    apt_packages:Optional[List[str]] = field(default_factory=list)
    # (Priority 2) Path to a dockerfile to be appended to the containedenv dockerfile
    dockerfile:Optional[str] = None
    # (Priority 3) Dockerfile lines to be appended to the containedenv dockerfile
    image:Optional[List[str]] = field(default_factory=list)



@dataclass_json
@dataclass
class Project(DataClassJsonMixin):
    name:str
    scmprofile:Optional[str] = None
    # Path in the container where the project will be installed
    workspace:Optional[str] = "$PROJECTS"
    # 'Package' required for this project
    requires:Optional[List[str]] = field(default_factory=list)
    # Dockerfile lines to be appended to the containedenv dockerfile
    image:Optional[List[str]] = field(default_factory=list)
    # List of git repositories ulrs to be cloned
    sources:Optional[List[str]] = field(default_factory=list)
    # Bash lines to be executed in the container after it launch
    container:Optional[List[str]] = field(default_factory=list)

@dataclass_json
@dataclass
class Config(DataClassJsonMixin):
    app:AppContainer
    # Package list that may or may not be installed in the container (depending on projects dependancies)
    packages:Optional[List[Package]] = field(default_factory=list)
    # List of projects
    projects:Optional[List[Project]] = field(default_factory=list)
    # Optional github profile to configure inside the container
    github_profile:Optional[GithubProfile] = None
    # Program arguments
    args:Optional[argparse.Namespace] = None
    
    def from_dict(d):
        # Use dataclass_json to load the config
        config = Config.from_dict(d["config"])
        # Get argparse arguments from the global dict
        config.args = d["args"]
        return config

    def from_args(args:argparse.Namespace) -> 'Config':
        conf = load_config()
        conf["args"] = args
        return Config.from_dict(conf)

    def appname(self) -> str:
        return self.app.name
    
    def user(self) -> str:
        return self.app.user

    def imagename(self) -> str:
        return f"containedenv:{self.appname()}"

    def containername(self) -> str:
        return f"{self.appname()}_cnt"




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

def get_github_credentials(user:str, token:str) -> str:
	# git config --global credential.helper 'store --file ~/.my-credentials'
	return f"https://{user}:{token}@github.com"
import docker
import os
from dockerfile import UbuntuDockerFile

class ContainedEnv:
    def __init__(self, config:dict) -> None:
        self._dockerfile:UbuntuDockerFile = UbuntuDockerFile()
        self._workspace = "C:\\Users\\a.ferreiradacosta\\PersonnalProjects\\containedenv\\torm"
        self._image = None
        self._container = None
        self._dockerclient = docker.from_env()

    def build_image(self):
        file = os.path.join(self._workspace, "Dockerfile")
        self._dockerfile.dump(
            file
        )
        self._dockerclient.images.build(
            path = self._workspace,
            dockerfile = file,
            tag = "containedenv:0.0.1",
            # Remove intermediate containers. 
            # The docker build command now defaults to --rm=true, 
            # but we have kept the old default of False to preserve backward compatibility
            rm = True,
            # Always remove intermediate containers, even after unsuccessful builds
            forcerm = True
        )
        return self._image
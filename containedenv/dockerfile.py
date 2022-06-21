import docker

class DockerFile:
    def __init__(self, path:str):
        self._path = path

    def FROM(self, image:str):
        return self
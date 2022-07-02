import docker
import os
from dockerfile import UbuntuDockerFile
from config import config_dir

class ContainedEnv:

    @property
    def image(self):
        return self._image

    @property
    def container(self):
        return self._container

    @property
    def congif(self):
        return self._config

    def __init__(self, config:dict) -> None:
        self._workspace = config_dir()
        self._config = config
        self._image = None
        self._container = None
        self.dockerclient = docker.from_env()

    def from_image(self, image:str) -> "ContainedEnv":
        self._image = self.dockerclient.images.get(image)
        return self

    def build_image(self) -> "ContainedEnv":
        appname = "testapp"
        imagename = f"containedenv:{appname}"
        dockerfilepath = os.path.join(self._workspace, f"Dockerfile.{appname}")

        # TODO check if image already exists (?)

        # Create docker file on file system
        dockerfile = UbuntuDockerFile()
        dockerfile.dump(dockerfilepath)

        # Build the actual image
        self._image, _ = self.dockerclient.images.build(
            path = self._workspace,
            dockerfile = dockerfilepath,
            tag = imagename,
            # Remove intermediate containers. 
            # The docker build command now defaults to --rm=true, 
            # but we have kept the old default of False to preserve backward compatibility
            rm = True,
            # Always remove intermediate containers, even after unsuccessful builds
            forcerm = True
        )

        # If everything went fine, remove docker file from file system
        if os.path.exists(dockerfilepath): os.unlink(dockerfilepath)

        return self

    def run_container(self) -> "ContainedEnv":
        if self.image is None:
            raise docker.errors.ImageNotFound

        appname = "testapp"
        containername = f"{appname}_cnt"
        
        # Find the image name tagged for this container
        matches = [tag for tag in self.image.tags if tag == f"containedenv:{appname}"]
        if len(matches) == 0:
            raise docker.errors.ImageNotFound

        self._container = self.dockerclient.containers.run(
            image = matches[0],
            #image = self._image.id,
            command = "bash",
            name = containername,
            hostname = appname,
            tty = True,
            detach = True
        )

        self.container.logs()
        _, out = self.container.exec_run("ls")
        print(out.decode('utf-8'))
        print(f"Enter this container with \"docker exec -it {containername} bash\"")
        #self.dockerclient.images.remove(matches[0], force = True)
        return self
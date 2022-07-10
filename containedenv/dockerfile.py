from typing import List
from pyrc.docker import DockerFile


class UbuntuDockerFile(DockerFile):
    def __init__(
            self,
            dockerfile:str,
            user:str = "root",
        ) -> None:
        super().__init__(dockerfile)

        # From ubuntu 22 
        self.FROM("ubuntu:22.04")

        # Run eveything as root
        self.USER(f"{user}")

        # Pkg setup
        self.RUN([
            "DEBIAN_FRONTEND=noninteractive apt-get update -y",
            "DEBIAN_FRONTEND=noninteractive apt-get upgrade -y"
        ])

    def install(self, ubuntu_packages:List[str]) -> "UbuntuDockerFile":
        if isinstance(ubuntu_packages, str):
            return self.install([ubuntu_packages])

        self.RUN(
            [f"DEBIAN_FRONTEND=noninteractive apt-get install -y {pkg}" for pkg in ubuntu_packages]
        )
        return self
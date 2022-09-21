from typing import List
from pyrc.docker import DockerFile


class UbuntuDockerFile(DockerFile):
    def __init__(
            self,
            dockerfile:str,
            imgfrom:str,
            user:str
        ) -> None:
        super().__init__(dockerfile, "w+")

        # open file
        self.open()

        # From ubuntu 22 
        self.FROM(imgfrom)

        # Run eveything as root
        self.USER(f"{user}")

        # Pkg setup
        self.RUN([
            f"{self.__package_manager()} update -y",
            f"{self.__package_manager()} upgrade -y"
        ])

        self.image:str = imgfrom.split(":")[0]
        self.tag:str = imgfrom.split(":")[0]

    def __package_manager(self) -> str:
        prefix:str = "DEBIAN_FRONTEND=noninteractive"
        if "debian" in self.image:
            return f"{prefix} dpkg"

        if "ubuntu" in self.image:
            return f"{prefix} apt-get"

        if "fedora" in self.image:
            return f"{prefix} yum"

        if "alpine" in self.image:
            return f"{prefix} apk"

    def install(self, ubuntu_packages:List[str]) -> "UbuntuDockerFile":
        if isinstance(ubuntu_packages, str):
            return self.install([ubuntu_packages])

        if len(ubuntu_packages) == 0:
            return self
        
        if len(ubuntu_packages) == 1:
            self.RUN(
                f"{self.__package_manager()} install -y {ubuntu_packages[0]}" 
            )
        else:
            install = " \ \n\t".join(ubuntu_packages)
            self.RUN(
                f"{self.__package_manager()} install -y \ \n\t{install}" 
            )
        return self
        
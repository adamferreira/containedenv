from typing import List, Union
import docker

class DockerFile:
    def __init__(self, image:str):
        self._statements = []
        self._from = image

    def dump(self, path:str) -> None:
        with open(path, "w+") as f:
            f.write("FROM" + " " + self._from + "\n\n")
            f.writelines(self._statements)

    def FROM(self, image:str) -> "DockerFile":
        self._from = image
        return self

    def RUN(self, statements:Union[str, List[str]]) -> "DockerFile":
        if isinstance(statements, str):
            return self.RUN([statements])

        self._statements.extend([f"{self.RUN.__name__} {s} \n" for s in statements])
        self._statements.append("")
        return self

    def USER(self, user:str) -> "DockerFile":
        self._statements.append(f"{self.USER.__name__} {user} \n\n")
        return self


class UbuntuDockerFile(DockerFile):
    def __init__(
            self,
            user:str = "root"
        ):
        super().__init__("ubuntu:latest")

        # Run eveything as root
        self.USER("root")

        # Pkg setup
        self.RUN([
            "DEBIAN_FRONTEND=noninteractive apt-get update -y",
            "DEBIAN_FRONTEND=noninteractive apt-get upgrade -y"
        ])

    def install(self, ubuntu_packages:List[str]) -> "UbuntuDockerFile":
        self.RUN(
            [f"DEBIAN_FRONTEND=noninteractive apt-get install -y {pkg}" for pkg in ubuntu_packages]
        )
        return self
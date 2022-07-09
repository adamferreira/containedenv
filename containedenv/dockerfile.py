from typing import List, Union
from pyrc.system import ScriptGenerator, OSTYPE

class DockerFile(ScriptGenerator):
    def __init__(self, dockerfile:str) -> None:
        ScriptGenerator.__init__(
            self,
            script_path = dockerfile,
            ostype = OSTYPE.LINUX
        )

    #@overrides
    def exec_command(self, cmd:str, cwd:str = "", environment:dict = None, event = None):
        self.script.writelines([
            f"{cmd}\n",
            "\n"
        ])

    def FROM(self, image:str) -> "DockerFile":
        self.exec_command(f"{self.FROM.__name__} {image}")
        return self

    def RUN(self, statements:Union[str, List[str]]) -> "DockerFile":
        if isinstance(statements, str):
            return self.RUN([statements])

        self.exec_command("\n".join([f"{self.RUN.__name__} {s}" for s in statements]))
        return self

    def USER(self, user:str) -> "DockerFile":
        self.exec_command(f"{self.USER.__name__} {user}")
        return self


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
        self.RUN(
            [f"DEBIAN_FRONTEND=noninteractive apt-get install -y {pkg}" for pkg in ubuntu_packages]
        )
        return self
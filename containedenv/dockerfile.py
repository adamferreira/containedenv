from typing import List, Union
import docker

class DockerFile:
    def __init__(self):
        self._statements = []
        self._from = "ubuntu:latest"

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
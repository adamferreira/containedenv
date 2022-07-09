import argparse
from distutils.command import config
import docker, os
from dockerfile import UbuntuDockerFile
from engine import ContainedEnv
from config import load_config, config_dir

def get_argparser():
    parser = argparse.ArgumentParser(
        description="Build a contained dev environment"
    )

    parser.add_argument(
        "--no-build",
        dest="build",
        action="store_false",
        help=(
            "Do not actually build the image. Useful in conjunction " "with --debug."
        ),
    )

def main():
    c = ContainedEnv(load_config())
    print(c.config)
    return None
    c.build_image().run_container()
    return None

if __name__ == "__main__":
    #main()
    dockerfile = UbuntuDockerFile(os.path.join(config_dir(), f"Dockerfile.test"))
    exit(-1)


    
    client = docker.from_env()
    print(client.containers.list())
    print(client.images.list())
    img = client.images.list()[0]
    cnt = client.containers.list()[0]
    #cnt.attach(stdout = True, stderr = True)
    _, out = cnt.exec_run("ls /home")
    print(out.decode('utf-8'))
    #cnt.stop()
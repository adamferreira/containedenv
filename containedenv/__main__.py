import argparse
import docker
from containedenv.engine import ContainedEnv
from containedenv.config import load_config

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
    c.build_image().run_container()
    #c.setup_github()
    return None

if __name__ == "__main__":
    main()
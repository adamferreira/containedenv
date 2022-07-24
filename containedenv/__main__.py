import argparse
import sys
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
        )
    )

    parser.add_argument(
        "--debug",
        "-d",
        dest="debug",
        action="store_false",
        help=(
            "Print all command outputs in image and container bulding"
        )
    )

    parser.add_argument(
        "--rebuild",
        dest="rebuild",
        action="store_false",
        help="Reconstruct the image even is an image with the same name is found",
    )

    parser.add_argument(
        "--config",
        type=str,
        default="config/default.yml",
        help="Path to config file for containedenv"
    )

    parser.add_argument(
        "--ghtoken",
        type=str,
        dest="ghtoken",
        help="Github access token",
    )

    parser.add_argument(
        "--ports",
        "-p",
        dest="ports",
        action="append",
        help=(
            "Specify port mappings for the image. Needs a command to "
            "run in the container." "Syntax is <port_on_host>:<port_in_container>"
        ),
        default=[]
    )

    return parser

def main():
    c = ContainedEnv(load_config())
    c.build_image()
    c.run_container()
    return None

if __name__ == "__main__":
    containedenvargs, otherargs = get_argparser().parse_known_args(sys.argv[1:])
    print(containedenvargs)
    #return None
    #main()
import argparse
import sys
from containedenv.engine import ContainedEnv
from containedenv.config import load_config

from pyrc.remote import create_default_sshconnectors

def get_argparser():
    parser = argparse.ArgumentParser(
        description="Build a contained dev environment"
    )

    parser.add_argument(
        "--no-build",
        dest="nobuild",
        action="store_true",
        help=(
            "Do not actually build the image. Useful in conjunction " "with --debug."
        )
    )

    parser.add_argument(
        "--debug",
        "-d",
        dest="debug",
        action="store_true",
        help=(
            "Print all command outputs in image and container bulding"
        )
    )

    parser.add_argument(
        "--rebuild",
        "-r",
        dest="rebuild",
        action="store_true",
        help="Reconstruct the image even is an image with the same name is found"
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
        default=None
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

if __name__ == "__main__":
    containedenvargs, otherargs = get_argparser().parse_known_args(sys.argv[1:])
    print(containedenvargs)
    c = ContainedEnv(load_config(), containedenvargs)
    c.build_image()
    c.run_container()
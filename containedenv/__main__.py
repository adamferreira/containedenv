import argparse
import docker


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
    return None

if __name__ == "__main__":
    main()
    client = docker.from_env()
    print(client.containers.list())
    print(client.images.list())
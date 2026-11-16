"""Explicit user desktop setup using the current installed Python environment."""

import argparse

from shrutadhara.desktop import install

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-desktop", action="store_true")
    print(install(no_desktop=parser.parse_args().no_desktop))

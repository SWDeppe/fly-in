"""Command-line and graphical entry points for Fly-in."""

import argparse
import os
from pathlib import Path

from fly_in.game_logic import GameLogic
from fly_in.parser import Parser

ROOT = Path(__file__).resolve().parents[1]


def build_parser() -> argparse.ArgumentParser:
    """Build the parser used by the executable entry point."""
    parser = argparse.ArgumentParser(description="Route drones through a map.")
    parser.add_argument(
        "map_file", type=Path, nargs="?", help="Optional map file to open."
    )
    return parser


class FlyInError(Exception):
    def __init__(self, *args: object) -> None:
        super().__init__(*args)


def main() -> None:
    args = build_parser().parse_args()

    map_folder = Path(__file__).parents[1] / "maps/"
    if not hasattr(args, "map_file") or args.map_file is None:
        raise FlyInError("Wrong usage map missing: python3 fly_in 'map file'")

    if not os.path.exists(str(Path(map_folder / args.map_file))):
        raise FlyInError("File does not exist !")

    map = Parser.parse(str(map_folder / args.map_file))
    game = GameLogic(map,  windowSiz=(800, 600))
    game.launch()

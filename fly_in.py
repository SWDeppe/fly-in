#!/usr/bin/python3.10
from visual_engine import VEngine, VEngineError


def main():
    ...


def test_VEngine():
    # Textures.preload_image()
    VEngine.load()
    # print("all fine")
    VEngine.launch()
    print(VEngineError.get_errors())


if __name__ == "__main__":
    test_VEngine()
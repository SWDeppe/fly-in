import unittest
from pathlib import Path

from src.parsing.parser import Parsing


class ParserTests(unittest.TestCase):
    def setUp(self) -> None:
        self.parser = Parsing()

    def test_parse_linear_map(self) -> None:
        map_path = Path(__file__).resolve().parents[1] / "maps" / "easy" / "01_linear_path.txt"

        data = self.parser.parse_file(map_path)

        self.assertEqual(data["nb_drones"], 2)
        self.assertEqual(data["start_hub"], "start")
        self.assertEqual(data["end_hub"], "goal")
        self.assertEqual(data["hubs"]["start"]["position"], [0, 0])
        self.assertEqual(data["hubs"]["start"]["kind"], "start")
        self.assertEqual(data["hubs"]["start"]["metadata"], {"color": "green"})
        self.assertEqual(data["connections"][0], {"from": "start", "to": "waypoint1", "metadata": {}})

    def test_parse_connection_metadata(self) -> None:
        map_path = Path(__file__).resolve().parents[1] / "maps" / "hard" / "02_capacity_hell.txt"

        data = self.parser.parse_file(map_path)

        self.assertEqual(data["nb_drones"], 12)
        self.assertEqual(data["connections"][0]["metadata"], {"max_link_capacity": 1})


if __name__ == "__main__":
    unittest.main()

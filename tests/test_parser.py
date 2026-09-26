from pathlib import Path

import pytest

from fly_in.parser.exceptions import ParseError
from fly_in.parser.parser import Parser


TOKEN_MAP_FILE = Path(__file__).parents[1] / "maps" / "test" / "token.txt"
PARSER_MAP_FILE = Path(__file__).parents[1] / "maps" / "test" / "parsing.txt"
INVALIDES_MAPS_DIR = Path(__file__).parents[1] / "maps" / "test" / "invalides"

def test_tokenizer_reads_sections_values_parameters_and_line_numbers() -> None:
	tokens = Parser.tokenizer(str(TOKEN_MAP_FILE))

	assert len(tokens) == 3
	assert tokens[0] == [
		(2, ("nb_drones", ["3"]), []),
		(3, ("start_hub", ["A"]), []),
	]
	assert tokens[1] == [
		(5, ("hub", ["A", "0", "0"]), [("type", "normal"), ("capacity", "2")]),
		(6, ("hub", ["B", "10", "0"]), [("type", "restricted")]),
	]
	assert tokens[2] == [(8, ("connection", ["A", "B"]), [])]


def test_tokenizer_rejects_line_without_colon(tmp_path: Path) -> None:
	map_file = tmp_path / "invalid.map"
	map_file.write_text("nb_drones 3\n", encoding="utf-8")

	with pytest.raises(ParseError, match=r"line: 1"):
		Parser.tokenizer(str(map_file))


def test_tokenizer_rejects_malformed_parameter(tmp_path: Path) -> None:
	map_file = tmp_path / "invalid.map"
	map_file.write_text("hub: A 0 0 [capacity]\n", encoding="utf-8")

	with pytest.raises(ParseError, match=r"line: 1"):
		Parser.tokenizer(str(map_file))

def test_parser_valide():
	map = Parser.parse(str(PARSER_MAP_FILE))
	assert map.drone_count == 5
	assert map.start == "start"
	assert map.end == "end"

	assert map.zones["start"].x == 0
	assert map.zones["start"].y == 0
	assert map.zones["start"].color == "blue"
	assert map.zones["start"].zone_type == "normal"

	assert map.zones["possible"].x == 1
	assert map.zones["possible"].y == -1
	assert map.zones["possible"].zone_type == "restricted"

	assert map.zones["impossible"].x == 1
	assert map.zones["impossible"].y == 1
	assert map.zones["impossible"].capacity == 2
	assert map.zones["impossible"].zone_type == "blocked"

	assert map.zones["end"].x == 2
	assert map.zones["end"].y == 0
	assert map.zones["end"].zone_type == "priority"

def test_parser_invalide():
	for map_file in INVALIDES_MAPS_DIR.iterdir():
		error_name, line_and_case = map_file.stem.split("_ligne", 1)
		expected_line = line_and_case.split("_", 1)[0]
		expected_error = error_name.replace("-colon-", ": ").replace("-", " ")

		with pytest.raises(ParseError) as raised_error:
			Parser.parse(str(map_file))

		actual_error = str(raised_error.value).replace("'", "")
		assert expected_error in actual_error
		assert f"(line: {expected_line})" in actual_error
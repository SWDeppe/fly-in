import os
from typing import Any, cast

from fly_in.models import Connection, MapData, Zone
from fly_in.parser.exceptions import ParseError


class Parser:
    """Parse a Fly-in map file into a validated MapData object."""
    Tsection = list[   # lines
        tuple[     # item, parameters
            int,  # line number for exception handeling
            tuple[str, list[str]],  # item (key: values)
            list[   # parameters [content]
                tuple[str, str]  # [key1=value1, key2...]
            ]
        ]
    ]

    @staticmethod
    def drone_num(num: str) -> int:
        value = int(num)
        if value <= 0:
            raise ValueError
        return value

    @staticmethod
    def zone(zone: str) -> str:
        if zone in ["blocked", "restricted", "normal", "priority"]:
            return zone
        else:
            raise ValueError

    @staticmethod
    def connection(connections: str) -> tuple[str, str]:
        if '-' in connections:
            connection1, connection2 = connections.split('-')
        else:
            connection1, connection2 = connections.split()

        return (connection1, connection2)

    hubMetadata: dict[str, Any] = {  # noqa: RUF012
        "type": zone,
        "zone": zone,
        "capacity": drone_num,
        "max_drones": drone_num,
        "color": str,
    }

    sectionsTypes: dict[str, list[Any]] = {  # noqa: RUF012
        "nb_drones": [drone_num],
        "start_hub": [str, int, int, hubMetadata],
        "end_hub": [str, int, int, hubMetadata],
        "hub": [str, int, int, hubMetadata],
        "connection":
        [
            connection,
            {
                "max_link_capacity": drone_num
            }
        ]
    }

    @staticmethod
    def tokenizer(map_file: str) -> list["Parser.Tsection"]:
        """Split a map file into sections of keyed values and parameters."""
        tokens: list[Parser.Tsection] = []
        if not os.path.exists(map_file):
            raise ParseError("File does not exist !", 0)
        with open(map_file, "r", encoding="utf-8") as map_stream:
            section: Parser.Tsection = []
            for line_number, line in enumerate(map_stream, start=1):
                line = line.strip()
                if line.startswith("#"):
                    continue
                if not line:
                    if section:
                        tokens.append(section)
                        section = []
                    continue
                try:
                    key, value = line.split(":")
                    if value.rstrip().endswith("]"):
                        params: list[tuple[str, str]] = []
                        index = value.find("[")
                        if index == -1:
                            raise ValueError
                        parameter_text = value[index + 1:-1].replace(",", " ")
                        for parameter in parameter_text.split():
                            try:
                                p_kv = parameter.strip().split("=")
                                parameter_key, parameter_value = p_kv
                                params.append((parameter_key, parameter_value))
                            except ValueError:
                                raise ParseError(
                                    "Parameter is missing or" +
                                    "has too much '=' char",
                                    line_number,
                                ) from None
                        value = value[:index]
                    else:
                        params = []
                    section.append(
                        (
                            line_number,
                            (
                                key.strip(),
                                value.strip().split()
                            ),
                            params
                        )
                    )
                except ValueError:
                    raise ParseError("Line does not contain 'key: value'",
                                     line_number) from None
            if section:
                tokens.append(section)
        return tokens

    @staticmethod
    def validate(tokens: list["Parser.Tsection"]) -> MapData:
        """Validate a tokenized map file and return a MapData object."""
        drone_count: int | None = None
        start: str | None = None
        end: str | None = None
        zones: dict[str, Zone] = {}
        connections: list[Connection] = []
        connection_keys: set[frozenset[str]] = set()

        for section in tokens:
            for line_number, (key, values), parameters in section:
                if key not in Parser.sectionsTypes:
                    raise ParseError(f"Unknown section '{key}'", line_number)

                expected = Parser.sectionsTypes[key]
                value_types = [item for item in expected
                               if not isinstance(item, dict)]
                parameter_types: dict[str, Any] = {}
                for item in expected:
                    if isinstance(item, dict):
                        parameter_types = cast(dict[str, Any], item)
                if len(values) != len(value_types):
                    raise ParseError(
                        f"'{key}' expects {len(value_types)} value(s)",
                        line_number,
                    )

                converted_values: list[Any] = []
                try:
                    for value, value_type in zip(values, value_types):
                        converted_values.append(value_type(value))
                except (TypeError, ValueError):
                    raise ParseError(f"Invalid value for '{key}'",
                                     line_number) from None

                converted_parameters: dict[str, Any] = {}
                seen_parameters: set[str] = set()
                for parameter, value in parameters:
                    if parameter in seen_parameters:
                        raise ParseError(
                            f"Parameter '{parameter}' is duplicated",
                            line_number,
                        )
                    if parameter not in parameter_types:
                        raise ParseError(
                            f"Unknown parameter '{parameter}' for '{key}'",
                            line_number,
                        )
                    seen_parameters.add(parameter)
                    try:
                        converted_parameters[parameter] = parameter_types[
                            parameter
                        ](value)
                    except (TypeError, ValueError):
                        raise ParseError(
                            f"Invalid parameter '{parameter}'",
                            line_number,
                        ) from None

                if key == "nb_drones":
                    if drone_count is not None:
                        raise ParseError("'nb_drones' is duplicated",
                                         line_number)
                    drone_count = converted_values[0]
                elif key in ("start_hub", "end_hub", "hub"):
                    name, x, y = converted_values
                    if key == "start_hub":
                        if start is not None:
                            raise ParseError("'start_hub' is duplicated",
                                             line_number)
                        start = name
                    elif key == "end_hub":
                        if end is not None:
                            raise ParseError("'end_hub' is duplicated",
                                             line_number)
                        end = name
                    if name in zones:
                        raise ParseError(f"Hub '{name}' is duplicated",
                                         line_number)
                    zones[name] = Zone(
                        name,
                        x,
                        y,
                        zone_type=converted_parameters.get(
                            "zone", converted_parameters.get("type", "normal")
                        ),
                        color=converted_parameters.get("color", "none"),
                        capacity=converted_parameters.get(
                            "max_drones",
                            converted_parameters.get("capacity", 1)
                        ),
                    )
                else:
                    first, second = converted_values[0]
                    key_pair = frozenset((first, second))
                    if key_pair in connection_keys:
                        raise ParseError("Connection is duplicated",
                                         line_number)
                    connection_keys.add(key_pair)
                    connections.append(
                        Connection(
                            first,
                            second,
                            converted_parameters.get("max_link_capacity", 1),
                        )
                    )

        if drone_count is None:
            raise ParseError("Missing 'nb_drones'", 0)
        if start is None:
            raise ParseError("Missing 'start_hub'", 0)
        if end is None:
            raise ParseError("Missing 'end_hub'", 0)
        for connection in connections:
            if connection.first not in zones or connection.second not in zones:
                raise ParseError("Connection references an unknown hub", 0)

        return MapData(drone_count, start, end, zones, connections)

    @staticmethod
    def parse(map_file: str) -> MapData:
        """Parse a Fly-in map file into a validated MapData object."""
        tokens = Parser.tokenizer(map_file)
        return Parser.validate(tokens)

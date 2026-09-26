from parser.exceptions import ParseError
import os


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
    def tokenizer(map_file: str) -> list[Parser.Tsection]:
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
    def validate(tokens: list[Parser.Tsection]) -> None:
        """Validate a tokenized map file and return a MapData object."""
        raise NotImplementedError

    @staticmethod
    def parse(map_file: str) -> None:
        """Parse a Fly-in map file into a validated MapData object."""
        tokens = Parser.tokenizer(map_file)
        return Parser.validate(tokens)

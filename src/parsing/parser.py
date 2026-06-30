
from pathlib import Path

from lark import Lark

from src.parsing.transformer.stransformer import fly_transformer


class Parsing:
    def __init__(self):
        grammar_path = Path(__file__).resolve().parent / "grammars" / "general.lark"
        grammar = grammar_path.read_text(encoding="utf-8")
        self.parser = Lark(grammar, parser="lalr")
        self.transformer = fly_transformer()

    def parse_text(self, text):
        self.transformer.reset()
        tree = self.parser.parse(text)
        result = self.transformer.transform(tree)
        if hasattr(result, "children"):
            return result.children[0]
        return result

    def parse_file(self, path):
        return self.parse_text(Path(path).read_text(encoding="utf-8"))
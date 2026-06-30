from lark import Transformer


class fly_transformer(Transformer):
    def __init__(self):
        super().__init__()
        self.reset()

    def reset(self):
        self.nb_drones = None
        self.start_hub = None
        self.end_hub = None
        self.hubs = {}
        self.connections = []

    def _coerce(self, value):
        if hasattr(value, "value"):
            return value.value
        return value

    def _coerce_int(self, value):
        return int(self._coerce(value))

    def _coerce_value(self, value):
        if isinstance(value, (list, tuple)):
            return [self._coerce_value(item) for item in value]
        if isinstance(value, dict):
            return {key: self._coerce_value(item) for key, item in value.items()}
        if isinstance(value, str):
            try:
                return int(value)
            except ValueError:
                return value
        return value

    def nb_drones_field(self, items):
        self.nb_drones = self._coerce_int(items[0])
        return self.nb_drones

    def _extract_position(self, items):
        if len(items) > 1 and isinstance(items[1], (list, tuple)):
            return [self._coerce_int(items[1][0]), self._coerce_int(items[1][1])]
        if len(items) > 2:
            return [self._coerce_int(items[1]), self._coerce_int(items[2])]
        raise ValueError("Position data was not provided")

    def _extract_metadata(self, items):
        if len(items) > 2 and isinstance(items[2], dict):
            return self._coerce_value(items[2])
        if len(items) > 2 and isinstance(items[2], (list, tuple)) and items[2] and isinstance(items[2][0], tuple):
            return self._coerce_value(dict(items[2]))
        return {}

    def start_field(self, items):
        name = self._coerce(items[0])
        position = self._extract_position(items)
        metadata = self._extract_metadata(items)
        self.start_hub = name
        self.hubs[name] = {"kind": "start", "position": position, "metadata": metadata}
        return name

    def hub_field(self, items):
        name = self._coerce(items[0])
        position = self._extract_position(items)
        metadata = self._extract_metadata(items)
        self.hubs[name] = {"kind": "hub", "position": position, "metadata": metadata}
        return name

    def end_field(self, items):
        name = self._coerce(items[0])
        position = self._extract_position(items)
        metadata = self._extract_metadata(items)
        self.end_hub = name
        self.hubs[name] = {"kind": "end", "position": position, "metadata": metadata}
        return name

    def connection_field(self, items):
        source = self._coerce(items[0])
        target = self._coerce(items[1])
        metadata = items[2] if len(items) > 2 else {}
        self.connections.append({"from": source, "to": target, "metadata": metadata})
        return {"from": source, "to": target, "metadata": metadata}

    def place(self, items):
        return [self._coerce_int(items[0]), self._coerce_int(items[1])]

    def metadata(self, items):
        if not items:
            return {}
        return {key: self._coerce_value(value) for key, value in dict(items).items()}

    def single_param(self, items):
        name = self._coerce(items[0])
        value = self._coerce(items[2]) if len(items) == 3 else self._coerce(items[1])
        return name, value

    def value(self, items):
        if not items:
            return None
        return self._coerce(items[0])

    def fields(self, items):
        return {
            "nb_drones": self.nb_drones,
            "start_hub": self.start_hub,
            "end_hub": self.end_hub,
            "hubs": self.hubs,
            "connections": self.connections,
        }

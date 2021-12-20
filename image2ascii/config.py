import re
from pathlib import Path
from typing import Any, Dict, Generic, List, Optional, Type, TypeVar, Union

from image2ascii.color import BaseColorConverter
from image2ascii.output import ANSIFormatter, BaseFormatter
from image2ascii.utils import import_string

_T = TypeVar("_T")


class ConfigListener:
    def config_changed(self, key, value):
        pass


class BaseConfigValue(Generic[_T]):
    value: _T

    def __init__(self, type: Type, value: Any, null: bool = False):
        self.type, self.value, self.null = type, self.cast(value), null

    def cast(self, value: Any) -> _T:
        return value

    def set_value(self, value: Any) -> bool:
        """Returns "changed" bool"""
        value = self.cast(value)
        if value != self.value:
            self.value = value
            return True
        return False


class NullableConfigValue(BaseConfigValue[Optional[Any]]):
    def __init__(self, type: Type, value: Any):
        super().__init__(type, value, null=True)


class ConfigValue(BaseConfigValue[Any]):
    pass


class BoolValue(BaseConfigValue[bool]):
    def __init__(self, value: Any, null: bool = False):
        super().__init__(bool, value, null=null)

    def cast(self, value: Any) -> bool:
        """
        Emulates ConfigParser.getboolean():
        https://docs.python.org/3.8/library/configparser.html#configparser.ConfigParser.getboolean
        """
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            if value.lower() in ("1", "yes", "true", "on"):
                return True
            if value.lower() in ("0", "no", "false", "off"):
                return False
        raise ValueError(f"'{value}' is not a valid boolean value.")


class IntValue(BaseConfigValue[int]):
    def __init__(self, value: Any, null: bool = False):
        super().__init__(int, value, null=null)

    def cast(self, value: Any) -> int:
        return int(value)


class NullableIntValue(BaseConfigValue[Optional[int]]):
    def __init__(self, value: Any = None):
        super().__init__(int, value, null=True)

    def cast(self, value: Any):
        if value is None:
            return None
        return int(value)


class FloatValue(BaseConfigValue[float]):
    def __init__(self, value: Any, null: bool = False):
        super().__init__(float, value, null=null)

    def cast(self, value: Any) -> float:
        return float(value)


class TypeValue(BaseConfigValue[type]):
    def cast(self, value: Any) -> type:
        if isinstance(value, str):
            value = import_string(value)
        if not isinstance(value, type):
            raise ValueError(f"'{value}' is not a valid type.")
        return value


class NullableTypeValue(NullableConfigValue, TypeValue):
    def __init__(self, type: Type, value: Any = None):
        super().__init__(type, value)

    def cast(self, value: Any):
        if value is None:
            return None
        return super().cast(value)


class Config:
    _fields: Dict[str, BaseConfigValue]
    _listeners: List[ConfigListener]

    def __init__(self):
        self._fields = dict(
            color=BoolValue(False),
            crop=BoolValue(False),
            debug=BoolValue(False),
            fill_all=BoolValue(False),
            full_rgb=BoolValue(False),
            invert=BoolValue(False),
            negative=BoolValue(False),
            color_converter_class=NullableTypeValue(BaseColorConverter),
            formatter_class=TypeValue(BaseFormatter, ANSIFormatter),
            brightness=FloatValue(1.0),
            color_balance=FloatValue(1.0),
            contrast=FloatValue(1.0),
            max_height=NullableIntValue(),
            min_likeness=FloatValue(0.9),
            quality=IntValue(5),
            ratio=FloatValue(2.0),
            width=IntValue(80),
            max_original_size=IntValue(2000),
        )
        self._listeners = []

    def __getattr__(self, name: str):
        if not name.startswith("_") and name in self._fields:
            return self._fields[name].value
        raise AttributeError()

    def __setattr__(self, name: str, value: Any):
        if not name.startswith("_") and name in self._fields:
            if self._fields[name].set_value(value):
                for listener in self._listeners:
                    listener.config_changed(name, self._fields[name].value)
        else:
            super().__setattr__(name, value)

    def __eq__(self, __o: object) -> bool:
        field_names = self._fields.keys()
        if isinstance(__o, self.__class__):
            return all([self._fields[name].value == __o._fields[name].value for name in field_names])
        return super().__eq__(__o)

    def __getstate__(self):
        return {"_fields": self._fields}

    def add_listener(self, listener: ConfigListener):
        if not hasattr(self, "_listeners"):
            self._listeners = []
        self._listeners.append(listener)

    def get_formatter(self) -> BaseFormatter:
        return self.formatter_class(self.color_converter_class)

    def update(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    @classmethod
    def from_default_files(cls):
        local_conf_path = Path(__file__).parent / "defaults.conf"
        user_conf_path = Path.home() / ".image2ascii"
        conf_path = user_conf_path if user_conf_path.is_file() \
            else local_conf_path if local_conf_path.is_file() \
            else None
        if conf_path is not None:
            return cls.from_file(conf_path)
        return cls()

    @classmethod
    def from_file(cls, file: Union[str, Path]):
        """Raises error if file cannot be read"""
        new_config = cls()

        with open(file) as f:
            for row in f:
                try:
                    key, value = re.split(r" *= *", row.strip(), maxsplit=1)
                    setattr(new_config, key, value)
                except ValueError:
                    # Row did not contain a "=", or cast failed
                    pass

        return new_config

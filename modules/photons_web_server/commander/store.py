import typing as tp

from photons_app.formatter import MergedOptionStringFormatter


class CommandDecorator:
    def __init__(self, name: str):
        self.name = name

    def __call__(self, func: tp.Callable) -> tp.Callable:
        return func


class Command:
    pass


class Store:
    Command: type[Command] = Command

    def __init__(self, default_path="", formatter=MergedOptionStringFormatter):
        self.formatter = formatter
        self.default_path = default_path

    def injected(self, name: str) -> tp.Any:
        return None

    def command(self, name: str) -> CommandDecorator:
        return CommandDecorator(name)

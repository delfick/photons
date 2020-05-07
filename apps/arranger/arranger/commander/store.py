from photons_app.formatter import MergedOptionStringFormatter

from whirlwind.store import Store

store = Store(default_path="/v1/lifx/command", formatter=MergedOptionStringFormatter)


def load_commands():
    __import__("arranger.commander.commands")

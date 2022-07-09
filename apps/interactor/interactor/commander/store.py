from photons_web_server.commander.store import Store

store = Store(default_path="/v1/lifx/command")


def load_commands():
    __import__("interactor.commander.commands")

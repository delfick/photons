from photons_web_server.commander.store import Store

store = Store()


def load_commands():
    __import__("interactor.commander.commands")

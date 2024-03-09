import strcs
from photons_web_server import commander

reg = strcs.CreateRegister()
creator = reg.make_decorator()

store = commander.Store(strcs_register=reg)

Command = commander.Command


def load_commands():
    __import__("interactor.commander.commands")

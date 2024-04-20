import binascii

import strcs
from photons_web_server import commander

from .parts import PartsCommand
from .selector import Serial

reg = strcs.CreateRegister()
creator = reg.make_decorator()

store = commander.Store(strcs_register=reg)


@creator(Serial)
def create_serial(value: object, /) -> strcs.ConvertResponse[Serial]:
    if not isinstance(value, str):
        return None

    if len(value) != 12:
        raise ValueError("serial must be 12 characters long")

    try:
        binascii.unhexlify(value)
    except binascii.Error:
        raise ValueError("serial must be a hex value")

    return {"serial": value}


def load_commands():
    store.command(PartsCommand)

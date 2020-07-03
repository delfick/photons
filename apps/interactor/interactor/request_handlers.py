from whirlwind.request_handlers.command import ProgressMessageMaker, WSHandler, CommandHandler
from whirlwind.request_handlers.base import reprer, MessageFromExc

from photons_app import helpers as hp

from delfick_project.errors import DelfickError
from bitarray import bitarray
import binascii
import logging


class ProgressMessageMaker(ProgressMessageMaker):
    def do_log(self, body, message, info, **kwargs):
        command_name = "Command"
        if body and type(body) is dict and "command" in body:
            command_name = body["command"]

        if "error" in info:
            logging.getLogger(self.logger_name).error(hp.lc(f"{command_name} progress", **info))
        else:
            logging.getLogger(self.logger_name).info(hp.lc(f"{command_name} progress", **info))


def better_reprer(o):
    if type(o) is bitarray:
        return binascii.hexlify(o.tobytes()).decode()
    return reprer(o)


class MessageFromExc(MessageFromExc):
    def process(self, exc_type, exc, tb):
        if isinstance(exc, DelfickError):
            return {"status": 400, "error": exc.as_dict(), "error_code": exc.__class__.__name__}
        return super().process(exc_type, exc, tb)


class CommandHandler(CommandHandler):
    progress_maker = ProgressMessageMaker

    def initialize(self, *args, **kwargs):
        super().initialize(*args, **kwargs)
        self.reprer = better_reprer
        self.message_from_exc = MessageFromExc()


class WSHandler(WSHandler):
    progress_maker = ProgressMessageMaker

    def initialize(self, *args, **kwargs):
        super().initialize(*args, **kwargs)
        self.reprer = better_reprer
        self.message_from_exc = MessageFromExc()

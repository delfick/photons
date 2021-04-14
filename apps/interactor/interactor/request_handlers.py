from whirlwind.request_handlers.command import ProgressMessageMaker, WSHandler, CommandHandler
from whirlwind.request_handlers.base import reprer, MessageFromExc

from photons_app import helpers as hp

from delfick_project.errors import DelfickError
from bitarray import bitarray
import binascii
import logging

log = logging.getLogger("interactor.request_handlers")


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


class BetterLogMessages:
    @hp.memoized_property
    def lc(self):
        from interactor.server import REQUEST_IDENTIFIER_HEADER

        return hp.lc.using(request_id=self.request.headers[REQUEST_IDENTIFIER_HEADER])

    def see_returned_exception(self, exc_typ, exc, tb):
        if exc is None:
            return

        log.error(self.lc("Error during request", error=exc), exc_info=(exc_typ, exc, tb))

    def log_json_error(self, body, error):
        if error is None:
            return

        log.error(self.lc("Failed to parse json", error=error, body=body))

    def handle_message_done_error(self, error, msg, final, message_key, exc_info):
        if error is None:
            return

        log.error(
            self.lc("Failed to finish request", error=error),
            exc_info=(type(error), error, error.__traceback__),
        )

    def handle_request_done_exception(self, error):
        if error is None:
            return

        log.error(
            self.lc("Error handling request", error=error),
            exc_info=(type(error), error, error.__traceback__),
        )


class CommandHandler(BetterLogMessages, CommandHandler):
    progress_maker = ProgressMessageMaker

    def initialize(self, *args, **kwargs):
        super().initialize(*args, **kwargs)
        self.reprer = better_reprer
        self.message_from_exc = MessageFromExc(see_exception=self.see_returned_exception)


class WSHandler(BetterLogMessages, WSHandler):
    progress_maker = ProgressMessageMaker

    def initialize(self, *args, **kwargs):
        super().initialize(*args, **kwargs)
        self.reprer = better_reprer
        self.message_from_exc = MessageFromExc(see_exception=self.see_returned_exception)

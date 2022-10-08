import asyncio
import binascii
import inspect
import logging
import types
import typing as tp

from attrs import asdict, define
from bitarray import bitarray
from delfick_project.errors import DelfickError
from delfick_project.logging import LogContext

log = logging.getLogger("photons_web_server.commander.messages")

ExcInfo: tp.TypeAlias = tp.Union[
    None,
    bool,
    tp.Tuple[None, None, None],
    tp.Tuple[tp.Type[BaseException], BaseException, types.TracebackType | None],
]

ExcTypO: tp.TypeAlias = tp.Union[tp.Type[BaseException], None]
ExcO: tp.TypeAlias = BaseException | None
TBO: tp.TypeAlias = types.TracebackType | None


class WithAsDict(tp.Protocol):
    def as_dict(self) -> dict: ...


class TReprer(tp.Protocol):
    def __call__(self, o: tp.Any) -> str: ...


def reprer(o: tp.Any) -> str:
    if type(o) is bitarray:
        return binascii.hexlify(o.tobytes()).decode()
    elif type(o) is bytes:
        return binascii.hexlify(o).decode()
    else:
        return repr(o)


class ExceptionSeer(tp.Protocol):
    def __call__(self, exc_type: ExcTypO, exc: ExcO, tb: TBO) -> None: ...


@define(eq=True, str=False, auto_exc=False)
class ErrorMessage(Exception):
    status: int
    error: dict | str
    error_code: str


class TMessageFromExc(tp.Protocol):
    def __init__(
        self,
        *,
        lc: LogContext,
        logger_name: str,
        log_exceptions=True,
        see_exception: ExceptionSeer | None = None,
    ): ...

    def __call__(self, exc_type: ExcTypO, exc: ExcO, tb: TBO) -> ErrorMessage: ...


class MessageFromExc:
    def __init__(
        self,
        *,
        lc: LogContext,
        logger_name: str,
        log_exceptions=True,
        see_exception: ExceptionSeer | None = None,
    ):
        self.lc = lc
        self.see_exception = see_exception
        self.log_exceptions = log_exceptions

        self.log = logging.getLogger(logger_name)

    def process(self, exc_type: ExcTypO, exc: ExcO, tb: TBO) -> ErrorMessage:
        if self.see_exception:
            self.see_exception(exc_type, exc, tb)

        if isinstance(exc, DelfickError):
            return ErrorMessage(status=400, error=exc.as_dict(), error_code=exc.__class__.__name__)

        elif exc_type is asyncio.CancelledError:
            return ErrorMessage(
                status=500, error="Request was cancelled", error_code="RequestCancelled"
            )

        elif exc and exc_type:
            if self.see_exception is None and self.log_exceptions:
                self.log.error(self.lc(str(exc)), exc_info=(exc_type, exc, tb))

        return ErrorMessage(
            status=500, error="Internal Server Error", error_code="InternalServerError"
        )

    __call__ = process


def get_logger_name(stack_level: int = 0, method: tp.Callable | None = None) -> str:
    mod = None
    if method is None:
        try:
            stack = inspect.stack()
            frm = stack[1 + stack_level]
            mod = inspect.getmodule(frm[0])
        except:
            pass
    else:
        parts = method.__qualname__.split(".")
        kls = ""
        if len(parts) >= 2:
            kls = parts[-2]
        return f"{method.__module__}:{kls}:{method.__name__}"

    if mod and hasattr(mod, "__name__"):
        return mod.__name__
    else:
        return "photons_web_server.command.messages"


def get_logger(stack_level: int = 0, method: tp.Callable | None = None) -> logging.Logger:
    return logging.getLogger(get_logger_name(stack_level + 1, method))


class TProgressMessageMaker(tp.Protocol):
    def __init__(self, *, lc: LogContext, logger_name: str): ...

    def __call__(self, body: tp.Any, message: tp.Any, do_log=True, **kwargs) -> dict: ...


class ProgressMessageMaker:
    def __init__(self, *, lc: LogContext, logger_name: str):
        self.lc = lc
        self.logger_name = logger_name
        self.log = logging.getLogger(self.logger_name)

    def __call__(self, body: tp.Any, message: tp.Any, do_log=True, **kwargs) -> dict:
        info = self.make_info(body, message, **kwargs)
        if do_log:
            self.do_log(body, message, info, **kwargs)
        return info

    def make_info(self, body: tp.Any, message: tp.Any, **kwargs) -> dict:
        info: dict[str, object] = {}

        if isinstance(message, Exception):
            info["error_code"] = message.__class__.__name__
            if hasattr(message, "as_dict"):
                info["error"] = tp.cast(WithAsDict, message).as_dict()
            elif hasattr(message, "__attrs_attrs__"):
                info["error"] = asdict(message)
            else:
                info["error"] = str(message)
        elif message is None:
            info["done"] = True
        elif type(message) is dict:
            info.update(message)
        else:
            info["info"] = message

        info.update(kwargs)
        return info

    def do_log(self, body: tp.Any, message: tp.Any, info: object, **kwargs) -> None:
        if isinstance(info, dict):
            if "error" in info:
                self.log.error(self.lc("progress", **info))
            else:
                self.log.info(self.lc("progress", **info))
        else:
            self.log.info(self.lc("progress", info=info))

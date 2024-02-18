import typing as tp

from sanic.response import BaseHTTPResponse as Response

Route = tp.Callable[..., Response | None]

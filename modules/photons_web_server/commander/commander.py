from sanic import Websocket, text
from sanic.request import Request
from sanic.response import HTTPResponse
from strcs import Meta

from .messages import MessageFromExc, ProgressMessageMaker, reprer
from .store import Store


class Commander:
    def __init__(
        self,
        store: Store,
        meta: Meta,
        reprer=reprer,
        message_from_exc=MessageFromExc,
        progress_message_maker=ProgressMessageMaker,
    ):
        self.meta = meta
        self.store = store
        self.reprer = reprer
        self.message_from_exc = message_from_exc
        self.progress_message_maker = progress_message_maker

    def http_handler(self, request: Request) -> HTTPResponse:
        return text("OK")

    async def ws_handler(self, request: Request, ws: Websocket, first: dict):
        pass

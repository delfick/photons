# coding: spec

from interactor.errors import InteractorError

from photons_app.formatter import MergedOptionStringFormatter

from delfick_project.norms import dictobj, sb
from whirlwind.store import Store
import random
import pytest

store = Store(default_path="/v1/lifx/command", formatter=MergedOptionStringFormatter)

serial_field = dictobj.Field(sb.string_spec, wrapper=sb.required)


@store.command("test_done_progress")
class TDoneProgress(store.Command):
    serial = serial_field
    progress_cb = store.injected("progress_cb")

    async def execute(self):
        self.progress_cb(None, serial=self.serial)
        return {"serial": self.serial}


@store.command("test_no_error")
class TNoError(store.Command):
    serial = serial_field
    progress_cb = store.injected("progress_cb")

    async def execute(self):
        self.progress_cb("hello", serial=self.serial)
        self.progress_cb("there")
        return {"serial": self.serial}


@store.command("test_error")
class TError(store.Command):
    serial = serial_field
    progress_cb = store.injected("progress_cb")

    async def execute(self):
        self.progress_cb(Exception("Nope"), serial=self.serial)
        self.progress_cb(ValueError("Yeap"))

        class Problem(InteractorError):
            desc = "a problem"

        self.progress_cb(Problem("wat", one=1), serial=self.serial)
        return {"serial": self.serial}


@pytest.fixture(scope="module")
async def server(server_wrapper):
    async with server_wrapper(store) as server:
        yield server


@pytest.fixture(autouse=True)
async def wrap_tests(server):
    async with server.per_test():
        yield


describe "Commands":

    def command(self, command):
        serial = "d073d5{:06d}".format(random.randrange(1, 9999))
        cmd = {"command": command, "args": {"serial": serial}}
        return cmd, serial

    async it "has progress cb functionality for http", server:
        command, serial = self.command("test_no_error")
        await server.assertCommand(
            "/v1/lifx/command", command, status=200, json_output={"serial": serial}
        )

        command, serial = self.command("test_error")
        await server.assertCommand(
            "/v1/lifx/command", command, status=200, json_output={"serial": serial}
        )

        command, serial = self.command("test_done_progress")
        await server.assertCommand(
            "/v1/lifx/command", command, status=200, json_output={"serial": serial}
        )

    async it "has progress cb functionality for websockets", server:
        async with server.ws_stream() as stream:

            # Done progress
            command, serial = self.command("test_done_progress")
            await stream.create("/v1/lifx/command", command)
            await stream.check_reply({"progress": {"done": True, "serial": serial}})
            await stream.check_reply({"serial": serial})

            # No error
            command, serial = self.command("test_no_error")
            await stream.create("/v1/lifx/command", command)
            await stream.check_reply({"progress": {"info": "hello", "serial": serial}})
            await stream.check_reply({"progress": {"info": "there"}})
            await stream.check_reply({"serial": serial})

            # With error
            command, serial = self.command("test_error")
            await stream.create("/v1/lifx/command", command)
            await stream.check_reply(
                {"progress": {"error": "Nope", "error_code": "Exception", "serial": serial}}
            )
            await stream.check_reply({"progress": {"error": "Yeap", "error_code": "ValueError"}})
            await stream.check_reply(
                {
                    "progress": {
                        "error": {"message": "a problem. wat", "one": 1},
                        "error_code": "Problem",
                        "serial": serial,
                    }
                }
            )
            await stream.check_reply({"serial": serial})

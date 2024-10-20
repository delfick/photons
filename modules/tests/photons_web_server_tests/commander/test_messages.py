# coding: spec
import asyncio
import inspect
import json
import logging
import sys
import types
import typing as tp
from unittest import mock

import pytest
from attrs import define
from bitarray import bitarray
from delfick_project.errors import DelfickError
from photons_app import helpers as hp
from photons_web_server.commander.messages import (
    ErrorMessage,
    MessageFromExc,
    ProgressMessageMaker,
    catch_ErrorMessage,
    get_logger,
    get_logger_name,
    reprer,
)
from sanic.exceptions import SanicException
from sanic.request import Request
from sanic.response import BaseHTTPResponse as Response

describe "reprer":
    it "turns bitarray into hex":
        b = bitarray(endian="little")
        b.frombytes(b"aa0022")
        assert reprer(b) == "616130303232"

    it "turns bytes into hex":
        b = bitarray(endian="little")
        b.frombytes(b"aa0022")
        assert reprer(b.tobytes()) == "616130303232"

    it "reprs everything else":

        class Thing:
            def __repr__(self):
                return "This thing is the best"

        assert reprer(Thing()) == "This thing is the best"
        assert reprer("wat") == "'wat'"
        assert reprer(None) == "None"

describe "catch_ErrorMessage":
    it "returns a sanic json response":
        exc = ErrorMessage(error_code="Bad", error="very bad", status=418)
        request = mock.Mock(name="request")
        res = catch_ErrorMessage(tp.cast(Request, request), exc)
        assert isinstance(res, Response)
        assert res.status == 418
        assert res.content_type == "application/json"
        assert res.body == b'{"error_code":"Bad","error":"very bad"}'

    it "defaults to repr":

        class Blah: ...

        blah = Blah()

        with pytest.raises(TypeError):
            json.dumps(blah)

        exc = ErrorMessage(error_code="Bad", error=blah, status=418)
        request = mock.Mock(name="Request")
        res = catch_ErrorMessage(tp.cast(request, request), exc)
        assert isinstance(res, Response)
        assert res.status == 418
        assert res.content_type == "application/json"
        assert json.loads(res.body.decode()) == {"error_code": "Bad", "error": repr(blah)}

describe "MessageFromExc":
    it "re raises SanicExceptions":
        with pytest.raises(SanicException):
            MessageFromExc(lc=hp.lc.using(), logger_name="logs")(
                SanicException, SanicException("wat"), None
            )

    it "can see SanicExceptions":
        try:
            raise Exception()
        except:
            tb = sys.exc_info()[2]

        see_exception = mock.Mock(name="see_exception")
        exc = SanicException("NOPE")
        with pytest.raises(SanicException):
            MessageFromExc(lc=hp.lc.using(), logger_name="logs", see_exception=see_exception)(
                type(exc), exc, tb
            )
        see_exception.assert_called_once_with(type(exc), exc, tb)

    it "does not log DelfickError or cancelledError", caplog:
        exc1 = asyncio.CancelledError()
        exc2 = DelfickError("wat")

        for exc in (exc1, exc2):
            res = MessageFromExc(lc=hp.lc.using(), logger_name="logs")(type(exc), exc, None)
            assert isinstance(res, ErrorMessage)

        assert caplog.text == ""

    it "does not log other exceptions if told not to", caplog:
        exc = ValueError("asdf")
        MessageFromExc(lc=hp.lc.using(), logger_name="logs", log_exceptions=False)(
            type(exc), exc, None
        )
        assert caplog.text == ""

        MessageFromExc(lc=hp.lc.using(), logger_name="logs", log_exceptions=True)(
            type(exc), exc, None
        )
        assert "asdf" in caplog.text

    it "turns DelfickError into a 400 error message":

        class MyError(DelfickError):
            desc = "hi"

        exc = MyError("wat", one=5)
        assert MessageFromExc(lc=hp.lc.using(), logger_name="logs")(
            type(exc), exc, None
        ) == ErrorMessage(status=400, error={"one": 5, "message": "hi. wat"}, error_code="MyError")

    it "turns cancelled error into request cancelled":
        exc = asyncio.CancelledError()
        assert MessageFromExc(lc=hp.lc.using(), logger_name="logs")(
            type(exc), exc, None
        ) == ErrorMessage(status=500, error="Request was cancelled", error_code="RequestCancelled")

    it "turns everything else into internal server errors":
        exc = ValueError("asdf")
        assert MessageFromExc(lc=hp.lc.using(), logger_name="logs")(
            type(exc), exc, None
        ) == ErrorMessage(
            status=500, error="Internal Server Error", error_code="InternalServerError"
        )

    it "has the ability to modify the error information":

        class MFE(MessageFromExc):
            def modify_error_dict(
                self,
                exc_type: type[Exception],
                exc: Exception,
                tb: types.TracebackType,
                dct: dict[str, object],
            ) -> dict[str, object]:
                return {"wrapped": dct}

        class MyError(DelfickError):
            desc = "hi"

        exc = MyError("hi", one=5)
        assert MFE(lc=hp.lc.using(), logger_name="logs")(type(exc), exc, None) == ErrorMessage(
            status=400, error={"wrapped": {"one": 5, "message": "hi. hi"}}, error_code="MyError"
        )


describe "get_logger_name":
    it "defaults to getting from previous frame", call_from_conftest:
        assert get_logger_name() == "photons_web_server_tests.commander.test_messages"

        assert get_logger_name(stack_level=1) == "alt_pytest_asyncio.machinery"

        name = call_from_conftest(get_logger_name)
        assert name == "photons_web_server_tests.conftest"

        # 2 because I'm calling a function that is defined in the function I'm calling it from
        name = call_from_conftest(lambda: get_logger_name(stack_level=2))
        assert name == "photons_web_server_tests.commander.test_messages"

        # Not possible to go too far
        assert len(inspect.stack()) < 100
        name = get_logger_name(stack_level=100)
        assert name == "photons_web_server.command.messages"

    it "can return based on a method":

        class Thing:
            def my_method(self):
                pass

        name = get_logger_name(method=Thing.my_method)
        assert name == "photons_web_server_tests.commander.test_messages:Thing:my_method"

        def my_other_method(self):
            pass

        name = get_logger_name(method=my_other_method)
        assert name == "photons_web_server_tests.commander.test_messages:<locals>:my_other_method"

describe "get_logger":
    it "gets a logger instance using get_logger_name for the name":
        get_logger_name = mock.Mock(name="get_logger_name")
        with mock.patch("photons_web_server.commander.messages.get_logger_name", get_logger_name):
            get_logger_name.return_value = "abolishlogging"
            log = get_logger()
            assert isinstance(log, logging.Logger)
            assert log.name == "abolishlogging"
            get_logger_name.assert_called_once_with(1, None)

            get_logger_name.reset_mock()
            get_logger_name.return_value = "growforests"
            log = get_logger(stack_level=3)
            assert isinstance(log, logging.Logger)
            assert log.name == "growforests"
            get_logger_name.assert_called_once_with(4, None)

            get_logger_name.reset_mock()
            get_logger_name.return_value = "freshair"
            method = mock.Mock(name="method")
            log = get_logger(method=method)
            assert isinstance(log, logging.Logger)
            assert log.name == "freshair"
            get_logger_name.assert_called_once_with(1, method)

describe "ProgressMessageMaker":

    @pytest.fixture
    def maker(self) -> ProgressMessageMaker:
        return ProgressMessageMaker(
            lc=hp.lc.using(), logger_name="photons_web_server_tests.commander.test_messages"
        )

    async it "calls do_log if that is asked for", maker: ProgressMessageMaker:
        message = mock.Mock(name="message")
        one = mock.Mock(name="one")
        two = mock.Mock(name="two")

        do_log = pytest.helpers.AsyncMock(name="do_log")

        info = pytest.helpers.AsyncMock(name="info")
        make_info = pytest.helpers.AsyncMock(name="make_info", return_value=info)

        with mock.patch.multiple(maker, do_log=do_log, make_info=make_info):
            assert await maker(message, do_log=True, three=one, four=two) is info

        do_log.assert_called_once_with(message, info, three=one, four=two)

    async it "does not call do_log if that is not asked for", maker: ProgressMessageMaker:
        message = mock.Mock(name="message")
        one = mock.Mock(name="one")
        two = mock.Mock(name="two")

        do_log = mock.Mock(name="do_log")

        info = pytest.helpers.AsyncMock(name="info")
        make_info = pytest.helpers.AsyncMock(name="make_info", return_value=info)

        with mock.patch.multiple(maker, do_log=do_log, make_info=make_info):
            assert await maker(message, do_log=False, three=one, four=two) is info

        do_log.assert_not_called()

    describe "make_info":

        async it "gathers information from errors", maker: ProgressMessageMaker:

            class MyDelfickError(DelfickError):
                desc = "I am the worst"

            @define
            class MyAttrsError(Exception):
                one: int
                two: str

            exc1 = MyDelfickError("nup", one=40)
            exc2 = MyAttrsError(one=22, two="fasdf")
            exc3 = ValueError("nup")

            assert await maker(exc1) == {
                "error_code": "MyDelfickError",
                "error": {"message": "I am the worst. nup", "one": 40},
            }
            assert await maker(exc2) == {
                "error_code": "MyAttrsError",
                "error": {"one": 22, "two": "fasdf"},
            }
            assert await maker(exc3) == {
                "error_code": "ValueError",
                "error": "nup",
            }

            assert await maker(exc2, seven=7) == {
                "error_code": "MyAttrsError",
                "error": {"one": 22, "two": "fasdf"},
                "seven": 7,
            }

        async it "turns None into done True", maker: ProgressMessageMaker:
            assert await maker(None) == {"done": True}
            assert await maker(None, six=6) == {"done": True, "six": 6}

        async it "Uses information if the message is a dictionary", maker: ProgressMessageMaker:
            message = {"one": 1, "two": 2}
            info = await maker(message)
            assert info == {"one": 1, "two": 2}
            info["three"] = 3
            assert info == {"one": 1, "two": 2, "three": 3}
            assert message == {"one": 1, "two": 2}

            assert await maker(message, four=4) == {"one": 1, "two": 2, "four": 4}
            assert message == {"one": 1, "two": 2}

        async it "uses message as an info value otherwise", maker: ProgressMessageMaker:
            message = mock.Mock(name="message")
            assert await maker(message) == {"info": message}
            assert await maker(message, five=5) == {"info": message, "five": 5}

    describe "do_log":

        @pytest.fixture
        def message(self) -> mock.Mock:
            return mock.Mock(name="message")

        def assertLastRecord(self, caplog, expected_level: str, expected_msg: dict):
            assert len(caplog.records) == 1
            rec = caplog.records.pop()
            assert rec.msg == expected_msg
            assert rec.levelname == expected_level

        async it "Logs info if no error key", caplog, message: mock.Mock, maker: ProgressMessageMaker:
            await maker.do_log(message, {"done": True})
            self.assertLastRecord(caplog, "INFO", {"msg": "progress", "done": True})

            await maker.do_log(message, {"one": True})
            self.assertLastRecord(caplog, "INFO", {"msg": "progress", "one": True})

        async it "Logs info as key if not a dict", caplog, message: mock.Mock, maker: ProgressMessageMaker:

            class Thing:
                pass

            thing = Thing()
            await maker.do_log(message, thing)
            self.assertLastRecord(caplog, "INFO", {"msg": "progress", "info": thing})

        async it "logs an error if error key is in info", caplog, message: mock.Mock, maker: ProgressMessageMaker:
            await maker.do_log(message, {"error": "bad", "things": "happen"})
            self.assertLastRecord(
                caplog, "ERROR", {"msg": "progress", "error": "bad", "things": "happen"}
            )

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

class TestReprer:
    def test_it_turns_bitarray_into_hex(self):
        b = bitarray(endian="little")
        b.frombytes(b"aa0022")
        assert reprer(b) == "616130303232"

    def test_it_turns_bytes_into_hex(self):
        b = bitarray(endian="little")
        b.frombytes(b"aa0022")
        assert reprer(b.tobytes()) == "616130303232"

    def test_it_reprs_everything_else(self):

        class Thing:
            def __repr__(self):
                return "This thing is the best"

        assert reprer(Thing()) == "This thing is the best"
        assert reprer("wat") == "'wat'"
        assert reprer(None) == "None"

class TestCatchErrorMessage:
    def test_it_returns_a_sanic_json_response(self):
        exc = ErrorMessage(error_code="Bad", error="very bad", status=418)
        request = mock.Mock(name="request")
        res = catch_ErrorMessage(tp.cast(Request, request), exc)
        assert isinstance(res, Response)
        assert res.status == 418
        assert res.content_type == "application/json"
        assert res.body == b'{"error_code":"Bad","error":"very bad"}'

    def test_it_defaults_to_repr(self):

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

class TestMessageFromExc:
    def test_it_re_raises_SanicExceptions(self):
        with pytest.raises(SanicException):
            MessageFromExc(lc=hp.lc.using(), logger_name="logs")(
                SanicException, SanicException("wat"), None
            )

    def test_it_can_see_SanicExceptions(self):
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

    def test_it_does_not_log_DelfickError_or_cancelledError(self, caplog):
        exc1 = asyncio.CancelledError()
        exc2 = DelfickError("wat")

        for exc in (exc1, exc2):
            res = MessageFromExc(lc=hp.lc.using(), logger_name="logs")(type(exc), exc, None)
            assert isinstance(res, ErrorMessage)

        assert caplog.text == ""

    def test_it_does_not_log_other_exceptions_if_told_not_to(self, caplog):
        exc = ValueError("asdf")
        MessageFromExc(lc=hp.lc.using(), logger_name="logs", log_exceptions=False)(
            type(exc), exc, None
        )
        assert caplog.text == ""

        MessageFromExc(lc=hp.lc.using(), logger_name="logs", log_exceptions=True)(
            type(exc), exc, None
        )
        assert "asdf" in caplog.text

    def test_it_turns_DelfickError_into_a_400_error_message(self):

        class MyError(DelfickError):
            desc = "hi"

        exc = MyError("wat", one=5)
        assert MessageFromExc(lc=hp.lc.using(), logger_name="logs")(
            type(exc), exc, None
        ) == ErrorMessage(status=400, error={"one": 5, "message": "hi. wat"}, error_code="MyError")

    def test_it_turns_cancelled_error_into_request_cancelled(self):
        exc = asyncio.CancelledError()
        assert MessageFromExc(lc=hp.lc.using(), logger_name="logs")(
            type(exc), exc, None
        ) == ErrorMessage(status=500, error="Request was cancelled", error_code="RequestCancelled")

    def test_it_turns_everything_else_into_internal_server_errors(self):
        exc = ValueError("asdf")
        assert MessageFromExc(lc=hp.lc.using(), logger_name="logs")(
            type(exc), exc, None
        ) == ErrorMessage(
            status=500, error="Internal Server Error", error_code="InternalServerError"
        )

    def test_it_has_the_ability_to_modify_the_error_information(self):

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


class TestGetLoggerName:
    def test_it_defaults_to_getting_from_previous_frame(self, call_from_conftest):
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

    def test_it_can_return_based_on_a_method(self):

        class Thing:
            def my_method(self):
                pass

        name = get_logger_name(method=Thing.my_method)
        assert name == "photons_web_server_tests.commander.test_messages:Thing:my_method"

        def my_other_method(self):
            pass

        name = get_logger_name(method=my_other_method)
        assert name == "photons_web_server_tests.commander.test_messages:<locals>:my_other_method"

class TestGetLogger:
    def test_it_gets_a_logger_instance_using_get_logger_name_for_the_name(self):
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

class TestProgressMessageMaker:

    @pytest.fixture
    def maker(self) -> ProgressMessageMaker:
        return ProgressMessageMaker(
            lc=hp.lc.using(), logger_name="photons_web_server_tests.commander.test_messages"
        )

    async def test_it_calls_do_log_if_that_is_asked_for(self, maker: ProgressMessageMaker):
        message = mock.Mock(name="message")
        one = mock.Mock(name="one")
        two = mock.Mock(name="two")

        do_log = pytest.helpers.AsyncMock(name="do_log")

        info = pytest.helpers.AsyncMock(name="info")
        make_info = pytest.helpers.AsyncMock(name="make_info", return_value=info)

        with mock.patch.multiple(maker, do_log=do_log, make_info=make_info):
            assert await maker(message, do_log=True, three=one, four=two) is info

        do_log.assert_called_once_with(message, info, three=one, four=two)

    async def test_it_does_not_call_do_log_if_that_is_not_asked_for(self, maker: ProgressMessageMaker):
        message = mock.Mock(name="message")
        one = mock.Mock(name="one")
        two = mock.Mock(name="two")

        do_log = mock.Mock(name="do_log")

        info = pytest.helpers.AsyncMock(name="info")
        make_info = pytest.helpers.AsyncMock(name="make_info", return_value=info)

        with mock.patch.multiple(maker, do_log=do_log, make_info=make_info):
            assert await maker(message, do_log=False, three=one, four=two) is info

        do_log.assert_not_called()

    class TestMakeInfo:

        async def test_it_gathers_information_from_errors(self, maker: ProgressMessageMaker):

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

        async def test_it_turns_None_into_done_True(self, maker: ProgressMessageMaker):
            assert await maker(None) == {"done": True}
            assert await maker(None, six=6) == {"done": True, "six": 6}

        async def test_it_Uses_information_if_the_message_is_a_dictionary(self, maker: ProgressMessageMaker):
            message = {"one": 1, "two": 2}
            info = await maker(message)
            assert info == {"one": 1, "two": 2}
            info["three"] = 3
            assert info == {"one": 1, "two": 2, "three": 3}
            assert message == {"one": 1, "two": 2}

            assert await maker(message, four=4) == {"one": 1, "two": 2, "four": 4}
            assert message == {"one": 1, "two": 2}

        async def test_it_uses_message_as_an_info_value_otherwise(self, maker: ProgressMessageMaker):
            message = mock.Mock(name="message")
            assert await maker(message) == {"info": message}
            assert await maker(message, five=5) == {"info": message, "five": 5}

    class TestDoLog:

        @pytest.fixture
        def message(self) -> mock.Mock:
            return mock.Mock(name="message")

        def assertLastRecord(self, caplog, expected_level: str, expected_msg: dict):
            assert len(caplog.records) == 1
            rec = caplog.records.pop()
            assert rec.msg == expected_msg
            assert rec.levelname == expected_level

        async def test_it_Logs_info_if_no_error_key(self, caplog, message: mock.Mock, maker: ProgressMessageMaker):
            await maker.do_log(message, {"done": True})
            self.assertLastRecord(caplog, "INFO", {"msg": "progress", "done": True})

            await maker.do_log(message, {"one": True})
            self.assertLastRecord(caplog, "INFO", {"msg": "progress", "one": True})

        async def test_it_Logs_info_as_key_if_not_a_dict(self, caplog, message: mock.Mock, maker: ProgressMessageMaker):

            class Thing:
                pass

            thing = Thing()
            await maker.do_log(message, thing)
            self.assertLastRecord(caplog, "INFO", {"msg": "progress", "info": thing})

        async def test_it_logs_an_error_if_error_key_is_in_info(self, caplog, message: mock.Mock, maker: ProgressMessageMaker):
            await maker.do_log(message, {"error": "bad", "things": "happen"})
            self.assertLastRecord(
                caplog, "ERROR", {"msg": "progress", "error": "bad", "things": "happen"}
            )

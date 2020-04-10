# coding: spec

from photons_control.device_finder import Searcher
from photons_transport.fake import FakeDevice

from photons_app import helpers as hp

from unittest import mock
import asyncio
import pytest

describe "Searcher":
    it "takes in a sender":
        sender = mock.Mock(name="sender")
        searcher = Searcher(sender)

        assert isinstance(searcher.search_fut, hp.ResettableFuture)
        assert searcher.search_fut.done()

        assert searcher.sender is sender

    describe "getting serials":
        async it "can get serials", memory_devices_runner:
            serials = ["d073d5000001", "d073d5000002", "d073d5000003"]
            devices = [FakeDevice(serial, []) for serial in serials]

            async with memory_devices_runner(devices) as runner:
                searcher = Searcher(runner.sender)
                assert (await searcher._serials()) == serials

    describe "discover":

        @pytest.fixture()
        def searcher(self):
            return Searcher(mock.NonCallableMock(name="sender", spec=[]))

        async it "does a search if the search_fut is resolved as None", searcher:
            serials = mock.Mock(name="serials")

            async def _serials():
                assert not searcher.search_fut.done()
                return serials

            assert searcher.search_fut.result() is None

            with mock.patch.object(searcher, "_serials", _serials):
                assert (await searcher.discover()) is serials

            assert searcher.search_fut.result() is serials

        async it "does not do a search if one is already in progress", searcher:
            called = []
            serials = mock.Mock(name="serials")
            continue_event = asyncio.Future()

            async def _serials():
                called.append("get_serials")
                await continue_event
                assert not searcher.search_fut.done()
                return serials

            streamer = hp.ResultStreamer(asyncio.Future())
            await streamer.add_coroutine(searcher.discover())
            await streamer.add_coroutine(searcher.discover())
            streamer.no_more_work()
            asyncio.get_event_loop().call_soon(continue_event.set_result, True)

            with mock.patch.object(searcher, "_serials", _serials):
                async with streamer:
                    async for result in streamer:
                        assert result.value is serials

            assert called == ["get_serials"]

        async it "does not search at all if the search_fut is already resolved", searcher:
            serials = mock.Mock(name="serials")
            searcher.search_fut.reset()
            searcher.search_fut.set_result(serials)

            _serials = mock.Mock(name="_serials")
            with mock.patch.object(searcher, "_serials", _serials):
                assert (await searcher.discover()) is serials

            _serials.assert_not_called()

        async it "ignores existing value if told to refresh", searcher:
            serials = mock.Mock(name="serials")
            serials2 = mock.Mock(name="serials2")

            searcher.search_fut.reset()
            searcher.search_fut.set_result(serials)

            async def _serials():
                assert not searcher.search_fut.done()
                return serials2

            with mock.patch.object(searcher, "_serials", _serials):
                assert (await searcher.discover(refresh=True)) is serials2

            assert searcher.search_fut.result() is serials2

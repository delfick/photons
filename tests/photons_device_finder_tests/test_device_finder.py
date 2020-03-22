# coding: spec

from photons_device_finder import DeviceFinder, Filter

from photons_app.errors import PhotonsAppError, FoundNoDevices
from photons_app.special import SpecialReference

from delfick_project.errors_pytest import assertRaises
from unittest import mock
import binascii
import pytest

describe "DeviceFinder":
    async it "makes itself a loops and sets daemon to False":
        target = mock.Mock(name="target")
        loops = mock.Mock(name="loops")
        service_interval = mock.Mock(name="service_interval")
        information_interval = mock.Mock(name="information_interval")
        repeat_spread = mock.Mock(name="repeat_spread")

        DeviceFinderLoops = mock.Mock(name="DeviceFinderLoops", return_value=loops)

        with mock.patch("photons_device_finder.DeviceFinderLoops", DeviceFinderLoops):
            finder = DeviceFinder(
                target,
                service_search_interval=service_interval,
                information_search_interval=information_interval,
                repeat_spread=repeat_spread,
            )

        assert finder.loops is loops
        assert finder.daemon == False

        DeviceFinderLoops.assert_called_once_with(
            target,
            service_search_interval=service_interval,
            information_search_interval=information_interval,
            repeat_spread=repeat_spread,
        )

    describe "functionality":

        @pytest.fixture()
        def loops(self):
            return mock.Mock(name="loops")

        @pytest.fixture()
        def finder(self, loops):
            target = mock.Mock(name="target")
            interval = mock.Mock(name="interval")
            DeviceFinderLoops = mock.Mock(name="DeviceFinderLoops", return_value=loops)

            with mock.patch("photons_device_finder.DeviceFinderLoops", DeviceFinderLoops):
                yield DeviceFinder(target, service_search_interval=interval)

        describe "start":
            async it "starts the loops and sets daemon to True", loops, finder:
                start = pytest.helpers.AsyncMock(name="start")
                loops.start = start

                quickstart = mock.Mock(name="quickstrt")
                await finder.start(quickstart=quickstart)
                assert finder.daemon is True

                start.assert_called_once_with(quickstart=quickstart)

            async it "defaults to not being a quickstart", loops, finder:
                start = pytest.helpers.AsyncMock(name="start")
                loops.start = start

                await finder.start()

                start.assert_called_once_with(quickstart=False)

        describe "finish":
            async it "calls finish on the loops", loops, finder:
                finish = pytest.helpers.AsyncMock(name="finish")
                loops.finish = finish

                await finder.finish()
                finish.assert_called_once_with()

        describe "args_for_run":
            async it "proxies to loops", finder, loops:
                afr = mock.Mock(name="afr")
                args_for_run = pytest.helpers.AsyncMock(name="finish", return_value=afr)
                loops.args_for_run = args_for_run

                assert await finder.args_for_run() is afr
                args_for_run.assert_called_once_with()

        describe "find":
            async it "proxies _find", finder:
                res = mock.Mock(name="res")
                _find = mock.Mock(name="_find", return_value=res)

                kwargs = {"one": "two", "three": "four"}
                with mock.patch.object(finder, "_find", _find):
                    assert finder.find(**kwargs) is res

                _find.assert_called_once_with(kwargs)

        describe "serials":
            async it "gets serials from our special reference", finder:
                found = mock.Mock(name="found")
                serials = mock.Mock(name="serials")

                reference = mock.Mock(name="reference")
                reference.find = pytest.helpers.AsyncMock(
                    name="find", return_value=(found, serials)
                )

                afr = mock.Mock(name="afr")
                args_for_run = pytest.helpers.AsyncMock(name="args_for_run", return_value=afr)

                _find = mock.Mock(name="_find", return_value=reference)

                kwargs = {"one": "two", "three": "four"}
                with mock.patch.multiple(finder, _find=_find, args_for_run=args_for_run):
                    assert (await finder.serials(**kwargs)) is serials

                args_for_run.assert_called_once_with()
                _find.assert_called_once_with(kwargs)
                reference.find.assert_called_once_with(afr, timeout=5)

        describe "info_for":
            async it "gets info from the store given found from our special reference", loops, finder:
                info = mock.Mock(name="info")
                store = mock.Mock(name="store")
                store.info_for.return_value = info
                loops.store = store

                found = mock.Mock(name="found")
                serials = ["d1", "d2"]

                reference = mock.Mock(name="reference")
                reference.find = pytest.helpers.AsyncMock(
                    name="find", return_value=(found, serials)
                )

                afr = mock.Mock(name="afr")
                args_for_run = pytest.helpers.AsyncMock(name="args_for_run", return_value=afr)

                _find = mock.Mock(name="_find", return_value=reference)

                kwargs = {"one": "two", "three": "four"}
                with mock.patch.multiple(finder, _find=_find, args_for_run=args_for_run):
                    assert (await finder.info_for(**kwargs)) is info

                args_for_run.assert_called_once_with()
                _find.assert_called_once_with(kwargs, for_info=True)
                reference.find.assert_called_once_with(afr, timeout=5)
                store.info_for.assert_called_once_with(["d1", "d2"])

        describe "private _find":
            async it "ensures the loops are interpreting and uses _reference with provided filtr", loops, finder:
                reference = mock.Mock(name="reference")
                _reference = mock.Mock(name="_reference", return_value=reference)
                filtr = mock.Mock(name="filtr")

                with mock.patch.object(finder, "_reference", _reference):
                    assert finder._find({"filtr": filtr}) is reference

                _reference.assert_called_once_with(filtr, for_info=False)
                loops.ensure_interpreting.assert_called_once_with()

            async it "complains if filtr is accompanied by other kwargs", finder:
                with assertRaises(
                    PhotonsAppError, "Please either specify filters or a filtr, not both"
                ):
                    finder._find({"filtr": mock.Mock(name="filtr"), "one": "two"})

            async it "uses from_options if filtr not provided", loops, finder:
                reference = mock.Mock(name="reference")
                _reference = mock.Mock(name="_reference", return_value=reference)

                filtr = mock.Mock(name="filtr")
                from_options = mock.Mock(name="from_options", return_value=filtr)

                kwargs = {"one": "two", "three": "four"}
                with mock.patch.object(Filter, "from_options", from_options):
                    with mock.patch.object(finder, "_reference", _reference):
                        assert finder._find(kwargs) is reference

                _reference.assert_called_once_with(filtr, for_info=False)
                loops.ensure_interpreting.assert_called_once_with()
                from_options.assert_called_once_with(kwargs)

        describe "private _reference":

            @pytest.fixture()
            def found(self):
                target1 = binascii.unhexlify("d071")
                target2 = binascii.unhexlify("d072")
                return {
                    target1: mock.Mock(name="target1"),
                    target2: mock.Mock(name="target2"),
                }

            @pytest.fixture()
            def serials(self):
                return ["d071", "d072"]

            async it "sets serials if that's the only thing in the filter", finder:
                filtr = Filter.from_kwargs(serial=["d1", "d2"])
                ref = finder._reference(filtr)
                assert ref.serials == ["d1", "d2"]

                filtr = Filter.from_kwargs(serial=["d1", "d2"], label="den")
                ref = finder._reference(filtr)
                assert not hasattr(ref, "serials")

                filtr = Filter.from_kwargs(label="den")
                ref = finder._reference(filtr)
                assert not hasattr(ref, "serials")

                filtr = Filter.from_kwargs()
                ref = finder._reference(filtr)
                assert not hasattr(ref, "serials")

            async it "does a refresh_from_filter if force_refresh", loops, finder, found, serials:
                finder.daemon = True

                afr = mock.Mock(name="afr")
                filtr = mock.Mock(name="filtr", force_refresh=True)
                loops.refresh_from_filter = pytest.helpers.AsyncMock(
                    name="refresh_from_filter", return_value=found
                )

                reference = finder._reference(filtr)
                assert isinstance(reference, SpecialReference)

                f, s = await reference.find(afr, timeout=1)
                assert f == found
                assert sorted(s) == sorted(serials)
                loops.refresh_from_filter.assert_called_once_with(
                    filtr, for_info=False, find_timeout=1
                )

            async it "does a refresh_from_filter if not a daemon", loops, finder, found, serials:
                assert not finder.daemon

                afr = mock.Mock(name="afr")
                filtr = mock.Mock(name="filtr", force_refresh=False)
                loops.refresh_from_filter = pytest.helpers.AsyncMock(
                    name="refresh_from_filter", return_value=found
                )

                reference = finder._reference(filtr, for_info=True)
                assert isinstance(reference, SpecialReference)

                f, s = await reference.find(afr, timeout=2)
                assert f == found
                assert sorted(s) == sorted(serials)
                loops.refresh_from_filter.assert_called_once_with(
                    filtr, for_info=True, find_timeout=2
                )

            async it "does just a found_from_filter if a daemon and not force_refresh", loops, finder, found, serials:
                finder.daemon = True

                afr = mock.Mock(name="afr")
                filtr = mock.Mock(name="filtr", force_refresh=False)

                store = mock.Mock(name="store")
                store.found_from_filter = pytest.helpers.AsyncMock(
                    name="found_from_filter", return_value=found
                )
                loops.store = store

                reference = finder._reference(filtr, for_info=True)
                assert isinstance(reference, SpecialReference)

                f, s = await reference.find(afr, timeout=3)
                assert f == found
                assert sorted(s) == sorted(serials)

                assert len(loops.refresh_from_filter.mock_calls) == 0
                store.found_from_filter.assert_called_once_with(
                    filtr, for_info=True, find_timeout=3
                )

            async it "raises FondNoDevices if there are no devices to be found", loops, finder:
                finder.daemon = True

                afr = mock.Mock(name="afr")
                filtr = mock.Mock(name="filtr", force_refresh=False)

                store = mock.Mock(name="store")
                store.found_from_filter = pytest.helpers.AsyncMock(
                    name="found_from_filter", return_value={}
                )
                loops.store = store

                reference = finder._reference(filtr, for_info=True)
                assert isinstance(reference, SpecialReference)

                with assertRaises(FoundNoDevices):
                    await reference.find(afr, timeout=3)

                assert len(loops.refresh_from_filter.mock_calls) == 0
                store.found_from_filter.assert_called_once_with(
                    filtr, for_info=True, find_timeout=3
                )

            async it "raises FoundNoDevices if we go via refresh_from_filter", loops, finder:
                afr = mock.Mock(name="afr")
                filtr = mock.Mock(name="filtr", force_refresh=False)

                loops.refresh_from_filter = pytest.helpers.AsyncMock(
                    name="refresh_from_filter", return_value={}
                )

                reference = finder._reference(filtr, for_info=True)
                assert isinstance(reference, SpecialReference)

                with assertRaises(FoundNoDevices):
                    await reference.find(afr, timeout=4)

                loops.refresh_from_filter.assert_called_once_with(
                    filtr, for_info=True, find_timeout=4
                )

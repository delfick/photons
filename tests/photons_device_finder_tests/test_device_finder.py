# coding: spec

from photons_device_finder import DeviceFinder, Filter

from photons_app.errors import PhotonsAppError, FoundNoDevices
from photons_app.test_helpers import AsyncTestCase
from photons_app.special import SpecialReference

from noseOfYeti.tokeniser.async_support import async_noy_sup_setUp
from unittest import mock
import asynctest
import binascii

describe AsyncTestCase, "DeviceFinder":
    async it "makes itself a loops and sets daemon to False":
        target = mock.Mock(name="target")
        loops = mock.Mock(name="loops")
        service_interval = mock.Mock(name='service_interval')
        information_interval = mock.Mock(name='information_interval')
        repeat_spread = mock.Mock(name='repeat_spread')

        DeviceFinderLoops = mock.Mock(name="DeviceFinderLoops", return_value=loops)

        with mock.patch("photons_device_finder.DeviceFinderLoops", DeviceFinderLoops):
            finder = DeviceFinder(target
                , service_search_interval = service_interval
                , information_search_interval = information_interval
                , repeat_spread = repeat_spread
                )

        self.assertIs(finder.loops, loops)
        self.assertEqual(finder.daemon, False)

        DeviceFinderLoops.assert_called_once_with(target
            , service_search_interval = service_interval
            , information_search_interval = information_interval
            , repeat_spread = repeat_spread
            )

    describe "functionality":
        async before_each:
            self.target = mock.Mock(name='target')
            self.loops = mock.Mock(name="loops")
            self.interval = mock.Mock(name="interval")

            DeviceFinderLoops = mock.Mock(name="DeviceFinderLoops", return_value=self.loops)

            with mock.patch("photons_device_finder.DeviceFinderLoops", DeviceFinderLoops):
                self.finder = DeviceFinder(self.target, service_search_interval=self.interval)

        describe "start":
            async it "starts the loops and sets daemon to True":
                start = asynctest.mock.CoroutineMock(name='start')
                self.loops.start = start

                quickstart = mock.Mock(name="quickstrt")
                await self.finder.start(quickstart=quickstart)
                self.assertIs(self.finder.daemon, True)

                start.assert_called_once_with(quickstart=quickstart)

            async it "defaults to not being a quickstart":
                start = asynctest.mock.CoroutineMock(name='start')
                self.loops.start = start

                await self.finder.start()

                start.assert_called_once_with(quickstart=False)

        describe "finish":
            async it "calls finish on the loops":
                finish = asynctest.mock.CoroutineMock(name="finish")
                self.loops.finish = finish

                await self.finder.finish()
                finish.assert_called_once_with()

        describe "args_for_run":
            async it "proxies to loops":
                afr = mock.Mock(name="afr")
                args_for_run = asynctest.mock.CoroutineMock(name="finish", return_value=afr)
                self.loops.args_for_run = args_for_run

                self.assertIs(await self.finder.args_for_run(), afr)
                args_for_run.assert_called_once_with()

        describe "find":
            async it "proxies _find":
                res = mock.Mock(name='res')
                _find = mock.Mock(name="_find", return_value=res)

                kwargs = {"one": "two", "three": "four"}
                with mock.patch.object(self.finder, "_find", _find):
                    self.assertIs(self.finder.find(**kwargs), res)

                _find.assert_called_once_with(kwargs)

        describe "serials":
            async it "gets serials from our special reference":
                found = mock.Mock(name="found")
                serials = mock.Mock(name="serials")

                reference = mock.Mock(name="reference")
                reference.find = asynctest.mock.CoroutineMock(name="find", return_value=(found, serials))

                afr = mock.Mock(name="afr")
                args_for_run = asynctest.mock.CoroutineMock(name="args_for_run", return_value=afr)

                _find = mock.Mock(name="_find", return_value=reference)

                kwargs = {"one": "two", "three": "four"}
                with mock.patch.multiple(self.finder, _find=_find, args_for_run=args_for_run):
                    self.assertIs(await self.wait_for(self.finder.serials(**kwargs)), serials)

                args_for_run.assert_called_once_with()
                _find.assert_called_once_with(kwargs)
                reference.find.assert_called_once_with(afr, timeout=5)

        describe "info_for":
            async it "gets info from the store given found from our special reference":
                info = mock.Mock(name="info")
                store = mock.Mock(name="store")
                store.info_for.return_value = info
                self.loops.store = store

                found = mock.Mock(name="found")
                serials = ["d1", "d2"]

                reference = mock.Mock(name="reference")
                reference.find = asynctest.mock.CoroutineMock(name="find", return_value=(found, serials))

                afr = mock.Mock(name="afr")
                args_for_run = asynctest.mock.CoroutineMock(name="args_for_run", return_value=afr)

                _find = mock.Mock(name="_find", return_value=reference)

                kwargs = {"one": "two", "three": "four"}
                with mock.patch.multiple(self.finder, _find=_find, args_for_run=args_for_run):
                    self.assertIs(await self.wait_for(self.finder.info_for(**kwargs)), info)

                args_for_run.assert_called_once_with()
                _find.assert_called_once_with(kwargs, for_info=True)
                reference.find.assert_called_once_with(afr, timeout=5)
                store.info_for.assert_called_once_with(["d1", "d2"])

        describe "private _find":
            async it "ensures the loops are interpreting and uses _reference with provided filtr":
                reference = mock.Mock(name='reference')
                _reference = mock.Mock(name="_reference", return_value=reference)
                filtr = mock.Mock(name="filtr")

                with mock.patch.object(self.finder, "_reference", _reference):
                    self.assertIs(self.finder._find({"filtr": filtr}), reference)

                _reference.assert_called_once_with(filtr, for_info=False)
                self.loops.ensure_interpreting.assert_called_once_with()

            async it "complains if filtr is accompanied by other kwargs":
                with self.fuzzyAssertRaisesError(PhotonsAppError, "Please either specify filters or a filtr, not both"):
                    self.finder._find({"filtr": mock.Mock(name="filtr"), "one": "two"})

            async it "uses from_options if filtr not provided":
                reference = mock.Mock(name='reference')
                _reference = mock.Mock(name="_reference", return_value=reference)

                filtr = mock.Mock(name="filtr")
                from_options = mock.Mock(name="from_options", return_value=filtr)

                kwargs = {"one": "two", "three": "four"}
                with mock.patch.object(Filter, "from_options", from_options):
                    with mock.patch.object(self.finder, "_reference", _reference):
                        self.assertIs(self.finder._find(kwargs), reference)

                _reference.assert_called_once_with(filtr, for_info=False)
                self.loops.ensure_interpreting.assert_called_once_with()
                from_options.assert_called_once_with(kwargs)

        describe "private _reference":
            async before_each:
                target1 = binascii.unhexlify("d071")
                target2 = binascii.unhexlify("d072")
                self.found = {target1: mock.Mock(name="target1"), target2: mock.Mock(name="target2")}
                self.serials = ["d071", "d072"]

            async it "sets serials if that's the only thing in the filter":
                filtr = Filter.from_kwargs(serial=["d1", "d2"])
                ref = self.finder._reference(filtr)
                self.assertEqual(ref.serials, ["d1", "d2"])

                filtr = Filter.from_kwargs(serial=["d1", "d2"], label="den")
                ref = self.finder._reference(filtr)
                assert not hasattr(ref, "serials")

                filtr = Filter.from_kwargs(label="den")
                ref = self.finder._reference(filtr)
                assert not hasattr(ref, "serials")

                filtr = Filter.from_kwargs()
                ref = self.finder._reference(filtr)
                assert not hasattr(ref, "serials")

            async it "does a refresh_from_filter if force_refresh":
                self.finder.daemon = True

                afr = mock.Mock(name='afr')
                filtr = mock.Mock(name="filtr", force_refresh=True)
                self.loops.refresh_from_filter = asynctest.mock.CoroutineMock(name="refresh_from_filter", return_value=self.found)

                reference = self.finder._reference(filtr)
                assert isinstance(reference, SpecialReference)

                f, s = await self.wait_for(reference.find(afr, timeout=1))
                self.assertEqual(f, self.found)
                self.assertEqual(sorted(s), sorted(self.serials))
                self.loops.refresh_from_filter.assert_called_once_with(filtr, for_info=False, find_timeout=1)

            async it "does a refresh_from_filter if not a daemon":
                assert not self.finder.daemon

                afr = mock.Mock(name='afr')
                filtr = mock.Mock(name="filtr", force_refresh=False)
                self.loops.refresh_from_filter = asynctest.mock.CoroutineMock(name="refresh_from_filter", return_value=self.found)

                reference = self.finder._reference(filtr, for_info=True)
                assert isinstance(reference, SpecialReference)

                f, s = await self.wait_for(reference.find(afr, timeout=2))
                self.assertEqual(f, self.found)
                self.assertEqual(sorted(s), sorted(self.serials))
                self.loops.refresh_from_filter.assert_called_once_with(filtr, for_info=True, find_timeout=2)

            async it "does just a found_from_filter if a daemon and not force_refresh":
                self.finder.daemon = True

                afr = mock.Mock(name='afr')
                filtr = mock.Mock(name="filtr", force_refresh=False)

                store = mock.Mock(name="store")
                store.found_from_filter = asynctest.mock.CoroutineMock(name="found_from_filter", return_value=self.found)
                self.loops.store = store

                reference = self.finder._reference(filtr, for_info=True)
                assert isinstance(reference, SpecialReference)

                f, s = await self.wait_for(reference.find(afr, timeout=3))
                self.assertEqual(f, self.found)
                self.assertEqual(sorted(s), sorted(self.serials))

                self.assertEqual(len(self.loops.refresh_from_filter.mock_calls), 0)
                store.found_from_filter.assert_called_once_with(filtr, for_info=True, find_timeout=3)

            async it "raises FondNoDevices if there are no devices to be found":
                self.finder.daemon = True

                afr = mock.Mock(name='afr')
                filtr = mock.Mock(name="filtr", force_refresh=False)

                store = mock.Mock(name="store")
                store.found_from_filter = asynctest.mock.CoroutineMock(name="found_from_filter", return_value={})
                self.loops.store = store

                reference = self.finder._reference(filtr, for_info=True)
                assert isinstance(reference, SpecialReference)

                with self.fuzzyAssertRaisesError(FoundNoDevices):
                    await self.wait_for(reference.find(afr, timeout=3))

                self.assertEqual(len(self.loops.refresh_from_filter.mock_calls), 0)
                store.found_from_filter.assert_called_once_with(filtr, for_info=True, find_timeout=3)

            async it "raises FoundNoDevices if we go via refresh_from_filter":
                afr = mock.Mock(name='afr')
                filtr = mock.Mock(name="filtr", force_refresh=False)

                self.loops.refresh_from_filter = asynctest.mock.CoroutineMock(name="refresh_from_filter", return_value={})

                reference = self.finder._reference(filtr, for_info=True)
                assert isinstance(reference, SpecialReference)

                with self.fuzzyAssertRaisesError(FoundNoDevices):
                    await self.wait_for(reference.find(afr, timeout=4))

                self.loops.refresh_from_filter.assert_called_once_with(filtr, for_info=True, find_timeout=4)

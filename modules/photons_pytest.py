"""pytest-cov: avoid already-imported warning: PYTEST_DONT_REWRITE."""


from contextlib import contextmanager
from delfick_project.norms import sb
from collections import defaultdict
from textwrap import dedent
from unittest import mock
import tempfile
import asyncio
import socket
import shutil
import errno
import time
import json
import sys
import re
import os


try:
    import pytest
except:

    class FakePytest:
        class fixture:
            def __init__(self, **kwargs):
                pass

            def __call__(self, func):
                return func

    pytest = FakePytest()


class AsyncCMMixin:
    """
    Copied from photons_app.helpers
    because it's important to not import photons in this file
    """

    async def __aenter__(self):
        try:
            return await self.start()
        finally:
            # aexit doesn't run if aenter raises an exception
            exc_info = sys.exc_info()
            if exc_info[1] is not None:
                await self.__aexit__(*exc_info)
                raise

    async def start(self):
        raise NotImplementedError()

    async def __aexit__(self, exc_typ, exc, tb):
        await self.finish(exc_typ, exc, tb)

    async def finish(self, exc_typ=None, exc=None, tb=None):
        raise NotImplementedError()


class PortHelpers:
    def free_port(self):
        """
        Return an unused port number
        """
        with socket.socket() as s:
            s.bind(("", 0))
            return s.getsockname()[1]

    async def wait_for_port(self, port, timeout=3, gap=0.01):
        """
        Wait for a port to have something behind it
        """
        start = time.time()
        while time.time() - start < timeout:
            if self.port_connected(port):
                break
            await asyncio.sleep(gap)
        assert self.port_connected(port)

    async def wait_for_no_port(self, port, timeout=3, gap=0.01):
        """
        Wait for a port to not have something behind it
        """
        start = time.time()
        while time.time() - start < timeout:
            if not self.port_connected(port):
                break
            await asyncio.sleep(gap)
        assert not self.port_connected(port)

    def port_connected(self, port):
        """
        Return whether something is listening on this port
        """
        with socket.socket() as sock:
            res = int(sock.connect_ex(("127.0.0.1", port)))

        if res == 0:
            return True

        error = errno.errorcode[res]
        assert res is errno.ECONNREFUSED, (error, port)
        return False


def run_pytest():
    class EditConfig:
        @pytest.hookimpl(hookwrapper=True)
        def pytest_cmdline_parse(pluginmanager, args):
            args.extend(
                [
                    "--tb=short",
                    "-o",
                    "console_output_style=classic",
                    "-o",
                    "default_alt_async_timeout=1.5",
                    "-W",
                    "ignore:Using or importing the ABCs:DeprecationWarning",
                    "--log-level=INFO",
                    "-p",
                    "helpers_namespace",
                ]
            )
            yield

    sys.exit(pytest.main(plugins=[EditConfig()]))


regexes = {}


@pytest.fixture(scope="session")
def a_temp_dir():
    class TempDir:
        def __enter__(self):
            self.d = tempfile.mkdtemp()
            return self.d, self.make_file

        def __exit__(self, exc_typ, exc, tb):
            if hasattr(self, "d") and os.path.exists(self.d):
                shutil.rmtree(self.d)

        def make_file(self, name, contents):
            location = os.path.join(self.d, name)
            parent = os.path.dirname(location)
            if not os.path.exists(parent):
                os.makedirs(parent)

            with open(location, "w") as fle:
                fle.write(dedent(contents))

            return location

    return TempDir


class FakeTimeImpl:
    def __init__(self, mock_sleep=False, mock_async_sleep=False):
        self.time = 0
        self.patches = []
        self.mock_sleep = mock_sleep
        self.mock_async_sleep = mock_async_sleep
        self.original_time = time.time
        self.original_async_sleep = asyncio.sleep

    def set(self, t):
        self.time = round(t, 3)

    def add(self, t):
        self.time = round(self.time + t, 3)

    def __enter__(self):
        return self.start()

    def start(self):
        self.patches.append(mock.patch("time.time", self))

        if self.mock_sleep:
            self.patches.append(mock.patch("time.sleep", self.sleep))
        if self.mock_async_sleep:
            self.patches.append(mock.patch("asyncio.sleep", self.async_sleep))

        for p in self.patches:
            p.start()

        return self

    def __exit__(self, exc_typ, exc, tb):
        self.finish(exc_typ, exc, tb)

    def finish(self, exc_typ=None, exc=None, tb=None):
        for p in self.patches:
            p.stop()

    def __call__(self):
        return round(self.time, 3)

    def sleep(self, amount):
        self.add(amount)

    async def async_sleep(self, amount):
        self.add(amount)
        await self.original_async_sleep(0.001)


class MockedCallLaterImpl(AsyncCMMixin):
    def __init__(self, t):
        self.t = t
        self.loop = asyncio.get_event_loop()

        self.task = None
        self.call_later_patch = None
        self.create_future_patch = None

        self.funcs = []
        self.called_times = []
        self.have_call_later = self.hp.ResettableFuture()

    async def start(self):
        self.task = self.hp.async_as_background(self._calls())
        self.call_later_patch = mock.patch.object(self.loop, "call_later", self._call_later)
        self.call_later_patch.start()
        return self

    async def finish(self, exc_typ=None, exc=None, tb=None):
        if self.call_later_patch:
            self.call_later_patch.stop()
        if self.task:
            await self.hp.cancel_futures_and_wait(self.task, name="MockedCallLater.exit")

    async def add(self, amount):
        await self._run(iterations=round(amount / 0.1))

    async def resume_after(self, amount):
        fut = self.hp.create_future()
        asyncio.get_event_loop().call_later(amount, fut.set_result, True)
        await fut

    @property
    def hp(self):
        return __import__("photons_app").helpers

    def _call_later(self, when, func, *args):
        self.have_call_later.reset()
        self.have_call_later.set_result(True)

        info = {"cancelled": False}

        def caller():
            if not info["cancelled"]:
                self.called_times.append(time.time())
                func(*args)

        caller.original = func

        class Handle:
            def cancel(s):
                info["cancelled"] = True

        self.funcs.append((round(time.time() + when, 3), caller))
        return Handle()

    async def _allow_real_loop(self, until=0):
        while True:
            ready = asyncio.get_event_loop()._ready
            ready_len = len(ready)
            await asyncio.sleep(0)
            if ready_len <= until:
                return

    async def _calls(self):
        await self.have_call_later

        while True:
            await self._allow_real_loop()
            await self.have_call_later
            await self._run()
            if not self.funcs:
                self.have_call_later.reset()

    async def _run(self, iterations=0):
        for iteration in range(iterations + 1):
            now = time.time()
            executed = False
            remaining = []

            for k, f in self.funcs:
                if now < k:
                    remaining.append((k, f))
                else:
                    executed = True
                    f()
                    await self._allow_real_loop(until=1)

            self.funcs = remaining

            if iterations >= 1 and iteration > 0:
                self.t.add(0.1)

        if not executed and iterations == 0:
            self.t.add(0.1)

        return executed


@pytest.fixture(scope="session")
def MockedCallLater():
    return MockedCallLaterImpl


@pytest.fixture(scope="session")
def FakeTime():
    return FakeTimeImpl


class FutureDominoes(AsyncCMMixin):
    """
    A helper to start a domino of futures.

    For example:

    .. code-block:: python

        async def run():
            async with FutureDominoes(expected=8) as futs:
                called = []

                async def one():
                    await futs[1]
                    called.append("first")
                    await futs[2]
                    called.append("second")
                    await futs[5]
                    called.append("fifth")
                    await futs[7]
                    called.append("seventh")

                async def two():
                    await futs[3]
                    called.append("third")

                    start = 4
                    while start <= 6:
                        await futs[start]
                        called.append(("gen", start))
                        yield ("genresult", start)
                        start += 2

                async def three():
                    await futs[8]
                    called.append("final")

                loop = asyncio.get_event_loop()
                loop.create_task(three())
                loop.create_task(one())

                async def run_two():
                    async for r in two():
                        called.append(r)

                loop.create_task(run_two())

                assert called == [
                    "first",
                    "second",
                    "third",
                    ("gen", 4),
                    ("genresult", 4),
                    "fifth",
                    ("gen", 6),
                    ("genresult", 6),
                    "seventh",
                    "final",
                ]
    """

    def __init__(self, *, before_next_domino=None, expected):
        self.futs = {}
        self.retrieved = {}

        self.upto = 1
        self.expected = int(expected)
        self.before_next_domino = before_next_domino
        self.finished = self.hp.ResettableFuture()

        for i in range(self.expected):
            self.make(i + 1)

    async def start(self):
        self._tick = self.hp.async_as_background(self.tick())
        self._tick.add_done_callback(self.hp.transfer_result(self.finished))
        return self

    async def finish(self, exc_typ=None, exc=None, tb=None):
        if hasattr(self, "_tick"):
            if exc and not self._tick.done():
                self._tick.cancel()
            await self.hp.wait_for_all_futures(self._tick)

        if not exc:
            await self._tick

    async def tick(self):
        async with self.hp.tick(0, min_wait=0) as ticks:
            async for i, _ in ticks:
                await self.hp.wait_for_all_futures(self.retrieved[i], self.futs[i])
                print(f"Waited for Domino {i}")

                self.upto = i

                await self._allow_real_loop()

                if i >= self.expected:
                    print("Finished knocking over dominoes")
                    if not self.finished.done():
                        self.finished.set_result(True)

                if self.finished.done():
                    return

                self.make(i + 1)

                if self.before_next_domino:
                    self.before_next_domino(i)

                if not self.futs[i + 1].done():
                    self.futs[i + 1].set_result(True)

    async def _allow_real_loop(self):
        while True:
            ready = asyncio.get_event_loop()._ready
            ready_len = len(ready)
            await asyncio.sleep(0)
            if ready_len == 0:
                return

    @property
    def hp(self):
        return __import__("photons_app").helpers

    @property
    def loop(self):
        return asyncio.get_event_loop()

    def make(self, num):
        if num > self.expected or self.finished.done():
            exc = Exception(f"Only expected up to {self.expected} dominoes")
            self.finished.reset()
            self.finished.set_exception(exc)
            raise exc

        if num in self.futs:
            return self.futs[num]

        fut = self.hp.create_future(name=f"Domino({num})")
        self.futs[num] = fut
        self.retrieved[num] = self.hp.create_future(name=f"Domino({num}.retrieved")
        fut.add_done_callback(self.hp.transfer_result(self.finished, errors_only=True))
        return fut

    def __getitem__(self, num):
        if not self.futs[1].done():
            self.futs[1].set_result(True)
        fut = self.make(num)
        if not self.retrieved[num].done():
            self.retrieved[num].set_result(True)
        return fut


def pytest_configure(config):
    config.addinivalue_line("markers", "focus: mark test to run")

    if not hasattr(pytest, "helpers"):
        return

    pytest.helpers.register(FutureDominoes)

    @pytest.helpers.register
    def has_caps_list(*have):
        want = [
            "buttons",
            "color",
            "chain",
            "ir",
            "hev",
            "matrix",
            "multizone",
            "relays",
            "variable_color_temp",
        ]

        result = []
        for a in want:
            if a in have:
                result.append(a)
            else:
                result.append(f"not_{a}")
        return sorted(result)

    @pytest.helpers.register
    def assertRegex(regex, value):
        __tracebackhide__ = True

        if isinstance(regex, str):
            if regex not in regexes:
                regexes[regex] = re.compile(regex)
            regex = regexes[regex]

        m = regex.match(value)
        if m:
            return

        def indented(v):
            return "\n".join(f"  {line}" for line in v.split("\n"))

        lines = [
            "Regex didn't match",
            "Wanted:\n",
            indented(regex.pattern),
            "\nto match:",
            indented(value),
        ]

        pytest.fail("\n".join(lines))

    @pytest.helpers.register
    def AsyncMock(*args, **kwargs):
        if sys.version_info < (3, 8):
            return __import__("mock").AsyncMock(*args, **kwargs)
        else:
            return mock.AsyncMock(*args, **kwargs)

    @pytest.helpers.register
    def MagicAsyncMock(*args, **kwargs):
        if sys.version_info < (3, 8):
            return __import__("mock").MagicMock(*args, **kwargs)
        else:
            return mock.MagicMock(*args, **kwargs)

    @pytest.helpers.register
    def child_future_of(fut):
        hp = __import__("photons_app").helpers

        class Compare:
            def __eq__(s, other):
                s.other = other
                s.eq = isinstance(other, hp.ChildOfFuture) and other.original_fut is fut
                return s.eq

            def __repr__(s):
                if not hasattr(s, "eq"):
                    return f"<<COMPARE child of future {fut}>>"
                if not s.eq:
                    return f"<<DIFFERENT got: {s.other.original_fut}, want: {fut}>>"
                return repr(s.other)

        return Compare()

    @pytest.helpers.register
    def assertComparison(got, wanted, *, is_json):
        if got != wanted:
            print("!" * 80)
            print("Got:")
            if is_json:
                got = json.dumps(got, sort_keys=True, indent="  ", default=lambda o: repr(o))
            for line in got.split("\n"):
                print(f"> {line}")

            print("Wanted:")
            if is_json:
                wanted = json.dumps(wanted, sort_keys=True, indent="  ", default=lambda o: repr(o))
            for line in wanted.split("\n"):
                print(f"> {line}")

        assert got == wanted
        return got

    @pytest.helpers.register
    @contextmanager
    def modified_env(**env):
        """
        A context manager that let's you modify environment variables until the block
        has ended where the environment is returned to how it was

        .. code-block:: python

            import os

            assert "ONE" not in os.environ
            assert os.environ["TWO"] == "two"

            with modified_env(ONE="1", TWO="2"):
                assert os.environ["ONE"] == "1"
                assert os.environ["TWO"] == "1"

            assert "ONE" not in os.environ
            assert os.environ["TWO"] == "two"
        """
        previous = {key: os.environ.get(key, sb.NotSpecified) for key in env}
        try:
            for key, val in env.items():
                if val is None:
                    if key in os.environ:
                        del os.environ[key]
                else:
                    os.environ[key] = val
            yield
        finally:
            for key, val in previous.items():
                if val is sb.NotSpecified:
                    if key in os.environ:
                        del os.environ[key]
                else:
                    os.environ[key] = val

    @pytest.helpers.register
    def assertFutCallbacks(fut, *cbs, exhaustive=False):
        callbacks = fut._callbacks

        try:
            from contextvars import Context
        except ImportError:
            Context = None

        if not cbs:
            if Context is not None:
                if callbacks:
                    assert len(callbacks) == 1, f"Expect only one context callback: got {callbacks}"
                    assert isinstance(
                        callbacks[0], Context
                    ), f"Expected just a context callback: got {callbacks}"
            else:
                assert callbacks == [], f"Expected no callbacks, got {callbacks}"

            return

        if not callbacks:
            assert False, f"expected callbacks, got {callbacks}"

        counts = defaultdict(lambda: 0)
        expected = defaultdict(lambda: 0)

        for cb in callbacks:
            if type(cb) is tuple:
                if len(cb) == 2 and Context and isinstance(cb[1], Context):
                    cb = cb[0]
                else:
                    assert False, f"Got a tuple instead of a callback, {cb} in {callbacks}"

            if not Context or not isinstance(cb, Context):
                counts[cb] += 1

        for cb in cbs:
            expected[cb] += 1

        for cb in cbs:
            msg = f"Expected {expected[cb]} instances of {cb}, got {counts[cb]} in {callbacks}"
            assert counts[cb] == expected[cb], msg

        if exhaustive and len(callbacks) != len(cbs):
            assert False, f"Expected exactly {len(cbs)} callbacks but have {len(callbacks)}"

    @pytest.helpers.register
    def assertPayloadsEquals(payload, expected, allow_missing=False):
        dct = payload.as_dict()

        different = []
        for k, v in expected.items():
            if not allow_missing and k not in dct:
                assert False, f"{k} was not in the payload: {dct}"
            if k in dct and v != dct[k]:
                different.append([k, dct[k], v])

        for k, got, want in different:
            print(f"KEY: {k} |:| GOT: {got} |:| WANT: {want}")

        assert len(different) == 0

    @pytest.helpers.register
    def print_packet_difference(one, two, ignore_unspecified_expected=True):
        different = False
        if one != two:
            print("\tGOT : {0}".format(one.payload.__class__))
            print("\tWANT: {0}".format(two.payload.__class__))
            if one.payload.__class__ == two.payload.__class__:
                dictc = dict(one)
                dictw = dict(two)
                for k, v in dictc.items():
                    if k not in dictw:
                        print("\t\tGot key not in wanted: {0}".format(k))
                        different = True
                    elif dictw[k] is sb.NotSpecified and v is not sb.NotSpecified:
                        print(f"\t\tkey {k} | Ignored because expected is NotSpecified | was {v}")
                    elif repr(v) != repr(dictw[k]):
                        if isinstance(v, bool) and dictw[k] in (1, 0) and int(v) == dictw[k]:
                            continue
                        print("\t\tkey {0} | got {1} | want {2}".format(k, v, dictw[k]))
                        different = True

                for k in dictw:
                    if k not in dictc:
                        print("\t\tGot key in wanted but not in what we got: {0}".format(k))
                        different = True
        return different

    port_helpers = PortHelpers()
    pytest.helpers.register(port_helpers.free_port)
    pytest.helpers.register(port_helpers.wait_for_port)
    pytest.helpers.register(port_helpers.wait_for_no_port)
    pytest.helpers.register(port_helpers.port_connected)


class MemoryDevicesRunner(AsyncCMMixin):
    def __init__(self, devices):
        self.final_future = __import__("photons_app").helpers.create_future()

        options = {
            "devices": devices,
            "final_future": self.final_future,
            "protocol_register": __import__("photons_messages").protocol_register,
        }

        MemoryTarget = __import__("photons_transport.targets").targets.MemoryTarget
        self.target = MemoryTarget.create(options)
        self.devices = devices

    async def start(self):
        for device in self.devices:
            await device.start()

        self.sender = await self.target.make_sender()
        return self

    async def finish(self, exc_typ=None, exc=None, tb=None):
        if hasattr(self, "sender"):
            await self.target.close_sender(self.sender)

        for device in self.target.devices:
            await device.finish(exc_typ, exc, tb)

        self.final_future.cancel()

    async def reset_devices(self):
        for device in self.devices:
            await device.reset()

    async def per_test(self):
        self.sender.received.clear()
        await self.reset_devices()
        del self.sender.gatherer

    @property
    def serials(self):
        return [device.serial for device in self.devices]


@pytest.fixture(scope="session")
def memory_devices_runner():
    return MemoryDevicesRunner

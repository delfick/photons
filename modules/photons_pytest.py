"""pytest-cov: avoid already-imported warning: PYTEST_DONT_REWRITE."""


from textwrap import dedent
from unittest import mock
import tempfile
import asyncio
import socket
import shutil
import time
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


def _port_connected(port):
    """
    Return whether something is listening on this port
    """
    s = socket.socket()
    s.settimeout(5)
    try:
        s.connect(("127.0.0.1", port))
        s.close()
        return True
    except Exception:
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
                    "default_alt_async_timeout=1",
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

        def __exit__(self, exc_type, exc, tb):
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
        self.patches.append(mock.patch("time.time", self))

        if self.mock_sleep:
            self.patches.append(mock.patch("time.sleep", self.sleep))
        if self.mock_async_sleep:
            self.patches.append(mock.patch("asyncio.sleep", self.async_sleep))

        for p in self.patches:
            p.start()

        return self

    def __exit__(self, exc_type, exc, tb):
        for p in self.patches:
            p.stop()

    def __call__(self):
        return round(self.time, 3)

    def sleep(self, amount):
        self.add(amount)

    async def async_sleep(self, amount):
        self.add(amount)
        await self.original_async_sleep(0.001)


class MockedCallLaterImpl:
    def __init__(self, t):
        self.t = t
        self.loop = asyncio.get_event_loop()

        self.task = None
        self.call_later_patch = None
        self.create_future_patch = None

        self.funcs = []
        self.called_times = []
        self.have_call_later = self.hp.ResettableFuture()

    async def __aenter__(self):
        self.task = self.hp.async_as_background(self._calls())
        self.call_later_patch = mock.patch.object(self.loop, "call_later", self._call_later)
        self.call_later_patch.start()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self.call_later_patch:
            self.call_later_patch.stop()
        if self.task:
            await self.hp.cancel_futures_and_wait(self.task, name="MockedCallLater.exit")

    async def add(self, amount):
        await self._run(iterations=round(amount / 0.1))

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

        class Handle:
            def cancel(s):
                info["cancelled"] = True

        self.funcs.append((round(time.time() + when, 3), caller))
        return Handle()

    async def _allow_real_loop(self):
        while True:
            ready = asyncio.get_event_loop()._ready
            ready_len = len(ready)
            await asyncio.sleep(0)
            if ready_len == 0:
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


class FutureDominoes:
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

    async def __aenter__(self):
        self._tick = self.hp.async_as_background(self.tick())
        self._tick.add_done_callback(self.hp.transfer_result(self.finished))
        return self

    async def __aexit__(self, exc_typ, exc, tb):
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
    def assert_regex(regex, value):
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
    def free_port():
        """
        Return an unused port number
        """
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("0.0.0.0", 0))
            return s.getsockname()[1]

    @pytest.helpers.register
    async def wait_for_port(port, timeout=3, gap=0.01):
        """
        Wait for a port to have something behind it
        """
        start = time.time()
        while time.time() - start < timeout:
            if _port_connected(port):
                break
            await asyncio.sleep(gap)
        assert _port_connected(port)

    @pytest.helpers.register
    def port_connected(port):
        return _port_connected(port)

    @pytest.helpers.register
    def AsyncMock(*args, **kwargs):
        if sys.version_info < (3, 8):
            return __import__("asynctest.mock").mock.CoroutineMock(*args, **kwargs)
        else:
            return mock.AsyncMock(*args, **kwargs)

    @pytest.helpers.register
    def MagicAsyncMock(*args, **kwargs):
        if sys.version_info < (3, 8):
            return __import__("asynctest").MagicMock(*args, **kwargs)
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


class MemoryDevicesRunner:
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

    async def __aenter__(self):
        for device in self.devices:
            await device.start()

        self.sender = await self.target.make_sender()
        return self

    async def __aexit__(self, typ, exc, tb):
        if hasattr(self, "sender"):
            await self.target.close_sender(self.sender)

        for device in self.target.devices:
            await device.finish()

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

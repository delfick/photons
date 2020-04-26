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


@pytest.fixture(scope="session")
def FakeTime():
    class FakeTime:
        def __init__(self, mock_sleep=False, mock_async_sleep=False):
            self.time = 0
            self.patches = []
            self.mock_sleep = mock_sleep
            self.mock_async_sleep = mock_async_sleep
            self.original_time = time.time
            self.original_async_sleep = asyncio.sleep

        def set(self, t):
            self.time = t

        def add(self, t):
            self.time += t

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
            return self.time

        def sleep(self, amount):
            self.add(amount)

        async def async_sleep(self, amount):
            self.add(amount)
            await self.original_async_sleep(0.001)

    return FakeTime


class FutureDominoes:
    """
    A helper to start a domino of futures.

    For example:

    .. code-block:: python

        async def run():
            futs = FutureDominoes(expected=8)

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

            futs.start()
            await futs

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
        self.upto = 1
        self.expected = int(expected)
        self.before_next_domino = before_next_domino

        hp = __import__("photons_app.helpers").helpers
        self.finished = hp.ResettableFuture()

    class F:
        def __init__(self, num, done_callback):
            self.num = num
            self.fut = asyncio.Future()
            self.ready_fut = asyncio.Future()
            self.done_callback = done_callback

            hp = __import__("photons_app.helpers").helpers

            self.combined_fut = asyncio.Future()
            self.fut.add_done_callback(hp.transfer_result(self.combined_fut))
            self.ready_fut.add_done_callback(hp.transfer_result(self.combined_fut))

        def done(self):
            return self.fut.done()

        def ready_to_resolve(self):
            if not self.ready_fut.done():
                self.ready_fut.set_result(True)

        def resolve(self):
            if not self.fut.done():
                self.fut.set_result(True)

        def __await__(self):
            try:
                yield from self.combined_fut
            except asyncio.CancelledError:
                pass
            self.done_callback()

    def make(self, num):
        if num > self.expected:
            exc = Exception(f"Only expected up to {self.expected} dominoes")
            self.finished.reset()
            self.finished.set_exception(exc)
            raise exc

        if num in self.futs:
            return self.futs[num]

        print(f"Making domino {num}")

        def fire_next():
            if self.before_next_domino:
                self.before_next_domino(num)

            if num + 1 > self.expected:
                print("Finished knocking over dominoes")
                if not self.finished.done():
                    self.finished.set_result(True)
            else:

                def resolve_next():
                    self[num + 1].ready_to_resolve()
                    self.upto = num + 1

                asyncio.get_event_loop().call_later(0.005, resolve_next)

        fut = self.futs[num] = self.F(num, fire_next)

        return fut

    def start(self):
        self[1].resolve()

    def __getitem__(self, num):
        return self.make(num)

    def __await__(self):
        if not self[1].done():
            raise Exception("The dominoes were never started")
        yield from self.finished


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


class MemoryDevicesRunner:
    def __init__(self, devices):
        self.final_future = asyncio.Future()
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
        await self.reset_devices()
        del self.sender.gatherer

    @property
    def serials(self):
        return [device.serial for device in self.devices]


@pytest.fixture(scope="session")
def memory_devices_runner():
    return MemoryDevicesRunner

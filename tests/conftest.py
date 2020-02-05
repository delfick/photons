from textwrap import dedent
from unittest import mock
import tempfile
import pytest
import shutil
import re
import os

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
        def __init__(self):
            self.time = 0

        def add(self, t):
            self.time += t

        def __enter__(self):
            self.patch = mock.patch("time.time", self)
            self.patch.start()
            return self

        def __exit__(self, exc_type, exc, tb):
            self.patch.stop()

        def __call__(self):
            return self.time

    return FakeTime


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

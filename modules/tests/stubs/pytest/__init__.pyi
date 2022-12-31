from _pytest import version_tuple as version_tuple
from _pytest._code import ExceptionInfo as ExceptionInfo
from _pytest.assertion import register_assert_rewrite as register_assert_rewrite
from _pytest.cacheprovider import Cache as Cache
from _pytest.capture import CaptureFixture as CaptureFixture
from _pytest.config import Config as Config
from _pytest.config import ExitCode as ExitCode
from _pytest.config import PytestPluginManager as PytestPluginManager
from _pytest.config import UsageError as UsageError
from _pytest.config import cmdline as cmdline
from _pytest.config import console_main as console_main
from _pytest.config import hookimpl as hookimpl
from _pytest.config import hookspec as hookspec
from _pytest.config import main as main
from _pytest.config.argparsing import OptionGroup as OptionGroup
from _pytest.config.argparsing import Parser as Parser
from _pytest.doctest import DoctestItem as DoctestItem
from _pytest.fixtures import FixtureLookupError as FixtureLookupError
from _pytest.fixtures import FixtureRequest as FixtureRequest
from _pytest.fixtures import fixture as fixture
from _pytest.fixtures import yield_fixture as yield_fixture
from _pytest.freeze_support import freeze_includes as freeze_includes
from _pytest.legacypath import TempdirFactory as TempdirFactory
from _pytest.legacypath import Testdir as Testdir
from _pytest.logging import LogCaptureFixture as LogCaptureFixture
from _pytest.main import Session as Session
from _pytest.mark import MARK_GEN as mark
from _pytest.mark import Mark as Mark
from _pytest.mark import MarkDecorator as MarkDecorator
from _pytest.mark import MarkGenerator as MarkGenerator
from _pytest.mark import param as param
from _pytest.monkeypatch import MonkeyPatch as MonkeyPatch
from _pytest.nodes import Collector as Collector
from _pytest.nodes import File as File
from _pytest.nodes import Item as Item
from _pytest.outcomes import exit as exit
from _pytest.outcomes import fail as fail
from _pytest.outcomes import importorskip as importorskip
from _pytest.outcomes import skip as skip
from _pytest.outcomes import xfail as xfail
from _pytest.pytester import HookRecorder as HookRecorder
from _pytest.pytester import LineMatcher as LineMatcher
from _pytest.pytester import Pytester as Pytester
from _pytest.pytester import RecordedHookCall as RecordedHookCall
from _pytest.pytester import RunResult as RunResult
from _pytest.python import Class as Class
from _pytest.python import Function as Function
from _pytest.python import Metafunc as Metafunc
from _pytest.python import Module as Module
from _pytest.python import Package as Package
from _pytest.python_api import approx as approx
from _pytest.python_api import raises as raises
from _pytest.recwarn import WarningsRecorder as WarningsRecorder
from _pytest.recwarn import deprecated_call as deprecated_call
from _pytest.recwarn import warns as warns
from _pytest.reports import CollectReport as CollectReport
from _pytest.reports import TestReport as TestReport
from _pytest.runner import CallInfo as CallInfo
from _pytest.stash import Stash as Stash
from _pytest.stash import StashKey as StashKey
from _pytest.tmpdir import TempPathFactory as TempPathFactory
from _pytest.warning_types import (
    PytestAssertRewriteWarning as PytestAssertRewriteWarning,
)
from _pytest.warning_types import PytestCacheWarning as PytestCacheWarning
from _pytest.warning_types import PytestCollectionWarning as PytestCollectionWarning
from _pytest.warning_types import PytestConfigWarning as PytestConfigWarning
from _pytest.warning_types import PytestDeprecationWarning as PytestDeprecationWarning
from _pytest.warning_types import (
    PytestExperimentalApiWarning as PytestExperimentalApiWarning,
)
from _pytest.warning_types import PytestRemovedIn8Warning as PytestRemovedIn8Warning
from _pytest.warning_types import (
    PytestReturnNotNoneWarning as PytestReturnNotNoneWarning,
)
from _pytest.warning_types import (
    PytestUnhandledCoroutineWarning as PytestUnhandledCoroutineWarning,
)
from _pytest.warning_types import (
    PytestUnhandledThreadExceptionWarning as PytestUnhandledThreadExceptionWarning,
)
from _pytest.warning_types import PytestUnknownMarkWarning as PytestUnknownMarkWarning
from _pytest.warning_types import (
    PytestUnraisableExceptionWarning as PytestUnraisableExceptionWarning,
)
from _pytest.warning_types import PytestWarning as PytestWarning
from _typeshed import Incomplete

set_trace: Incomplete

import typing as tp
from unittest import mock

from photons_pytest import FutureDominoes
from tests.photons_web_server_tests.conftest import IsInstance

class helpers:
    @staticmethod
    def free_port() -> int: ...
    @staticmethod
    async def wait_for_port(port: int, timeout: float = 3, gap: float = 0.01) -> None: ...

    AsyncMock: tp.ClassVar[type[mock.AsyncMock]]
    IsInstance: tp.ClassVar[type[IsInstance]]
    FutureDominoes: tp.ClassVar[type[FutureDominoes]]

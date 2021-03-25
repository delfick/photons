from photons_app.errors import ApplicationStopped, PhotonsAppError
from photons_app.tasks.tasks import NewTask as Task, GracefulTask
from photons_app import helpers as hp

from contextlib import ExitStack
from textwrap import dedent
import subprocess
import platform
import asyncio
import inspect
import signal
import pytest
import sys
import os

if hasattr(asyncio, "exceptions"):
    cancelled_error_name = "asyncio.exceptions.CancelledError"
else:
    cancelled_error_name = "concurrent.futures._base.CancelledError"


class RunAsExternal:
    def __init__(
        self,
        task_kls,
        basekls="from photons_app.tasks.tasks import NewTask as Task",
    ):
        self.script = (
            basekls
            + "\n"
            + dedent(inspect.getsource(task_kls))
            + "\n"
            + dedent(
                """
            from photons_app.errors import ApplicationCancelled, ApplicationStopped, UserQuit, PhotonsAppError
            from photons_app.tasks.runner import Runner
            from photons_app.collector import Collector
            from photons_app import helpers as hp

            import asyncio
            import signal
            import sys
            import os

            def notify():
                os.kill(int(sys.argv[2]), signal.SIGUSR1)

            collector = Collector()
            collector.prepare(None, {})
        """
            )
            + "\n"
            + f"{task_kls.__name__}.create(collector).run_loop(collector=collector, notify=notify, output=sys.argv[1])"
        )

    def __enter__(self):
        self.exit_stack = ExitStack()
        self.exit_stack.__enter__()

        self.fle = self.exit_stack.enter_context(hp.a_temp_file())
        self.fle.write(self.script.encode())
        self.fle.flush()

        self.out = self.exit_stack.enter_context(hp.a_temp_file())
        self.out.close()
        os.remove(self.out.name)

        return self.run

    def __exit__(self, exc_typ, exc, tb):
        if hasattr(self, "exit_stack"):
            self.exit_stack.__exit__(exc_typ, exc, tb)

    async def run(
        self,
        sig=None,
        expected_stdout=None,
        expected_stderr=None,
        expected_output=None,
        extra_argv=None,
        *,
        code,
    ):

        fut = hp.create_future()

        def ready(signum, frame):
            fut.set_result(True)

        signal.signal(signal.SIGUSR1, ready)

        pipe = subprocess.PIPE
        cmd = [
            sys.executable,
            self.fle.name,
            self.out.name,
            str(os.getpid()),
            *[str(a) for a in (extra_argv or [])],
        ]

        p = subprocess.Popen(
            cmd,
            stdout=pipe,
            stderr=pipe,
        )

        await fut

        if sig is not None:
            p.send_signal(sig)

        p.wait(timeout=1)

        got_stdout = p.stdout.read().decode()
        got_stderr = p.stderr.read().decode().split("\n")

        redacted_stderr = []
        in_tb = False

        last_line = None
        for line in got_stderr:
            if last_line == "During handling of the above exception, another exception occurred:":
                redacted_stderr = redacted_stderr[:-5]
                last_line = line
                continue

            if in_tb and not line.startswith(" "):
                in_tb = False

            if line.startswith("Traceback"):
                in_tb = True
                redacted_stderr.append(line)
                redacted_stderr.append("  <REDACTED>")

            if not in_tb:
                redacted_stderr.append(line)

            last_line = line

        got_stderr = "\n".join(redacted_stderr)

        print("=== STDOUT:")
        print(got_stdout)
        print("=== STDERR:")
        print(got_stderr)

        def assertOutput(out, regex):
            if regex is None:
                return

            regex = dedent(regex).strip()

            out = out.strip()
            regex = regex.strip()
            assert len(out.split("\n")) == len(regex.split("\n"))
            pytest.helpers.assertRegex(f"(?m){regex}", out)

        if expected_output is not None:
            got = None
            if os.path.exists(self.out.name):
                with open(self.out.name) as o:
                    got = o.read().strip()
            assert got == expected_output.strip()

        assertOutput(got_stdout.strip(), expected_stdout)
        assertOutput(got_stderr.strip(), expected_stderr)

        assert p.returncode == code

        return got_stdout, got_stderr


class RunAsExternalGraceful(RunAsExternal):
    def __init__(self, task_kls, basekls="from photons_app.tasks.tasks import GracefulTask"):
        super().__init__(task_kls, basekls=basekls)


class TestRunnerSignals:
    """
    I want to inspect.getsource on the `T` classes in these tests

    But I can't do that if I'm using noseOfYeti, sigh
    """

    async def test_it_works(self):
        class A(Task):
            """Run inside an external script during test via subprocess"""

            async def execute_task(self, notify, output, **kwargs):
                notify()
                with open(output, "w") as fle:
                    fle.write("HI")

        expected_stdout = ""
        expected_stderr = ""
        expected_output = "HI"

        with RunAsExternal(A) as assertRuns:
            await assertRuns(
                expected_output=expected_output,
                expected_stdout=expected_stdout,
                expected_stderr=expected_stderr,
                code=0,
            )

    async def test_it_puts_UserQuit_on_final_future_on_SIGINT(self):
        class B(Task):
            """Run inside an external script during test via subprocess"""

            async def execute_task(self, collector, notify, output, **kwargs):
                try:
                    notify()
                    await hp.create_future()
                finally:
                    with open(output, "w") as fle:
                        fle.write(str(collector.photons_app.final_future.exception()))

        expected_stdout = ""

        expected_stderr = r"""
        Traceback \(most recent call last\):
          <REDACTED>
        delfick_project.errors.UserQuit: "User Quit"
        """

        expected_output = '"User Quit"'

        with RunAsExternal(B) as assertRuns:
            await assertRuns(
                expected_output=expected_output,
                expected_stdout=expected_stdout,
                expected_stderr=expected_stderr,
                sig=signal.SIGINT,
                code=1,
            )

    async def test_ensures_with_statements_get_cleaned_up_when_we_have_an_exception(self):
        class C(Task):
            """Run inside an external script during test via subprocess"""

            async def execute_task(self, notify, output, **kwargs):
                try:
                    notify()
                    raise PhotonsAppError("WAT")
                finally:
                    with open(output, "w") as fle:
                        fle.write("FINALLY")

        expected_stdout = ""

        expected_stderr = r"""
        Traceback \(most recent call last\):
          <REDACTED>
        photons_app.errors.PhotonsAppError: "WAT"
        """

        expected_output = "FINALLY"

        with RunAsExternal(C) as assertRuns:
            await assertRuns(
                expected_output=expected_output,
                expected_stdout=expected_stdout,
                expected_stderr=expected_stderr,
                code=1,
            )

    async def test_ensures_async_generates_are_closed_on_sigint(self):
        class D(Task):
            """Run inside an external script during test via subprocess"""

            async def execute_task(self, notify, output, **kwargs):
                async def gen():
                    try:
                        notify()
                        await asyncio.sleep(10)
                        yield 1
                    except asyncio.CancelledError:
                        with open(output, "w") as fle:
                            fle.write("CANCELLED")
                        raise
                    finally:
                        with open(output, "a") as fle:
                            fle.write(str(sys.exc_info()[0]))

                async for i in gen():
                    pass

        expected_stdout = ""

        expected_stderr = r"""
        Traceback \(most recent call last\):
          <REDACTED>
        delfick_project.errors.UserQuit: "User Quit"
        """

        expected_output = f"CANCELLED<class '{cancelled_error_name}'>"

        with RunAsExternal(D) as assertRuns:
            await assertRuns(
                expected_output=expected_output,
                expected_stdout=expected_stdout,
                expected_stderr=expected_stderr,
                sig=signal.SIGINT,
                code=1,
            )

    async def test_it_says_the_program_was_cancelled_if_quit_with_CancelledError(self):
        class E(Task):
            """Run inside an external script during test via subprocess"""

            async def execute_task(self, notify, output, **kwargs):
                try:
                    fut = hp.create_future()
                    fut.cancel()
                    notify()
                    await fut
                except asyncio.CancelledError:
                    with open(output, "w") as fle:
                        fle.write("CANCELLED")
                    raise
                finally:
                    with open(output, "a") as fle:
                        fle.write(str(sys.exc_info()[0]))

        expected_stdout = ""

        expected_stderr = r"""
        Traceback \(most recent call last\):
          <REDACTED>
        photons_app.errors.ApplicationCancelled: "The application itself was cancelled"
        """

        expected_output = f"CANCELLED<class '{cancelled_error_name}'>"

        with RunAsExternal(E) as assertRuns:
            await assertRuns(
                expected_output=expected_output,
                expected_stdout=expected_stdout,
                expected_stderr=expected_stderr,
                code=1,
            )

    async def test_stops_the_program_on_SIGTERM(self):
        if platform.system() == "Windows":
            return

        class F(Task):
            """Run inside an external script during test via subprocess"""

            async def execute_task(self, collector, notify, output, **kwargs):
                try:
                    notify()
                    await collector.photons_app.final_future
                except ApplicationStopped:
                    with open(output, "w") as fle:
                        fle.write("STOPPED")
                    raise
                except:
                    with open(output, "w") as fle:
                        fle.write(f"Stopped incorrectly {sys.exc_info()}")
                    raise
                finally:
                    with open(output, "a") as fle:
                        fle.write(str(sys.exc_info()[0]))

        expected_stdout = ""

        expected_stderr = r"""
        Traceback \(most recent call last\):
          <REDACTED>
        photons_app.errors.ApplicationStopped: "The application itself was stopped"
        """

        expected_output = "STOPPED<class 'photons_app.errors.ApplicationStopped'>"

        with RunAsExternal(F) as assertRuns:
            await assertRuns(
                expected_output=expected_output,
                expected_stdout=expected_stdout,
                expected_stderr=expected_stderr,
                sig=signal.SIGTERM,
                code=1,
            )


class TestGracefulRunnerSignals:
    """
    I want to inspect.getsource on the `T` classes in these tests

    But I can't do that if I'm using noseOfYeti, sigh
    """

    async def test_it_works(self):
        class G(GracefulTask):
            """Run inside an external script during test via subprocess"""

            async def execute_task(self, notify, output, **kwargs):
                notify()
                with open(output, "w") as fle:
                    fle.write("HI")

        expected_stdout = ""
        expected_stderr = ""
        expected_output = "HI"

        with RunAsExternalGraceful(G) as assertRuns:
            await assertRuns(
                expected_output=expected_output,
                expected_stdout=expected_stdout,
                expected_stderr=expected_stderr,
                code=0,
            )

    @pytest.mark.parametrize("sig", [signal.SIGINT, signal.SIGTERM, None])
    async def test_it_doesnt_kill_task_when_graceful_happens(self, sig):
        class H(GracefulTask):
            """Run inside an external script during test via subprocess"""

            async def execute_task(
                self, collector, notify, output, graceful_final_future, **kwargs
            ):
                notify()
                if sys.argv[3] == "None":
                    graceful_final_future.cancel()
                await hp.wait_for_all_futures(graceful_final_future)
                assert not collector.photons_app.final_future.done()
                with open(output, "w") as fle:
                    fle.write("still ran!")

        expected_output = "still ran!"

        with RunAsExternalGraceful(H) as assertRuns:
            stdout, stderr = await assertRuns(
                expected_output=expected_output,
                sig=sig,
                extra_argv=[str(sig)],
                code=0 if sig in (signal.SIGTERM, None) else 1,
            )

            for word in ("asyncio", "RuntimeError", "InvalidState"):
                assert word not in stdout
                assert word not in stderr

    async def test_it_passes_on_exception_when_task_raises_exception(self):
        class J(GracefulTask):
            """Run inside an external script during test via subprocess"""

            def run_loop(self, **kwargs):
                try:
                    super().run_loop(**kwargs)
                finally:
                    output = kwargs["output"]
                    with open(output, "w") as fle:
                        print("ran", file=fle)
                    assert not self._final_future.cancelled(), "final future was cancelled"
                    assert self._graceful.cancelled()
                    assert (
                        self._final_future.exception() is self._error
                    ), "final future has wrong error"
                    with open(output, "a") as fle:
                        print("All good!", file=fle)

            async def execute_task(
                self, collector, notify, output, graceful_final_future, **kwargs
            ):
                self._final_future = collector.photons_app.final_future
                self._graceful = graceful_final_future
                self._error = PhotonsAppError("HI")
                notify()
                raise self._error

        expected_stdout = ""

        expected_output = "ran\nAll good!"

        expected_stderr = r"""
        Traceback \(most recent call last\):
          <REDACTED>
        photons_app.errors.PhotonsAppError: "HI"
        """

        with RunAsExternalGraceful(J) as assertRuns:
            await assertRuns(
                expected_output=expected_output,
                expected_stdout=expected_stdout,
                expected_stderr=expected_stderr,
                code=1,
            )

    async def test_interupting_graceful_is_exit_code_0(self):
        class K(GracefulTask):
            """Run inside an external script during test via subprocess"""

            async def execute_task(self, notify, graceful_final_future, output, **kwargs):
                notify()
                await hp.wait_for_all_futures(graceful_final_future)
                with open(output, "a") as fle:
                    print(graceful_final_future.exception(), file=fle)

        expected_stdout = ""

        expected_output = '"The application itself was stopped"'

        expected_stderr = ""

        with RunAsExternalGraceful(K) as assertRuns:
            await assertRuns(
                expected_output=expected_output,
                expected_stdout=expected_stdout,
                expected_stderr=expected_stderr,
                sig=signal.SIGTERM,
                code=0,
            )

    async def test_finishing_final_future_finishes_graceful_future(self):
        class L(GracefulTask):
            """Run inside an external script during test via subprocess"""

            async def execute_task(self, notify, graceful_final_future, output, **kwargs):
                notify()
                self.collector.photons_app.loop.call_soon(
                    self.collector.photons_app.final_future.set_exception, ValueError("NOPE")
                )
                with open(output, "a") as fle:
                    print("before", file=fle)
                await hp.wait_for_all_futures(graceful_final_future)
                with open(output, "a") as fle:
                    print("after", file=fle)

        expected_stdout = ""

        expected_output = "before\nafter"

        expected_stderr = r"""
        Traceback \(most recent call last\):
          <REDACTED>
        ValueError: NOPE
        """

        with RunAsExternalGraceful(L) as assertRuns:
            await assertRuns(
                expected_output=expected_output,
                expected_stdout=expected_stdout,
                expected_stderr=expected_stderr,
                code=1,
            )

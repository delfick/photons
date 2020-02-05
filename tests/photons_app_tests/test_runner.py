# coding: spec

from photons_app.runner import run, on_done_task
from photons_app import helpers as hp

from delfick_project.errors_pytest import assertRaises
from textwrap import dedent
from unittest import mock
import subprocess
import platform
import asyncio
import signal
import socket
import pytest
import time
import sys
import os

if hasattr(asyncio, "exceptions"):
    cancelled_error_name = "asyncio.exceptions.CancelledError"
else:
    cancelled_error_name = "concurrent.futures._base.CancelledError"

describe "run":

    def assertRunnerBehaviour(
        self, script, expected_finally_block, expected_stdout, expected_stderr, sig=signal.SIGINT
    ):
        with hp.a_temp_file() as fle:
            fle.write(script.encode())
            fle.flush()

            with hp.a_temp_file() as out, hp.a_temp_file() as ss:
                out.close()
                ss.close()

                os.remove(out.name)
                os.remove(ss.name)

                s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                s.bind(ss.name)
                s.listen(1)

                pipe = subprocess.PIPE
                p = subprocess.Popen(
                    [sys.executable, fle.name, out.name, ss.name], stdout=pipe, stderr=pipe
                )
                s.accept()
                time.sleep(0.1)

                p.send_signal(sig)
                p.wait(timeout=2)

                got_stdout = p.stdout.read().decode()
                got_stderr = p.stderr.read().decode()

                print("=== STDOUT:")
                print(got_stdout)
                print("=== STDERR:")
                print(got_stderr)

                def assertOutput(out, regex):
                    out = out.strip()
                    regex = regex.strip()
                    assert len(out.split("\n")) == len(regex.split("\n"))
                    pytest.helpers.assert_regex(f"(?m){regex}", out)

                assertOutput(got_stdout, expected_stdout)
                assertOutput(got_stderr, expected_stderr)

                with open(out.name) as o:
                    got = o.read()
                assert got.strip() == expected_finally_block.strip()

    it "ensures with statements get cleaned up on SIGINT":
        script = dedent(
            """
        from photons_app.actions import an_action

        from delfick_project.addons import addon_hook
        import asyncio
        import socket
        import sys

        @addon_hook()
        def __lifx__(*args, **kwargs):
            pass

        @an_action()
        async def a_test(collector, reference, artifact, **kwargs):
            try:
                s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                s.connect(artifact)
                s.close()

                await asyncio.sleep(20)
            finally:
                with open(reference, 'w') as fle:
                    fle.write("FINALLY")

        if __name__ == "__main__":
            from photons_app.executor import main
            import sys
            main(["a_test"] + sys.argv[1:])
        """
        )

        expected_stdout = dedent(
            """
        !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
        Something went wrong! -- UserQuit
        \t"User Quit"
        """
        )

        expected_stderr = dedent(
            r"""
        [^I]+INFO\s+delfick_project.option_merge.collector Adding configuration from .+
        [^I]+INFO\s+delfick_project.addons Found lifx.photons.__main__ addon
        [^I]+INFO\s+delfick_project.option_merge.collector Converting photons_app
        [^I]+INFO\s+delfick_project.option_merge.collector Converting target_register
        [^I]+INFO\s+delfick_project.option_merge.collector Converting targets
        """
        )

        self.assertRunnerBehaviour(script, "FINALLY", expected_stdout, expected_stderr)

    it "ensures with statements get cleaned up on SIGINT when we have an exception":
        script = dedent(
            """
        from photons_app.errors import PhotonsAppError
        from photons_app.actions import an_action

        from delfick_project.addons import addon_hook
        import socket
        import sys

        @addon_hook()
        def __lifx__(*args, **kwargs):
            pass

        @an_action()
        async def a_test(collector, reference, artifact, **kwargs):
            try:
                s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                s.connect(artifact)
                s.close()
                raise PhotonsAppError("WAT")
            finally:
                with open(reference, 'w') as fle:
                    fle.write("FINALLY")

        if __name__ == "__main__":
            from photons_app.executor import main
            import sys
            main(["a_test"] + sys.argv[1:])
        """
        )

        expected_stdout = dedent(
            r"""
        !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
        Something went wrong! -- PhotonsAppError
        \t"WAT"
        """
        )

        expected_stderr = dedent(
            r"""
        [^I]+INFO\s+delfick_project.option_merge.collector Adding configuration from .+
        [^I]+INFO\s+delfick_project.addons Found lifx.photons.__main__ addon
        [^I]+INFO\s+delfick_project.option_merge.collector Converting photons_app
        [^I]+INFO\s+delfick_project.option_merge.collector Converting target_register
        [^I]+INFO\s+delfick_project.option_merge.collector Converting targets
        """
        )

        self.assertRunnerBehaviour(script, "FINALLY", expected_stdout, expected_stderr)

    it "ensures async generators are closed on SIGINT":
        script = dedent(
            """
        from photons_app.actions import an_action

        from delfick_project.addons import addon_hook
        import asyncio
        import socket
        import sys

        @addon_hook()
        def __lifx__(*args, **kwargs):
            pass

        async def gen(out, sock):
            try:
                s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                s.connect(sock)
                s.close()

                await asyncio.sleep(10)
                yield 1
            except asyncio.CancelledError:
                with open(out, 'w') as fle:
                    fle.write("CANCELLED")
                raise
            finally:
                with open(out, 'a') as fle:
                    fle.write(str(sys.exc_info()[0]))

        @an_action()
        async def a_test(collector, reference, artifact, **kwargs):
            async for i in gen(reference, artifact):
                pass

        if __name__ == "__main__":
            from photons_app.executor import main
            import sys
            main(["a_test"] + sys.argv[1:])
        """
        )

        expected_stdout = dedent(
            r"""
        !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
        Something went wrong! -- UserQuit
        \t"User Quit"
        """
        )

        expected_stderr = dedent(
            r"""
        [^I]+INFO\s+delfick_project.option_merge.collector Adding configuration from .+
        [^I]+INFO\s+delfick_project.addons Found lifx.photons.__main__ addon
        [^I]+INFO\s+delfick_project.option_merge.collector Converting photons_app
        [^I]+INFO\s+delfick_project.option_merge.collector Converting target_register
        [^I]+INFO\s+delfick_project.option_merge.collector Converting targets
        """
        )

        self.assertRunnerBehaviour(
            script, f"CANCELLED<class '{cancelled_error_name}'>", expected_stdout, expected_stderr,
        )

    it "stops the program on SIGTERM":
        if platform.system() == "Windows":
            return

        script = dedent(
            """
        from photons_app.actions import an_action

        from delfick_project.addons import addon_hook
        import asyncio
        import socket
        import sys

        @addon_hook()
        def __lifx__(*args, **kwargs):
            pass

        async def gen(out, sock):
            try:
                s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                s.connect(sock)
                s.close()

                await asyncio.sleep(10)
                yield 1
            except asyncio.CancelledError:
                with open(out, 'w') as fle:
                    fle.write("CANCELLED")
                raise
            finally:
                with open(out, 'a') as fle:
                    fle.write(str(sys.exc_info()[0]))

        @an_action()
        async def a_test(collector, reference, artifact, **kwargs):
            async for i in gen(reference, artifact):
                pass

        if __name__ == "__main__":
            from photons_app.executor import main
            import sys
            main(["a_test"] + sys.argv[1:])
        """
        )

        expected_stdout = dedent(
            r"""
        !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
        Something went wrong! -- ApplicationCancelled
        \t"The application itself was shutdown"
        """
        )

        expected_stderr = dedent(
            r"""
        [^I]+INFO\s+delfick_project.option_merge.collector Adding configuration from .+
        [^I]+INFO\s+delfick_project.addons Found lifx.photons.__main__ addon
        [^I]+INFO\s+delfick_project.option_merge.collector Converting photons_app
        [^I]+INFO\s+delfick_project.option_merge.collector Converting target_register
        [^I]+INFO\s+delfick_project.option_merge.collector Converting targets
        """
        )

        self.assertRunnerBehaviour(
            script,
            f"CANCELLED<class '{cancelled_error_name}'>",
            expected_stdout,
            expected_stderr,
            sig=signal.SIGTERM,
        )

    it "runs the collector and runs cleanup when that's done":
        info = {"cleaned": False, "ran": False}

        loop = asyncio.new_event_loop()
        final_future = asyncio.Future(loop=loop)

        target_register = mock.Mock(name="target_register")

        async def cleanup(tr):
            assert tr == target_register.used_targets
            await asyncio.sleep(0.01)
            info["cleaned"] = True

        async def doit():
            await asyncio.sleep(0.01)
            info["ran"] = True

        photons_app = mock.Mock(
            name="photons_app",
            loop=loop,
            chosen_task="task",
            reference="reference",
            final_future=final_future,
        )
        photons_app.cleanup.side_effect = cleanup

        run(doit(), photons_app, target_register)
        assert info == {"cleaned": True, "ran": True}

    it "cleans up even if runner raise an exception":
        info = {"cleaned": False, "ran": False}

        loop = asyncio.new_event_loop()
        final_future = asyncio.Future(loop=loop)

        target_register = mock.Mock(name="target_register")

        async def cleanup(tr):
            assert tr == target_register.used_targets
            await asyncio.sleep(0.01)
            info["cleaned"] = True

        async def doit():
            await asyncio.sleep(0.01)
            info["ran"] = True
            raise ValueError("Nope")

        photons_app = mock.Mock(
            name="photons_app",
            loop=loop,
            chosen_task="task",
            reference="reference",
            final_future=final_future,
        )
        photons_app.cleanup.side_effect = cleanup

        with assertRaises(ValueError, "Nope"):
            run(doit(), photons_app, target_register)

        assert info == {"cleaned": True, "ran": True}

    describe "on_done_task":
        it "sets exception on final future if one is risen":
            final_future = asyncio.Future()

            error = Exception("wat")
            fut = asyncio.Future()
            fut.set_exception(error)

            on_done_task(final_future, fut)
            assert final_future.exception() == error

        it "sets exception on final future if one is risen unless it's already cancelled":
            final_future = asyncio.Future()
            final_future.cancel()

            error = Exception("wat")
            fut = asyncio.Future()
            fut.set_exception(error)

            on_done_task(final_future, fut)
            assert final_future.cancelled()

        it "doesn't fail if the final_future is already cancelled when the task finishes":
            final_future = asyncio.Future()
            final_future.cancel()

            fut = asyncio.Future()
            fut.set_result(None)

            on_done_task(final_future, fut)
            assert final_future.cancelled()

        it "doesn't fail if the final_future is already done when the task finishes":
            final_future = asyncio.Future()
            final_future.set_result(None)

            fut = asyncio.Future()
            fut.set_result(None)

            on_done_task(final_future, fut)
            assert final_future.result() == None

        it "doesn't fail if the final_future already has an exception when the task finishes":
            final_future = asyncio.Future()
            error = Exception("WAT")
            final_future.set_exception(error)

            fut = asyncio.Future()
            fut.set_result(None)

            on_done_task(final_future, fut)
            assert final_future.exception() == error

        it "doesn't fail if the final_future already has an exception when the task has an error":
            final_future = asyncio.Future()
            error = Exception("WAT")
            final_future.set_exception(error)

            fut = asyncio.Future()
            error2 = Exception("WAT2")
            fut.set_exception(error2)

            on_done_task(final_future, fut)
            assert final_future.exception() == error

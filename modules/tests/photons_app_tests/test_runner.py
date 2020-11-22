# coding: spec

from photons_app.errors import ApplicationCancelled, ApplicationStopped
from photons_app.option_spec.photons_app_spec import PhotonsApp
from photons_app.formatter import MergedOptionStringFormatter
from photons_app.runner import run, transfer_result
from photons_app import helpers as hp

from delfick_project.errors_pytest import assertRaises
from delfick_project.norms import Meta
from contextlib import contextmanager
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


@contextmanager
def make_photons_app(cleanup, **options):
    photons_app = PhotonsApp.FieldSpec(formatter=MergedOptionStringFormatter).normalise(
        Meta({}, []).at("photons_app"), options
    )

    photons_app.loop = asyncio.new_event_loop()

    with mock.patch.object(photons_app, "cleanup", cleanup):
        yield photons_app


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
                s.settimeout(2)
                s.bind(ss.name)
                s.listen(1)

                pipe = subprocess.PIPE
                p = subprocess.Popen(
                    [sys.executable, fle.name, out.name, ss.name], stdout=pipe, stderr=pipe
                )

                if sig is not None:
                    try:
                        s.accept()
                        time.sleep(0.1)
                    except socket.timeout:
                        pass

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

    it "SIGINT gets given a UserQuit":
        script = dedent(
            """
        from photons_app.actions import an_action
        from photons_app.errors import UserQuit

        from delfick_project.addons import addon_hook
        import asyncio
        import socket
        import sys

        @addon_hook()
        def __lifx__(*args, **kwargs):
            pass

        @an_action()
        async def a_test(collector, reference, artifact, **kwargs):
            photons_app = collector.photons_app

            # KeyboardInterrupt is special and requires the graceful future
            # Otherwise the error that we get from the final_future is
            # asyncio.CancelledError because final_future gets cancelled
            # before this task has time to act on the UserQuit
            with photons_app.using_graceful_future() as final_future:
                try:
                    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                    s.connect(artifact)
                    s.close()
                    await final_future
                except UserQuit:
                    with open(reference, 'w') as fle:
                        fle.write("USERQUIT")
                finally:
                    # So python is a bit strange in that KeyboardInterrupt is special
                    # And sys.exc_info() here is the KeyboardInterrupt rather than the UserQuit
                    with open(reference, 'a') as fle:
                        fle.write(str(sys.exc_info()[0]))

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

        self.assertRunnerBehaviour(
            script,
            "USERQUIT<class 'KeyboardInterrupt'>",
            expected_stdout,
            expected_stderr,
            sig=signal.SIGINT,
        )

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
            script, f"CANCELLED<class '{cancelled_error_name}'>", expected_stdout, expected_stderr
        )

    it "says the program was cancelled if the program quits with asyncio.CancelledError":
        if platform.system() == "Windows":
            return

        script = dedent(
            """
        from photons_app.actions import an_action
        from photons_app import helpers as hp

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
                fut = hp.create_future()
                fut.cancel()
                await fut
            except asyncio.CancelledError:
                with open(reference, 'w') as fle:
                    fle.write("CANCELLED")
                raise
            finally:
                with open(reference, 'a') as fle:
                    fle.write(str(sys.exc_info()[0]))

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
        \t"The application itself was cancelled"
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
            sig=None,
        )

    it "stops the program on SIGTERM":
        if platform.system() == "Windows":
            return

        script = dedent(
            """
        from photons_app.errors import ApplicationCancelled, UserQuit, ApplicationStopped
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

                await collector.photons_app.final_future
            except (asyncio.CancelledError, ApplicationCancelled, UserQuit):
                with open(reference, 'w') as fle:
                    fle.write(f"Stopped incorrectly {sys.exc_info()}")
                raise
            except ApplicationStopped:
                with open(reference, 'w') as fle:
                    fle.write("STOPPED")
                raise
            finally:
                with open(reference, 'a') as fle:
                    fle.write(str(sys.exc_info()[0]))

        if __name__ == "__main__":
            from photons_app.executor import main
            import sys
            main(["a_test"] + sys.argv[1:])
        """
        )

        expected_stdout = dedent(
            r"""
        !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
        Something went wrong! -- ApplicationStopped
        \t"The application itself was stopped"
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
            "STOPPED<class 'photons_app.errors.ApplicationStopped'>",
            expected_stdout,
            expected_stderr,
            sig=signal.SIGTERM,
        )

    it "runs the collector and runs cleanup when that's done":
        info = {"cleaned": False, "ran": False}

        target_register = mock.Mock(name="target_register")

        async def cleanup(tr):
            assert tr == target_register.used_targets
            await asyncio.sleep(0.01)
            info["cleaned"] = True

        async def doit():
            await asyncio.sleep(0.01)
            info["ran"] = True

        with make_photons_app(cleanup) as photons_app:
            run(doit(), photons_app, target_register)

        assert info == {"cleaned": True, "ran": True}

    it "cleans up even if runner raise an exception":
        info = {"cleaned": False, "ran": False}

        target_register = mock.Mock(name="target_register")

        async def cleanup(tr):
            assert tr == target_register.used_targets
            await asyncio.sleep(0.01)
            info["cleaned"] = True

        async def doit():
            await asyncio.sleep(0.01)
            info["ran"] = True
            raise ValueError("Nope")

        with make_photons_app(cleanup) as photons_app:
            with assertRaises(ValueError, "Nope"):
                run(doit(), photons_app, target_register)

        assert info == {"cleaned": True, "ran": True}

    it "cleans up before we finish task if it's cancelled outside":
        info = {
            "ran": None,
            "cleaned": None,
            "cleaned_in_except": None,
            "cleaned_in_finally": None,
        }

        target_register = mock.Mock(name="target_register")

        async def cleanup(tr):
            assert tr == target_register.used_targets
            await asyncio.sleep(0.01)
            info["cleaned"] = True

        async def doit():
            info["ran"] = True
            try:
                asyncio.get_event_loop().call_later(0.02, photons_app.final_future.cancel)
                await asyncio.sleep(10)
            except:
                await asyncio.sleep(0.05)
                info["cleaned_in_except"] = info["cleaned"]
                raise
            finally:
                info["cleaned_in_finally"] = info["cleaned"]

        with make_photons_app(cleanup) as photons_app:
            with assertRaises(ApplicationCancelled):
                run(doit(), photons_app, target_register)

        assert info == {
            "ran": True,
            "cleaned": True,
            "cleaned_in_except": None,
            "cleaned_in_finally": None,
        }

    it "has a graceful future ability so that the application stops before final_future is done":
        info = {
            "ran": None,
            "cleaned": None,
            "exception": None,
            "cleaned_in_except": None,
            "cleaned_in_finally": None,
            "final_future_in_hanging": None,
            "final_future_done_in_except": None,
            "final_future_done_in_finally": None,
            "final_future_done_in_cleanup": None,
        }

        fut = {"final": None}

        target_register = mock.Mock(name="target_register")

        async def cleanup(tr):
            assert tr == target_register.used_targets
            await asyncio.sleep(0.01)
            info["cleaned"] = True
            info["final_future_done_in_cleanup"] = fut["final"].done()

        async def doit(photons_app):
            info["ran"] = True

            async def hanging():
                # This task will be cancelled in cleanup
                try:
                    await asyncio.sleep(20)
                finally:
                    info["final_future_in_hanging"] = fut["final"].done()

            asyncio.get_event_loop().create_task(hanging())

            asyncio.get_event_loop().call_later(
                0.02, photons_app.graceful_final_future.set_exception, ApplicationStopped
            )

            with photons_app.using_graceful_future() as final_future:
                try:
                    await final_future
                except:
                    info["exception"] = sys.exc_info()[0]
                    await asyncio.sleep(0.05)
                    info["final_future_done_in_except"] = fut["final"].done()
                    info["cleaned_in_except"] = info["cleaned"]
                    raise
                finally:
                    info["cleaned_in_finally"] = info["cleaned"]
                    info["final_future_done_in_finally"] = fut["final"].done()

        with make_photons_app(cleanup) as photons_app:
            fut["final"] = photons_app.final_future

            with assertRaises(ApplicationStopped):
                run(doit(photons_app), photons_app, target_register)

        assert info == {
            "ran": True,
            "cleaned": True,
            "cleaned_in_except": None,
            "cleaned_in_finally": None,
            "exception": ApplicationStopped,
            "final_future_done_in_except": False,
            "final_future_done_in_finally": False,
            "final_future_done_in_cleanup": False,
            "final_future_in_hanging": True,
        }

    describe "transfer_result":
        it "sets exception on final future if one is risen":
            final_future = hp.create_future()

            error = Exception("wat")
            fut = hp.create_future()
            fut.set_exception(error)

            transfer_result(fut, final_future)
            assert final_future.exception() == error

        it "sets exception on final future if one is risen unless it's already cancelled":
            final_future = hp.create_future()
            final_future.cancel()

            error = Exception("wat")
            fut = hp.create_future()
            fut.set_exception(error)

            transfer_result(fut, final_future)
            assert final_future.cancelled()

        it "doesn't fail if the final_future is already cancelled when the task finishes":
            final_future = hp.create_future()
            final_future.cancel()

            fut = hp.create_future()
            fut.set_result(None)

            transfer_result(fut, final_future)
            assert final_future.cancelled()

        it "doesn't fail if the final_future is already done when the task finishes":
            final_future = hp.create_future()
            final_future.set_result(None)

            fut = hp.create_future()
            fut.set_result(None)

            transfer_result(fut, final_future)
            assert final_future.result() is None

        it "doesn't fail if the final_future already has an exception when the task finishes":
            final_future = hp.create_future()
            error = Exception("WAT")
            final_future.set_exception(error)

            fut = hp.create_future()
            fut.set_result(None)

            transfer_result(fut, final_future)
            assert final_future.exception() == error

        it "doesn't fail if the final_future already has an exception when the task has an error":
            final_future = hp.create_future()
            error = Exception("WAT")
            final_future.set_exception(error)

            fut = hp.create_future()
            error2 = Exception("WAT2")
            fut.set_exception(error2)

            transfer_result(fut, final_future)
            assert final_future.exception() == error

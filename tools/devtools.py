import http.server
import inspect
import os
import platform
import shlex
import shutil
import socket
import socketserver
import sys
import threading
import time
import typing as tp
import webbrowser
from pathlib import Path

here = Path(__file__).parent

if platform.system() == "Windows":
    import mslex

    shlex = mslex  # noqa


class Command:
    __is_command__: bool

    def __call__(self, bin_dir: Path, args: list[str]) -> None: ...


def command(func: tp.Callable) -> tp.Callable:
    tp.cast(Command, func).__is_command__ = True
    return func


def run(*args: str | Path) -> None:
    cmd = " ".join(shlex.quote(str(part)) for part in args)
    print(f"Running '{cmd}'")
    ret = os.system(cmd)
    if ret != 0:
        sys.exit(1)


class App:
    commands: dict[str, Command]

    def __init__(self):
        self.commands = {}

        compare = inspect.signature(type("C", (Command,), {})().__call__)

        for name in dir(self):
            val = getattr(self, name)
            if getattr(val, "__is_command__", False):
                assert (
                    inspect.signature(val) == compare
                ), f"Expected '{name}' to have correct signature, have {inspect.signature(val)} instead of {compare}"
                self.commands[name] = val

    def __call__(self, args: list[str]) -> None:
        bin_dir = Path(sys.executable).parent

        if args and args[0] in self.commands:
            os.chdir(here.parent)
            self.commands[args[0]](bin_dir, args[1:])
            return

        sys.exit(f"Unknown command:\nAvailable: {sorted(self.commands)}\nWanted: {args}")

    @command
    def format(self, bin_dir: Path, args: list[str]) -> None:
        if not args:
            args = [".", *args]
        run(bin_dir / "black", *args)
        run(bin_dir / "isort", *args)

    @command
    def lint(self, bin_dir: Path, args: list[str]) -> None:
        run(bin_dir / "pylama", *args)

    @command
    def tests(self, bin_dir: Path, args: list[str]) -> None:
        if "-q" not in args:
            args = ["-q", *args]

        env = os.environ
        env["NOSE_OF_YETI_BLACK_COMPAT"] = "false"
        for unwanted in ("HARDCODED_DISCOVERY", "SERIAL_FILTER"):
            if unwanted in env:
                del env[unwanted]

        files: list[str] = []
        if "TESTS_CHDIR" in env:
            ags: list[str] = []
            test_dir = Path(env["TESTS_CHDIR"]).absolute()
            for a in args:
                test_name = ""
                if "::" in a:
                    filename, test_name = a.split("::", 1)
                else:
                    filename = a
                try:
                    p = Path(filename).absolute()
                except:
                    ags.append(a)
                else:
                    if p.exists():
                        rel = p.relative_to(test_dir)
                        if test_name:
                            files.append(f"{rel}::{test_name}")
                        else:
                            files.append(str(rel))
                    else:
                        ags.append(a)
            args = ags
            os.chdir(test_dir)

        run(bin_dir / "run_photons_core_tests", *files, *args)

    @command
    def tox(self, bin_dir: Path, args: list[str]) -> None:
        run(bin_dir / "tox", *args)

    @command
    def types(self, bin_dir: Path, args: list[str]) -> None:
        if args and args[0] == "restart":
            args.pop(0)
            run(bin_dir / "dmypy", "stop")

        files = []
        ags = ["run"]
        for a in args:
            if Path(a).exists():
                files.append(a)
            else:
                ags.append(a)

        args = ags
        if not files:
            files.append(".")

        if "--" not in args:
            args.extend(["--", *files, "--show-column-numbers"])

        run(bin_dir / "dmypy", *args)

    @command
    def docs(self, bin_dir: Path, args: list[str]) -> None:
        docs_path = here / ".." / "docs"
        os.chdir(docs_path)

        os.environ["LIFX_CONFIG"] = str(docs_path / "docs.yml")
        run(bin_dir / "photons-docs", *args)


app = App()

if __name__ == "__main__":
    app(sys.argv[1:])

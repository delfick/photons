import os
import pathlib
import subprocess
import sys

import click
from photons_app.executor import lifx_main
from photons_docs.executor import main as docs_main

here = pathlib.Path(__file__).parent


def run(*args: str, env: dict[str, str] | None = None, cwd: pathlib.Path | None = None) -> None:
    try:
        subprocess.run(["/bin/bash", str(here / "uv"), "run", *args], env=env, cwd=cwd, check=True)
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode)


@click.group()
def cli() -> None:
    pass


@cli.command(context_settings=dict(ignore_unknown_options=True))
@click.argument("args", nargs=-1, type=click.UNPROCESSED)
def lifx(args: list[str]) -> None:
    lifx_main(args)


@cli.command(context_settings=dict(ignore_unknown_options=True))
@click.argument("args", nargs=-1, type=click.UNPROCESSED)
def docs(args: list[str]) -> None:
    os.environ["LIFX_CONFIG"] = str(here / ".." / "docs" / "docs.yml")
    docs_main(args)


@cli.command(context_settings=dict(ignore_unknown_options=True))
@click.argument("args", nargs=-1, type=click.UNPROCESSED)
def format(args: list[str]) -> None:
    """
    Run ruff format and ruff check fixing I and UP rules
    """
    if not args:
        args = [".", *args]
    try:
        subprocess.run([sys.executable, "-m", "ruff", "format", *args], check=True)
        subprocess.run(
            [sys.executable, "-m", "ruff", "check", "--fix", "--select", "I,UP", *args],
            check=True,
        )
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode)


@cli.command(context_settings=dict(ignore_unknown_options=True))
@click.argument("args", nargs=-1, type=click.UNPROCESSED)
def lint(args: list[str]) -> None:
    """
    Run ruff check
    """
    os.execv(sys.executable, [sys.executable, "-m", "ruff", "check", *args])


@cli.command(context_settings=dict(ignore_unknown_options=True))
@click.argument("args", nargs=-1, type=click.UNPROCESSED)
def types(args: list[str]) -> None:
    """
    Run mypy
    """
    locations: list[str] = [a for a in args if not a.startswith("-")]
    args = [a for a in args if a.startswith("-")]

    if not locations:
        locations.append(str((here / "..").resolve()))
    else:
        cwd = pathlib.Path.cwd()
        paths: list[pathlib.Path] = []
        for location in locations:
            from_current = cwd / location
            from_root = here.parent / location

            if from_current.exists():
                paths.append(from_current)
            elif from_root.exists():
                paths.append(from_root)
            else:
                raise ValueError(f"Couldn't find path for {location}")

        locations = [str(path) for path in paths]

    run("python", "-m", "mypy", *locations, *args)


def _test_args(args: list[str], cwd: pathlib.Path) -> tuple[list[str], dict[str, str]]:
    if "-q" not in args:
        args = ["-q", *args]

    env = dict(os.environ)
    for unwanted in ("HARDCODED_DISCOVERY", "SERIAL_FILTER"):
        if unwanted in env:
            del env[unwanted]

    files: list[str] = []

    ags: list[str] = []

    for a in args:
        test_name = ""
        if "::" in a:
            filename, test_name = a.split("::", 1)
        else:
            filename = a
        try:
            p = pathlib.Path(filename).absolute()
        except Exception:
            ags.append(a)
        else:
            if p.exists():
                rel = p.relative_to(cwd)
                if test_name:
                    files.append(f"{rel}::{test_name}")
                else:
                    files.append(str(rel))
            else:
                ags.append(a)

    return ags, env


@cli.command(context_settings=dict(ignore_unknown_options=True))
@click.argument("args", nargs=-1, type=click.UNPROCESSED)
def tests(args: list[str]) -> None:
    """
    Run core photons and interactor tests
    """
    module_tests(args)
    interactor_tests(args)


@cli.command(context_settings=dict(ignore_unknown_options=True))
@click.argument("args", nargs=-1, type=click.UNPROCESSED)
def module_tests(args: list[str]) -> None:
    """
    Run core photons tests
    """
    cwd = here / ".." / "modules"
    ags, env = _test_args(args, cwd)
    run("run_photons_core_tests", *ags, env=env, cwd=cwd)


@cli.command(context_settings=dict(ignore_unknown_options=True))
@click.argument("args", nargs=-1, type=click.UNPROCESSED)
def interactor_tests(args: list[str]) -> None:
    """
    Run pytest in apps/interactor
    """
    cwd = here / ".." / "apps" / "interactor"
    ags, env = _test_args(args, cwd)
    run("run_photons_core_tests", *ags, env=env, cwd=cwd)


@cli.command(context_settings=dict(ignore_unknown_options=True))
@click.argument("args", nargs=-1, type=click.UNPROCESSED)
def interactor_docker(args: list[str]) -> None:
    """
    Run harpoon for the interactor
    """
    harpoon_folder = here / ".." / "apps" / "interactor" / "docker"
    os.chdir(harpoon_folder)

    def run(*ags: str) -> None:
        try:
            subprocess.run(["/bin/bash", str(here / "uv"), "--directory", str(harpoon_folder), *ags], cwd=str(harpoon_folder), check=True)
        except subprocess.CalledProcessError as e:
            sys.exit(e.returncode)

    os.environ["VIRTUAL_ENV"] = ""

    run("sync")
    run("run", "harpoon", *args)


if __name__ == "__main__":
    cli()

#!/usr/bin/python3 -ci=__import__;o=i("os");s=i("sys");a=s.argv;p=o.path;y=p.join(p.dirname(a[1]),".python");o.execv(y,a)

import asyncio
import json
import logging
import readline
import sys
import threading
from textwrap import dedent

from delfick_project.logging import setup_logging
from photons_app import helpers as hp
from photons_app.errors import UserQuit
from photons_app.executor import library_setup
from photons_control.colour import ColourParser
from photons_control.device_finder import DeviceFinderDaemon, Filter

log = logging.getLogger("device_finder")


def write_prompt():
    sys.stdout.write("> ")
    sys.stdout.flush()


async def process_command(daemon, command):
    if " " not in command:
        options = ""
    else:
        command, options = command.split(" ", 1)

    if command.endswith("_json"):
        command = command[: command.rfind("_")]
        fltr = Filter.from_json_str(options)
    else:
        fltr = Filter.from_key_value_str(options)

    if command.startswith("serials"):
        async for device in daemon.serials(fltr):
            print(device.serial)
    elif command.startswith("info"):
        async for device in daemon.info(fltr):
            print(device.serial)
            print("\n".join(f"  {line}" for line in json.dumps(device.info, sort_keys=True, indent="  ").split("\n")))
    elif command.startswith("set_"):
        msg = ColourParser.msg(command[4:])
        await daemon.sender(msg, daemon.reference(fltr))
    else:
        print(
            dedent(
                """
            commands are of the form '(serials|info|set_<color>) KEY=VALUE KEY=VALUE ...'

            or of the form '(serials_json|info_json|set_<color>_json) {"key": "value", "key": "value"}'
        """
            )
        )


async def doit(collector):
    lan_target = collector.resolve_target("lan")
    final_future = collector.photons_app.final_future
    async with lan_target.session() as sender:
        async with DeviceFinderDaemon(sender, final_future=final_future) as daemon:
            await daemon.start()
            await run_prompt(daemon, final_future, collector.photons_app.loop)


async def run_prompt(daemon, final_future, loop):
    readline.parse_and_bind("")

    def get_command(done):
        try:
            nxt = input()
        except Exception as error:
            if isinstance(error, EOFError | KeyboardInterrupt):
                error = UserQuit()
            if not final_future.done():
                final_future.set_exception(error)

        if final_future.done():
            return

        loop.call_soon_threadsafe(done.set_result, nxt.strip())

    while True:
        write_prompt()

        done = hp.create_future(name="||run_prompt[done]")

        thread = threading.Thread(target=get_command, args=(done,))
        thread.daemon = True
        thread.start()

        nxt = await done

        if nxt:
            try:
                await process_command(daemon, nxt)
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("Unexpected error")

        if final_future.done():
            return


if __name__ == "__main__":
    setup_logging(level=logging.ERROR)
    collector = library_setup()
    collector.run_coro_as_main(doit(collector))

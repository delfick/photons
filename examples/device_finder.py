#!/usr/bin/python -ci=__import__;o=i("os");s=i("sys");a=s.argv;p=o.path;y=p.join(p.dirname(a[1]),".python");o.execv(y,a)

from photons_app.executor import library_setup

from photons_device_finder import DeviceFinder, Filter
from photons_control.colour import ColourParser

from delfick_project.logging import setup_logging
from textwrap import dedent
import readline
import asyncio
import logging
import json
import sys


log = logging.getLogger("device_finder")


def write_prompt():
    sys.stdout.write("> ")
    sys.stdout.flush()


async def process_command(lan_target, device_finder, command):
    if " " not in command:
        options = ""
    else:
        command, options = command.split(" ", 1)

    if command.endswith("_json"):
        command = command[: command.rfind("_")]
        filtr = Filter.from_json_str(options)
    else:
        filtr = Filter.from_key_value_str(options)

    if command.startswith("serials"):
        info = await device_finder.serials(filtr=filtr)
    elif command.startswith("info"):
        info = await device_finder.info_for(filtr=filtr)
    elif command.startswith("set_"):
        color = command[4:]
        sender = await device_finder.make_sender()
        await sender(ColourParser.msg(color), device_finder.find(filtr=filtr))
        info = ""
    else:
        print(
            dedent(
                """
            commands are of the form '(serials|info|set_<color>) KEY=VALUE KEY=VALUE ...'

            or of the form '(serials_json|info_json|set_<color>_json) {"key": "value", "key": "value"}'
        """
            )
        )
        return

    print(json.dumps(info, indent=4, sort_keys=True))


async def doit(collector):
    lan_target = collector.resolve_target("lan")

    readline.parse_and_bind("")

    final = asyncio.Future()
    loop = asyncio.get_event_loop()

    device_finder = DeviceFinder(lan_target)
    await device_finder.start()

    def get_command(done):
        try:
            nxt = input()
        except Exception as error:
            loop.call_soon_threadsafe(done.set_result, None)
            loop.call_soon_threadsafe(final.set_exception, error)
            return

        loop.call_soon_threadsafe(done.set_result, nxt.strip())

    try:
        while True:
            done = asyncio.Future()
            write_prompt()
            await loop.run_in_executor(None, get_command, done)

            nxt = await done
            if nxt:
                try:
                    await process_command(lan_target, device_finder, nxt)
                except asyncio.CancelledError:
                    raise
                except:
                    log.exception("Unepected error")

            if final.done():
                try:
                    await final
                except EOFError:
                    break
    finally:
        await device_finder.finish()


if __name__ == "__main__":
    setup_logging(level=logging.ERROR)
    collector = library_setup()
    collector.run_coro_as_main(doit(collector))

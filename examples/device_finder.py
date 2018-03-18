from photons_app.executor import library_setup

from photons_device_finder import DeviceFinder, Filter
from photons_colour import Parser

from textwrap import dedent
import traceback
import readline
import asyncio
import json
import sys

collector = library_setup()

lan_target = collector.configuration['target_register'].resolve("lan")

def write_prompt():
    sys.stdout.write("> ")
    sys.stdout.flush()

async def process_command(device_finder, command):
    if " " not in command:
        options = ""
    else:
        command, options = command.split(" ", 1)

    if command.endswith("_json"):
        command = command[:command.rfind("_")]
        filtr = Filter.from_json_str(options)
    else:
        filtr = Filter.from_key_value_str(options)

    if command.startswith("serials"):
        info = await device_finder.serials(filtr=filtr)
    elif command.startswith("info"):
        info = await device_finder.info_for(filtr=filtr)
    elif command.startswith("set_"):
        color = command[4:]
        afr = await device_finder.args_for_run()
        await lan_target.script(Parser.color_to_msg(color)).run_with_all(device_finder.find(filtr=filtr), afr)
        info = ''
    else:
        print(dedent("""
            commands are of the form '(serials|info|set_<color>) KEY=VALUE KEY=VALUE ...'

            or of the form '(serials_json|info_json|set_<color>_json) {"key": "value", "key": "value"}'
        """))
        return

    print(json.dumps(info, indent=4, sort_keys=True))

async def doit():
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
                    await process_command(device_finder, nxt)
                except KeyboardInterrupt:
                    break
                except Exception as error:
                    traceback.print_exc()

            if final.done():
                await final
    finally:
        await device_finder.finish()

loop = collector.configuration["photons_app"].uvloop
try:
    loop.run_until_complete(doit())
except (EOFError, KeyboardInterrupt):
    pass

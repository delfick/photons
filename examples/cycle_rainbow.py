from photons_app.special import HardCodedSerials, FoundSerials
from photons_app.executor import library_setup

from photons_messages import DeviceMessages, LightMessages
from photons_control.script import Pipeline, Repeater
from photons_colour import Parser

from delfick_logging import setup_logging
import argparse
import logging

collector = library_setup()

lan_target = collector.configuration["target_register"].resolve("lan")

log = logging.getLogger("cycle_rainbow")


async def doit():
    setup_logging()

    parser = argparse.ArgumentParser()
    parser.add_argument("--reference", required=True)
    args = parser.parse_args()

    if args.reference == "_":
        reference = FoundSerials()
    else:
        reference = HardCodedSerials(args.reference.split(","))

    async with lan_target.session() as afr:
        power_on = DeviceMessages.SetPower(level=65535)

        spread = 1
        color_names = ["blue", "red", "orange", "yellow", "cyan", "green", "blue", "purple", "pink"]
        color_msgs = [
            Parser.color_to_msg(name, overrides={"res_required": False, "duration": spread})
            for name in color_names
        ]
        colors = Pipeline(*color_msgs, spread=spread, synchronized=True)

        pipeline = Pipeline(
            power_on, Repeater(colors, min_loop_time=len(color_names)), synchronized=True
        )

        def e(error):
            log.error(error)

        await lan_target.script(pipeline).run_with_all(
            reference, afr, message_timeout=1, error_catcher=e
        )


loop = collector.configuration["photons_app"].loop
loop.run_until_complete(doit())

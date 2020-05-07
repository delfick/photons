#!/usr/bin/python -ci=__import__;o=i("os");s=i("sys");a=s.argv;p=o.path;y=p.join(p.dirname(a[1]),".python");o.execv(y,a)

from photons_app.executor import library_setup

from photons_control.script import Pipeline, Repeater
from photons_control.colour import ColourParser
from photons_messages import DeviceMessages

from delfick_project.logging import setup_logging
import argparse
import logging


log = logging.getLogger("cycle_rainbow")


async def doit(collector):
    lan_target = collector.resolve_target("lan")

    parser = argparse.ArgumentParser()
    parser.add_argument("--reference", default="_")
    parser.add_argument("--brightness", type=float, default=1)
    args = parser.parse_args()

    reference = collector.reference_object(args.reference)

    power_on = DeviceMessages.SetPower(level=65535)

    spread = 1
    color_names = ["blue", "red", "orange", "yellow", "cyan", "green", "blue", "purple", "pink"]
    color_msgs = [
        ColourParser.msg(
            name,
            overrides={"res_required": False, "duration": spread, "brightness": args.brightness},
        )
        for name in color_names
    ]
    colors = Pipeline(*color_msgs, spread=spread, synchronized=True)

    pipeline = Pipeline(
        power_on, Repeater(colors, min_loop_time=len(color_names)), synchronized=True
    )

    def e(error):
        log.error(error)

    await lan_target.send(pipeline, reference, message_timeout=1, error_catcher=e)


if __name__ == "__main__":
    setup_logging()
    collector = library_setup()
    collector.run_coro_as_main(doit(collector))

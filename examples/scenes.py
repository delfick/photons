from photons_app.executor import library_setup

from photons_control.transform import Transformer
from photons_control.script import FromGenerator

from delfick_project.logging import setup_logging
import logging
import asyncio
import time


log = logging.getLogger("scenes")

scenes = [
    {
        "d073d514b730": {"color": "red", "duration": 1, "power": "on"},
        "d073d558b679": {"color": "blue", "duration": 1, "power": "on"},
    },
    {
        "d073d514b730": {"color": "hue:100 brightness:0.1", "duration": 1},
        "d073d558b679": {"color": "hue:200 brightness:0.5", "duration": 1},
    },
    {
        "d073d514b730": {"color": "hue:200 brightness:0.5", "duration": 1},
        "d073d558b679": {"color": "hue:100 brightness:0.1", "duration": 1},
    },
]


async def doit(collector):
    lan_target = collector.resolve_target("lan")

    def e(error):
        log.error(error)

    def apply_scene(scene):
        transformer = Transformer()

        async def gen(reference, afr, **kwargs):
            for state in scene.values():
                if "power" in state:
                    yield transformer.power_message(state)
                if "color" in state:
                    yield transformer.color_message(state, keep_brightness=False)

        return FromGenerator(gen)

    scripts = []
    for scene in scenes:
        for serial, options in scene.items():
            options["target"] = serial
        max_duration = max([options.get("duration", 1) for options in scene.values()])
        scripts.append((max_duration, apply_scene(scene)))

    async def gen(reference, afr, **kwargs):
        while True:
            for max_duration, script in scripts:
                start = time.time()
                r = yield script
                await r
                diff = max_duration - (time.time() - start)
                await asyncio.sleep(diff)

    apply_scenes = FromGenerator(gen)

    await lan_target.send(apply_scenes, message_timeout=1, error_catcher=e, find_timeout=10)


if __name__ == "__main__":
    setup_logging()
    collector = library_setup()
    collector.run_coro_as_main(doit(collector))

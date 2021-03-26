from photons_canvas.animations.infrastructure.finish import Finish
from photons_canvas.animations.runner import AnimationRunner

from photons_app.tasks import task_register as task

from textwrap import dedent
import logging
import sys
import os

log = logging.getLogger("photons_canvas.animations.action")

special_descriptions = {
    ":color_range:": """
        This can be used to specify a range of colours to choose from.

        "rainbow" is a special value and says every time this is used to create
        a new colour, any colour can be chosen.

        This can be a single value, a ':' separated string, or a list of
        values.

        A value is a ``(hue, saturation, brightness, kelvin)`` tuple of values
        which can be specified as one to 4 of those items. This is either a list
        or a comma separated string.

        For example: ``[0-180]`` is a all the hue values from 0 to 180 with
        a saturation of 1, a brightness of 1 and a kelvin of 3500.

        Or ``[0-180, 0-0.5]`` is all hue values from 0 to 180 combined with
        saturation values between 0 and 0.5, all with brightness 1 and kelvin
        3500.

        If a list of specifiers are given, then a random one is chosen from the
        list and then if that item can have multiple values, a random one of
        those is used.
        """,
    ":range:": """
        This can be used to specify a number in a range of values. The options
        given to this will determine exactly how the value is determined.

        In all cases, the values are either a single string or a list of strings
        where each string is ``<number>`` or ``<number>-<number>``.

        For example, ``["1-5", "7-10"]`` will give back a value either between
        1 and 5 or between 7 and 10, each time a value is requested.

        Note that the option that uses this may specify whether the value
        can be a float or an integer and maximum/minimum values.
        """,
}


def expand(doc, *, output):
    def p(s=""):
        if output:
            print(s, file=output)

    props = ((":color_range:", "colour range"), (":range:", "range"))
    extra = {}
    for prop, name in props:
        if prop in doc:
            extra[prop] = True
            doc = doc.replace(prop, name)

    p(doc)

    if not extra:
        p()
        return

    p()
    p("=" * 80)
    p()

    for prop, name in props:
        if prop in extra:
            p()
            p(f"{name} options")
            for line in dedent(special_descriptions[prop]).strip().split("\n"):
                p(f"    {line}")
            p()


def print_help(*, animation_kls=None, animation_name=None, output=sys.stdout):
    from photons_canvas.animations import register

    def p(s=""):
        if output:
            print(s, file=output)

    if animation_kls is None:
        p("This command will run an animation on tiles on the network")
        p()
        p("Running `lifx lan:animate` with no other options will default")
        p("to running a small selection of the built in animations on any")
        p("tile found on the network")
        p()
        p("Alternatively:")
        p()
        p("  Run particular animation::")
        p()
        p("    lifx lan:animate balls")

        p()
        p("  Target particular devices::")
        p()
        p("    lifx lan:animate balls match:label=wall")

        p()
        p("  Provide options::")
        p()
        p("""    lifx lan:animate balls -- '{"num_balls": 2}'""")
        p()
        p("See https://photons.delfick.com/animations/commands.html")
        p()

        p("Available animations include")
        for animation in register.available_animations():
            p(f"* {animation}")
        p()

        p("To see options for a particular animation, run this again")
        p("but with the name of the animation::")
        p()
        p("    lifx lan:animate help falling")
        p()
        return

    command = sys.argv[0]
    if os.path.basename(command) == "lifx":
        command = f"lifx {sys.argv[1]} {animation_name}"

    p(f"This will run the '{animation_name}' animation")
    p()
    p()
    p("A particular device may be specified with a reference::")
    p()
    p(f"    {command} match:label=wall")
    p()
    p("And options can be given::")
    p()
    p(f"""    {command} -- '{{"option1": "value1"}}'""")
    p()
    p("See https://photons.delfick.com/animations/commands.html")
    p()
    p()
    p("-" * 80)
    p(f"{animation_name} animtion")
    p("-" * 80)
    p()
    expand(dedent(animation_kls.__doc__ or "").strip(), output=output)


class AnimationTask(task.Task):
    target = task.requires_target()
    artifact = task.provides_artifact()
    reference = task.provides_reference()

    animation_kls = NotImplemented
    animation_name = None

    async def execute_task(self, **kwargs):
        if self.reference == "help":
            print_help(animation_kls=self.animation_kls, animation_name=self.animation_name)
            return

        self.reference = self.collector.reference_object(self.reference)
        return await self.run_animation(**kwargs)

    @property
    def run_options(self):
        return {}

    @property
    def message_timeout(self):
        return 1

    def error_catcher(self, e):
        log.error(e)

    async def run_animation(self, **kwargs):
        try:
            with self.collector.photons_app.using_graceful_future() as final_future:
                async with self.target.session() as sender:
                    runner = AnimationRunner(
                        sender,
                        self.reference,
                        self.run_options,
                        final_future=final_future,
                        message_timeout=self.message_timeout,
                        error_catcher=self.error_catcher,
                    )

                    async with runner:
                        await runner.run()
        except Finish:
            pass

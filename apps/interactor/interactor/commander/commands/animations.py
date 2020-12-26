from interactor.commander.command import DeviceChangeMixin
from interactor.commander.store import store

from delfick_project.norms import dictobj, sb
import secrets


@store.command(name="animation/help")
class AnimationHelpCommand(store.Command):
    """
    Return help information for animations
    """

    animations_runner = store.injected("animations")

    animation_name = dictobj.NullableField(
        sb.string_spec(),
        help="Optionally the specific name of an animation to get help about",
    )

    async def execute(self):
        return await self.animations_runner.help(self.animation_name)


@store.command(name="animation/info")
class AnimationInfoCommand(store.Command):
    """
    Return information about running animations
    """

    animations_runner = store.injected("animations")

    identity = dictobj.NullableField(
        sb.string_spec,
        help="optional identity of a specific animation you want info for",
    )

    async def execute(self):
        return self.animations_runner.info(expand=True, identity=self.identity)


@store.command(name="animation/start")
class AnimationStartCommand(store.Command, DeviceChangeMixin):
    """
    Start an animation

    For example::

        PUT /v1/lifx/command {
          "command": "animation/start",
          "args": {
            "matcher": {"label": "wall"},
            "animations": [["balls", {"num_seconds": 5}], "dice"],
            "run_options": {"reinstate_on_end": true, "animation_limit": 3}
          }
        }

    """

    # Make the timeout not appear in help output
    timeout = store.injected("")

    animations_runner = store.injected("animations")

    animations = dictobj.Field(
        sb.any_spec,
        wrapper=sb.optional_spec,
        help="The animations options!",
    )

    run_options = dictobj.Field(
        sb.any_spec,
        wrapper=sb.optional_spec,
        help="The options for animations in general",
    )

    identity = dictobj.Field(
        sb.string_spec, wrapper=sb.optional_spec, help="Optional identity for the animation"
    )

    async def execute(self):
        identity = self.identity
        if identity is sb.NotSpecified:
            identity = secrets.token_urlsafe(6)

        return await self.animations_runner.start(
            identity,
            self.device_finder,
            run_options=self.run_options,
            animations=self.animations,
        )


@store.command(name="animation/pause")
class AnimationPauseCommand(store.Command):
    """
    Pause an animation
    """

    animations_runner = store.injected("animations")

    pause = dictobj.Field(
        sb.listof(sb.string_spec()),
        help="The animation identities to pause",
    )

    async def execute(self):
        return await self.animations_runner.pause(*self.pause)


@store.command(name="animation/resume")
class AnimationResumeCommand(store.Command):
    """
    Resume an animation
    """

    animations_runner = store.injected("animations")

    resume = dictobj.Field(
        sb.listof(sb.string_spec()),
        help="The animation identities to resume",
    )

    async def execute(self):
        return await self.animations_runner.resume(*self.resume)


@store.command(name="animation/stop")
class AnimationStopCommand(store.Command):
    """
    Stop an animation
    """

    animations_runner = store.injected("animations")

    stop = dictobj.Field(
        sb.listof(sb.string_spec()),
        help="The animation identities to stop",
    )

    async def execute(self):
        return await self.animations_runner.stop(*self.stop)

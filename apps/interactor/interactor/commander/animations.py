import asyncio
import io
import logging
from textwrap import dedent

from delfick_project.norms import sb
from delfick_project.option_merge import MergedOptions
from photons_app import helpers as hp
from photons_app.errors import PhotonsAppError
from photons_canvas.animations import AnimationRunner, register
from photons_canvas.animations.action import expand

log = logging.getLogger("interactor.commander.animations")


def errors(e):
    if isinstance(e, KeyboardInterrupt):
        return

    if not isinstance(e, PhotonsAppError):
        log.exception(e)
    else:
        log.error(e)


class Animation:
    def __init__(self, final_future, identity, runner, pauser):
        self.runner = runner
        self.pauser = pauser
        self.paused = False
        self.identity = identity
        self.final_future = final_future

    @property
    def info(self):
        return self.runner.info

    async def pause(self):
        if not self.paused:
            await self.pauser.acquire()
            self.paused = True

    async def resume(self):
        self.paused = False
        self.pauser.release()

    async def stop(self):
        self.final_future.cancel()

    def start(self, tasks, *callbacks):
        async def animation():
            async with self.runner:
                await self.runner.run()

        self.task = tasks.add(animation())
        for cb in callbacks:
            self.task.add_done_callback(cb)

        return self


class Animations:
    available = register.available_animations()

    def __init__(self, final_future, tasks, sender, animation_options):
        self.tasks = tasks
        self.sender = sender
        self.final_future = final_future
        self.animation_options = animation_options

        self.animations = {}

    def info(self, identity=None, expand=False, **extra):
        if identity is not None:
            if identity not in self.animations:
                return
            else:
                return self.animations[identity].info

        animations = {
            identity: animation.info for identity, animation in sorted(self.animations.items())
        }
        if not expand:
            animations = sorted(animations)

        return {
            "animations": animations,
            "paused": sorted(
                [animation.identity for animation in self.animations.values() if animation.paused]
            ),
            **extra,
        }

    async def start(
        self,
        identity,
        reference,
        *,
        run_options=sb.NotSpecified,
        animations=sb.NotSpecified,
    ):
        pauser = asyncio.Semaphore()
        final_future = hp.ChildOfFuture(
            self.final_future, name=f"Animations::start({identity})[final_future]"
        )

        if run_options is sb.NotSpecified:
            run_options = {}

        if animations is not sb.NotSpecified:
            run_options = MergedOptions.using(run_options, {"animations": animations}).as_dict()

        runner = AnimationRunner(
            self.sender,
            reference,
            run_options,
            final_future=final_future,
            error_catcher=errors,
            animation_options=self.animation_options,
        )

        runner.run_options.pauser = pauser

        def remove(res):
            if identity in self.animations:
                del self.animations[identity]

        self.animations[identity] = Animation(final_future, identity, runner, pauser).start(
            self.tasks, remove
        )

        return self.info(started=identity)

    async def pause(self, *identities):
        return await self.action("pause", "pausing", identities)

    async def resume(self, *identities):
        return await self.action("resume", "resuming", identities)

    async def stop(self, *identities):
        return await self.action("stop", "stopping", identities)

    async def help(self, animation_name=None):
        out = io.StringIO()

        def p(s=""):
            print(s, file=out)

        animation_kls = None
        if animation_name in register.animations:
            animation_kls = register.animations[animation_name].Animation

        if animation_kls is None:
            p("Available animations include")
            for animation in register.available_animations():
                p(f"* {animation}")
            p()

            p("To see options for a particular animation, run this again")
            p("but with the `animation_name` option set to the name of the animation.")
            p()
        else:
            p()
            p("-" * 80)
            p(f"{animation_name} animation")
            p("-" * 80)
            p()
            expand(dedent(animation_kls.__doc__ or "").strip(), output=out)

        out.flush()
        out.seek(0)
        return out.read()

    async def action(self, method, verb, identities):
        if not identities:
            identities = list(self.animations)

        changed = []
        async with hp.TaskHolder(self.final_future, name=f"Animations::action({method})[ts]") as ts:
            for identity in identities:
                if identity in self.animations:
                    changed.append(identity)
                    ts.add(getattr(self.animations[identity], method)())

        return self.info(**{verb: changed})

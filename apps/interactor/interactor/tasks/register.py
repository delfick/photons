from interactor.commander.command import DeviceChangeMixin
from interactor.tasks.location import NaturalLightPresets
from interactor.tasks.time_specs import duration_spec

from photons_app.formatter import MergedOptionStringFormatter
from photons_app.errors import PhotonsAppError
from photons_app import helpers as hp

from photons_control.script import FromGenerator, Repeater

from delfick_project.option_merge import MergedOptions
from delfick_project.norms import dictobj, sb, Meta
from collections import defaultdict
from functools import partial
from datetime import datetime
import asyncio
import logging
import uuid


log = logging.getLogger("interactor.tasks.register")

registerers = []


def registerer(func):
    registerers.append(func)
    return func


class pauser_spec(sb.Spec):
    def normalise(self, meta, val):
        event = asyncio.Event()
        if val is True:
            event.set()
        elif val is False:
            pass
        elif meta.everything["default_paused"] is True:
            event.set()
        return event


class NoSuchType(PhotonsAppError):
    desc = "No such task type"


class AlreadyCreatedTask(PhotonsAppError):
    desc = "Already created a task with this name"


class DeviceTask(DeviceChangeMixin):
    paused = dictobj.Field(
        pauser_spec,
        help="""
    Set to True if you want this task to be paused on start
    """,
    )

    update_every = dictobj.Field(
        sb.float_spec,
        default=10,
        help="""
    Update the lights every this seconds. Defaults to 10 seconds
    """,
    )

    async def run(self, final_future, action):
        async def gen(reference, sender, **kwargs):
            if final_future.done():
                raise Repeater.Stop()

            if self.paused.is_set():
                return

            async for msg in action(reference, sender, **kwargs):
                yield msg

        await self.send(
            Repeater(
                FromGenerator(gen, reference_override=self.device_finder),
                min_loop_time=self.update_every,
            ),
            self.device_finder,
        )

    async def status(self, name):
        return {
            "name": name,
            "paused": self.paused.is_set(),
            "serials": await self.serials,
        }


class TaskRegister(hp.AsyncCMMixin):
    def __init__(self, final_future, task_holder, meta):
        self.meta = meta
        self.task_holder = task_holder
        self.final_future = final_future

        self.types = {}
        self.listeners = defaultdict(dict)
        self.registered = {}

    class Config(dictobj.Spec):
        class TaskConfig(dictobj.Spec):
            type = dictobj.Field(sb.string_spec, wrapper=sb.required)
            skip = dictobj.Field(sb.boolean, default=False)
            units = dictobj.Field(sb.dictof(sb.string_spec(), duration_spec(units_from_meta=False)))
            paused = dictobj.Field(sb.boolean, default=False)
            options = dictobj.Field(sb.dictionary_spec)

        natural_light = dictobj.Field(NaturalLightPresets.spec())
        presets = dictobj.Field(sb.dictof(sb.string_spec(), TaskConfig.FieldSpec()))

    def register(self, typ, options_kls, run):
        self.types[typ] = (options_kls, run)

    async def status(self):
        status = {}
        for name, (_, _, options) in sorted(self.registered.items()):
            if hasattr(options, "status"):
                status[name] = await options.status(name)
            else:
                status[name] = {"name": name}

        return status

    async def start(self):
        return self

    async def finish(self, exc_typ=None, exc=None, tb=None):
        for name in list(self.registered):
            await self.remove(name)

    async def add(self, meta, name, config):
        if name in self.registered:
            raise AlreadyCreatedTask(task=name, running=sorted(self.registered))

        if config.type not in self.types:
            raise NoSuchType(task=name, wanted=config.type, available=sorted(self.types))

        meta = Meta(
            MergedOptions.using(
                meta.everything,
                self.meta.everything,
                {"default_paused": config.paused, "units": config.units},
            ),
            meta.path,
        )

        options_kls, run = self.types[config.type]
        options = options_kls.FieldSpec(formatter=MergedOptionStringFormatter).normalise(
            meta, config.options
        )

        final_future = hp.ChildOfFuture(
            self.final_future, name=f"TaskRegistered::create[{name}.final_future]"
        )

        log.info(hp.lc("Starting task", name=name, type=config.type))
        task = self.task_holder.add(run(final_future, options, partial(self.progress, name)))
        task.add_done_callback(partial(self.remove_task_on_done, name))
        self.registered[name] = (task, final_future, options)

    def remove_task_on_done(self, name, res=None):
        if name in self.registered:
            del self.registered[name]

    async def remove(self, name):
        if name in self.registered:
            task, final_future, _ = self.registered[name]
            final_future.cancel()
            task.cancel()

    def pause(self, name):
        if name in self.registered:
            options = self.registered[name][2]
            if hasattr(options, "paused"):
                options.paused.set()

    def resume(self, name):
        if name in self.registered:
            options = self.registered[name][2]
            if hasattr(options, "paused"):
                options.paused.clear()

    def progress(self, name, msg, **kwargs):
        for progress, silent in self.listeners[name].values():
            if "do_log" not in kwargs:
                kwargs["do_log"] = not silent
            if "timestamp" not in kwargs:
                kwargs["timestamp"] = datetime.now().isoformat()
            progress(msg, **kwargs)

    @hp.asynccontextmanager
    async def listener_for(self, name, progress_cb, silent=True):
        identity = uuid.uuid1().hex
        try:
            self.listeners[name][identity] = (progress_cb, silent)
            yield
        finally:
            if identity in self.listeners[name]:
                del self.listeners[name][identity]

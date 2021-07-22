from photons_control.script import FromGenerator
from photons_control.planner import Skip

from photons_app.tasks import task_register as task

from photons_messages import LightMessages

from delfick_project.norms import sb, Meta
from datetime import timedelta

try:
    import humanize
except ImportError:
    humanize = None


def humanize_duration(duration, precision=False):
    result = f"{duration} seconds"
    if humanize:
        if precision:
            result = humanize.precisedelta(timedelta(seconds=duration))
        else:
            result = humanize.naturaldelta(timedelta(seconds=duration))

    return result


def SetCleanConfig(*, indication, duration, reference=None, **kwargs):
    """
    Returns a valid message that will set the default clean cycle configuration
    for the device.

    For example:

    .. code-block:: python

        await target.send(SetCleanConfig(indication=True), ["d073d5000001", "d073d5000001"])

    The options are:

    indication - boolean - default False
        whether to run a short flashing indication at the end of the HEV cycle.

    duration - seconds - default 7200 seconds
        duration in seconds for a cleaning cycle, if no duration provided.
    """

    async def gen(ref, sender, **kwargs):
        r = ref if reference is None else reference

        plans = sender.make_plans("capability")
        async for serial, _, info in sender.gatherer.gather(plans, r, **kwargs):
            if info["cap"].has_hev:
                yield LightMessages.SetHevCycleConfiguration(
                    indication=bool(indication),
                    duration_s=duration,
                    target=serial,
                    ack_required=True,
                    res_required=False,
                )

    return FromGenerator(gen)


@task
class set_clean_config(task.Task):
    """
    Set the default clean cycle configuration for a device

    ``target:clean_config match:cap=hev -- '{"indication": false, "duration": 7200}'``

    Options are:
        indication: run a short flashing indication at the end of the HEV cycle.
        duration: in seconds, how long to run a cleaning cycle by default

    """

    target = task.requires_target()
    reference = task.provides_reference(special=True)

    async def execute_task(self, **kwargs):
        options = sb.set_options(
            indication=sb.required(sb.boolean()),
            duration=sb.required(sb.integer_spec()),
        ).normalise(Meta.empty(), self.photons_app.extra_as_json)

        await self.target.send(SetCleanConfig(**options), self.reference, **kwargs)


@task
class get_clean_config(task.Task):
    """
    Get the default HEV cleaning cycle configuration values for the specified devices
    """

    target = task.requires_target()
    reference = task.provides_reference(special=True)

    async def execute_task(self, **kwargs):
        async with self.target.session() as sender:
            plans = sender.make_plans("hev_config")
            async for serial, _, info in sender.gatherer.gather(plans, self.reference, **kwargs):
                if info is not Skip:
                    indicator = "yes" if info["indication"] else "no"
                    duration = humanize_duration(info["duration"])
                    print(serial)
                    print(f"    Clean cycle duration: {duration}")
                    print(f"    Flash when cycle ends: {indicator}")
                    print("")


def ChangeCleanCycle(*, enable, duration=0, **kwargs):
    """
    Returns a valid message that will either start or stop the cleaning (HEV)
    cycle of devices used against it.

    When a cycle is started, if the duration=0 or is not provided, the default
    duration will be used.

    For example:

    .. code-block:: python

        await target.send(ChangeCleanCycle(enable=True), ["d073d5000001", "d073d5000001"])

    Options are:

        enable - boolean (required)
            Pass True to start a cleaning cycle or False to stop a cycle in progress

        duration - integer (optional)
            Only used if enable=True. Specifies the duration (in seconds) for
            the cleaning cycle. If not specified, the default duration will be
            used. Default duration can be set using target:set_clean_config and
            returned using target_get_clean_config

    """

    async def gen(reference, sender, **kwargs):
        plans = sender.make_plans("capability")
        async for serial, _, info in sender.gatherer.gather(plans, reference, **kwargs):
            if info["cap"].has_hev:
                yield LightMessages.SetHevCycle(
                    enable=enable,
                    res_required=False,
                    ack_required=True,
                    duration_s=duration,
                    target=serial,
                )

    return FromGenerator(gen)


@task
class start_clean_cycle(task.Task):
    """
    Start a cleaning cycle on an HEV-capable bulb

    ``target:start_clean_cycle match:cap=hev -- '{"duration": 7200}'``

    It  takes a ``duration`` field that is the seconds of the duration. If not
    provided, or set to 0, the default duration will be used.
    """

    target = task.requires_target()
    reference = task.provides_reference(special=True)

    async def execute_task(self, **kwargs):
        options = sb.dictionary_spec().normalise(Meta.empty(), self.photons_app.extra_as_json)
        await self.target.send(ChangeCleanCycle(**{**options, "enable": True}), self.reference)


@task
class stop_clean_cycle(task.Task):
    """
    Stop a cleaning cycle on an HEV-capable bulb

    ``target:stop_clean_cycle match:cap=hev``

    """

    target = task.requires_target()
    reference = task.provides_reference(special=True)

    async def execute_task(self, **kwargs):
        options = sb.dictionary_spec().normalise(Meta.empty(), self.photons_app.extra_as_json)
        await self.target.send(ChangeCleanCycle(**{**options, "enable": False}), self.reference)


@task
class get_clean_status(task.Task):
    """
    Get the current cleaning status from the specified bulb.
    """

    target = task.requires_target()
    reference = task.provides_reference(special=True)

    async def execute_task(self, **kwargs):
        async with self.target.session() as sender:
            plans = sender.make_plans("hev_status")
            async for serial, _, info in sender.gatherer.gather(plans, self.reference, **kwargs):
                if info is not Skip:
                    print(serial)
                    if info["current"]["active"]:
                        power_off = "yes" if info["current"]["power_off"] else "no"
                        remaining = humanize_duration(info["current"]["remaining"])
                        print("    Cycle in progress: yes")
                        print(f"    Time left: {remaining}")
                        print(f"    Power off: {power_off}")
                    else:
                        print("    Cycle in progress: no")
                        print(f"    Last cycle result: {info['last']['result']}")
                    print("")

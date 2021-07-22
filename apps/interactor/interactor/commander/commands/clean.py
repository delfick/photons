from interactor.commander.command import DeviceChangeMixin
from interactor.commander import helpers as ihp
from interactor.commander.store import store

from photons_control.script import FromGeneratorPerSerial
from photons_control.clean import ChangeCleanCycle
from photons_control.planner import Skip

from photons_messages import LightLastHevCycleResult

from delfick_project.norms import dictobj, sb


@store.command(name="clean/start")
class StartCleanCommand(store.Command, DeviceChangeMixin):
    """
    Starts a cleaning cycle on the specified HEV device(s). Will use
    the default duration if a duration is not provided.
    """

    duration = dictobj.Field(
        sb.integer_spec, default=0, help="(optional) duration of the cleaning cycle, in seconds"
    )

    async def execute(self):
        return await self.send(
            FromGeneratorPerSerial(ChangeCleanCycle(enable=True, duration=self.duration)),
            add_replies=False,
        )


@store.command(name="clean/stop")
class StopCleanCommand(store.Command, DeviceChangeMixin):
    """
    Stops a cleaning cycle on the specified HEV-enabled device(s). The device
    will revert back to the power state it was in before the cleaning cycle
    started.
    """

    async def execute(self):
        return await self.send(ChangeCleanCycle(enable=False), add_replies=False)


@store.command(name="clean/status")
class StatusCleanCommand(store.Command, DeviceChangeMixin):
    """
    Returns the current state and default configuration for an HEV enabled
    device
    """

    async def execute(self):
        plans = self.sender.make_plans("hev_status", "hev_config")

        serials = await self.serials
        result = ihp.ResultBuilder()

        async for serial, complete, info in self.sender.gatherer.gather_per_serial(
            plans, serials, error_catcher=result.error, message_timeout=self.timeout
        ):

            if not complete:
                continue

            final = {}

            if info["hev_status"] is not Skip:
                final["status"] = info["hev_status"]
                final["status"]["last"]["result"] = LightLastHevCycleResult(final["status"]["last"]["result"]).name

            if info["hev_config"] is not Skip:
                final["config"] = info["hev_config"]

            if len(final) > 0:
                result.result["results"][serial] = final

        return result

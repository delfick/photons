from interactor.commander.command import DeviceChangeMixin
from interactor.commander import helpers as ihp
from interactor.commander.store import store

from photons_control.clean import ChangeCleanCycle
from photons_control.planner import Skip

from delfick_project.option_merge import MergedOptions
from delfick_project.norms import dictobj, sb


@store.command(name="clean/start")
class StartCleanCommand(store.Command, DeviceChangeMixin):
    """
    Starts a cleaning cycle on the specified HEV device(s). Will use
    the default duration if a duration is not provided.
    """

    duration_s = dictobj.Field(
        sb.integer_spec, default=0, help="(optional) duration of the cleaning cycle, in seconds"
    )

    async def execute(self):
        return await self.send(
            ChangeCleanCycle(enable=True, duration_s=self.duration_s), add_replies=False
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

        got = await self.sender.gatherer.gather_all(
            plans, serials, error_catcher=result.error, message_timeout=self.timeout
        )

        for serial, (complete, info) in got.items():
            if not complete:
                continue

            if info["hev_status"] is Skip:
                continue

            if "hev_status" in info and "hev_config" in info:
                # Create a copy so we don't corrupt the gatherer cache
                final = result.result["results"][serial] = {}
                final["status"] = MergedOptions.using(info["hev_status"]).as_dict()
                final["status"]["last"]["result"] = final["status"]["last"]["result"].name
                final["config"] = info["hev_config"]

        return result

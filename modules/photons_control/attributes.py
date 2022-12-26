import sys
from textwrap import dedent

from delfick_project.norms import sb
from photons_app.errors import BadOption, DeprecatedTask
from photons_app.tasks import task_register as task
from photons_control.multizone import SetZonesEffect
from photons_control.planner import Skip
from photons_control.script import FromGenerator
from photons_control.tile import SetTileEffect
from photons_messages import LightMessages


def find_packet(protocol_register, value, prefix):
    """
    Return either None or the class object for this value/prefix combination.

    For example, if value is GetHostFirmware then the GetHostFirmware packet is returned

    If the value is host_firmware or HostFirmware, then we get GetHostFirmware if the prefix is Get and SetHostFirmware if the prefix is Set
    """
    prefix = prefix.lower().capitalize()

    kls_name_plain = f"{prefix}{value}"
    kls_name_transformed = f"""{prefix}{"".join(part.capitalize() for part in value.split("_"))}"""

    for messages in protocol_register.message_register(1024):
        for kls in messages.by_type.values():
            if kls.__name__ in (value, kls_name_plain, kls_name_transformed):
                return kls


@task
class attr(task.Task):
    """
    Send a message to your bulb and print out all the replies.

    ``target:attr d073d5000000 GetHostFirmware``
    """

    target = task.requires_target()
    artifact = task.provides_artifact()
    reference = task.provides_reference(special=True)

    async def execute_task(self, **kwargs):
        protocol_register = self.collector.configuration["protocol_register"]

        if self.artifact is sb.NotSpecified:
            raise BadOption(
                f"Please specify what you want to get\nUsage: {sys.argv[0]} <target>:attr <reference> <attr_to_get>"
            )

        kls = find_packet(protocol_register, self.artifact, "")
        if kls is None:
            raise BadOption(
                "Sorry, couldn't a class for this message", prefix="", want=self.artifact
            )

        extra = self.photons_app.extra_as_json

        if "extra_payload_kwargs" in kwargs:
            extra.update(kwargs["extra_payload_kwargs"])

        msg = kls.create(extra)
        async with self.target.session() as sender:
            found, serials = await self.reference.find(sender, timeout=20)
            self.reference.raise_on_missing(found)

            msg = kls.create(extra)
            async for pkt in sender(msg, serials, **kwargs):
                if len(serials) == 1:
                    print(repr(pkt.payload))
                else:
                    print(f"{pkt.serial}: {repr(pkt.payload)}")


@task
class attr_actual(task.Task):
    """
    Same as the attr command but prints out the actual values on the replies rather than transformed values
    """

    target = task.requires_target()
    artifact = task.provides_artifact()
    reference = task.provides_reference(special=True)

    async def execute_task(self, **kwargs):
        protocol_register = self.collector.configuration["protocol_register"]

        if self.artifact is sb.NotSpecified:
            raise BadOption(
                f"Please specify what you want to get\nUsage: {sys.argv[0]} <target>:attr_actual <reference> <attr_to_get>"
            )

        kls = find_packet(protocol_register, self.artifact, "")
        if kls is None:
            raise BadOption(
                "Sorry, couldn't a class for this message", prefix="", want=self.artifact
            )

        extra = self.photons_app.extra_as_json

        if "extra_payload_kwargs" in kwargs:
            extra.update(kwargs["extra_payload_kwargs"])

        def lines(pkt, indent="    "):
            for field in pkt.Meta.all_names:
                val = pkt[field]
                if isinstance(val, list):
                    yield f"{indent}{field}:"
                    for item in val:
                        ind = f"{indent}    "
                        ls = list(lines(item, ind))
                        first = list(ls[0])
                        first[len(indent) + 2] = "*"
                        ls[0] = "".join(first)
                        yield from ls
                else:
                    yield f"{indent}{field}: {pkt.actual(field)}"

        msg = kls.create(extra)
        async for pkt in self.target.send(msg, self.reference, **kwargs):
            print()
            print(f"""{"=" * 10}: {pkt.serial}""")
            for line in lines(pkt):
                print(line)


@task
class get_attr(task.Task):
    """
    Deprecated in favour of the ``attr`` task
    """

    async def execute_task(self, **kwargs):
        raise DeprecatedTask(
            dedent(
                """

            Please use the attr task instead.

            So instead of ``lan:get_attr _ color`` you would use
            ``lan:attr _ GetColor``

        """
            )
        )


@task
class set_attr(task.Task):
    """
    Deprecated in favour of the ``attr`` task
    """

    async def execute_task(self, **kwargs):
        raise DeprecatedTask(
            dedent(
                """

            Please use the attr task instead.

            So instead of ``lan:set_attr _ color -- '{...}'`` you would use
            ``lan:attr _ SetColor -- '{...}'``

        """
            )
        )


@task
class get_effects(task.Task):
    """
    Determine what firmware effects are running on your devices
    """

    target = task.requires_target()
    reference = task.provides_reference(special=True)

    async def execute_task(self, **kwargs):
        async with self.target.session() as sender:
            plans = sender.make_plans("firmware_effects")

            async for serial, _, info in sender.gatherer.gather(plans, self.reference):
                if info is Skip:
                    continue

                print(f"{serial}: {info['type']}")
                for field, value in info["options"].items():
                    if field == "palette":
                        if value:
                            print("\tpalette:")
                            for c in value:
                                print(f"\t\t{repr(c)}")
                    else:
                        print(f"\t{field}: {value}")
                print()


@task
class effect_off(task.Task):
    target = task.requires_target()
    reference = task.provides_reference(special=True)

    async def execute_task(self, **kwargs):
        async def gen(reference, sender, **kwargs):
            plans = sender.make_plans("capability")
            async for serial, _, info in sender.gatherer.gather(plans, reference):
                print(f"Turning off effects for {serial}")

                yield LightMessages.SetWaveformOptional(res_required=False, target=serial)

                if info["cap"].has_multizone:
                    yield SetZonesEffect("OFF", power_on=False)
                elif info["cap"].has_matrix:
                    yield SetTileEffect("OFF", power_on=False)

        await self.target.send(FromGenerator(gen), self.reference)

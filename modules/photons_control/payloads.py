import base64
import binascii

from photons_app.tasks import task_register as task
from photons_messages import protocol_register
from photons_protocol.messages import Messages


@task
class pack(task.Task):
    """
    Pack json found after the ``--`` into hexlified string

    ``lifx pack -- '{"protocol": 1024, "source": 2, "sequence": 1, "target": "d073d5000001", "pkt_type": 21, "level": 0}'``
    """

    async def execute_task(self, **kwargs):
        extra = self.photons_app.extra_as_json

        if "extra_payload_kwargs" in kwargs:
            extra.update(kwargs["extra_payload_kwargs"])

        packd = Messages.pack(extra, protocol_register, unknown_ok=True)
        print(binascii.hexlify(packd.tobytes()).decode())


@task
class pack_payload(task.Task):
    """
    Pack json found after the ``--`` into hexlified string

    ``pack_payload 21 -- '{"level": 65535}'``
    """

    reference = task.provides_reference()

    async def execute_task(self, **kwargs):
        extra = self.photons_app.extra_as_json
        message_register = protocol_register.message_register(1024)

        if "extra_payload_kwargs" in kwargs:
            extra.update(kwargs["extra_payload_kwargs"])

        packd = Messages.pack_payload(self.reference, extra, message_register)
        print(binascii.hexlify(packd.tobytes()).decode())


@task
class unpack(task.Task):
    """
    Unpack hexlified string found after the ``--`` into a json dictionary

    ``unpack -- 310000148205ed33d073d51261e20000000000000000030100000000000000006600000000f4690000ffffac0d00000000``
    """

    async def execute_task(self, **kwargs):
        bts = binascii.unhexlify(self.photons_app.extra)
        pkt = Messages.create(bts, protocol_register, unknown_ok=True)
        print(repr(pkt))


@task
class unpack_base64(task.Task):
    """
    Unpack base64 string found after the ``--`` into a json dictionary

    ``unpack_base64 -- MQAAFIIF7TPQc9USYeIAAAAAAAAAAAMBAAAAAAAAAABmAAAAAPRpAAD//6wNAAAAAA==``
    """

    async def execute_task(self, **kwargs):
        bts = base64.b64decode(self.photons_app.extra)
        pkt = Messages.create(bts, protocol_register, unknown_ok=True)
        print(repr(pkt))

from photons_messages import protocol_register, LightMessages, DeviceMessages
from photons_socket.fake import FakeDevice, MemorySocketTarget, MemoryTarget
from photons_protocol.types import Type as T

from input_algorithms.dictobj import dictobj
from input_algorithms import spec_base as sb
import asyncio

def pktkeys(msgs):
    keys = []
    for msg in msgs:
        clone = msg.payload.clone()
        for name, typ in clone.Meta.field_types:
            if clone.actual(name) is sb.NotSpecified and isinstance(typ, type(T.Reserved)):
                clone[name] = None

        key = (msg.protocol, msg.pkt_type, repr(clone))
        if key not in keys:
            keys.append(key)
    return keys

class Color(dictobj):
    fields = ["hue", "saturation", "brightness", "kelvin"]

class Device(FakeDevice):
    def __init__(self, serial, *, label="", power=0, color=Color(0, 0, 1, 3500), **kwargs):
        super().__init__(serial, protocol_register, **kwargs)

        def reset():
            self.online = True
            self.label = label

            self.received = []
            self.received_processing = None

            self.change_hsbk(color)
            self.change_power(power)

        self.reset = reset
        reset()

    def set_received_processing(self, processor):
        if self.use_sockets:
            assert False, "Setting received_processing callback on a device that won't ever use it"
        self.received_processing = processor

    def change_power(self, power):
        self.power = power

    def change_label(self, label):
        self.label = label

    def change_hsbk(self, color):
        self.hue = color.hue
        self.saturation = color.saturation
        self.brightness = color.brightness
        self.kelvin = color.kelvin

    def compare_received(self, expected):
        expect_keys = pktkeys(expected)
        got_keys = pktkeys(self.received)

        def do_print():
            print(self.serial)
            print("GOT:")
            for key in got_keys:
                print(f"\t{key}")
            print()
            print("EXPECTED:")
            for key in expect_keys:
                print(f"\t{key}")
            print()

        if len(expect_keys) != len(got_keys):
            do_print()
            assert False, "Expected a different number of messages to what we got"

        different = False
        for i, (got, expect) in enumerate(zip(got_keys, expect_keys)):
            if got != expect:
                print(f"{self.serial} Message {i} is different\n\tGOT:\n\t\t{got}\n\tEXPECT:\n\t\t{expect}")
                different = True

        if different:
            print("=" * 80)
            do_print()
            assert False, "Expected messages to be the same"

    async def async_got_message(self, pkt):
        if self.received_processing:
            if await self.received_processing(pkt) is False:
                return

        async for msg in super().async_got_message(pkt):
            yield msg

    def make_response(self, pkt, protocol):
        self.received.append(pkt)

        if pkt | LightMessages.GetColor:
            return self.light_state_message()

        elif pkt | DeviceMessages.SetPower or pkt | LightMessages.SetLightPower:
            res = DeviceMessages.StatePower(level=pkt.level)
            self.change_power(pkt.level)
            return res

        elif pkt | DeviceMessages.GetPower:
            return DeviceMessages.StatePower(level=self.power)

        elif pkt | LightMessages.SetWaveformOptional or pkt | LightMessages.SetColor:
            self.change_hsbk(Color(pkt.hue, pkt.saturation, pkt.brightness, pkt.kelvin))
            return self.light_state_message()

        elif pkt | DeviceMessages.SetLabel:
            self.change_label(pkt.label)
            return DeviceMessages.StateLabel(label=self.label)

        elif pkt | DeviceMessages.GetLabel:
            return DeviceMessages.StateLabel(label=self.label)

    def light_state_message(self):
        return LightMessages.LightState(
              hue = self.hue
            , saturation = self.saturation
            , brightness = self.brightness
            , power = self.power
            , label = "light"
            )

class MemoryTargetRunner:
    def __init__(self, final_future, devices, use_sockets=True):
        options = {
              "final_future": final_future
            , "protocol_register": protocol_register
            }
        if use_sockets:
            self.target = MemorySocketTarget.create(options)
        else:
            self.target = MemoryTarget.create(options)

        self.devices = devices

    async def __aenter__(self):
        await self.start()

    async def start(self):
        for device in self.devices:
            await device.start()
            self.target.add_device(device)
        self.afr = await self.target.args_for_run()

    async def __aexit__(self, typ, exc, tb):
        await self.close()

    async def close(self):
        await self.target.close_args_for_run(self.afr)
        for device in self.target.devices.values():
            await device.finish()

    def reset_devices(self):
        for device in self.devices:
            device.reset()

    @property
    def serials(self):
        return [device.serial for device in self.devices]

def with_runner(func):
    async def test(s, **kwargs):
        final_future = asyncio.Future()
        try:
            runner = MemoryTargetRunner(final_future, s.devices, **kwargs)
            async with runner:
                await s.wait_for(func(s, runner))
        finally:
            final_future.cancel()
            runner.reset_devices()
    test.__name__ = func.__name__
    return test

class ModuleLevelRunner:
    def __init__(self, *args, **kwargs):
        self.loop = asyncio.new_event_loop()

        self.args = args
        self.kwargs = kwargs

    async def server_runner(self, devices, **kwargs):
        final_future = asyncio.Future()
        runner = MemoryTargetRunner(final_future, devices, **kwargs)
        await runner.start()

        async def close():
            final_future.cancel()
            await runner.close()

        return runner, close

    def setUp(self):
        """
        Set the loop to our loop and use ``serve_runner`` to get a runner and
        closer
        """
        asyncio.set_event_loop(self.loop)
        self.runner, self.closer = self.loop.run_until_complete(self.server_runner(*self.args, **self.kwargs))

    def tearDown(self):
        """
        Call our closer function returned from ``server_runner`` and set close
        our loop
        """
        if self.closer is not None:
            self.loop.run_until_complete(self.closer())
        self.loop.close()
        asyncio.set_event_loop(asyncio.new_event_loop())

    def test(self, func):
        async def test(s):
            self.runner.reset_devices()
            await s.wait_for(func(s, self.runner), timeout=10)
        test.__name__ = func.__name__
        return test

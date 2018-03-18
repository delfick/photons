# coding: spec

from photons_transform.transformer import Transformer

from photons_app.test_helpers import AsyncTestCase, FakeTargetIterator

from photons_device_messages import DeviceMessages
from photons_colour import ColourMessages, Parser
from photons_script.script import Pipeline

from noseOfYeti.tokeniser.async_support import async_noy_sup_setUp
from functools import partial
import mock

def simplify(item_kls, script_part, chain=None):
    if type(script_part) is not list:
        script_part = [script_part]

    final = []
    for p in script_part:
        if getattr(p, "has_children", False):
            final.append(p.simplified(partial(simplify, item_kls), []))
            continue
        else:
            final.append(p)

    yield item_kls(final)

describe AsyncTestCase, "Transformer":
    describe "just a power message":
        async it "Uses SetPower if no duration":
            msg = Transformer.using({"power": "off"})
            self.assertEqual(msg.pkt_type, DeviceMessages.SetPower.Payload.message_type)
            self.assertEqual(msg.payload.as_dict(), {"level": 0})

            msg = Transformer.using({"power": "on"})
            self.assertEqual(msg.pkt_type, DeviceMessages.SetPower.Payload.message_type)
            self.assertEqual(msg.payload.as_dict(), {"level": 65535})

        async it "uses SetLightPower if we have duration":
            msg = Transformer.using({"power": "off", "duration": 100})
            self.assertEqual(msg.pkt_type, DeviceMessages.SetLightPower.Payload.message_type)
            self.assertEqual(msg.payload.as_dict(), {"level": 0, "duration": 100})

            msg = Transformer.using({"power": "on", "duration": 20})
            self.assertEqual(msg.pkt_type, DeviceMessages.SetLightPower.Payload.message_type)
            self.assertEqual(msg.payload.as_dict(), {"level": 65535, "duration": 20})

    describe "when we have more than just power change":
        async before_each:
            self.target = FakeTargetIterator()
            self.afr = mock.Mock(name='afr')
            self.serial = "d073d5000000"

        async def transform(self, state, keep_brightness=False):
            class item_kls:
                def __init__(s, parts):
                    s.parts = parts

                async def run_with(s, *args, **kwargs):
                    for part in s.parts:
                        if isinstance(part, Pipeline):
                            async for info in part.run_with(*args, **kwargs):
                                yield info
                        else:
                            async for info in self.target.script(part).run_with(*args, **kwargs):
                                yield info

            msg = Transformer.using(state, keep_brightness=keep_brightness)
            simplified = msg.simplified(partial(simplify, item_kls))
            async def doit():
                async for _ in simplified.run_with([self.serial], self.afr):
                    pass
            await self.wait_for(doit())

        async def assertTransformBehaves(self, transform_into, state, first_colour_message, power_message, second_colour_message, **kwargs):
            expected = 0
            getter = ColourMessages.GetColor(ack_required=False, res_required=True)
            self.target.expect_call(
                mock.call(getter, [self.serial], self.afr
                    , error_catcher=mock.ANY, timeout=1, find_timeout=1
                    )
                  , [(state, None, None)]
                  )

            if first_colour_message is not None:
                expected += 1
                first_colour_message.target = self.serial
                first_colour_message.res_required = False
                first_colour_message.ack_required = True

                self.target.expect_call(
                    mock.call(first_colour_message, [], self.afr
                        , error_catcher=mock.ANY, timeout=1, accept_found=True
                        )
                    , []
                    )

            if power_message is not None:
                expected += 1
                power_message.target = self.serial
                power_message.res_required = False
                power_message.ack_required = True

                self.target.expect_call(
                    mock.call(power_message, [], self.afr
                        , error_catcher=mock.ANY, timeout=1, accept_found=True
                        )
                    , []
                    )

            if second_colour_message is not None:
                expected += 1
                second_colour_message.target = self.serial
                second_colour_message.res_required = False
                second_colour_message.ack_required = True

                self.target.expect_call(
                    mock.call(second_colour_message, [], self.afr
                        , error_catcher=mock.ANY, timeout=1, accept_found=True
                        )
                    , []
                    )

            await self.transform(transform_into, **kwargs)
            self.assertEqual(self.target.call, expected)

        async it "sets power on if it needs to":
            state = ColourMessages.LightState.empty_normalise(
                  target=self.serial, source=0, sequence=0
                , hue=0, saturation=0, brightness=0.5, kelvin=3500
                , power=0, label="blah"
                )

            first_colour_message = Parser.color_to_msg("blue", {"brightness": 0})
            power_message = DeviceMessages.SetPower(level=65535)
            second_colour_message = Parser.color_to_msg("blue", {"brightness": 0.5})

            await self.assertTransformBehaves({"color": "blue", "power": "on"}, state
                , first_colour_message
                , power_message
                , second_colour_message
                )

        async it "sets power on if it needs to with duration":
            state = ColourMessages.LightState.empty_normalise(
                  target=self.serial, source=0, sequence=0
                , hue=0, saturation=0, brightness=0.5, kelvin=3500
                , power=0, label="blah"
                )

            first_colour_message = Parser.color_to_msg("blue", {"brightness": 0})
            power_message = DeviceMessages.SetLightPower(level=65535, duration=10)
            second_colour_message = Parser.color_to_msg("blue", {"brightness": 0.5, "duration": 10})

            await self.assertTransformBehaves({"color": "blue", "power": "on", "duration": 10}, state
                , first_colour_message
                , power_message
                , second_colour_message
                )

        async it "doesn't set power if it doesn't need to":
            state = ColourMessages.LightState.empty_normalise(
                  target=self.serial, source=0, sequence=0
                , hue=0, saturation=0, brightness=0.5, kelvin=3500
                , power=0, label="blah"
                )

            first_colour_message = Parser.color_to_msg("blue", {"brightness": 0})
            power_message = None
            second_colour_message = Parser.color_to_msg("blue", {"brightness": 0.5, "duration": 10})

            await self.assertTransformBehaves({"color": "blue", "power": "off", "duration": 10}, state
                , first_colour_message
                , power_message
                , second_colour_message
                )

        async it "doesn't set power if it doesn't need to because power not provided":
            state = ColourMessages.LightState.empty_normalise(
                  target=self.serial, source=0, sequence=0
                , hue=0, saturation=0, brightness=0.5, kelvin=3500
                , power=0, label="blah"
                )

            first_colour_message = Parser.color_to_msg("blue", {"brightness": 0})
            power_message = None
            second_colour_message = Parser.color_to_msg("blue", {"brightness": 0.5, "duration": 10})

            await self.assertTransformBehaves({"color": "blue", "duration": 10}, state
                , first_colour_message
                , power_message
                , second_colour_message
                )

        async it "doesn't reset if it doesn't need to":
            state = ColourMessages.LightState.empty_normalise(
                  target=self.serial, source=0, sequence=0
                , hue=0, saturation=0, brightness=0.5, kelvin=3500
                , power=65535, label="blah"
                )

            first_colour_message = None
            power_message = None
            second_colour_message = Parser.color_to_msg("blue", {"duration": 10})

            await self.assertTransformBehaves({"color": "blue", "duration": 10}, state
                , first_colour_message
                , power_message
                , second_colour_message
                )

        async it "doesn't reset if it doesn't need to and power is specified on":
            state = ColourMessages.LightState.empty_normalise(
                  target=self.serial, source=0, sequence=0
                , hue=0, saturation=0, brightness=0.5, kelvin=3500
                , power=65535, label="blah"
                )

            first_colour_message = None
            power_message = None
            second_colour_message = Parser.color_to_msg("blue", {"duration": 10})

            await self.assertTransformBehaves({"color": "blue", "power": "on", "duration": 10}, state
                , first_colour_message
                , power_message
                , second_colour_message
                )

        async it "doesn't reset if it doesn't need to and power is specified off":
            state = ColourMessages.LightState.empty_normalise(
                  target=self.serial, source=0, sequence=0
                , hue=0, saturation=0, brightness=0.5, kelvin=3500
                , power=65535, label="blah"
                )

            first_colour_message = None
            power_message = DeviceMessages.SetLightPower(level=0, duration=10)
            second_colour_message = Parser.color_to_msg("blue", {"duration": 10})

            await self.assertTransformBehaves({"color": "blue", "power": "off", "duration": 10}, state
                , first_colour_message
                , power_message
                , second_colour_message
                )

        async it "doesn't reset if it doesn't need to and power is specified off and not duration":
            state = ColourMessages.LightState.empty_normalise(
                  target=self.serial, source=0, sequence=0
                , hue=0, saturation=0, brightness=0.5, kelvin=3500
                , power=65535, label="blah"
                )

            first_colour_message = None
            power_message = DeviceMessages.SetPower(level=0)
            second_colour_message = Parser.color_to_msg("blue")

            await self.assertTransformBehaves({"color": "blue", "power": "off"}, state
                , first_colour_message
                , power_message
                , second_colour_message
                )

        async it "overrides brightness if we say keep brightness":
            state = ColourMessages.LightState.empty_normalise(
                  target=self.serial, source=0, sequence=0
                , hue=0, saturation=0, brightness=0.5, kelvin=3500
                , power=65535, label="blah"
                )

            first_colour_message = None
            power_message = DeviceMessages.SetPower(level=0)
            second_colour_message = Parser.color_to_msg("blue", {"brightness": 0.5})

            await self.assertTransformBehaves({"color": "blue", "power": "off"}, state
                , first_colour_message
                , power_message
                , second_colour_message
                , keep_brightness=True
                )

        async it "overrides brightness if we say keep brightness and turning power on":
            state = ColourMessages.LightState.empty_normalise(
                  target=self.serial, source=0, sequence=0
                , hue=0, saturation=0, brightness=0.5, kelvin=3500
                , power=65535, label="blah"
                )

            first_colour_message = None
            power_message = None
            second_colour_message = Parser.color_to_msg("blue", {"brightness": 0.5})

            await self.assertTransformBehaves({"color": "blue", "power": "on"}, state
                , first_colour_message
                , power_message
                , second_colour_message
                , keep_brightness=True
                )

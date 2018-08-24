from photons_app.executor import library_setup
from photons_app.special import FoundSerials

from photons_script.script import ATarget, Pipeline
from photons_device_messages import DeviceMessages
from photons_colour import Parser, ColourMessages

import asyncio

collector = library_setup()

lan_target = collector.configuration['target_register'].resolve("lan")

color_names = ["blue", "red", "orange", "yellow", "cyan", "green", "blue", "purple", "pink"]

spread = 2

power_on = DeviceMessages.SetPower(level=65535)
get_color = ColourMessages.GetColor()
color_msgs = [Parser.color_to_msg(name, overrides={"res_required": False, "duration": spread}) for name in color_names]

async def doit():
    async with ATarget(lan_target) as afr:
        # By using a pipeline we can introduce a wait time between successful sending of colors
        colors = Pipeline(*color_msgs, spread=spread, synchronized=True)

        # by having power_on and get_color in an array we are sending both at the same time
        # without waiting for the other to get a reply first
        # We use a pipeline so that the power is turned on before we start the colors
        pipeline = Pipeline([power_on, get_color], colors, synchronized=True)

        original_colors = {}
        async for pkt, _, _ in lan_target.script(pipeline).run_with(FoundSerials(), afr):
            # We set res_required on the colors to False on line 20
            # Which means only the ``get_color`` messages will return a LightState
            # We use this to record what the color of the light was before the rainbow
            if pkt | ColourMessages.LightState:
                color = "kelvin:{kelvin} hue:{hue} saturation:{saturation} brightness:{brightness}"
                original_colors[pkt.target] = (pkt.power, color.format(**pkt.payload.as_dict()))

        await asyncio.sleep(spread)

        msgs = []
        for target, (level, color) in original_colors.items():
            msg1 = Parser.color_to_msg(color, overrides={"duration": spread})
            msg2 = DeviceMessages.SetPower(level=level)

            # By setting the target directly on the message we don't have to
            # provide the references to the run_with_all call
            for msg in (msg1, msg2):
                msg.target = target
                msg.res_required = False
                msgs.append(msg)

        # We share the afr we got from ATarget so that we don't have to search for the ips of the lights again
        await lan_target.script(msgs).run_with_all(None, afr)

loop = collector.configuration["photons_app"].loop
loop.run_until_complete(doit())

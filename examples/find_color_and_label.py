from photons_app.executor import library_setup
from photons_app.special import FoundSerials

from photons_messages import DeviceMessages, ColourMessages
from photons_script.script import Decider

collector = library_setup()

lan_target = collector.configuration['target_register'].resolve("lan")

async def doit():
    getter = [DeviceMessages.GetLabel(), ColourMessages.GetColor()]

    def found(serial, *states):
        info = {"label": "", "hsbk": ""}
        for s in states:
            if s | DeviceMessages.StateLabel:
                info["label"] = s.label
            elif s | ColourMessages.LightState:
                info["hsbk"] = " ".join(
                      "{0}={1}".format(key, s.payload[key])
                      for key in ("hue", "saturation", "brightness", "kelvin")
                    )
        print("{0}: {1}: {2}".format(serial, info["label"], info["hsbk"]))
        return []

    msg = Decider(getter, found, [DeviceMessages.StateLabel, ColourMessages.LightState])
    await lan_target.script(msg).run_with_all(FoundSerials())

loop = collector.configuration["photons_app"].loop
loop.run_until_complete(doit())

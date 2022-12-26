import itertools
import os
import sys

from photons_app import helpers as hp
from photons_app.mimic.device import Device
from photons_app.mimic.event import Events
from photons_app.mimic.transport import MemoryTarget
from photons_messages import Services, protocol_register
from photons_transport.targets import LanTarget

this_dir = os.path.dirname(__file__)
for fle in os.listdir(os.path.join(this_dir, "operators")):
    if fle.startswith(".") or fle.startswith("_"):
        continue

    if fle.endswith(".py"):
        fle = fle[:-3]

    __import__(f"photons_app.mimic.operators.{fle}")


class Serials:
    def __init__(self):
        self.num = 0xD073D5000000

    def __iter__(self):
        return self

    def __next__(self):
        self.num += 1
        return f"{self.num:12x}"


class Store:
    def __init__(self):
        self.record = []
        self._intercept = None

    @property
    def device(self):
        return self._device

    @device.setter
    def device(self, device):
        self._device = device

    def __str__(self):
        return str(self.record)

    def __repr__(self):
        return f"<Store: {self.record}>"

    def __iter__(self):
        return iter(self.record)

    def intercept(self, event):
        if self._intercept:
            return self._intercept(event)
        else:
            return event

    def clear(self):
        self.record.clear()

    def __bool__(self):
        return bool(self.record)

    def assertNotContains(self, *want, record=None):
        want = list(want)
        recorded = self.record if record is None else record
        for w in want:
            assert all(r != w for r in recorded)

    def assertContainsInOrder(self, *want, record=None):
        want = list(want)
        recorded = self.record if record is None else record
        if recorded == want:
            return

        original = list(recorded)
        recorded = list(recorded)
        while want:
            if not recorded:
                print("Remaining items")
                for w in want:
                    print(f"  - {w}")

                print()
                print("original contained")
                for r in original:
                    print(f"  - {r}")
                assert False

            nxtwant = want.pop(0)

            while recorded:
                nxtrecorded = recorded.pop(0)
                if nxtrecorded == nxtwant:
                    if not want:
                        return
                    else:
                        break

                if not recorded:
                    want.insert(0, nxtwant)
                    break

    def __eq__(self, other, *, record=None):
        recorded = self.record if record is None else record
        if recorded == other:
            return True

        for i, (r, w) in enumerate(itertools.zip_longest(recorded, other)):
            if r != w:
                print(f"Different item: {i}")
                print(f"    Recorded  : {r}")
                print(f"    Want      : {w}")
                print("==")
            else:
                print(f"Same item    : {i}")
                print(f"    Recorded : {r}")
                print(f"    Want     : {w}")
                print("==")
        return recorded == other

    def count(self, event):
        return sum(1 for e in self.record if e == event)

    def incoming(self, ignore=None):
        found = []
        ig = ignore
        if ignore is None:
            ig = []
        for e in self.record:
            if e | Events.INCOMING and not any(e | ii for ii in ig):
                found.append(e)
        return found

    def assertAttrs(self, **attrs):
        for k, v in attrs.items():
            assert k in self.device.attrs
            got = getattr(self.device.attrs, k)
            if hasattr(got, "as_dict"):
                got = got.as_dict()
            if hasattr(v, "as_dict"):
                v = v.as_dict()
            assert got == v

    def assertIncoming(self, *expected, ignore=None, remove_duplicates=True):
        got = list(self.incoming(ignore=ignore))
        want = [Events.INCOMING(self.device, self.device.io["MEMORY"], pkt=pkt) for pkt in expected]

        unmatched = []
        remaining = list(got)
        ww = list(want)
        while ww:
            w = ww.pop(0)
            found = False
            buf = []
            for f in remaining:
                if not found and f == w:
                    found = True
                else:
                    buf.append(f)

            if not found:
                unmatched.append(w)
            remaining = buf

        if remove_duplicates:
            remaining = [event for event in remaining if not any(event == w for w in want)]

        if not unmatched and not remaining:
            return

        print("Wanted the following")
        for event in want:
            print(f" - {event}")
        print()

        print("Got the following")
        for event in got:
            print(f" - {event}")
        print()

        if unmatched:
            print("Following did not have matches")
            for event in unmatched:
                print(f" - {event}")
            print()

        if remaining:
            print("Following was found unexpectedly")
            for event in remaining:
                print(f" - {event}")
            print()

        assert False

    def assertNoSetMessages(self):
        for e in self.record:
            if e | Events.INCOMING and "Set" in e.pkt.__class__.__name__:
                for i, e in enumerate(self.record):
                    print(f"    Event {i}: {e}")
                assert False, "Found a set message"

    def append(self, event):
        self.record.append(self.intercept(event))


class DeviceCollection:
    Events = Events

    def __init__(self, has_udp=False, has_memory=True):
        self.devices = {}
        self.stores = {}
        self.serial_seq = iter(Serials())

        self.has_udp = has_udp
        self.has_memory = has_memory

    def __iter__(self):
        return iter(self.devices.values())

    def __len__(self):
        return len(self.devices)

    def __contains__(self, device):
        try:
            self[device]
        except KeyError:
            return False
        else:
            return True

    @property
    def serials(self):
        return sorted([d.serial for d in self.devices.values()])

    def add(self, label):
        def adder(serial, *args, **kwargs):
            if "value_store" not in kwargs:
                kwargs["value_store"] = {}
            store = Store()
            self.stores[serial] = store
            kwargs["value_store"] = {
                **kwargs["value_store"],
                "record_events_store": store,
                "make_packet_waiter": True,
            }

            kwargs["value_store"] = {
                "no_memory_io": not self.has_memory,
                "no_udp_io": not self.has_udp,
                **kwargs["value_store"],
            }

            device = Device(serial, *args, **kwargs)
            store.device = device
            self.devices[label] = device
            return device

        return adder

    def store(self, device):
        device = self[device]
        return self.stores[device.serial]

    def __getitem__(self, device):
        if device in self.devices:
            return self.devices[device]
        if device in self.devices.values():
            return device

        for d in self.devices.values():
            if d.serial == device:
                return d

        raise KeyError(device)

    def for_attribute(self, key, value, expect=1):
        got = []
        for d in self.devices.values():
            if d.attrs[key] == value:
                got.append(d)
        assert len(got) == expect, f"Expected {expect} devices, got {len(got)}: {got}"
        return got

    @hp.asynccontextmanager
    async def for_test(self, final_future, udp=False):
        async with hp.TaskHolder(final_future, name="DeviceCollection::for_test") as ts:
            sessions = [device.session(final_future) for device in self.devices.values()]
            try:
                tt = []
                for session in sessions:
                    tt.append(ts.add(session.start()))

                await hp.wait_for_all_futures(
                    *tt, name="DeviceCollection::for_test[wait_for_start]"
                )

                configuration = {
                    "final_future": final_future,
                    "protocol_register": protocol_register,
                    "devices": [device for device in self.devices.values()],
                }
                if udp:
                    target = LanTarget.create(configuration)
                else:
                    target = MemoryTarget.create(configuration)

                async with target.session() as sender:
                    if udp:
                        for device in self.devices.values():
                            await sender.add_service(
                                device.serial,
                                Services.UDP,
                                port=device.io["UDP"].options.port,
                                host="127.0.0.1",
                            )
                    for store in self.stores.values():
                        store.clear()
                    yield sender

            finally:
                exc_typ, exc, tb = sys.exc_info()
                for session in sessions:
                    ts.add(session.finish(exc_typ=exc_typ, exc=exc, tb=tb))


__all__ = ["Device", "DeviceCollection"]

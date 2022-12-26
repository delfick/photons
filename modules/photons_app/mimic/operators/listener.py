from delfick_project.norms import dictobj, sb
from photons_app import helpers as hp
from photons_app.mimic.event import Events
from photons_app.mimic.operator import Viewer, operator


@operator
class Listener(Viewer):
    class Options(dictobj.Spec):
        show_packets_from_other_devices = dictobj.Field(sb.boolean, default=False)
        show_set64_contents = dictobj.Field(sb.boolean, default=False)

    @classmethod
    def select(kls, device):
        if device.value_store.get("console_output", True):
            return kls(device, device.value_store)

    async def respond(self, event):
        if (
            hasattr(event, "pkt")
            and not self.options.show_packets_from_other_devices
            and event.pkt.serial != self.device.serial
            and event.pkt.serial != "00" * 6
        ):
            return

        for line in event.for_console(show_set64_contents=self.options.show_set64_contents):
            print(line)
        print()


@operator
class Recorder(Viewer):
    class Options(dictobj.Spec):
        test_console_record = dictobj.Field(sb.any_spec, wrapper=sb.required)

    @classmethod
    def select(kls, device):
        if "test_console_record" in device.value_store:
            return kls(device, {"test_console_record": device.value_store["test_console_record"]})

    async def respond(self, event):
        for line in event.for_console(time=False):
            print(line, file=self.options.test_console_record)
        print(file=self.options.test_console_record)


@operator
class RecordEvents(Viewer):
    class Options(dictobj.Spec):
        got_event_fut = dictobj.NullableField(sb.any_spec())
        record_annotations = dictobj.Field(sb.boolean, default=False)
        record_events_store = dictobj.Field(sb.any_spec(), wrapper=sb.required)

    @classmethod
    def select(kls, device):
        if "record_events_store" in device.value_store:
            return kls(device, device.value_store)

    async def respond(self, event):
        if not self.options.record_annotations and event | Events.ANNOTATION:
            return

        self.options.record_events_store.append(event)
        if self.options.got_event_fut is not None:
            self.options.got_event_fut.reset()
            self.options.got_event_fut.set_result(event)


class EventWaiter:
    def __init__(self, device):
        self.waiters = []
        self.device = device

    def match(self, event):
        after = []
        waiters = list(self.waiters)

        while waiters:
            fut, match = waiters.pop(0)
            if match(event):
                if not fut.done():
                    fut.set_result(event)
                break
            else:
                after.append((fut, match))

        self.waiters = after + waiters

    def wait_for_incoming(self, io, pkt):
        if isinstance(pkt, type):
            desc = pkt.__name__
        elif isinstance(pkt, tuple):
            desc = f"{pkt[0].__name__}({pkt[1]})"
        else:
            desc = "{pkt.__class__.__name__}({repr(pkt.payload)})"

        fut = hp.create_future(name=f"EventWaiter::wait_incoming[{io}, {desc}]")

        def match(event):
            return event == Events.INCOMING(self.device, io, pkt=pkt)

        self.waiters.append((fut, match))
        return fut

    def wait_for_event(self, want):
        fut = hp.create_future(name=f"EventWaiter::wait_for_event[{repr(want)}]")

        def match(event):
            return event | want

        self.waiters.append((fut, match))
        return fut


@operator
class PacketWaiter(Viewer):
    @classmethod
    def select(kls, device):
        if "make_packet_waiter" in device.value_store:
            return kls(device)

    attrs = [
        Viewer.Attr.Lambda(
            "event_waiter", from_zero=lambda event, options: EventWaiter(event.device)
        )
    ]

    async def respond(self, event):
        if hasattr(self.device.attrs, "event_waiter"):
            self.device.attrs.event_waiter.match(event)

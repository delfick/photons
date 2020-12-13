from photons_transport.session.memory import MemoryService

from photons_app.errors import PhotonsAppError
from photons_app import helpers as hp

from photons_messages import Services, CoreMessages, DiscoveryMessages, DeviceMessages
from photons_protocol.messages import Messages
from photons_protocol.types import Type as T

from contextlib import contextmanager
from delfick_project.norms import sb
from collections import defaultdict
from functools import partial
import binascii
import logging
import asyncio
import socket
import time
import uuid

log = logging.getLogger("photons_transport.fake")


class IgnoreMessage(Exception):
    pass


class NoSuchResponder(PhotonsAppError):
    desc = "Device didn't have desired responder on it"


class Attrs:
    def __init__(self, device):
        self._attrs = {}
        self._device = device

    def _set_attr(self, key, value):
        self._device.validate_attr(key, value)
        self._attrs[key] = value

    def __contains__(self, key):
        return key in self._attrs

    def __setitem__(self, key, value):
        self._set_attr(key, value)

    def __setattr__(self, key, value):
        if key.startswith("_"):
            object.__setattr__(self, key, value)
        else:
            self._set_attr(key, value)

    def __getitem__(self, key):
        return self._attrs[key]

    def __getattr__(self, key):
        if key.startswith("_"):
            return object.__getattribute__(self, key)
        else:
            attrs = object.__getattribute__(self, "_attrs")
            if key not in attrs:
                raise AttributeError(f"No such attribute {key}")
            return attrs[key]

    def __dir__(self):
        return sorted(object.__dir__(self) + list(self._attrs.keys()))


class Service:
    def __init__(self, service, closer, add_service, state_service, address):
        self.service = service
        self.closer = closer
        self.address = address
        self.add_service = add_service
        self.state_service = state_service


def pktkeys(msgs, keep_duplicates=False):
    keys = []
    for msg in msgs:
        clone = msg.payload.clone()
        if hasattr(clone, "instanceid"):
            clone.instanceid = 0
        for name, typ in clone.Meta.field_types:
            if clone.actual(name) is sb.NotSpecified and isinstance(typ, type(T.Reserved)):
                clone[name] = None

        key = (msg.protocol, msg.pkt_type, repr(clone))
        if key not in keys or keep_duplicates:
            keys.append(key)
    return keys


def safe_packet_repr(pkt, *, limit=None):
    try:
        payload_repr = repr(pkt.payload)
    except Exception as error:
        payload_repr = f"<Failed repr ({error.__class__.__name__}): {pkt.__class__.__name__}>"

    if limit and len(payload_repr) > limit:
        payload_repr = f"{payload_repr[:limit]}..."

    return payload_repr


class Responder:
    _fields = []

    def __init__(self, **kwargs):
        for field in self._fields:
            if not isinstance(field, tuple) and field not in kwargs:
                raise TypeError(f"Missing argument {field}")

            key = field
            zero = None
            if isinstance(field, tuple):
                if len(field) != 2:
                    raise TypeError(f"tuple field should be (name, default), got {field}")

                if field[0] not in kwargs:
                    zero = field[1]()

                key = field[0]

            if key not in kwargs and isinstance(field, tuple):
                setattr(self, f"_attr_default_{key}", zero)
            else:
                setattr(self, f"_attr_default_{key}", kwargs[key])

    async def reset(self, device, *, zero=False):
        for field in self._fields:
            zero_val = None
            has_zero = False
            if isinstance(field, tuple):
                if zero:
                    zero_val = field[1]()
                    has_zero = True
                field = field[0]

            if zero and has_zero:
                val = zero_val
            else:
                val = getattr(self, f"_attr_default_{field}")

            device.attrs[field] = val

    async def respond(self, device, pkt, source):
        if False:
            yield


class ServicesResponder(Responder):
    _fields = [("limited_services", lambda: None), ("delay_discovery", lambda: False)]

    @classmethod
    @contextmanager
    def limited_services(kls, device, *services):
        before = device.attrs.limited_services
        try:
            device.attrs.limited_services = services
            yield
        finally:
            device.attrs.limited_services = before

    @classmethod
    def filtered_services(kls, device):
        for service in device.services:
            if device.attrs.limited_services:
                if not any(service.service is s for s in device.attrs.limited_services):
                    continue
            yield service

    async def respond(self, device, pkt, source):
        if pkt | DiscoveryMessages.GetService:
            if device.attrs.delay_discovery:
                await asyncio.sleep(0.2)
            for service in self.filtered_services(device):
                yield service.state_service


class EchoResponder(Responder):
    async def respond(self, device, pkt, source):
        if pkt | DeviceMessages.EchoRequest:
            yield DeviceMessages.EchoResponse(echoing=pkt.echoing)


class FakeDevice(hp.AsyncCMMixin):
    def __init__(
        self,
        serial,
        responders,
        protocol_register=None,
        port=None,
        use_sockets=False,
        delay_discovery=False,
    ):
        self.port = port
        self.serial = serial
        self.use_sockets = use_sockets
        if protocol_register is None:
            from photons_messages import protocol_register
        self.protocol_register = protocol_register

        self.responders = responders
        self.echo_responder = EchoResponder()
        self.service_responder = ServicesResponder(delay_discovery=delay_discovery)

        self.attrs = Attrs(self)
        self.attrs.online = False

        self.wait_for_reboot_fut = hp.ResettableFuture(
            name=f"FakeDevice({serial})::__init__[wait_for_reboot_fut]"
        )
        self.wait_for_reboot_fut.set_result(True)

        self.reboots = []
        self.services = []
        self.pre_reboot = None
        self.write_tasks = []
        self.time_rebooting = 1

        self.setup()

    def __repr__(self):
        product = ""
        if "product" in self.attrs:
            product = f": {self.attrs.product.friendly}"
        return f"<FakeDevice {self.serial}{product}>"

    def get_responder(self, kls):
        for responder in self.responders:
            if isinstance(responder, kls):
                return responder
        raise NoSuchResponder(wanted=kls)

    def setup(self):
        pass

    @property
    def all_responders(self):
        for r in self.responders:
            yield r
        yield self.service_responder
        yield self.echo_responder

    def validate_attr(self, key, value):
        for r in self.all_responders:
            if hasattr(r, "validate_attr"):
                r.validate_attr(self, key, value)

    async def reset(self, *, zero=False):
        self.no_res = {}
        self.no_acks = {}
        self.reboots = []
        self.waiters = {}
        self.set_replies = defaultdict(list)
        self.intercept_got_message = None

        self.reset_received()

        for responder in self.all_responders:
            await responder.reset(self, zero=zero)

        self.attrs.online = True

    @contextmanager
    def reboot_options(self, time_rebooting, pre_reboot=None):
        before_time_rebooting = self.time_rebooting
        before_pre_reboot = self.pre_reboot
        try:
            self.time_rebooting = time_rebooting
            self.pre_reboot = pre_reboot
            yield
        finally:
            self.time_rebooting = before_time_rebooting
            self.pre_reboot = before_pre_reboot

    async def reboot(self):
        if callable(self.pre_reboot):
            await self.pre_reboot(self)

        self.attrs.online = False
        self.reboots.append(time.time())

        self.wait_for_reboot_fut.reset()

        for responder in self.all_responders:
            if hasattr(responder, "shutdown"):
                await responder.shutdown(self)

        async def back_online(time_rebooting, power_on):
            await asyncio.sleep(time_rebooting)
            await power_on()
            if not self.wait_for_reboot_fut.done():
                self.wait_for_reboot_fut.set_result(True)

        if self.time_rebooting >= 0:
            hp.async_as_background(back_online(self.time_rebooting, self.power_on))
        else:
            self.wait_for_reboot_fut.set_result(True)

    async def power_on(self):
        self.attrs.online = True
        for responder in self.all_responders:
            if hasattr(responder, "restart"):
                await responder.restart(self)

    async def start(self):
        await self.finish()
        await self.reset()

        if self.use_sockets:
            await self.ensure_udp_service()
        else:
            await self.ensure_memory_service()

        for responder in self.all_responders:
            if hasattr(responder, "start"):
                await responder.start(self)

    async def finish(self, exc_typ=None, exc=None, tb=None):
        for service in self.services:
            await service.closer()
        self.services = []

        for responder in self.all_responders:
            if hasattr(responder, "shutdown"):
                await responder.shutdown(self)

        await hp.cancel_futures_and_wait(
            *self.write_tasks, name=f"FakeDevice({self.serial})::finish[wait_for_writes]"
        )

    def set_intercept_got_message(self, interceptor):
        self.intercept_got_message = interceptor

    def set_reply(self, kls, msg):
        self.set_replies[kls].append(msg)

    def reset_received(self):
        self.received = []

    async def add_services(self, adder):
        for service in ServicesResponder.filtered_services(self):
            await service.add_service(adder)

    def sync_write(self, *args, **kwargs):
        task = hp.async_as_background(self.write(*args, **kwargs))
        self.write_tasks.append(task)
        return task

    async def write(self, source, received_data, bts, addr=None):
        if not self.attrs.online:
            return

        if addr is None:
            for service in self.services:
                a = service.address(source)
                if a:
                    addr = a
                    break

        if addr is None:
            log.warning(
                hp.lc(
                    "Tried to write a packet to the fake device, but no appropriate service found",
                    source=source,
                    serial=self.serial,
                )
            )
            return

        log.debug(
            hp.lc("RECV", bts=binascii.hexlify(bts).decode(), source=source, serial=self.serial)
        )

        pkt = Messages.create(bts, self.protocol_register, unknown_ok=True)
        pkt.Information.update(remote_addr=addr, sender_message=None)
        if pkt.serial not in ("000000000000", self.serial):
            return

        async for msg in self.got_message(pkt, source):
            await received_data(msg.tobytes(serial=self.serial), addr)

    async def is_reachable(self, broadcast_address):
        return self.attrs.online

    async def discoverable(self, broadcast_address):
        if not await self.is_reachable(broadcast_address):
            return False

        for responder in self.all_responders:
            if hasattr(responder, "undiscoverable"):
                if await responder.undiscoverable(self):
                    return False

        return True

    @contextmanager
    def offline(self):
        try:
            self.attrs.online = False
            yield
        finally:
            self.attrs.online = True

    @contextmanager
    def no_acks_for(self, kls):
        ident = str(uuid.uuid4())
        try:
            self.no_acks[ident] = kls
            yield
        finally:
            if ident in self.no_acks:
                del self.no_acks[ident]

    @contextmanager
    def no_replies_for(self, kls):
        ident = str(uuid.uuid4())
        try:
            self.no_res[ident] = kls
            yield
        finally:
            if ident in self.no_res:
                del self.no_res[ident]

    @contextmanager
    def no_responses_for(self, kls):
        with self.no_acks_for(kls), self.no_replies_for(kls):
            yield

    def wait_for(self, source, kls):
        assert (source, kls) not in self.waiters
        fut = hp.create_future(name=f"FakeDevice({self.serial})::wait_for[fut]")
        self.waiters[(source, kls)] = fut
        return fut

    async def got_message(self, pkt, source):
        log.info(
            hp.lc(
                "Got packet",
                source=source,
                pkt=pkt.__class__.__name__,
                ip=pkt.Information.remote_addr,
                payload=safe_packet_repr(pkt, limit=300),
                pkt_source=pkt.source,
                serial=self.serial,
            )
        )

        if self.intercept_got_message:
            if await self.intercept_got_message(pkt, source) is False:
                return

        ack = await self.ack_for(pkt, source)
        if ack:
            ack.sequence = pkt.sequence
            ack.source = pkt.source
            ack.target = self.serial
            yield ack
            await self.process_reply(ack, source, pkt)

        try:
            async for res in self.response_for(pkt, source):
                res.sequence = pkt.sequence
                res.source = pkt.source
                res.target = self.serial

                log.info(
                    hp.lc(
                        "Created response",
                        source=source,
                        pkt=res.__class__.__name__,
                        payload=safe_packet_repr(res, limit=300),
                        pkt_source=res.source,
                        pkt_sequence=res.sequence,
                        serial=self.serial,
                    )
                )
                yield res
                await self.process_reply(res, source, pkt)
        except IgnoreMessage:
            pass

        for key, fut in list(self.waiters.items()):
            s, kls = key
            if s == source and pkt | kls:
                del self.waiters[key]
                fut.set_result(pkt)

    async def process_reply(self, pkt, source, request):
        for responder in self.all_responders:
            if hasattr(responder, "process_reply"):
                await responder.process_reply(self, pkt, source, request)

    async def stop_service(self, service):
        services = []
        existing = None

        for s in self.services:
            if s.service is service:
                existing = s
            else:
                services.append(s)

        self.services = services
        if existing:
            await existing.closer()

    async def ensure_memory_service(self):
        await self.stop_service(MemoryService)

        async def closer():
            pass

        async def add_service(adder):
            await adder(self.serial, MemoryService, writer=partial(self.write, "memory"))

        def address(source):
            if source == "memory":
                return (f"fake://{self.serial}/memory", 56700)

        state_service = DiscoveryMessages.StateService(service=Services.UDP, port=56700)
        self.services.append(Service(MemoryService, closer, add_service, state_service, address))

    async def ensure_udp_service(self):
        await self.stop_service(Services.UDP)

        class ServerProtocol(asyncio.Protocol):
            def connection_made(sp, transport):
                sp.udp_transport = transport

            def datagram_received(sp, data, addr):
                if not self.attrs.online:
                    return

                async def received_data(bts, a):
                    sp.udp_transport.sendto(bts, addr)

                self.sync_write("udp", received_data, data, addr)

            def error_received(sp, exc):
                log.error(hp.lc("Error on udp transport", error=exc))

        remote = None

        for i in range(3):
            port = self.port
            if port is None:
                port = self.make_port()

            try:
                remote, _ = await asyncio.get_event_loop().create_datagram_endpoint(
                    ServerProtocol, local_addr=("0.0.0.0", port)
                )
                break
            except OSError:
                log.exception("Couldn't make datagram server")
                await asyncio.sleep(0.1)

        if remote is None:
            raise Exception("Failed to bind to a udp socket for fake device")

        async def closer():
            remote.close()

        async def add_service(adder):
            await adder(self.serial, Services.UDP, host="127.0.0.1", port=port)

        def address(source):
            if source == "udp":
                return ("127.0.0.1", port)

        state_service = DiscoveryMessages.StateService(service=Services.UDP, port=port)
        self.services.append(Service(Services.UDP, closer, add_service, state_service, address))

    async def ack_for(self, pkt, source):
        for kls in self.no_acks.values():
            if pkt | kls:
                return

        if pkt.ack_required:
            return CoreMessages.Acknowledgement()

    async def do_send_response(self, pkt, source):
        for kls in self.no_res.values():
            if pkt | kls:
                return False

        if pkt.__class__.__name__.startswith("Get"):
            return True

        return pkt.res_required

    async def response_for(self, pkt, source):
        res = await self.make_response(pkt, source)
        if res is None or not await self.do_send_response(pkt, source):
            return

        if type(res) is list:
            for r in res:
                yield r
        else:
            yield res

    def make_port(self):
        """Return the port to listen to"""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("0.0.0.0", 0))
            return s.getsockname()[1]

    async def extra_make_response(self, pkt, source):
        """Hook for handling other messages"""
        if False:
            yield None

    async def make_response(self, pkt, source):
        self.received.append(pkt)

        for kls, msgs in self.set_replies.items():
            if msgs and pkt | kls:
                sr = msgs.pop()
                if callable(sr):
                    res = await sr(pkt, source)
                    msg = res
                    persist = False
                    if isinstance(res, tuple):
                        persist, msg = res
                    if persist:
                        msgs.append(sr)
                    if msg is not None:
                        return msg
                else:
                    return sr

        for responder in self.all_responders:
            res = []
            async for r in responder.respond(self, pkt, source):
                res.append(r)

            if res:
                return res

        extra = []
        async for r in self.extra_make_response(pkt, source):
            extra.append(r)

        if extra:
            return extra

        log.info(
            hp.lc(
                "Message wasn't handled",
                source=source,
                pkt=pkt.__class__.__name__,
                payload=safe_packet_repr(pkt, limit=300),
                serial=self.serial,
            )
        )

        res = []
        async for r in self.unhandled_response(pkt, source):
            res.append(r)

        if res:
            return res

    async def unhandled_response(self, pkt, source):
        """Hook async generator for making messages to send back when we can't handle a message"""
        if False:
            yield None

    def compare_received(self, expected, keep_duplicates=False):
        expect_keys = pktkeys(expected, keep_duplicates)
        got_keys = pktkeys(self.received, keep_duplicates)

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
                print(
                    f"{self.serial} Message {i} is different\n\tGOT:\n\t\t{got}\n\tEXPECT:\n\t\t{expect}"
                )
                different = True

        if different:
            print("=" * 80)
            do_print()
            assert False, "Expected messages to be the same"

    def compare_received_klses(self, expected):
        got = self.received
        got_keys = pktkeys(self.received, True)

        def do_print():
            print(self.serial)
            print("GOT:")
            for key in got_keys:
                print(f"\t{key}")
            print()
            print("EXPECTED:")
            for kls in expected:
                print(f"\t{kls}")
            print()

        if len(expected) != len(got):
            do_print()
            assert False, "Expected a different number of messages to what we got"

        different = False
        for i, (got, expect) in enumerate(zip(got, expected)):
            if not got | expect:
                print(
                    f"{self.serial} Message {i} is different\n\tGOT:\n\t\t{got}\n\tEXPECT:\n\t\t{expect}"
                )
                different = True

        if different:
            print("=" * 80)
            do_print()
            assert False, "Expected messages to be the same"

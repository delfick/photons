# coding: spec

from photons_socket.messages import Services, DiscoveryMessages
from photons_socket.target import SocketTarget

from photons_app.formatter import MergedOptionStringFormatter
from photons_app.test_helpers import AsyncTestCase
from photons_app.registers import ProtocolRegister
from photons_protocol.frame import LIFXPacket
from photons_app.errors import TimedOut
from photons_app import helpers as hp

from noseOfYeti.tokeniser.async_support import async_noy_sup_setUp, async_noy_sup_tearDown
from input_algorithms.meta import Meta
import threading
import asynctest
import binascii
import asyncio
import socket
import mock

describe AsyncTestCase, "SocketTarget":
    async before_each:
        self.protocol_register = ProtocolRegister()
        self.protocol_register.add(1024, LIFXPacket)
        self.protocol_register.message_register(1024).add(DiscoveryMessages)

        self.final_future = asyncio.Future()
        options = {"final_future": self.final_future, "protocol_register": self.protocol_register}

        meta = Meta(options, []).at("targets").at("lan")
        self.target = SocketTarget.FieldSpec(formatter=MergedOptionStringFormatter).normalise(meta, {})
        self.bridge = await self.target.args_for_run()

    async after_each:
        # Make sure we cleanup
        if hasattr(self, "bridge"):
            await self.target.close_args_for_run(self.bridge)
        self.final_future.cancel()

    async it "can communicate with a device":
        target = "d073d5000001"

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('0.0.0.0', 0))
            port = s.getsockname()[1]

        class ServerProtocol(asyncio.Protocol):
            def connection_made(sp, transport):
                self.transport = transport

            def datagram_received(sp, data, addr):
                pkt = DiscoveryMessages.unpack(data, protocol_register=self.protocol_register)
                assert pkt | DiscoveryMessages.GetService

                res = DiscoveryMessages.StateService(target=target, source=pkt.source, sequence=pkt.sequence, service=Services.UDP, port=port)
                self.transport.sendto(res.tobytes(None), addr)

        remote, _ = await self.loop.create_datagram_endpoint(ServerProtocol, local_addr=("0.0.0.0", port))

        try:
            self.assertEqual(self.bridge.found, {})
            await self.bridge.find_devices(('127.0.0.1', port), timeout=3)

            self.assertEqual(self.bridge.found
                  , { binascii.unhexlify(target)[:6]: (set([(Services.UDP, ("127.0.0.1", port))]), "127.0.0.1")
                  }
                )

            found = []
            script = self.target.script(DiscoveryMessages.GetService(ack_required=False))
            async for pkt, _, _ in script.run_with([target], self.bridge, timeout=3):
                found.append(pkt)

            self.assertEqual(len(found), 1)
            self.assertEqual(pkt.target[:6], binascii.unhexlify(target))
            self.assertEqual(pkt.service, Services.UDP)
            self.assertEqual(pkt.port, port)
        finally:
            remote.close()

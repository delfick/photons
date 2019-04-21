# coding: spec

from photons_socket.target import SocketTarget

from photons_app.test_helpers import AsyncTestCase
from photons_app.errors import TimedOut
from photons_app import helpers as hp

from photons_messages import Services, DiscoveryMessages, protocol_register

from noseOfYeti.tokeniser.async_support import async_noy_sup_setUp, async_noy_sup_tearDown
from unittest import mock
import threading
import asynctest
import binascii
import asyncio
import socket

describe AsyncTestCase, "SocketTarget":
    async before_each:
        self.final_future = asyncio.Future()
        options = {"final_future": self.final_future, "protocol_register": protocol_register}
        self.target = SocketTarget.create(options)
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
                pkt = DiscoveryMessages.unpack(data, protocol_register=protocol_register)
                assert pkt | DiscoveryMessages.GetService

                res = DiscoveryMessages.StateService(target=target, source=pkt.source, sequence=pkt.sequence, service=Services.UDP, port=port)
                self.transport.sendto(res.tobytes(None), addr)

        remote, _ = await self.loop.create_datagram_endpoint(ServerProtocol, local_addr=("0.0.0.0", port))

        try:
            self.assertEqual(self.bridge.found, {})
            await self.bridge.find_devices(timeout=3, broadcast=('127.0.0.1', port))

            self.assertEqual(self.bridge.found
                  , { binascii.unhexlify(target)[:6]: (set([(Services.UDP, ("127.0.0.1", port))]), "127.0.0.1")
                  }
                )

            found = []
            script = self.target.script(DiscoveryMessages.GetService(ack_required=False))
            async for pkt, _, _ in script.run_with([target], self.bridge, message_timeout=3):
                found.append(pkt)

            self.assertEqual(len(found), 1)
            self.assertEqual(pkt.target[:6], binascii.unhexlify(target))
            self.assertEqual(pkt.service, Services.UDP)
            self.assertEqual(pkt.port, port)
        finally:
            remote.close()

# coding: spec

from photons_socket.target import SocketTarget, SocketBridge

from photons_app.errors import TimedOut, FoundNoDevices
from photons_app.test_helpers import AsyncTestCase

from photons_messages import DiscoveryMessages, Services, protocol_register

from noseOfYeti.tokeniser.async_support import async_noy_sup_setUp, async_noy_sup_tearDown
import asynctest
import binascii
import asyncio
import mock

describe AsyncTestCase, "SocketBridge":
    async before_each:
        self.final_future = asyncio.Future()
        options = {"final_future": self.final_future, "protocol_register": protocol_register}
        self.target = SocketTarget.create(options)

    async after_each:
        self.final_future.cancel()

    async it "can be got from the target":
        bridge = None
        try:
            bridge = await self.target.args_for_run()
            self.assertEqual(type(bridge), SocketBridge)
        finally:
            if bridge:
                await self.target.close_args_for_run(bridge)

    describe "find_devices":
        async before_each:
            self.bridge = await self.target.args_for_run()

            self.target1 = "d073d5000001"
            self.target2 = "d073d5000002"
            self.target3 = "d073d5000003"

            self.target1_6 = binascii.unhexlify(self.target1)[:6]
            self.target2_6 = binascii.unhexlify(self.target2)[:6]
            self.target3_6 = binascii.unhexlify(self.target3)[:6]

            self.assertNotEqual(self.target1_6, self.target2_6)

            self.s = mock.Mock(name="s")
            self.s_run_with = mock.Mock(name="run_with")

            async def run_with(*args, **kwargs):
                for info in self.s_run_with(*args, **kwargs):
                    yield info
            self.s.run_with = run_with
            self.script = mock.Mock(name="script", return_value=self.s)

        async after_each:
            # Make sure to cleanup our bridge
            if hasattr(self, "bridge"):
                await self.target.close_args_for_run(self.bridge)

        async it "successfully finds devices":
            SS = DiscoveryMessages.StateService
            self.s_run_with.return_value = [
                  (SS(service=Services.UDP, port=56700, target=self.target1), "192.168.0.4", "255.255.255.255")
                , (SS(service=Services.UDP, port=56700, target=self.target2), "192.168.0.5", "255.255.255.255")
                ]

            with mock.patch.object(self.target, "script", self.script):
                self.assertEqual(self.bridge.found, {})
                await self.bridge.find_devices("255.255.255.255")

            self.assertEqual(self.bridge.found
                , { self.target1_6: (set([(Services.UDP, "192.168.0.4")]), "255.255.255.255")
                  , self.target2_6: (set([(Services.UDP, "192.168.0.5")]), "255.255.255.255")
                  }
                )

            self.script.assert_called_with(
                  DiscoveryMessages.GetService(ack_required=False, res_required=True, target=None, addressable=True, tagged=True)
                )

            self.s_run_with.assert_called_once_with([], self.bridge
                , broadcast = "255.255.255.255"
                , accept_found = True
                , message_timeout = 60
                )

        async it "forgets devices by default":
            self.bridge.found = {
                    self.target1_6: (set([(Services.UDP, "192.168.0.4")]), "255.255.255.255")
                  , self.target3_6: (set([(Services.UDP, "192.168.0.6")]), "255.255.255.255")
                  }

            SS = DiscoveryMessages.StateService
            self.s_run_with.return_value = [
                  (SS(service=Services.UDP, port=56700, target=self.target1), "192.168.0.4", "255.255.255.255")
                , (SS(service=Services.UDP, port=56700, target=self.target2), "192.168.0.5", "255.255.255.255")
                ]

            with mock.patch.object(self.target, "script", self.script):
                await self.bridge.find_devices("255.255.255.255")

            self.assertEqual(self.bridge.found
                , { self.target1_6: (set([(Services.UDP, "192.168.0.4")]), "255.255.255.255")
                  , self.target2_6: (set([(Services.UDP, "192.168.0.5")]), "255.255.255.255")
                  }
                )

        async it "can be told not to forget devices":
            self.bridge.found = {
                    self.target1_6: (set([(Services.UDP, "192.168.0.4")]), "255.255.255.255")
                  , self.target3_6: (set([(Services.UDP, "192.168.0.6")]), "255.255.255.255")
                  }

            SS = DiscoveryMessages.StateService
            self.s_run_with.return_value = [
                  (SS(service=Services.UDP, port=56700, target=self.target1), "192.168.0.4", "255.255.255.255")
                , (SS(service=Services.UDP, port=56700, target=self.target2), "192.168.0.5", "255.255.255.255")
                ]

            with mock.patch.object(self.target, "script", self.script):
                await self.bridge.find_devices("255.255.255.255", ignore_lost=True)

            self.assertEqual(self.bridge.found
                , { self.target1_6: (set([(Services.UDP, "192.168.0.4")]), "255.255.255.255")
                  , self.target2_6: (set([(Services.UDP, "192.168.0.5")]), "255.255.255.255")
                  , self.target3_6: (set([(Services.UDP, "192.168.0.6")]), "255.255.255.255")
                  }
                )

        async it "doesn't care if it finds none":
            SS = DiscoveryMessages.StateService
            self.s_run_with.return_value = []

            with mock.patch.object(self.target, "script", self.script):
                await self.bridge.find_devices("255.255.255.255")

            self.assertEqual(self.bridge.found, {})

        async it "can be told to care if it finds none":
            SS = DiscoveryMessages.StateService
            self.s_run_with.side_effect = TimedOut()

            with self.fuzzyAssertRaisesError(FoundNoDevices):
                with mock.patch.object(self.target, "script", self.script):
                    await self.bridge.find_devices("255.255.255.255", raise_on_none=True)

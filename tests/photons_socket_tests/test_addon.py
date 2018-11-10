# coding: spec

from photons_socket.target import SocketTarget

from photons_app.test_helpers import TestCase
from photons_app.collector import Collector
from photons_app import helpers as hp

from photons_messages import DiscoveryMessages

from textwrap import dedent

describe TestCase, "Addon":
    it "works":
        collector = Collector()
        with hp.a_temp_file() as fle:
            fle.write(dedent("""
            ---

            photons_app:
              addons:
                lifx.photons:
                  - socket

            targets:
              lan:
                type: lan
            """).encode())

            fle.flush()
            collector.prepare(fle.name, {})
            collector.configuration["target_register"].add_targets(collector.configuration["targets"])

        lan_target = collector.configuration["target_register"].resolve("lan")
        self.assertIs(type(lan_target), SocketTarget)

        protocol_register = collector.configuration["protocol_register"]
        assert DiscoveryMessages in protocol_register.message_register(1024).message_classes

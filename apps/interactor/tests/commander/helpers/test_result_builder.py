# coding: spec

import types

from interactor.commander import helpers as ihp
from photons_app.errors import PhotonsAppError
from photons_messages import DeviceMessages


class ATraceback:
    def __eq__(self, other):
        return isinstance(other, types.TracebackType)


describe "ResultBuilder":
    it "initializes itself":
        builder = ihp.ResultBuilder(["one", "two"])
        assert builder.serials == ["one", "two"]
        assert builder.result == {"results": {}}

    it "can add serials":
        builder = ihp.ResultBuilder(["one", "two"])
        assert builder.serials == ["one", "two"]

        builder.add_serials(["three", "two", "four"])
        assert builder.serials == ["one", "two", "three", "four"]

    describe "as_dict":
        it "returns results but with ok for devices":
            builder = ihp.ResultBuilder(["one", "two"])
            dct = builder.as_dict()
            assert builder.result == {"results": {}}
            assert dct == {"results": {"one": "ok", "two": "ok"}}

        it "doesn't give ok for devices that already have results":
            builder = ihp.ResultBuilder(["one", "two", "three"])
            builder.result["results"]["one"] = {"pkt_type": 1}
            builder.result["results"]["three"] = {"error": "blah"}
            dct = builder.as_dict()

            assert builder.result == {
                "results": {"one": {"pkt_type": 1}, "three": {"error": "blah"}}
            }
            assert dct == {
                "results": {"one": {"pkt_type": 1}, "two": "ok", "three": {"error": "blah"}}
            }

        it "includes errors on result":
            builder = ihp.ResultBuilder(["one", "two"])
            builder.result["errors"] = ["error1", "error2"]
            dct = builder.as_dict()

            assert builder.result == {"results": {}, "errors": ["error1", "error2"]}
            assert dct == {"results": {"one": "ok", "two": "ok"}, "errors": ["error1", "error2"]}

    describe "add_packet":
        it "sets info for that serial in results":
            packet = DeviceMessages.StatePower(level=0, target="d073d5000001")
            info = {"pkt_type": 22, "pkt_name": "StatePower", "payload": {"level": 0}}
            builder = ihp.ResultBuilder(["d073d5000001"])
            builder.add_packet(packet)

            assert builder.as_dict() == {"results": {"d073d5000001": info}}

        it "makes a list if already have packet for that bulb":
            packet1 = DeviceMessages.StatePower(level=0, target="d073d5000001")
            packet2 = DeviceMessages.StatePower(level=65535, target="d073d5000001")
            packet3 = DeviceMessages.StateHostFirmware(
                build=0, version_major=1, version_minor=2, target="d073d5000001"
            )

            info1 = {"pkt_type": 22, "pkt_name": "StatePower", "payload": {"level": 0}}
            info2 = {"pkt_type": 22, "pkt_name": "StatePower", "payload": {"level": 65535}}
            info3 = {
                "pkt_type": 15,
                "pkt_name": "StateHostFirmware",
                "payload": {"build": 0, "version_major": 1, "version_minor": 2},
            }

            builder = ihp.ResultBuilder(["d073d5000001"])
            builder.add_packet(packet1)
            assert builder.as_dict() == {"results": {"d073d5000001": info1}}

            builder.add_packet(packet2)
            assert builder.as_dict() == {"results": {"d073d5000001": [info1, info2]}}

            builder.add_packet(packet3)
            assert builder.as_dict() == {"results": {"d073d5000001": [info1, info2, info3]}}

    describe "error":
        it "adds the error for that serial if we can get serial from the error":
            builder = ihp.ResultBuilder(["d073d5000001"])

            class BadError(PhotonsAppError):
                pass

            error = BadError("blah", serial="d073d5000001")
            builder.error(error)
            assert builder.as_dict() == {
                "results": {
                    "d073d5000001": {
                        "error": {"message": "blah"},
                        "error_code": "BadError",
                        "status": 400,
                    }
                }
            }

            class Error(PhotonsAppError):
                desc = "an error"

            error2 = None

            try:
                raise Error("wat", thing=1, serial="d073d5000001")
            except Exception as error:
                error2 = error

            builder.error(error2)
            assert builder.as_dict() == {
                "results": {
                    "d073d5000001": {
                        "error": {"message": "an error. wat", "thing": 1},
                        "error_code": "Error",
                        "status": 400,
                    }
                }
            }

        it "adds error to errors in result if no serial on the error":
            builder = ihp.ResultBuilder(["d073d5000001"])

            error = PhotonsAppError("blah")
            builder.error(error)
            assert builder.as_dict() == {
                "results": {"d073d5000001": "ok"},
                "errors": [
                    {"error": {"message": "blah"}, "error_code": "PhotonsAppError", "status": 400}
                ],
            }

            class Error(PhotonsAppError):
                desc = "an error"

            error2 = None
            try:
                raise Error("wat", thing=1)
            except Exception as e:
                error2 = e

            builder.error(error2)
            assert builder.as_dict() == {
                "results": {"d073d5000001": "ok"},
                "errors": [
                    {"error": {"message": "blah"}, "error_code": "PhotonsAppError", "status": 400},
                    {
                        "error": {"message": "an error. wat", "thing": 1},
                        "error_code": "Error",
                        "status": 400,
                    },
                ],
            }

            builder = ihp.ResultBuilder(["d073d5000001"])
            error3 = ValueError("nope")
            builder.error(error3)
            assert builder.as_dict() == {
                "results": {"d073d5000001": "ok"},
                "errors": [
                    {
                        "error": "Internal Server Error",
                        "error_code": "InternalServerError",
                        "status": 500,
                    }
                ],
            }

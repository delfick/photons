
from photons_canvas.points import containers as cont
from photons_products import Products

class TestDevice:
    def test_it_has_serial_cap_and_width(self):
        serial = "d073d5001337"
        cap = Products.LCM3_TILE.cap

        device = cont.Device(serial, cap)
        assert device.serial == serial
        assert device.cap is cap

        assert repr(device) == "<Device (d073d5001337,LCM3_TILE)>"

    def test_it_can_be_used_as_a_key_in_a_dictionary(self):
        device1 = cont.Device("d073d5001337", None)
        device2 = cont.Device("d073d5001337", None)
        device3 = cont.Device("d073d5001338", None)

        d = {device1: 3, device3: 5, "d073d5001339": 20}
        assert d[device1] == 3
        assert d[device2] == 3
        assert d[device3] == 5
        assert d[cont.Device("d073d5001339", None)] == 20

    def test_it_can_be_compared(self):
        device1 = cont.Device("d073d5001337", None)
        device2 = cont.Device("d073d5001337", None)
        device3 = cont.Device("d073d5001338", None)

        assert device1 == device2
        assert device1 == "d073d5001337"

        assert device1 != device3
        assert device1 != "d073d5004556"

class WithSender(object):
    """
    A special message that can be used in target.script for returning response packets
    along with a key representing the original packet that was sent.

    Usage looks like:

    .. code-block:: python

        msg = DeviceMessages.GetPower()

        key1 = str(uuid.uuid4())
        key2 = str(uuid.uuid4())

        item1 = WithSender(msg, key1, "d073d5000001")
        item2 = WithSender(msg, key2, "d073d5000002")

        async for key, pkt in target.script([item1, item2]).run_with(None):
            # You'll get back two DeviceMessages.StatePower packets
            # With the associated key for that message
            # Note that pkt._with_sender_address will be the (ip, port) of the device

    Note that because we are yielding different items than the usual (pkt, addr, sendto) you
    should not mix WithSender with normal script items!

    It is not recommended that you use this class directly.
    """
    def __init__(self, original, key, serial):
        self.key = key
        self.serial = serial
        self.original = original

    def simplified(self, simplifier):
        clone = self.original.clone()
        clone.target = self.serial
        clone.ack_required = False
        clone.res_required = True
        item = list(simplifier(clone))[0]
        return self.Item(self.key, item)

    class Item:
        def __init__(self, key, item):
            self.key = key
            self.item = item

        async def run_with(self, reference, args_for_run, **kwargs):
            async for pkt, addr, sentto in self.item.run_with(reference, args_for_run, **kwargs):
                pkt.__dict__["_with_sender_address"] = addr
                yield self.key, pkt

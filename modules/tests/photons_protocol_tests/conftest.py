from photons_protocol.messages import Messages
from photons_protocol.types import Type as T
from photons_messages import LIFXPacket

import pytest


msg = LIFXPacket.message


class M(Messages):
    # fmt:off
    One = msg(78
        , ("one", T.String(16))
        )

    Two = msg(99)

    Three = msg(98
        , ("three", T.Int8.transform(lambda _, v: v + 5, lambda _, v: v - 5))
        )
    # fmt:on


@pytest.fixture()
def TestMessages():
    return M

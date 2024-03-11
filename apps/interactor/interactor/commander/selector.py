from typing import Annotated

import attrs
import strcs
from interactor.commander.store import creator
from photons_app.registers import ReferenceResolverRegister
from photons_app.special import SpecialReference
from photons_control.device_finder import DeviceFinder, Finder
from photons_messages.enums import MultiZoneEffectType, TileEffectType


@attrs.define
class TileEffectTypeValue:
    effect: TileEffectType | None = None


@creator(TileEffectTypeValue)
def create_tile_effect_type_value(value: object, /) -> strcs.ConvertResponse[TileEffectTypeValue]:
    if value in (None, strcs.NotSpecified):
        return {"effect": None}

    elif isinstance(value, str | int | TileEffectType):
        if isinstance(value, str | int):
            for en in TileEffectType.__members__.values():
                if value == en.name or value == en.value:
                    return {"effect": en}
        else:
            return {"effect": value}

    return None


@attrs.define
class MultiZoneEffectTypeValue:
    effect: MultiZoneEffectType | None = None


@creator(MultiZoneEffectTypeValue)
def create_multi_zone_effect_type_value(
    value: object,
    /,
) -> strcs.ConvertResponse[MultiZoneEffectTypeValue]:
    if value in (None, strcs.NotSpecified):
        return {"effect": None}

    elif isinstance(value, str | int | MultiZoneEffectType):
        if isinstance(value, str | int):
            for en in MultiZoneEffectType.__members__.values():
                if value == en.name or value == en.value:
                    return {"effect": en}
        else:
            return {"effect": value}
    else:
        return None


@attrs.define
class Selector:
    raw: object
    selector: SpecialReference


@creator(Selector)
def create_selector(
    val: object, /, reference_resolver_register: ReferenceResolverRegister, finder: Finder
) -> strcs.ConvertResponse[Selector]:
    if val is strcs.NotSpecified:
        val = "_"

    if isinstance(val, str):
        return {"raw": val, "selector": reference_resolver_register.reference_object(val)}
    elif isinstance(val, dict):
        return {"raw": val, "selector": DeviceFinder.from_options(val, finder=finder)}
    elif isinstance(val, SpecialReference):
        return {"raw": repr(val), "selector": val}

    return None


@creator(SpecialReference)
def create_special_reference(
    val: object, /, reference_resolver_register: ReferenceResolverRegister
) -> strcs.ConvertResponse[SpecialReference]:
    if isinstance(val, Selector):
        return val.selector
    return None


def create_matcher_raw(val: object, /) -> strcs.ConvertResponse[str | dict[str | object]]:
    if isinstance(val, str | dict):
        return val
    return None


@attrs.define
class Matcher:
    """
    What lights to target. If this isn't specified then we interact with all
    the lights that can be found on the network.

    This can be specfied as either a space separated key=value string or as
    a dictionary.

    For example,
    "label=kitchen,bathroom location_name=home"
    or
    ``{"label": ["kitchen", "bathroom"], "location_name": "home"}``

    See https://photons.delfick.com/interacting/device_finder.html#valid-filters
    for more information on what filters are available.
    """

    raw: Annotated[str | dict[str | object] | None, strcs.Ann(creator=create_matcher_raw)]


@creator(Matcher)
def create_matcher(val: object, /) -> strcs.ConvertResponse[Matcher]:
    if val in (None, strcs.NotSpecified):
        return {"raw": "_"}
    elif isinstance(val, str):
        return {"raw": f"match:{val}"}
    elif isinstance(val, dict):
        return {"raw": val}
    else:
        return None


@attrs.define
class Timeout:
    """
    The max amount of time we wait for replies from the lights
    """

    value: int | float


@creator(int | float)
def create_timeout_value(val: object, /) -> strcs.ConvertResponse[int | float]:
    if isinstance(val, int | float):
        return val
    return None


@creator(Timeout)
def create_timeout(val: object, /) -> strcs.ConvertResponse[Timeout]:
    if val is strcs.NotSpecified:
        return {"value": 20}

    if isinstance(val, str) and val.isdigit():
        return {"value": int(val)}

    elif (
        isinstance(val, str)
        and val.count(".") == 1
        and all(part.isdigit() for part in val.split("."))
    ):
        return {"value": float(val)}

    elif isinstance(val, int | float):
        return {"value": val}

    else:
        return None

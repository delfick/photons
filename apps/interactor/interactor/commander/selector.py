import attrs
import strcs
from interactor.commander.store import creator
from photons_app.registers import ReferenceResolverRegister
from photons_app.special import SpecialReference
from photons_control.device_finder import DeviceFinder, Finder


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

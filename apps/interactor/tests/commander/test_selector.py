import asyncio
import functools
from typing import Protocol

import pytest
import strcs
from interactor.commander import selector
from interactor.commander.store import reg
from photons_app import special
from photons_app.registers import ReferenceResolverRegister
from photons_control.device_finder import DeviceFinder, Finder
from photons_transport.comms.base import Communication


class BlahSpecialReference(special.SpecialReference):
    def __init__(self, options: str) -> None:
        super().__init__()
        self.options = options


@pytest.fixture
def finder(sender: Communication, final_future: asyncio.Future) -> Finder:
    return Finder(sender, final_future)


@pytest.fixture
def reference_resolver_register() -> ReferenceResolverRegister:
    register = ReferenceResolverRegister()

    def resolve_blah(options: str) -> BlahSpecialReference:
        return BlahSpecialReference(options)

    register.add("blah", resolve_blah)
    return register


class SelectorCreator(Protocol):
    def __call__(self, options: str | strcs.NotSpecifiedMeta = strcs.NotSpecified) -> selector.Selector: ...


@pytest.fixture
def create_selector(reference_resolver_register: ReferenceResolverRegister, finder: Finder) -> SelectorCreator:
    return functools.partial(
        reg.create,
        selector.Selector,
        meta=strcs.Meta({"reference_resolver_register": reference_resolver_register, "finder": finder}),
    )


class TestSelector:
    def test_it_can_create_from_NotSpecified(self, create_selector: SelectorCreator):
        made = create_selector()
        assert isinstance(made, selector.Selector)
        assert made.raw == "_"
        assert isinstance(made.selector, special.FoundSerials)

    def test_it_can_create_from_special_reference(self, create_selector: SelectorCreator):
        want = special.FoundSerials()
        made = create_selector(want)
        assert isinstance(made, selector.Selector)
        assert made.raw == repr(want)
        assert made.selector is want

    def test_it_can_create_from_underscore(self, create_selector: SelectorCreator):
        made = create_selector("_")
        assert isinstance(made, selector.Selector)
        assert made.raw == "_"
        assert isinstance(made.selector, special.FoundSerials)

    def test_it_can_create_from_str_match(self, create_selector: SelectorCreator):
        made = create_selector("blah:stuff_and_things")
        assert isinstance(made, selector.Selector)
        assert made.raw == "blah:stuff_and_things"
        assert isinstance(made.selector, BlahSpecialReference)
        assert made.selector.options == "stuff_and_things"

    def test_it_can_create_from_dictionary(self, finder: Finder, create_selector: SelectorCreator):
        raw: dict[str, object] = {"serial": "d073d500000a"}
        made = create_selector(raw)
        assert isinstance(made, selector.Selector)
        assert made.raw == raw
        assert isinstance(made.selector, DeviceFinder)
        assert made.selector.finder is finder
        assert made.selector.fltr["serial"] == ["d073d500000a"]

    def test_it_can_create_from_selector_instance(self, create_selector: SelectorCreator):
        hard_coded = special.HardCodedSerials(["d073d5"])
        want = selector.Selector(raw="one", selector=hard_coded)
        made = create_selector(want)
        assert made is want

    def test_it_can_create_SpecialReference_from_selector(self, reference_resolver_register: ReferenceResolverRegister):
        hard_coded = special.HardCodedSerials(["d073d5"])
        made = reg.create(
            selector.SpecialReference,
            selector.Selector(raw="_", selector=hard_coded),
            meta=strcs.Meta({"reference_resolver_register": reference_resolver_register}),
        )
        assert made is hard_coded


class TestMatcher:
    def test_it_can_be_made_from_nothing(self):
        made = reg.create(selector.Matcher)
        assert isinstance(made, selector.Matcher)
        assert made.raw == "_"

    def test_it_can_be_made_from_str(self):
        made = reg.create(selector.Matcher, "label=kitchen")
        assert isinstance(made, selector.Matcher)
        assert made.raw == "match:label=kitchen"

    def test_it_can_be_made_from_dict(self):
        made = reg.create(selector.Matcher, {"label": "kitchen"})
        assert isinstance(made, selector.Matcher)
        assert made.raw == {"label": "kitchen"}


class TestTimeout:
    def test_it_can_be_made_from_nothing(self):
        made = reg.create(selector.Timeout)
        assert isinstance(made, selector.Timeout)
        assert made.value == 20

    def test_it_can_be_made_from_str_int(self):
        made = reg.create(selector.Timeout, "40")
        assert isinstance(made, selector.Timeout)
        assert made.value == 40

    def test_it_can_be_made_from_str_float(self):
        made = reg.create(selector.Timeout, "50.566")
        assert isinstance(made, selector.Timeout)
        assert made.value == 50.566

    def test_it_can_be_made_from_int(self):
        made = reg.create(selector.Timeout, 70)
        assert isinstance(made, selector.Timeout)
        assert made.value == 70

    def test_it_can_be_made_from_float(self):
        made = reg.create(selector.Timeout, 70.665)
        assert isinstance(made, selector.Timeout)
        assert made.value == 70.665

    def test_it_wont_convert_bad_string(self):
        with pytest.raises(strcs.errors.UnableToConvert):
            reg.create(selector.Timeout, "70.665.777")

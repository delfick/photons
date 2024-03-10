# coding: spec

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
    def __call__(
        self, options: str | strcs.NotSpecifiedMeta = strcs.NotSpecified
    ) -> selector.Selector: ...


@pytest.fixture
def create_selector(
    reference_resolver_register: ReferenceResolverRegister, finder: Finder
) -> SelectorCreator:
    return functools.partial(
        reg.create,
        selector.Selector,
        meta=strcs.Meta(
            {"reference_resolver_register": reference_resolver_register, "finder": finder}
        ),
    )


describe "Selector":
    it "can create from NotSpecified", create_selector: SelectorCreator:
        made = create_selector()
        assert isinstance(made, selector.Selector)
        assert made.raw == "_"
        assert isinstance(made.selector, special.FoundSerials)

    it "can create from special reference", create_selector: SelectorCreator:
        want = special.FoundSerials()
        made = create_selector(want)
        assert isinstance(made, selector.Selector)
        assert made.raw == repr(want)
        assert made.selector is want

    it "can create from underscore", create_selector: SelectorCreator:
        made = create_selector("_")
        assert isinstance(made, selector.Selector)
        assert made.raw == "_"
        assert isinstance(made.selector, special.FoundSerials)

    it "can create from str match", create_selector: SelectorCreator:
        made = create_selector("blah:stuff_and_things")
        assert isinstance(made, selector.Selector)
        assert made.raw == "blah:stuff_and_things"
        assert isinstance(made.selector, BlahSpecialReference)
        assert made.selector.options == "stuff_and_things"

    it "can create from dictionary", finder: Finder, create_selector: SelectorCreator:
        raw: dict[str, object] = {"serial": "d073d500000a"}
        made = create_selector(raw)
        assert isinstance(made, selector.Selector)
        assert made.raw == raw
        assert isinstance(made.selector, DeviceFinder)
        assert made.selector.finder is finder
        assert made.selector.fltr["serial"] == ["d073d500000a"]

    it "can create from selector instance", create_selector: SelectorCreator:
        hard_coded = special.HardCodedSerials(["d073d5"])
        want = selector.Selector(raw="one", selector=hard_coded)
        made = create_selector(want)
        assert made is want

    it "can create SpecialReference from selector", reference_resolver_register: ReferenceResolverRegister:
        hard_coded = special.HardCodedSerials(["d073d5"])
        made = reg.create(
            selector.SpecialReference,
            selector.Selector(raw="_", selector=hard_coded),
            meta=strcs.Meta({"reference_resolver_register": reference_resolver_register}),
        )
        assert made is hard_coded


describe "Matcher":
    it "can be made from nothing":
        made = reg.create(selector.Matcher)
        assert isinstance(made, selector.Matcher)
        assert made.raw == "_"

    it "can be made from str":
        made = reg.create(selector.Matcher, "label=kitchen")
        assert isinstance(made, selector.Matcher)
        assert made.raw == "match:label=kitchen"

    it "can be made from dict":
        made = reg.create(selector.Matcher, {"label": "kitchen"})
        assert isinstance(made, selector.Matcher)
        assert made.raw == {"label": "kitchen"}


describe "Timeout":
    it "can be made from nothing":
        made = reg.create(selector.Timeout)
        assert isinstance(made, selector.Timeout)
        assert made.value == 20

    it "can be made from str int":
        made = reg.create(selector.Timeout, "40")
        assert isinstance(made, selector.Timeout)
        assert made.value == 40

    it "can be made from str float":
        made = reg.create(selector.Timeout, "50.566")
        assert isinstance(made, selector.Timeout)
        assert made.value == 50.566

    it "can be made from int":
        made = reg.create(selector.Timeout, 70)
        assert isinstance(made, selector.Timeout)
        assert made.value == 70

    it "can be made from float":
        made = reg.create(selector.Timeout, 70.665)
        assert isinstance(made, selector.Timeout)
        assert made.value == 70.665

    it "won't convert bad string":
        with pytest.raises(strcs.errors.UnableToConvert):
            reg.create(selector.Timeout, "70.665.777")

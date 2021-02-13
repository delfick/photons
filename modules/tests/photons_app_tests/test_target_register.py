# coding: spec

from photons_app.errors import TargetNotFound, TargetTypeNotFound, ProgrammerError
from photons_app.registers import Target, TargetRegister

from delfick_project.errors_pytest import assertRaises
from delfick_project.norms import sb
from unittest import mock
import pytest


describe "Target":
    it "takes in things":
        target = Target.FieldSpec().empty_normalise(type="thing", optional=True, options={"one": 2})
        assert target.type == "thing"
        assert target.optional is True
        assert target.options == {"one": 2}

    it "has defaults":
        target = Target.FieldSpec().empty_normalise(type="thing")
        assert target.type == "thing"
        assert target.optional is False
        assert target.options == {}

describe "TargetRegister":

    @pytest.fixture()
    def reg(self):
        return TargetRegister()

    it "has some information on it", reg:
        assert reg.types == {}
        assert reg.created == {}
        assert reg.registered == {}

    describe "getting registered tasks":
        it "complains if we ask for None", reg:
            with assertRaises(ProgrammerError, "Targets are key'd by their name"):
                reg[None]

            reg._registered[None] = ("typ", mock.Mock(name="target"), mock.Mock(name="creator"))
            with assertRaises(ProgrammerError, "Targets are key'd by their name"):
                reg[None]

        it "complains if we ask for sb.NotSpecified", reg:
            with assertRaises(ProgrammerError, "Targets are key'd by their name"):
                reg[sb.NotSpecified]

            reg._registered[sb.NotSpecified] = (
                "name",
                mock.Mock(name="target"),
                mock.Mock(name="creator"),
            )
            with assertRaises(ProgrammerError, "Targets are key'd by their name"):
                reg[sb.NotSpecified]

        it "complains if the name not in registered", reg:
            with assertRaises(TargetNotFound, wanted="thing"):
                reg["thing"]

            thing = ("n", mock.Mock(name="target"), mock.Mock(name="creator"))
            reg._registered["thing"] = thing
            assert reg["thing"] is thing

        it "retrieves from registered", reg:
            thing = ("o", mock.Mock(name="target"), mock.Mock(name="creator"))
            reg._registered["thing"] = thing
            assert reg["thing"] is thing

    describe "contains":
        it "says no if empty", reg:
            assert "" not in reg
            assert None not in reg
            assert sb.NotSpecified not in reg

            reg._registered[None] = ("typ", mock.Mock(name="target"), mock.Mock(name="creator"))
            reg._registered[""] = ("typ", mock.Mock(name="target"), mock.Mock(name="creator"))
            reg._registered[sb.NotSpecified] = (
                "typ",
                mock.Mock(name="target"),
                mock.Mock(name="creator"),
            )

            assert "" not in reg
            assert None not in reg
            assert sb.NotSpecified not in reg

        it "says no if the name or target doesn't exist", reg:
            road = mock.Mock(
                name="resolvedroad", instantiated_name="road", spec=["instantiated_name"]
            )
            assert road not in reg
            assert "road" not in reg

            InfraTarget = mock.Mock(name="InfraTarget")
            infratarget = Target.FieldSpec().empty_normalise(type="infrastructure")

            reg.register_type("infrastructure", InfraTarget)
            road = mock.Mock(
                name="resolvedroad", instantiated_name="road", spec=["instantiated_name"]
            )

            roadcreator = mock.Mock(name="roadcreator", return_value=road)
            reg.add_target("road", infratarget, roadcreator)

            assert "road" in reg
            assert "house" not in reg

            # Target not in there till it's resolved
            assert road not in reg
            assert reg.resolve("road") is road
            assert road in reg

            restricted = reg.restricted(target_types=["hero"])
            assert road not in restricted
            assert road in restricted.created.values()
            assert "road" not in restricted

    describe "used_targets":
        it "returns targets that were resolved", reg:
            made1 = mock.Mock(name="made1")
            made2 = mock.Mock(name="made2")
            made3 = mock.Mock(name="made3")

            creator1 = mock.Mock(name="creator1", return_value=made1)
            creator2 = mock.Mock(name="creator2", return_value=made2)
            creator3 = mock.Mock(name="creator3", return_value=made3)

            reg.register_type("o", mock.Mock(name="oTarget"))
            reg.register_type("t", mock.Mock(name="tTarget"))

            reg.add_target("one", Target.FieldSpec().empty_normalise(type="o"), creator1)
            reg.add_target("two", Target.FieldSpec().empty_normalise(type="t"), creator2)
            reg.add_target("three", Target.FieldSpec().empty_normalise(type="o"), creator3)

            assert reg.used_targets == []

            assert reg.resolve("one") is made1
            assert reg.used_targets == [made1]

            # Resolving again should make no difference
            assert reg.resolve("one") is made1
            assert reg.used_targets == [made1]

            # And multiple resolves should be fine
            assert reg.resolve("three") is made3
            assert reg.used_targets == [made1, made3]

    describe "type_for":
        it "returns the type of the target", reg:
            reg.register_type("o", mock.Mock(name="oTarget"))
            reg.add_target(
                "one", Target.FieldSpec().empty_normalise(type="o"), mock.Mock(name="creator")
            )
            assert reg.type_for("one") == "o"

            with assertRaises(TargetNotFound):
                reg.type_for("two")

            reg.register_type("s", mock.Mock(name="sTarget"))
            reg.add_target(
                "two", Target.FieldSpec().empty_normalise(type="s"), mock.Mock(name="creator")
            )
            assert reg.type_for("one") == "o"
            assert reg.type_for("two") == "s"

    describe "desc_for":
        it "returns description or doc or empty from a resolved target", reg:
            made = mock.Mock(name="made", spec=[])
            made.__doc__ = None
            creator = mock.Mock(name="creator", return_value=made)

            with assertRaises(TargetNotFound):
                reg.type_for("one")

            reg.register_type("o", mock.Mock(name="oTarget"))
            reg.add_target("one", Target.FieldSpec().empty_normalise(type="o"), creator)

            assert reg.desc_for("one") == ""
            made.__doc__ = "stuff and things"
            assert reg.desc_for("one") == "stuff and things"
            made.description = "better stuff"
            assert reg.desc_for("one") == "better stuff"

    describe "register_type":
        it "adds the type to the types dictionary", reg:
            assert reg.types == {}

            OneTarget = mock.Mock(name="OneTarget")
            reg.register_type("one", OneTarget)
            assert reg.types == {"one": OneTarget}

            OneTarget2 = mock.Mock(name="OneTarget2")
            reg.register_type("one", OneTarget2)
            assert reg.types == {"one": OneTarget2}

            TwoTarget = mock.Mock(name="TwoTarget")
            reg.register_type("two", TwoTarget)
            assert reg.types == {"one": OneTarget2, "two": TwoTarget}

    describe "resolve":
        it "will only use already created target if exists and isn't restricted", reg:
            HeroTarget = mock.Mock(name="HeroTarget")
            made = mock.Mock(name="made")
            target = Target.FieldSpec().empty_normalise(type="hero")
            creator = mock.Mock(name="creator", spec=[], return_value=made)

            reg.register_type("hero", HeroTarget)
            reg.add_target("superman", target, creator)

            with assertRaises(TargetNotFound):
                reg.resolve(made)

            assert reg.resolve("superman") is made
            assert reg.resolve(made) is made

            with assertRaises(TargetNotFound):
                reg.restricted(target_names=["batman"]).resolve(made)

            reg.restricted(target_names=["superman"]).resolve(made)

        it "will complain if the name doesn't exists", reg:
            with assertRaises(TargetNotFound, wanted="things"):
                reg.resolve("things")

            made = mock.Mock(name="made")
            with assertRaises(TargetNotFound, wanted=made):
                reg.resolve(made)

        it "will use the type object and the creator to create a target", reg:
            HeroTarget = mock.Mock(name="HeroTarget")

            made = mock.Mock(name="made")
            target = Target.FieldSpec().empty_normalise(type="hero")
            creator = mock.Mock(name="creator", spec=[], return_value=made)

            reg.register_type("hero", HeroTarget)
            reg.add_target("superman", target, creator)

            assert reg.resolve("superman") is made
            creator.assert_called_once_with("superman", HeroTarget, target)

    describe "add_target":
        it "complains if the type doesn't exist and the target isn't optional", reg:
            target = Target.FieldSpec().empty_normalise(type="hero")
            assert not target.optional

            with assertRaises(TargetTypeNotFound, target="superman", wanted="hero"):
                reg.add_target("superman", target, mock.Mock(name="creator"))

        it "does nothing if the type doesn't exist but the target is optional", reg:
            target = Target.FieldSpec().empty_normalise(type="hero", optional=True)
            reg.add_target("superman", target, mock.Mock(name="creator"))
            assert reg.registered == {}

        it "puts the information in registered otherwise", reg:
            HeroTarget = mock.Mock(name="HeroTarget")
            reg.register_type("hero", HeroTarget)

            target = Target.FieldSpec().empty_normalise(type="hero")
            creator = mock.Mock(name="creator")
            reg.add_target("superman", target, creator)
            assert reg.registered == {"superman": ("hero", target, creator)}

            target2 = Target.FieldSpec().empty_normalise(type="hero")
            creator2 = mock.Mock(name="creator2")
            reg.add_target("batman", target2, creator2)
            assert reg.registered == {
                "superman": ("hero", target, creator),
                "batman": ("hero", target2, creator2),
            }

    describe "creating a restriction":
        it "changes underlying data", reg:
            HeroTarget = mock.Mock(name="HeroTarget")
            reg.register_type("hero", HeroTarget)
            restricted = reg.restricted(target_types=["hero"])

            superman = mock.Mock(name="resolvedsuperman")
            target = Target.FieldSpec().empty_normalise(type="hero")
            creator = mock.Mock(name="creator", return_value=superman)
            restricted.add_target("superman", target, creator)
            assert restricted.registered == {"superman": ("hero", target, creator)}

            batman = mock.Mock(name="resolvedbatman")
            target2 = Target.FieldSpec().empty_normalise(type="hero")
            creator2 = mock.Mock(name="creator2", return_value=batman)
            reg.add_target("batman", target2, creator2)
            assert reg.registered == {
                "superman": ("hero", target, creator),
                "batman": ("hero", target2, creator2),
            }

            assert reg.created == {}
            assert restricted.created == {}
            r1 = reg.resolve("superman")
            assert r1 is superman
            assert reg.created == {"superman": r1}
            assert restricted.created == {"superman": r1}

            assert restricted.registered == {
                "superman": ("hero", target, creator),
                "batman": ("hero", target2, creator2),
            }

            VillianTarget = mock.Mock(name="VillianTarget")
            restricted.register_type("villian", VillianTarget)

            target3 = Target.FieldSpec().empty_normalise(type="villian")
            creator3 = mock.Mock(name="creator3")
            reg.add_target("licorice", target3, creator3)
            assert reg.registered == {
                "superman": ("hero", target, creator),
                "batman": ("hero", target2, creator2),
                "licorice": ("villian", target3, creator3),
            }
            assert restricted.registered == {
                "superman": ("hero", target, creator),
                "batman": ("hero", target2, creator2),
            }
            assert restricted.restricted(target_types=["villian"]).registered == {
                "licorice": ("villian", target3, creator3),
            }

            r2 = restricted.resolve("batman")
            assert r2 is batman
            assert reg.created == {"superman": r1, "batman": r2}
            assert restricted.created == {"superman": r1, "batman": r2}
            assert restricted.restricted().created == {"superman": r1, "batman": r2}

            with assertRaises(TargetNotFound, wanted="licorice", available=["batman", "superman"]):
                restricted["licorice"]

            assert reg["licorice"] == ("villian", target3, creator3)
            assert restricted.restricted()["licorice"] == ("villian", target3, creator3)

            with assertRaises(KeyError, "This dictionary is read only"):
                reg.registered["one"] = 1
            with assertRaises(KeyError, "This dictionary is read only"):
                reg.registered.pop("one")
            with assertRaises(KeyError, "This dictionary is read only"):
                reg.registered.pop("licorice")
            with assertRaises(KeyError, "This dictionary is read only"):
                del reg.registered["one"]
            with assertRaises(KeyError, "This dictionary is read only"):
                del reg.registered["licorice"]
            with assertRaises(KeyError, "This dictionary is read only"):
                reg.registered.clear()
            with assertRaises(KeyError, "This dictionary is read only"):
                reg.registered.popitem()
            with assertRaises(KeyError, "This dictionary is read only"):
                reg.registered.update({"one": 1})

            assert reg.restricted(target_names=["batman"]).registered == {
                "batman": ("hero", target2, creator2)
            }
            assert reg.restricted(target_names=["batman", "licorice"]).registered == {
                "licorice": ("villian", target3, creator3),
                "batman": ("hero", target2, creator2),
            }
            assert reg.restricted(
                target_names=["batman", "licorice"], target_types=["villian"]
            ).registered == {
                "licorice": ("villian", target3, creator3),
            }

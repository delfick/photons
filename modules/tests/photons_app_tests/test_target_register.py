from unittest import mock

import pytest
from delfick_project.errors_pytest import assertRaises
from delfick_project.norms import sb
from photons_app.errors import ProgrammerError, TargetNotFound, TargetTypeNotFound
from photons_app.registers import Target, TargetRegister


class TestTarget:
    def test_it_takes_in_things(self):
        target = Target.FieldSpec().empty_normalise(type="thing", optional=True, options={"one": 2})
        assert target.type == "thing"
        assert target.optional is True
        assert target.options == {"one": 2}

    def test_it_has_defaults(self):
        target = Target.FieldSpec().empty_normalise(type="thing")
        assert target.type == "thing"
        assert target.optional is False
        assert target.options == {}


class TestTargetRegister:
    @pytest.fixture()
    def reg(self):
        return TargetRegister()

    def test_it_has_some_information_on_it(self, reg):
        assert reg.types == {}
        assert reg.created == {}
        assert reg.registered == {}

    class TestGettingRegisteredTasks:
        def test_it_complains_if_we_ask_for_None(self, reg):
            with assertRaises(ProgrammerError, "Targets are key'd by their name"):
                reg[None]

            reg._registered[None] = ("typ", mock.Mock(name="target"), mock.Mock(name="creator"))
            with assertRaises(ProgrammerError, "Targets are key'd by their name"):
                reg[None]

        def test_it_complains_if_we_ask_for_sbNotSpecified(self, reg):
            with assertRaises(ProgrammerError, "Targets are key'd by their name"):
                reg[sb.NotSpecified]

            reg._registered[sb.NotSpecified] = (
                "name",
                mock.Mock(name="target"),
                mock.Mock(name="creator"),
            )
            with assertRaises(ProgrammerError, "Targets are key'd by their name"):
                reg[sb.NotSpecified]

        def test_it_complains_if_the_name_not_in_registered(self, reg):
            with assertRaises(TargetNotFound, wanted="thing"):
                reg["thing"]

            thing = ("n", mock.Mock(name="target"), mock.Mock(name="creator"))
            reg._registered["thing"] = thing
            assert reg["thing"] is thing

        def test_it_retrieves_from_registered(self, reg):
            thing = ("o", mock.Mock(name="target"), mock.Mock(name="creator"))
            reg._registered["thing"] = thing
            assert reg["thing"] is thing

    class TestContains:
        def test_it_says_no_if_empty(self, reg):
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

        def test_it_says_no_if_the_name_or_target_doesnt_exist(self, reg):
            road = mock.Mock(name="resolvedroad", instantiated_name="road", spec=["instantiated_name"])
            assert road not in reg
            assert "road" not in reg

            InfraTarget = mock.Mock(name="InfraTarget")
            infratarget = Target.FieldSpec().empty_normalise(type="infrastructure")

            reg.register_type("infrastructure", InfraTarget)
            road = mock.Mock(name="resolvedroad", instantiated_name="road", spec=["instantiated_name"])

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

    class TestUsedTargets:
        def test_it_returns_targets_that_were_resolved(self, reg):
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

    class TestTypeFor:
        def test_it_returns_the_type_of_the_target(self, reg):
            reg.register_type("o", mock.Mock(name="oTarget"))
            reg.add_target("one", Target.FieldSpec().empty_normalise(type="o"), mock.Mock(name="creator"))
            assert reg.type_for("one") == "o"

            with assertRaises(TargetNotFound):
                reg.type_for("two")

            reg.register_type("s", mock.Mock(name="sTarget"))
            reg.add_target("two", Target.FieldSpec().empty_normalise(type="s"), mock.Mock(name="creator"))
            assert reg.type_for("one") == "o"
            assert reg.type_for("two") == "s"

    class TestDescFor:
        def test_it_returns_description_or_doc_or_empty_from_a_resolved_target(self, reg):
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

    class TestRegisterType:
        def test_it_adds_the_type_to_the_types_dictionary(self, reg):
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

    class TestResolve:
        def test_it_will_only_use_already_created_target_if_exists_and_isnt_restricted(self, reg):
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

        def test_it_will_complain_if_the_name_doesnt_exists(self, reg):
            with assertRaises(TargetNotFound, wanted="things"):
                reg.resolve("things")

            made = mock.Mock(name="made")
            with assertRaises(TargetNotFound, wanted=made):
                reg.resolve(made)

        def test_it_will_use_the_type_object_and_the_creator_to_create_a_target(self, reg):
            HeroTarget = mock.Mock(name="HeroTarget")

            made = mock.Mock(name="made")
            target = Target.FieldSpec().empty_normalise(type="hero")
            creator = mock.Mock(name="creator", spec=[], return_value=made)

            reg.register_type("hero", HeroTarget)
            reg.add_target("superman", target, creator)

            assert reg.resolve("superman") is made
            creator.assert_called_once_with("superman", HeroTarget, target)

    class TestAddTarget:
        def test_it_complains_if_the_type_doesnt_exist_and_the_target_isnt_optional(self, reg):
            target = Target.FieldSpec().empty_normalise(type="hero")
            assert not target.optional

            with assertRaises(TargetTypeNotFound, target="superman", wanted="hero"):
                reg.add_target("superman", target, mock.Mock(name="creator"))

        def test_it_does_nothing_if_the_type_doesnt_exist_but_the_target_is_optional(self, reg):
            target = Target.FieldSpec().empty_normalise(type="hero", optional=True)
            reg.add_target("superman", target, mock.Mock(name="creator"))
            assert reg.registered == {}

        def test_it_puts_the_information_in_registered_otherwise(self, reg):
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

    class TestCreatingARestriction:
        def test_it_changes_underlying_data(self, reg):
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

            assert reg.restricted(target_names=["batman"]).registered == {"batman": ("hero", target2, creator2)}
            assert reg.restricted(target_names=["batman", "licorice"]).registered == {
                "licorice": ("villian", target3, creator3),
                "batman": ("hero", target2, creator2),
            }
            assert reg.restricted(target_names=["batman", "licorice"], target_types=["villian"]).registered == {
                "licorice": ("villian", target3, creator3),
            }

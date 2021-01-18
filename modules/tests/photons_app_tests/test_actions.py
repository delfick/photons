# coding: spec

from photons_app.actions import an_action
from photons_app import helpers as hp
from photons_app.tasks import Task

from unittest import mock
import pytest
import uuid

describe "an_action":
    it "takes in some options":
        target = mock.Mock(name="target")
        needs_reference = mock.Mock(name="needs_reference")
        special_reference = mock.Mock(name="special_reference")
        needs_target = mock.Mock(name="needs_target")

        wrapper = an_action(
            target=target,
            needs_reference=needs_reference,
            special_reference=special_reference,
            needs_target=needs_target,
        )

        assert wrapper.target is target
        assert wrapper.needs_reference is needs_reference
        assert wrapper.special_reference is special_reference
        assert wrapper.needs_target is needs_target

    describe "wrapping a function":

        @pytest.fixture()
        def V(self):
            class V:
                target = mock.Mock(name="target")
                needs_reference = mock.Mock(name="needs_reference")
                special_reference = mock.Mock(name="special_reference")
                needs_target = mock.Mock(name="needs_target")
                func_name = str(uuid.uuid1())

                @hp.memoized_property
                def wrapper(s):
                    return an_action(
                        target=s.target,
                        needs_reference=s.needs_reference,
                        special_reference=s.special_reference,
                        needs_target=s.needs_target,
                    )

                @hp.memoized_property
                def func(s):
                    return mock.Mock(name="func", __name__=s.func_name)

            return V()

        it "namespaces by target in available_actions", V:
            actions = {}
            with mock.patch("photons_app.actions.available_actions", actions):
                assert V.wrapper(V.func) is V.func

            assert actions == {V.target: {V.func_name: V.func}}

        it "adds information to the func", V:
            actions = {}
            with mock.patch("photons_app.actions.available_actions", actions):
                assert V.wrapper(V.func) is V.func

            assert V.func.target is V.target
            assert V.func.needs_reference is V.needs_reference
            assert V.func.special_reference is V.special_reference
            assert V.func.needs_target is V.needs_target

        it "adds to all_tasks", V:
            actions = {}
            all_tasks = {}
            with mock.patch("photons_app.actions.available_actions", actions):
                with mock.patch("photons_app.actions.all_tasks", all_tasks):
                    assert V.wrapper(V.func) is V.func

            assert all_tasks == {V.func_name: Task(action=V.func_name, label="Project")}

        it "adds to all_tasks with specified label", V:
            label = str(uuid.uuid1())
            actions = {}
            all_tasks = {}
            with mock.patch("photons_app.actions.available_actions", actions):
                with mock.patch("photons_app.actions.all_tasks", all_tasks):
                    assert an_action(label=label)(V.func) is V.func

            assert all_tasks == {V.func_name: Task(action=V.func_name, label=label)}

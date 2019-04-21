# coding: spec

from photons_app.test_helpers import TestCase
from photons_app import helpers as hp

from unittest import mock
import os

describe TestCase, "add_error":
    it "calls the error_catcher with the error if it's a callable":
        error = mock.Mock(name="error")
        catcher = mock.Mock(name="catcher")
        hp.add_error(catcher, error)
        catcher.assert_called_once_with(error)

    it "appends to the error catcher if it's a list":
        error = mock.Mock(name="error")
        catcher = []
        hp.add_error(catcher, error)
        self.assertEqual(catcher, [error])

    it "adds to the error catcher if it's a set":
        error = mock.Mock(name="error")
        catcher = set()
        hp.add_error(catcher, error)
        self.assertEqual(catcher, set([error]))

describe TestCase, "a_temp_file":
    it "gives us the tmpfile":
        with hp.a_temp_file() as fle:
            fle.write(b"wassup")
            fle.seek(0)
            assert os.path.exists(fle.name)
            self.assertEqual(fle.read(), b"wassup")
        assert not os.path.exists(fle.name)

    it "doesn't fail if we delete the file early":
        with hp.a_temp_file() as fle:
            fle.close()
            os.remove(fle.name)
        assert not os.path.exists(fle.name)

describe TestCase, "nested_dict_retrieve":
    it "returns us the dflt if we can't find the key":
        data = {"one": {"two": {"three": 3}}}
        dflt = mock.Mock(name="dflt")
        for keys in (["one", "four"], ["four", "five"], ["one", "two", "five"], ["one", "two", "three", "four"]):
            self.assertIs(hp.nested_dict_retrieve(data, keys, dflt), dflt)

    it "returns us what it finds":
        data = {"one": {"two": {"three": 3}}}
        dflt = mock.Mock(name="dflt")

        self.assertEqual(hp.nested_dict_retrieve(data, [], dflt), data)
        self.assertEqual(hp.nested_dict_retrieve(data, ["one"], dflt), {"two": {"three": 3}})
        self.assertEqual(hp.nested_dict_retrieve(data, ["one", "two"], dflt), {"three": 3})
        self.assertEqual(hp.nested_dict_retrieve(data, ["one", "two", "three"], dflt), 3)

describe TestCase, "memoized_property":
    it "caches on the instance":
        called = []
        blah = mock.Mock(name="blah")

        class Thing:
            @hp.memoized_property
            def blah(self):
                called.append(1)
                return blah

        thing = Thing()
        self.assertEqual(called, [])
        self.assertIs(thing.blah, blah)
        self.assertEqual(called, [1])

        self.assertEqual(thing._blah, blah)
        self.assertIs(thing.blah, blah)
        self.assertEqual(called, [1])

    it "caches on the instance if the return is None":
        called = []

        class Thing:
            @hp.memoized_property
            def blah(self):
                called.append(1)
                return None

        thing = Thing()
        self.assertEqual(called, [])
        self.assertIs(thing.blah, None)
        self.assertEqual(called, [1])

        self.assertEqual(thing._blah, None)
        self.assertIs(thing.blah, None)
        self.assertEqual(called, [1])

    it "caches on the instance if the return is False":
        called = []

        class Thing:
            @hp.memoized_property
            def blah(self):
                called.append(1)
                return False

        thing = Thing()
        self.assertEqual(called, [])
        self.assertIs(thing.blah, False)
        self.assertEqual(called, [1])

        self.assertEqual(thing._blah, False)
        self.assertIs(thing.blah, False)
        self.assertEqual(called, [1])

    it "can set the value":
        called = []
        blah = mock.Mock(name="blah")
        meh = mock.Mock(name="meh")

        class Thing:
            @hp.memoized_property
            def blah(self):
                called.append(1)
                return blah

        thing = Thing()
        self.assertEqual(called, [])
        self.assertIs(thing.blah, blah)
        self.assertEqual(called, [1])

        self.assertEqual(thing._blah, blah)
        thing.blah = meh
        self.assertEqual(thing._blah, meh)

        self.assertIs(thing.blah, meh)
        self.assertEqual(called, [1])

    it "can delete the cache":
        called = []
        blah = mock.Mock(name="blah")

        class Thing:
            @hp.memoized_property
            def blah(self):
                called.append(1)
                return blah

        thing = Thing()
        self.assertEqual(called, [])
        self.assertIs(thing.blah, blah)
        self.assertEqual(called, [1])

        self.assertEqual(thing._blah, blah)
        self.assertIs(thing.blah, blah)
        self.assertEqual(called, [1])

        del thing.blah
        assert not hasattr(thing, "_blah")

        self.assertIs(thing.blah, blah)
        self.assertEqual(called, [1, 1])

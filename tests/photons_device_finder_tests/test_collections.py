# coding: spec

from photons_device_finder import Collection, Collections

from photons_app.test_helpers import TestCase

from noseOfYeti.tokeniser.support import noy_sup_setUp
from unittest import mock
import uuid

describe TestCase, "Collection":
    it "has properties":
        typ = str(uuid.uuid1())
        cuuid = str(uuid.uuid1())
        name = str(uuid.uuid1())

        collection = Collection.FieldSpec().empty_normalise(
              typ = typ
            , uuid = cuuid
            , name = name
            )

        self.assertEqual(collection.typ, typ)
        self.assertEqual(collection.uuid, cuuid)
        self.assertEqual(collection.name, name)
        self.assertEqual(collection.newest_timestamp, None)

    describe "add_name":
        it "adds new name if we don't have a timestamp yet":
            typ = str(uuid.uuid1())
            cuuid = str(uuid.uuid1())
            name = str(uuid.uuid1())
            timestamp = 123

            collection = Collection.FieldSpec().empty_normalise(
                  typ = typ
                , uuid = cuuid
                )

            self.assertEqual(collection.name, "")
            self.assertEqual(collection.newest_timestamp, None)

            collection.add_name(timestamp, name)

            self.assertEqual(collection.name, name)
            self.assertEqual(collection.newest_timestamp, timestamp)

        it "only adds new name if we a greater timestamp":
            typ = str(uuid.uuid1())
            cuuid = str(uuid.uuid1())

            name = str(uuid.uuid1())
            name2 = str(uuid.uuid1())

            collection = Collection.FieldSpec().empty_normalise(
                  typ = typ
                , uuid = cuuid
                )

            self.assertEqual(collection.name, "")
            self.assertEqual(collection.newest_timestamp, None)

            collection.add_name(1, name)

            self.assertEqual(collection.name, name)
            self.assertEqual(collection.newest_timestamp, 1)

            collection.add_name(2, name2)

            self.assertEqual(collection.name, name2)
            self.assertEqual(collection.newest_timestamp, 2)

            collection.add_name(1, name)

            self.assertEqual(collection.name, name2)
            self.assertEqual(collection.newest_timestamp, 2)

    describe "equality":
        it "says no if not a collection":
            class Other:
                pass

            collection = Collection.FieldSpec().empty_normalise(uuid="stuff", typ="group")
            self.assertNotEqual(collection, Other())

        it "says no if not the same typ":
            class Other:
                pass

            collection1 = Collection.FieldSpec().empty_normalise(uuid="stuff", typ="group")
            collection2 = Collection.FieldSpec().empty_normalise(uuid="stuff", typ="location")
            self.assertNotEqual(collection1, collection2)

        it "says no if not the same uuid":
            class Other:
                pass

            collection1 = Collection.FieldSpec().empty_normalise(uuid="stuff", typ="group")
            collection2 = Collection.FieldSpec().empty_normalise(uuid="meh", typ="group")
            self.assertNotEqual(collection1, collection2)

        it "says yes if the same uuid and typ":
            class Other:
                pass

            collection1 = Collection.FieldSpec().empty_normalise(uuid="stuff", typ="group")
            collection2 = Collection.FieldSpec().empty_normalise(uuid="stuff", typ="group")
            self.assertEqual(collection1, collection2)

        it "says yes if the same uuid and typ even if names are different":
            class Other:
                pass

            collection1 = Collection.FieldSpec().empty_normalise(uuid="stuff", typ="group", name="one")
            collection2 = Collection.FieldSpec().empty_normalise(uuid="stuff", typ="group", name="two")
            self.assertEqual(collection1, collection2)

describe TestCase, "Collections":
    it "starts with collections":
        collections = Collections()
        self.assertEqual(collections.collections, {"group": {}, "location": {}})

    it "starts with a spec for creating collection objects":
        typ = str(uuid.uuid1())
        cuuid = str(uuid.uuid1())
        collection = Collections().collection_spec.empty_normalise(typ=typ, uuid=cuuid)
        self.assertEqual(type(collection), Collection)
        self.assertEqual(collection.typ, typ)
        self.assertEqual(collection.uuid, cuuid)

    describe "adding":
        before_each:
            self.uuid = str(uuid.uuid1())
            self.updated_at = mock.Mock(name="updated_at")
            self.label = str(uuid.uuid1())
            self.collections = Collections()

        describe "add_group":
            it "uses add_collection":
                add_collection = mock.Mock(name="add_collection")
                with mock.patch.object(self.collections, "add_collection", add_collection):
                    self.collections.add_group(self.uuid, self.updated_at, self.label)

                add_collection.assert_called_once_with("group", self.uuid, self.updated_at, self.label)

        describe "add_location":
            it "uses add_collection":
                add_collection = mock.Mock(name="add_collection")
                with mock.patch.object(self.collections, "add_collection", add_collection):
                    self.collections.add_location(self.uuid, self.updated_at, self.label)

                add_collection.assert_called_once_with("location", self.uuid, self.updated_at, self.label)

        describe "add_collection":
            it "creates the collection if it doesn't exist":
                collection = mock.Mock(name="collection")
                collection_spec = mock.Mock(name="collection_spec")
                collection_spec.empty_normalise.return_value = collection

                self.assertEqual(self.collections.collections, {"group": {}, "location": {}})

                with mock.patch.object(self.collections, "collection_spec", collection_spec):
                    self.assertIs(self.collections.add_collection("group", self.uuid, 1, self.label), collection)

                collection_spec.empty_normalise.assert_called_once_with(typ="group", uuid=self.uuid)
                collection.add_name.assert_called_with(1, self.label)

            it "doesn't recreate collection if it exists":
                collection = mock.Mock(name="collection")
                collection_spec = mock.Mock(name="collection_spec")
                collection_spec.empty_normalise.side_effect = Exception("Expect empty_normalise to not be called")

                self.collections.collections["location"][self.uuid] = collection

                with mock.patch.object(self.collections, "collection_spec", collection_spec):
                    self.assertIs(self.collections.add_collection("location", self.uuid, 1, self.label), collection)

                self.assertEqual(len(collection_spec.empty_normalise.mock_calls), 0)
                collection.add_name.assert_called_with(1, self.label)

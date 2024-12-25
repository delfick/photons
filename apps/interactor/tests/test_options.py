import os
from unittest import mock


class TestOptions:
    def test_it_has_defaults(self, options_maker):
        options = options_maker(memory=False)
        assert options.host == "127.0.0.1"
        assert options.port == 6100
        assert options.database.as_dict() == {
            "uri": f"sqlite:///{os.getcwd()}/interactor.db",
            "db_migrations": mock.ANY,
        }

    def test_it_can_set_values_of_its_own(self, options_maker):
        options = options_maker("blah", 9001, database={"uri": "somewhere"})

        assert options.host == "blah"
        assert options.port == 9001
        assert options.database.as_dict() == {
            "uri": "sqlite:///somewhere",
            "db_migrations": mock.ANY,
        }

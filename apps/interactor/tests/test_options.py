# coding: spec

import os
from unittest import mock

describe "Options":
    it "has defaults", options_maker:
        options = options_maker(memory=False)
        assert options.host == "127.0.0.1"
        assert options.port == 6100
        assert options.database.as_dict() == {
            "uri": f"sqlite:///{os.getcwd()}/interactor.db",
            "db_migrations": mock.ANY,
        }

    it "can set values of it's own", options_maker:
        options = options_maker("blah", 9001, database={"uri": "somewhere"})

        assert options.host == "blah"
        assert options.port == 9001
        assert options.database.as_dict() == {
            "uri": "sqlite:///somewhere",
            "db_migrations": mock.ANY,
        }

from interactor import VERSION

from setuptools import setup, find_packages

# fmt: off

setup(
      name = "lifx-photons-interactor"
    , version = VERSION
    , packages = find_packages(include="interactor.*", exclude=["tests*"])
    , include_package_data = True

    , python_requires = ">= 3.6"

    , install_requires =
      [ "lifx-photons-core>=0.33.0"
      , "tornado>=6.1"
      , "SQLAlchemy==1.3.3"
      , "alembic==1.3.2"
      , "whirlwind-web>=0.9.0"
      , "aiohttp==3.7.4"
      ]

    , entry_points =
      { "lifx.photons": ["interactor = interactor.addon"]
      }

    # metadata for upload to PyPI
    , url = "http://github.com/delfick/photons/apps/interactor"
    , author = "Stephen Moore"
    , author_email = "github@delfick.com"
    , description = "A server for interacting with LIFX lights over the LAN"
    , license = "MIT"
    , keywords = "lifx photons"
    , long_description = open("README.rst").read()
    )

# fmt: on

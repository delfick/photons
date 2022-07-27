from interactor import VERSION

from setuptools import setup, find_packages

# fmt: off

setup(
      name = "lifx-photons-interactor"
    , version = VERSION
    , packages = find_packages(include="interactor.*", exclude=["tests*"])
    , include_package_data = True

    , python_requires = ">= 3.7"

    , install_requires =
      [ "lifx-photons-core>=0.42.6"
      , "tornado>=6.1"
      , "SQLAlchemy[asyncio]==1.4.23"
      , "aiosqlite==0.17.0"
      , "alembic==1.3.2"
      , "whirlwind-web==0.12.0"
      , "aiohttp==3.7.4"
      , "zeroconf==0.36.12"
      , "netifaces==0.11.0"
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

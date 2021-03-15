from arranger import VERSION

from setuptools import setup, find_packages

# fmt: off

setup(
      name = "lifx-photons-arranger"
    , version = VERSION
    , packages = find_packages(include="arranger.*", exclude=["tests*"])
    , include_package_data = True

    , python_requires = ">= 3.6"

    , install_requires =
      [ "lifx-photons-core>=0.33.0"
      , "tornado>=5.1.1"
      , "whirlwind-web>=0.9.0"
      ]

    , entry_points =
      { "lifx.photons": ["arranger = arranger.addon"]
      }

    # metadata for upload to PyPI
    , url = "http://github.com/delfick/photons/apps/arranger"
    , author = "Stephen Moore"
    , author_email = "github@delfick.com"
    , description = "A web interface for changing the user co-ordinates of LIFX tiles"
    , license = "MIT"
    , keywords = "lifx photons arranger"
    , long_description = open("README.rst").read()
    )

# fmt: on

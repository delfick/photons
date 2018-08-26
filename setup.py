from photons_app import VERSION

from setuptools import setup, find_packages
import os

packages = []
py_modules = []
photons_entry_points = []

# __file__ can sometimes be "" instead of what we want
# in that case we assume we're already in this directory
this_dir = os.path.dirname(__file__) or '.'

for filename in os.listdir(this_dir):
    if filename.startswith("photons_") and filename.endswith(".py"):
        name = os.path.splitext(filename)[0]
        py_modules.append(name)
        photons_entry_points.append("{0} = {1}".format(name[8:], name))
    elif filename.startswith("photons_") and os.path.isdir(filename):
        packages.extend([filename] + ["{0}.{1}".format(filename, pkg) for pkg in find_packages(filename)])
        if filename != 'photons_app':
            photons_entry_points.append("{0} = {1}.addon".format(filename[8:], filename))

setup(
      name = "lifx-photons-core"
    , version = VERSION
    , packages = packages
    , py_modules = py_modules
    , include_package_data = True

    , install_requires =
      [
      # photons_app
        "delfick_error==1.7.8"
      , "input_algorithms==0.6.0"
      , "delfick_app==0.9.7"
      , "option_merge==1.6"
      , "option_merge_addons==0.3"
      , "pyYaml==3.13"

      # photons-tile-messages
      , "lru-dict==1.1.6"

      # photons-protocol
      , "bitarray == 0.8.1"
      ]

    , extras_require =
      { "tests":
        [ "noseOfYeti>=1.7"
        , "asynctest==0.10.0"
        , "nose"
        , "mock"
        ]
      }

    , entry_points =
      { 'console_scripts' :
        [ 'lifx = photons_app.executor:lifx_main'
        ]
      , "lifx.photons": photons_entry_points
      }

    # metadata for upload to PyPI
    , url = "http://github.com/delfick/photons-core"
    , author = "Stephen Moore"
    , author_email = "delfick755@gmail.com"
    , description = "The core modules of the photons framework"
    , long_description = open("README.rst").read()
    , license = "MIT"
    , keywords = "lifx photons"
    )

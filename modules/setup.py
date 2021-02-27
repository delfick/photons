from photons_app import VERSION

from setuptools import setup, find_packages
import os

packages = []
py_modules = []
photons_entry_points = []

readme_location = os.path.join(os.path.dirname(__file__), "README.rst")

# __file__ can sometimes be "" instead of what we want
# in that case we assume we're already in this directory
this_dir = os.path.dirname(__file__) or "."

for filename in os.listdir(this_dir):
    if filename.startswith("photons_") and filename.endswith(".py"):
        name = os.path.splitext(filename)[0]
        py_modules.append(name)
        photons_entry_points.append("{0} = {1}".format(name[8:], name))
    elif filename.startswith("photons_") and os.path.isdir(filename):
        packages.extend(
            [filename] + ["{0}.{1}".format(filename, pkg) for pkg in find_packages(filename)]
        )
        if filename != "photons_app" and os.path.exists(os.path.join(filename, "addon.py")):
            photons_entry_points.append("{0} = {1}.addon".format(filename[8:], filename))

# fmt: off

setup(
      name = "lifx-photons-core"
    , version = VERSION
    , packages = packages
    , py_modules = py_modules
    , include_package_data = True

    , python_requires = ">= 3.6"

    , install_requires =
      [ "delfick_project==0.7.9"
      , "ruamel.yaml==0.16.12"
      , "rainbow_logging_handler==2.2.2"

      # photons-tile-messages
      , "lru-dict==1.1.6"

      # photons-protocol
      , "bitarray==1.6.1"
    
      # photons-canvas
      , "kdtree==0.16"
      ]

    , extras_require =
      { "tests":
        [ "noseOfYeti==2.0.2"
        , "pytest==6.1.2"
        , "mock==4.0.2"
        , "alt-pytest-asyncio==0.5.3"
        , "pytest-helpers-namespace==2019.1.8"
        ]
      }

    , entry_points =
      { 'console_scripts' :
        [ 'lifx = photons_app.executor:lifx_main'
        , 'run_photons_core_tests = photons_pytest:run_pytest'
        ]
      , "pytest11": ["lifx_photons_core = photons_pytest"]
      , "lifx.photons": photons_entry_points
      }

    # metadata for upload to PyPI
    , url = "http://github.com/delfick/photons"
    , author = "Stephen Moore"
    , author_email = "github@delfick.com"
    , description = "The core modules of the photons framework"
    , long_description = open(readme_location).read()
    , license = "MIT"
    , keywords = "lifx photons"
    )

# fmt: on

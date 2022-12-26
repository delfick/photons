from photons_docs import VERSION
from setuptools import find_packages, setup

# fmt: off

setup(
      name = "lifx-photons-docs"
    , version = VERSION
    , packages = ["photons_docs"] + ["photons_docs.{0}".format(pkg) for pkg in find_packages("photons_docs")]

    , install_requires =
      [ "Sphinx==4.3.2"
      , "tornado==6.1"
      , "sphinx_rtd_theme==1.0.0"
      ]

    , entry_points =
      { 'console_scripts' :
        [ 'photons-docs = photons_docs.executor:main'
        ]
      , "lifx.photons": ["docs = photons_docs.addon"]
      }
    )

# fmt: on

from photons_docs import VERSION
from setuptools import find_packages, setup

# fmt: off

setup(
      name = "lifx-photons-docs"
    , version = VERSION
    , packages = ["photons_docs"] + ["photons_docs.{0}".format(pkg) for pkg in find_packages("photons_docs")]

    , install_requires =
      [ "Sphinx==7.2.6"
      , "sphinx_rtd_theme==2.0.0"
      ]

    , entry_points =
      { 'console_scripts' :
        [ 'photons-docs = photons_docs.executor:main'
        ]
      , "lifx.photons": ["docs = photons_docs.addon"]
      }
    )

# fmt: on

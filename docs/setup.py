from photons_docs import VERSION

from setuptools import setup, find_packages

# fmt: off

setup(
      name = "lifx-photons-docs"
    , version = VERSION
    , packages = ["photons_docs"] + ["photons_docs.{0}".format(pkg) for pkg in find_packages("photons_docs")]

    , install_requires =
      [ "Sphinx==3.5.3"
      , "tornado==6.1"
      , "docutils==0.16"
      , "sphinx_rtd_theme==0.5.1"
      ]

    , entry_points =
      { 'console_scripts' :
        [ 'photons-docs = photons_docs.executor:main'
        ]
      , "lifx.photons": ["docs = photons_docs.addon"]
      }
    )

# fmt: on

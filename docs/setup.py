from photons_docs import VERSION

from setuptools import setup, find_packages

# fmt: off

setup(
      name = "lifx-photons-docs"
    , version = VERSION
    , packages = ["photons_docs"] + ["photons_docs.{0}".format(pkg) for pkg in find_packages("photons_docs")]

    , install_requires =
      [ "Sphinx==2.4.4"
      , "tornado==6.0.4"
      , "sphinx_rtd_theme==0.5.0"
      ]

    , entry_points =
      { 'console_scripts' :
        [ 'photons-docs = photons_docs.executor:main'
        ]
      , "lifx.photons": ["docs = photons_docs.addon"]
      }
    )

# fmt: on

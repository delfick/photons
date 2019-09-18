from setuptools import setup, find_packages

# fmt: off

setup(
      name = "lifx-photons-docs"
    , version = "0.1"
    , packages = ["photons_docs"] + ["photons_docs.{0}".format(pkg) for pkg in find_packages("photons_docs")]

    , install_requires =
      [ "Sphinx==1.6.3"
      , "sphinx_rtd_theme==0.2.5b1"
      , "sphinxcontrib-trio==1.0.0"
      ]

    , entry_points =
      { 'console_scripts' :
        [ 'photons-docs = photons_docs.executor:main'
        ]
      , "lifx.photons": ["docs = photons_docs.addon"]
      }
    )

# fmt: on

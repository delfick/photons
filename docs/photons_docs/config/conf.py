import pkg_resources

extensions = [
    "sphinx.ext.autodoc",
    "photons_docs.config.ext.plans",
    "photons_docs.config.ext.colour",
    "photons_docs.config.ext.packets",
    "photons_docs.config.ext.products",
]

html_theme = "sphinx_rtd_theme"
html_static_path = ["static"]
html_css_files = ["extra.css"]

html_theme_options = {
    "collapse_navigation": False,
    "sticky_navigation": True,
    "navigation_depth": 4,
    "titles_only": True,
}

html_static_path = [pkg_resources.resource_filename("photons_docs", "config/static")]

exclude_patterns = ["_build/**", "venv/**"]

master_doc = "index"
source_suffix = ".rst"

pygments_style = "pastie"

copyright = u"Stephen Moore"
project = u"Photons"

version = "0.1"
release = "0.1"

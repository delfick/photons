import sphinx_rtd_theme
import pkg_resources

extensions = [
    "sphinx.ext.autodoc",
    "photons_messages.sphinx.messages",
]

html_theme = "the_theme"
html_theme_path = [
    pkg_resources.resource_filename("photons_docs", "config/templates"),
    sphinx_rtd_theme.get_html_theme_path(),
]
html_static_path = [pkg_resources.resource_filename("photons_docs", "config/static")]

exclude_patterns = ["_build/**", "venv/**"]

master_doc = "index"
source_suffix = ".rst"

pygments_style = "pastie"

copyright = u"Stephen Moore"
project = u"Photons"

version = "0.1"
release = "0.1"

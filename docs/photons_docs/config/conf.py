import sphinx_rtd_theme
import pkg_resources

extensions = [
    "sphinx.ext.autodoc",
    "photons_messages.sphinx.messages",
    "photons_app.sphinx.code_for",
    "photons_app.sphinx.structures",
    "photons_app.sphinx.docstrings",
    "photons_app.sphinx.tasks",
    "photons_app.sphinx.target_fields",
    "photons_docs.config.ext.photons_errors",
    "photons_docs.config.ext.photons_app_ext",
    "photons_docs.config.ext.available_modules",
    "photons_docs.config.ext.photons_protocol_extra",
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

copyright = u"2018, Stephen Moore"
project = u"Photons"

version = "0.1"
release = "0.1"

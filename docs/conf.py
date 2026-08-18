"""Configuration file for the Sphinx documentation builder."""

from datetime import datetime
from importlib.metadata import metadata
from importlib.metadata import version as distribution_version

distribution = metadata("isobands")
project = distribution["Name"]
author = distribution.get("Author") or distribution.get("Author-email", "")
version = distribution_version(project)
release = version
year = datetime.now().year
copyright = f"{year}, {author}"

language = "en"
templates_path = ["_templates"]
html_static_path = []
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]
pygments_style = "sphinx"

extensions = [
    "myst_parser",
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.intersphinx",
    "sphinx.ext.napoleon",
    "sphinxcontrib.mermaid",
    "sphinx_copybutton",
]

autodoc_member_order = "bysource"
autodoc_typehints = "description"
autodoc_default_options = {
    "members": True,
    "member-order": "bysource",
    "special-members": "__init__",
    "undoc-members": True,
    "show-inheritance": True,
}
autosummary_generate = True

nitpicky = True
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "geopandas": ("https://geopandas.org/en/stable/", None),
    "xarray": ("https://docs.xarray.dev/en/stable/", None),
}

linkcheck_timeout = 10
linkcheck_retries = 2

html_theme = "palewire"

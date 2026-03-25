# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# http://www.sphinx-doc.org/en/master/config

import os
import sys
import django

os.environ['DJANGO_SETTINGS_MODULE'] = 'tom_base.settings'
django.setup()

sys.path.insert(0, os.path.abspath(".."))

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.viewcode",
    "sphinx_breeze_theme",
    'myst_parser',
]
templates_path = ["_templates"]
source_suffix = {
    ".rst": "restructuredtext",
    ".txt": "markdown",
    ".md": "markdown",
}
master_doc = "index"
project = "TOM Toolkit"
copyright = "2026, Las Cumbres Observatory"
author = "Joey Chatelain, David Collom, Lindy Lindstrom, Austin Riba, Rachel Street"

language = "en"
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store", "requirements.txt"]
# If true, `todo` and `todoList` produce output, else they produce nothing.
todo_include_todos = False
today_fmt = "%Y-%m-%d %H:%M"

# -- Options for HTML output -------------------------------------------
html_theme = "breeze"
html_show_sphinx = True
html_static_path = ['_static']
html_css_files = ["custom.css"]
html_favicon = "_static/logo-color.png"

github_doc_root = "https://github.com/TOMToolkit/tom_base/tree/dev/docs"

def setup(app):
    pass

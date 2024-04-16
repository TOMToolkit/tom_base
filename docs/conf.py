# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# http://www.sphinx-doc.org/en/master/config

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
import os
import sys
import django
import sphinx_rtd_theme

from recommonmark.parser import CommonMarkParser

from tom_base import __version__

sys.path.insert(0, os.path.abspath('..'))


# -- Project information -----------------------------------------------------

project = 'TOM Toolkit'
copyright = '2021-4, Las Cumbres Observatory'
author = 'Joey Chatelain, David Collom, Lindy Lindstrom, Austin Riba'

# The full version, including alpha/beta/rc tags
# This has to mirror the setup.py version for PDF generation
release = __version__

# -- Django Configuration -------------------------------------------------

# import os
# import sys
# import django
# sys.path.insert(0, os.path.abspath('..'))
os.environ['DJANGO_SETTINGS_MODULE'] = 'tom_base.settings'
django.setup()


# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.autosectionlabel',
    'sphinx.ext.autosummary',
    'sphinx.ext.intersphinx',
    'sphinx_panels',
    'sphinx_copybutton',
]

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

# source_parsers = {
#     '.md': 'recommonmark.parser.CommonMarkParser',
# }

# source_suffix = ['.rst', '.md']

# autodoc_mock_imports = ['rise-set']
autodoc_inherit_docstrings = False
autodoc_default_options = {
    # 'members':         True,
    'member-order':    'bysource',
    # 'special-members': '__init__',
}
autoclass_content = 'both'

# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.

html_sidebars = {
    '**': [
        'about.html',
        'navigation.html',
        'relations.html',
        'searchbox.html',
        'donate.html',
    ]
}

html_static_path = ['_static']
html_theme = 'alabaster'
# html_theme = 'sphinx_rtd_theme'

html_theme_path = [sphinx_rtd_theme.get_html_theme_path()]
html_theme_options = {
    'logo': 'logo-color.png',
    'logo_name': 'false',
    'github_repo': 'tom_base',
    'github_button': 'false',
}

pygments_style = 'sphinx'

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
# html_static_path = ['_static']


def setup(app):
    app.add_source_suffix('.md', 'markdown')
    app.add_source_parser(CommonMarkParser)

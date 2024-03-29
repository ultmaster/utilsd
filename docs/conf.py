# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
import os
import sys
from datetime import datetime
sys.path.insert(0, os.path.abspath('..'))

version_file = '../utilsd/__init__.py'

def get_version(rel_path):
    with open(rel_path) as f:
        for line in f.readlines():
            if line.startswith('__version__'):
                delim = '"' if '"' in line else "'"
                return line.split(delim)[1]
    raise RuntimeError("Unable to find version string.")

__version__ = get_version(version_file)

# -- Project information -----------------------------------------------------

project = 'utilsd'
copyright = f'{datetime.now().year}, Yuge Zhang'
author = 'utilsd dev'
version = __version__
release = __version__

# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    'sphinx.ext.napoleon',
    'nbsphinx'
]

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store', '.ipynb_checkpoints']

# The master toctree document.
master_doc = 'index'

# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = 'pydata_sphinx_theme'

html_theme_options = {
    # Set you GA account ID to enable tracking
    'google_analytics_id': 'G-4BJDV0VR74',

    'icon_links': [
        {
            # Label for this link
            'name': 'GitHub',
            # URL where the link will redirect
            'url': 'https://github.com/ultmaster/utilsd',  # required
            # Icon class (if 'type': 'fontawesome'), or path to local image (if 'type': 'local')
            'icon': 'fab fa-github-square',
            # Whether icon should be a FontAwesome class, or a local file
            'type': 'fontawesome',  # Default is fontawesome
        }
   ]
}

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ['_static']

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
sys.path.insert(0, os.path.abspath('../spiderfoot'))
sys.path.insert(0, os.path.abspath('..'))


# -- Project information -----------------------------------------------------

project = 'SpiderFoot'
copyright = '2012-2024, Steve Micallef'
author = 'Steve Micallef'
version = '5.2.2'
release = '5.2.2'


# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',
    'sphinx.ext.viewcode',
    'sphinx.ext.todo',
    'sphinx.ext.githubpages',
    'sphinx.ext.intersphinx',
    'sphinx.ext.coverage',
    'sphinx.ext.doctest',
    'myst_parser',
    'sphinx_copybutton',
]

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# The language for content autogenerated by Sphinx. Refer to documentation
# for a list of supported languages.
#
# This is also used if you do content translation via gettext catalogs.
# Usually you set "language" from the command line for these cases.
language = 'en'

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

# The master toctree document.
master_doc = 'index'

# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = 'sphinx_rtd_theme'

# Theme options are theme-specific and customize the look and feel of a theme
# further.  For a list of options available for each theme, see the
# documentation.
html_theme_options = {
    'canonical_url': '',
    'analytics_id': '',
    'logo_only': False,
    'display_version': True,
    'prev_next_buttons_location': 'bottom',
    'style_external_links': False,
    'vcs_pageview_mode': '',
    'style_nav_header_background': '#2980B9',
    # Toc options
    'collapse_navigation': True,
    'sticky_navigation': True,
    'navigation_depth': 4,
    'includehidden': True,
    'titles_only': False
}

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ['_static']

# Custom sidebar templates, must be a dictionary that maps document names
# to template names.
html_sidebars = {
    '**': [
        'about.html',
        'navigation.html',
        'relations.html',
        'searchbox.html',
        'donate.html',
    ]
}

# -- Extension configuration -------------------------------------------------

# -- Options for todo extension ----------------------------------------------

# If true, `todo` and `todoList` produce output, else they produce nothing.
todo_include_todos = True

# -- Options for intersphinx extension ---------------------------------------

# Example configuration for intersphinx: refer to the Python standard library.
intersphinx_mapping = {
    'python': ('https://docs.python.org/3/', None),
    'requests': ('https://requests.readthedocs.io/en/master/', None),
}

# -- Options for autodoc extension -------------------------------------------

# This value controls how to represent typehints.
autodoc_typehints = 'description'

# This value selects what content will be inserted into the main body of an autoclass directive.
autoclass_content = 'both'

# This value selects if automatically documented members are sorted alphabetical or by member type.
autodoc_member_order = 'bysource'

# This value is a list of autodoc directive flags that should be automatically applied to all autodoc directives.
autodoc_default_flags = ['members', 'undoc-members', 'show-inheritance']

# -- Options for Napoleon extension ------------------------------------------

# Enable parsing of Google style docstrings
napoleon_google_docstring = True

# Enable parsing of NumPy style docstrings
napoleon_numpy_docstring = True

# Include init docstrings in class docstring
napoleon_include_init_with_doc = False

# Include private members starting with _
napoleon_include_private_with_doc = False

# Include special members starting with __
napoleon_include_special_with_doc = False

# Use admonitions for sections
napoleon_use_admonition_for_examples = False
napoleon_use_admonition_for_notes = False
napoleon_use_admonition_for_references = False

# Use param role for parameters
napoleon_use_param = True

# Use rtype role for return types
napoleon_use_rtype = True

# Markdown support
source_suffix = {
    '.rst': None,
    '.md': 'myst_parser',
}

# MyST parser configuration
myst_enable_extensions = [
    "deflist",
    "tasklist",
    "html_admonition",
    "html_image",
    "colon_fence",
    "smartquotes",
    "replacements",
    "linkify",
    "substitution",
]

myst_heading_anchors = 3

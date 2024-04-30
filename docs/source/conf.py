# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html
import sys, os
#import sphinx_rtd_theme


sys.path.append(os.path.abspath('../../brood_hostside/'))
print(sys.path[-1])
#sys.path.append(os.path.abspath('../../brood_hostside/'))
# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'ho-brood-hostside'
copyright = '2024, Rob Mills, Rafael Barmak, Daniel Hofstadler'
author = 'Rob Mills, Rafael Barmak, Daniel Hofstadler'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions =  ['sphinx.ext.autodoc', 'myst_parser', 'sphinx.ext.githubpages', 'sphinx_copybutton'] 

templates_path = ['_templates']
exclude_patterns = []

# configure the code highlighting
pygments_style = 'sphinx'

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

#html_theme = 'alabaster'
#html_theme = 'sphinx_rtd_theme'
#html_theme = 'sphinx_material'
html_theme = 'sphinx_book_theme' # this has the ctrl-k search feature.

html_static_path = ['static']

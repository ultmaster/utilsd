.. utilsd documentation master file, created by
   sphinx-quickstart on Mon Jun  7 12:15:09 2021.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

==================================
Welcome to utilsd's documentation!
==================================

I'm collecting *common utils* that are used in at least 2 of the projects I have been working on. I expect most of the utils are in the corner of logging, experiment setup, config management, log analysis, and etc. As I almost always use PyTorch and most of the projects are featuring vision tasks, it will be built upon PyTorch.

Getting started
---------------

To install from pip,

.. code-block:: bash

   $ pip install utilsd

.. note:: utilsd is under intense development. Please use ``--upgrade`` to keep track of the latest features.

To install the development version,

.. code-block:: bash

   $ git clone https://github.com/ultmaster/utilsd
   $ python setup.py develop

Contents
--------

.. toctree::
   :caption: Tutorials
   :maxdepth: 2

   tutorials/index

.. toctree::
   :caption: References
   :maxdepth: 2

   references


Indices and tables
------------------

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

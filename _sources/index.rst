.. ho-brood-hostside documentation master file, created by
   sphinx-quickstart on Fri Feb  9 21:38:10 2024.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Documentation for ho-brood-hostside
===================================


.. toctree::
   :maxdepth: 2
   :caption: Contents:

.. include:: quickstart.rst

Key classes
===========


libabc -- ABCHandle
-------------------

The primary class used to interact with the broodnest robotic frame is
``libabc.ABCHandle``.  This provides the top-level entry point to a robot module,
facilitating the acquisition of samples from all sensors, as well as
configuration, and actuator control. 


.. autoclass:: brood_hostside.libabc.ABCHandle
   :members:
   :member-order: bysource

libabc -- exceptions
---------------------

.. automodule:: brood_hostside.libabc
   :exclude-members: ABCHandle, parse_pwr, parse_co2, parse_rht, HtrReadings
   :members:
   :member-order: bysource

libabc -- other functionality
-----------------------------

.. autofunction:: brood_hostside.libabc.parse_pwr 
.. autofunction:: brood_hostside.libabc.parse_co2 
.. autofunction:: brood_hostside.libabc.parse_rht 

.. autoclass:: brood_hostside.libabc.HtrReadings
   :members:
   :member-order: bysource
   

..   :undoc-members:
..   :show-inheritance:



Support classes
===============

The functionality of ``brood_hostside`` is divided into several modules, which
implement other classes or supporting functions used to interact with the
broodnest robotic frame.  Most of these libraries are back-end, instantiated by
``libabc.ABCHandle``, but users do not need to be overly concerned with the 
details. 

Database interaction -- **libdb**
---------------------------------

.. automodule:: brood_hostside.libdb
   :members:
   :member-order: bysource


User interface wrappers -- **libui**
------------------------------------

.. automodule:: brood_hostside.libui
   :members:
   :member-order: bysource


Logging library
---------------

.. automodule:: brood_hostside.liblog
   :members:
   :member-order: bysource


Baseclass -- **libbase**
------------------------

.. automodule:: brood_hostside.libbase
   :members:
   :member-order: bysource



.. comment: note that these RST files have their own headers
.. include:: usage_notes.rst
.. include:: dev_notes.rst

Citation
========

Our article in IEEE Access contains detailed information on the design and 
validation of the robotic system.

R. Barmak, D.N. Hofstadler, M. Stefanec, L. Piotet, R. Cherfan, T. Schmickl, F.
Mondada, R. Mills (2024)  "**Biohybrid Superorganisms—On the Design of a Robotic
System for Thermal Interactions With Honeybee Colonies,**" in *IEEE Access*, vol.
12, pp. 50849-50871, 2024, doi: 
`10.1109/ACCESS.2024.3385658 <https://doi.org/10.1109/ACCESS.2024.3385658>`_. 



Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

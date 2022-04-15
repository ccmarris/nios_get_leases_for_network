===========================
NIOS Get leases for network
===========================

| Version: 0.1.0
| Author: Chris Marrison
| Email: chris@infoblox.com

Description
-----------

Demo script to retrieve lease information for a network using threads to
improve performance by approximately 50% using default settings.

Prerequisites
-------------

Python 3.6+


Installing Python
~~~~~~~~~~~~~~~~~

You can install the latest version of Python 3.x by downloading the appropriate
installer for your system from `python.org <https://python.org>`_.

.. note::

  If you are running MacOS Catalina (or later) Python 3 comes pre-installed.
  Previous versions only come with Python 2.x by default and you will therefore
  need to install Python 3 as above or via Homebrew, Ports, etc.

  By default the python command points to Python 2.x, you can check this using 
  the command::

    $ python -V

  To specifically run Python 3, use the command::

    $ python3


.. important::

  Mac users will need the xcode command line utilities installed to use pip3,
  etc. If you need to install these use the command::

    $ xcode-select --install

.. note::

  If you are installing Python on Windows, be sure to check the box to have 
  Python added to your PATH if the installer offers such an option 
  (it's normally off by default).


Modules
~~~~~~~

Non-standard modules:

    - rich (for pretty printing)

Complete list of modules::

  import logging
  from rich import print
  import requests
  import argparse
  import configparser
  import time
  import concurrent.futures


Installation
------------

The simplest way to install and maintain the tools is to clone this 
repository::

    % git clone https://github.com/ccmarris/nios_get_leases_for_network


Alternative you can download as a Zip file.


Basic Configuration
-------------------

The script utilises a gm.ini file to specify the Grid Master, API version
and user/password credentials.


gm.ini
~~~~~~~

The *gm.ini* file is used by the script to define the details to connect to
to Grid Master. A sample inifile is provided and follows the following 
format::

  [NIOS]
  gm = '192.168.1.10'
  api_version = 'v2.12'
  valid_cert = 'false'
  user = 'admin'
  pass = 'infoblox'


You can use either an IP or hostname for the Grid Master. This inifile 
should be kept in a safe area of your filesystem. 

Use the --config/-c option to specify the ini file.


Usage
-----

The script supports -h or --help on the command line to access the options 
available::

  % ./nios_get_leases_for_network.py --help
  usage: nios_get_leases_for_network.py [-h] [-c CONFIG] -n NETWORK [-v VIEW] [-t THREADS] [-s SESSIONS] [-d]

  Retrieve leases for specified network.

  optional arguments:
    -h, --help            show this help message and exit
    -c CONFIG, --config CONFIG
                          Override ini file
    -n NETWORK, --network NETWORK
                          Specify network to get IP information
    -v VIEW, --view VIEW  Specify the network view 
    -t THREADS, --threads THREADS
                          Number of Threads
    -s SESSIONS, --sessions SESSIONS
                          Number of HTTP Session to create
    -d, --debug           Enable debug messages


The script, by default, uses five threads and a single HTTP session. However,
these can be speficied on the command line. With larger subnets you may try
using 10 threads (-t 10) to further improve performance, but please feel free
to try alternate numbers of threads and or sessions and see what works best
for your dataset. With larger numbers of active leases in a network, the 
performance improvements over a serial approach should be greater.


Examples
--------

Simple example::

  % ./nios_get_leases_for_network.py --config gm.ini --network 192.168.1.0


Specify an alternate network view::

  % ./nios_get_leases_for_network.py -c gm.ini -n 192.168.1.0 -v internal


Increase the numnber of threads::

  % ./nios_get_leases_for_network.py -c gm.ini -n 192.168.1.0 -t 10
 

License
-------

This project, and the bloxone module are licensed under the 2-Clause BSD License
- please see LICENSE file for details.


Aknowledgements
---------------

Thanks to Ingmar Schraub for bringing the question to me and testing.

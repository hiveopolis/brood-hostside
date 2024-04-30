Quickstart
==========

Assuming that you are running the robot in conjunction with a RPi, running raspian or similar:

1. Install binary dependencies

    .. code-block:: bash
        
        sudo apt install python3-numpy

2. install the package

   .. code-block:: bash

        mkdir software && cd software
        pip3 install brood_hostside.tar.gz

3. edit the example config to match your system

   .. code-block:: bash
      nano cfg/example.cfg

4. run the sampling-only handler:

   .. code-block:: bash

       python3 abc_read.py -c cfg/example.cfg



5. or run the actuator-enabled handler:

   .. code-block:: bash
        `python3 abc_run.py -c cfg/example.cfg`

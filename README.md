# brood-hostside

Code to manage the hiveopolis ABC broodnest system - control, config, logging

## Brief overview

* the ABC comb firmware runs a micropython interface (with other chibiOS RTOS
  threads in the background to handle all the sensors and actuators).
* to obtain current status we use the library `pyboard`.

* the script `abc_read` is the key entry point to all sampling, without
  actuation.  It is parameterised by a config file, which is passed on the
  command line.
* the script `abc_run` additionally enables actuators, also using the config
  file for parameters 

* Data is gathered, and stored in multiple local log files:
  * `<node_name>_<snr>_<date>.csv` --> 5 csv files for 5 different sensor types.
    each sample is on a new row, and includes human-readable and unix timestamps.
  * `<node_name>_<date>.log` --> transcript of activity at various levels of
    logging.

* All boards have a unique serial in their USB attributes, allowing the udev
  rules to generate symlinks for repeatable access to the same board (see
 `udev/` subdir)


## Expected format of hostname

The hostname is expected to have three elements, with the last two having an
integer at the end:

    `location-hiveX-rpiY`, e.g. `paris-hive3-rpi2`

If this is not suitable for your deployment, the config file has a manual
override to cope with other sitautions. 

## Citations

The detailed design of the system is published in:

"Biohybrid superorganisms - on the design of a robotic system for thermal interactions with honeybee colonies"
By R. Barmak, D. N. Hofstadler, M. Stefanec, L. Piotet, R. Cherfan, T. Schmickl, F. Mondada, and R. Mills.
IEEE Access, 2024, 12:50849--50871, [doi:10.1109/ACCESS.2024.3385658](https://doi.org/10.1109/ACCESS.2024.3385658)

The system was also used to demonstrate interaction with winter clusters in the following article:

"A robotic honeycomb for interaction with a honeybee colony"
by Barmak, R., Stefanec, M., Hofstadler, D. N., Piotet, L., Schoenwetter-Fuchs-Schistek, S., Mondada, F., Schmickl, T., & Mills, R. Science Robotics, 2023, 8(76). [doi:10.1126/scirobotics.add7385](https://doi.org/10.1126/scirobotics.add7385)


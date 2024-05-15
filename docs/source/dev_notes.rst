Some developer notes
====================

Requirements
------------

The python packages required are defined in `setup.py``:

- pyserial (note: NOT `serial`; both are used as `import serial`, confusingly)
- influxdb-client
- numpy 

The current version has been tested using RPi platforms of armv7l and arm64 variants,
running python versions 3.7.3, 3.9.2. 
For database interaction, it has been tested with `influxdb-client==1.36.0` and
influx 2.x databases.


The database of influx 2.x has been tested hosted on ubuntu 22.04 servers and on
RPi4B with arm64 arch. With a 64-bit architecture, a RPi can host both a local
influx database instance and one or more robots. Other documentation within the 
project will explain such setups further if needed.

Earlier versions were tested with the client `influxdb==5.2.0` for influx 1.x
databases, and tested with influxd 1.6.4 (hosted on RPi3B with armv7l arch).


Database setup
--------------

Measurements generated are in sub-tables (influxDB calls these different 'measurements'):

+-------+-------+-------+-------+-------+
|  rht  | temp  |  co2  |  pwr  |  htr  |
+-------+-------+-------+-------+-------+

Metadata relating to the robot (e.g. short name, MCU-UUID) and its installation
location (e.g. hive number, geographic location) are attached to the injected points.
In InfluxDB, metadata is called 'tags'. The cardinality of the unique tag combinations,
but not the number of tags, affects the performance of the database -- so more tags 
does not inherently mean worse performance. See influxDB docs for more details.


## Links to docs
^^^^^^^^^^^^^^^^

* InfluxDB python client, v2.x (`import influxdb_client.InfluxDBClient`)
    * `Github repo <https://github.com/influxdata/influxdb-client-python>`_
    * `readthedocs <https://influxdb-client.readthedocs.io/en/stable/api.html>`_

Python version
--------------

Due to deployment on resource-limited devices, we avoided using too many recent features of python. 
Much development was validated using python 3.7.3, requires >=3.6

- requires >=3.6
   - f-strings are used
   - using `timespec` arg in `datetime.datetime.isoformat()`

- requires >=3.5
   - function type hints used in datetime handling


Some open issues
----------------

See issue tracker within github repository

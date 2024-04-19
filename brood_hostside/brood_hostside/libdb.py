'''
Class to interact with influxDB database (V2.x), sending points from ABC
measurements.

Date formats are important for injecting the data correctly, including
timezones.  The method `libbase.ABCBase.timestamp4db()` prepares the timestamps
consistently, here we add notes for reference only.

Influx supports several formats, we elect to use iso-8601 format, using a 
UTC timezone. For one example date, these representations are equivalent:

* unix timestamp:               1628768585
* human-readable:               Thu 12 Aug 13:43:05 CEST 2021
* ISO-8601 (w/CEST offset)      2021-08-12T13:43:05+02:00
* ISO-8601 (w/UTC offset)       2021-08-12T11:43:05+00:00
* ISO-8601 (compact, if UTC)    2021-08-12T11:43:05Z

We use the last one in this package.
   
'''

from typing import List, Union
from configparser import ConfigParser
from pathlib import Path
import platform
import time
import requests
import urllib3
import json


# 2.x api
from influxdb_client import InfluxDBClient as InfluxDBClientv2
from influxdb_client import Point, WritePrecision
#from influxdb_client import Point
from influxdb_client.client.write_api import SYNCHRONOUS
from influxdb_client.rest import ApiException

from brood_hostside.libbase import ABCBase

# {{{ some exceptions
class DBBaseError(Exception):           # noqa: E302
    ''' base class for errors relating to DBInjector & libdb functions'''
    pass
class DBFailedWrite(DBBaseError):       # noqa: E302
    ''' Could not write points to database '''
    pass
class DBBadFormatWrite(DBBaseError):    # noqa: E302
    ''' write request message is badly formatted
        (did you use the api to form it?)
    '''
class DBBadCredentials(DBBaseError):    # noqa: E302
    ''' incorrect authorisation for database '''
    pass
class DBTimedoutOnWrite(DBBaseError):   # noqa: E302
    ''' Could not connect to DB on write - http timeout'''
    pass
# }}}

# {{{ ping influxDB2
# adapted from Vitalijs; note - implemented as a standalone function since
# it does not require a connection, thus we don't need to instantiate an
# object - but for convenience DBInjector has method ping()
def wait_for_engine(host, port, maxcount=50, timeout=3) -> bool:
    '''block until ping response is ok from influxDB instance `host:port`

    returns True if successful, False if reached `maxcount` unsucessful attempts
    each with a duration `timeout`.
    '''
    # NOTE: there is also a <db-addr>/health endpoint, may be more informative
    url = f"http://{host}:{port}/ping"
    t_start = time.time()
    while True:
        try:
            res = requests.get(url, timeout=timeout).status_code
        except:
            res = 0

        if res == 204: # the influx request response that indicates OK
            return True
        else:
            elap = time.time() - t_start

            print(f"[I] Waiting for engine... (after {elap:.1f}s)")
            time.sleep(timeout-1)
            maxcount -= 1

            if maxcount < 0:
                elap = time.time() - t_start
                print(f"[W] DB2: influxDB not reachable after {elap:.1f}s!")
                return False
                #exit(-1)
# }}}

class BaseDBInjector:
    '''
    A class providing influxDB database interaction


    '''
    def __init__(self, credfile:Union[str, Path], start_connected:bool=False, **kwargs):
        #super().__init__(**kwargs)

        self.credfile = Path(credfile).expanduser()  # required arg Path or str
        self.verb = kwargs.get("verb", False)

        self.read_influxdb_conn_cfg()
        self._populate_queries()
        self.write_precision = WritePrecision.S 

        self._connected_db = False # did we open a connection?
        self._db_ok = False        # did the DB respond to ping or healthcheck?
        if start_connected:
            self.attach_client()

    def read_influxdb_conn_cfg(self):
        ''' read the influxDB connection settings'''
        cfg = ConfigParser()
        cfg.read(self.credfile)

        sec = "InfluxDB"
        # DB server location
        self.ifhost    = cfg.get(sec, "host")       # noqa: E221
        self.ifport    = cfg.get(sec, "port")       # noqa: E221

        # ifdb2 credentials 
        self.if2token  = cfg.get(sec, "token")      # noqa: E221
        self.if2org    = cfg.get(sec, "org")        # noqa: E221
        self.if2bucket = cfg.get(sec, "bucket")     # noqa: E221


    def attach_client(self, verb:bool=True, no_ping_fatal:bool=False):
        if not self._connected_db:
            try:
                url = f"http://{self.ifhost}:{self.ifport}"
                self.client = InfluxDBClientv2(url=url, token=self.if2token)
                self._connected_db = True
                print(f"DB2|[I] Connected with ifdb cli rev 2.x: "
                      f"{self.ifhost}:{self.if2org} - {self.if2bucket}")
                # pass
            finally:
                print(
                    f"'Finally' in attach_client(verb={verb}), "
                    f"self.client={self.client}, "
                    f"self.connected_db={self._connected_db}."
                )

            self.write_api = self.client.write_api(write_options=SYNCHRONOUS)

            # try pinging
            self._db_ok = self.ping(maxcount=3, timeout=3)
            if self._db_ok:
                print(f"DB2|[I] ping ok with influxDB @ {url}")
            else:
                if no_ping_fatal:
                    raise RuntimeError(
                        f"[F] cannot connect to influxDB instance @ {url}")
                else:
                    print(f"[W] ifdb @ {url} unresponsive to pings")

        else:
            print("[W] already have connection established "
                  f"with {self.ifhost}:{self.if2org} - {self.if2bucket}")

        if verb:
            mlist =  self.get_measurements()
            msg = f"[I] measurements in bucket '{self.if2bucket}': {mlist}"
            print(f"DB2|{msg}")
 
    def closedown(self):
        if self._connected_db:
            self.client.close()
            print(f"[I] closed connection with db {self.if2bucket}")

            self._connected_db = False
    # }}}

    # {{{ some useful queries
    def _populate_queries(self):
        self.q_meas_list = f'''
        import "influxdata/influxdb/schema"
        schema.measurements(bucket: "{self.if2bucket}")
        '''

    def get_measurements(self):
        '''Query ifdb2 for list of measurements in the current bucket'''
        the_meas = []
        cli = self.client.query_api()
        if self._db_ok:
            meas_tab = cli.query(self.q_meas_list, org=self.if2org)
            for table in meas_tab:
                for r in table.records:
                    m = r.get_value()
                    if m:
                        the_meas.append(m)
        else:
            print("[W] did not attempt query, db has not responded to pings")
        return the_meas

    def ping(self, maxcount: int = 3, timeout: int =3):
        db_ok = wait_for_engine(
            self.ifhost, self.ifport, maxcount=maxcount, timeout=timeout)
        return db_ok
    # }}}

    def write_points(self, points:List[dict], verb:bool=False) -> bool:
        '''write a list of dict points to DB'''
        # first convert
        pp = [Point.from_dict(point, write_precision=self.write_precision) for point in points]
        if verb:
            p = pp[0]
            msg = f"{p.to_line_protocol()}"
            print("DBG|" + msg)
        # and now write them, return success boolean
        return self._write_points(pp, verb=verb)

    def write_linepoints(self, points:List[str], verb:bool=False) -> bool:
        '''write a list of line protocol points to DB'''
        if verb:
            print(f"DBG|{points[0]}")
        # nothing to do, just pass on the data to the internal wrapper
        return self._write_points(points, verb=verb)


    def _write_points(self, points:List[str], verb:bool=False) -> bool:
        """Thin wrapper for point injection with influxDB2 client.

        Ensures client is available.
        returns True if successfully transmitted
        """
        if not self._connected_db:
            rc = self.attach_client()
            if rc is False:
                return False

        # Annoyingly we can't access the return code unless it is bad, but
        # a successful synchronous write returns http-204 No Content.
        # docs.influxdata.com/influxdb/v1.8/guides/write_data/#http-response-summary

        # Write - see issue 279 re: write_api
        rv = False
        try:
            self.write_api.write(self.if2bucket, self.if2org, points, write_precision=self.write_precision)
            #self.write_api.write(self.if2bucket, self.if2org, points, 's')
            
            rv = True
        except ApiException as e:
            # Missing credentials
            if e.status == 401:
                emsg = f"bad credentials for db {self.if2bucket}!"
                raise DBBadCredentials(emsg) from e
            # Badly formatted
            if e.status == 400:
                message = json.loads(e.body)['message']
                raise DBBadFormatWrite(f"Badly formatted: '{message}'.") from e

            # Other exceptions - give some debug at least
            emsg = f"Could not write {len(points)} points {points[0]}"  # noqa: E501
            raise DBFailedWrite(emsg) from e
        except urllib3.exceptions.TimeoutError as e:
            raise DBTimedoutOnWrite("http timeout :(") from e

        return rv

# it turns out there is only one method from ABCBase that is used:
# deps = [ABCBase.timestamp4db, ] 

class DBInjector(ABCBase, BaseDBInjector):
    '''
    A class providing influxDB database interaction and point preparation 
    for broodnest modules, loading and setting metadata for the tags, and
    appropriate date/time construction. 

    '''

    # {{{ initialisers
    def __init__(self, credfile:Union[str, Path], start_connected:bool=False, **kwargs):
        # explicitly call the base class initialisers
        # ABCBase.__init__(self, **kwargs) #-- in fact we don't need this init
        BaseDBInjector.__init__(self,
            credfile=credfile, start_connected=start_connected, **kwargs)

        self.read_abc_metadata_from_cfg()
        self.populate_metadata()


    def read_abc_metadata_from_cfg(self):
        cfg = ConfigParser()
        cfg.read(self.credfile)

        # Note: *sec [InfluxDB]* is read by base class `BaseDBInjector`

        sec = "Metadata"
        for prop in ["geo_loc", "phys_loc", "inhive_loc"]:
            setattr(self, prop, cfg.get(sec, prop))

        sec = "Host"
        manual_hostname = cfg.getboolean(sec, "override_host")
        if manual_hostname:
            self.hostname = cfg.get(sec, "hostname")
        else:
            # NOTE: Want machine name, no need for fqdn (fully qualified)
            self.hostname = platform.node()

        self.parse_hostname()

    def populate_metadata(self):
        """Fill the tags dict to put with all measurements."""
        # Note: some of these properties (tags) should be populated
        # from the ABC side, via the set_meta_* methods.

        self.metadata = {
            "serial_id": 0,
            "board_id": "0",
            "inhive_loc": self.inhive_loc,
            "geo_loc": self.geo_loc,
            "mcu_uuid": 0,
            "hive_num": self.hive_num,
            "rpi_num": self.rpi_num,
        }

    def set_meta_uuid(self, uuid:int):
        '''supply the UUID from the MCU (a 96-bit int)'''
        self.metadata["mcu_uuid"] = uuid

    def set_meta_serial(self, sid:Union[int, str]):
        ''' supply the USB serial device identifier, e.g. N03'''
        self.metadata["serial_id"] = sid

    def set_meta_board(self, board_id:str):
        ''' supply the board ID, e.g. abc03'''
        self.metadata["board_id"] = board_id

   # }}}



    # {{{ prepare points to inject
    def prep_point_rht(self, rht_dict:dict) -> dict:
        return self._prep_point_from_dict(rht_dict, meas='rht')

    def prep_point_pwr(self, pwr_dict:dict) -> dict:
        return self._prep_point_from_dict(pwr_dict, meas='pwr')

    def prep_point_co2(self, co2_dict:dict) -> dict:
        return self._prep_point_from_dict(co2_dict, meas='co2')

    def prep_point_temp(self, temp_dict:dict) -> dict:
        return self._prep_point_from_dict(temp_dict, meas='tmp')

    def prep_point_htr(self, heat_dict:dict):
        raise DeprecationWarning('Use prep_htr_pointlist instead.')
        return self._prep_point_from_dict(heat_dict, meas='htr')

    def prep_htr_pointlist(self, heat_dict:dict, n_htrs:int=10) -> List[dict]:
        ''' generate list of 10 point dicts, one per actuator
         
        input: dict with 50 elements of data plus some metadata, where the 
        keys have field x instance encoded.

        output: list of 10 x 5-field points, with all entries ready for influxDB 
        (measurement, tags, fields timestamp)
          
        '''

        meas = "htr"

        # assuming 10 heaters, with the labels h00_ to h09_
        _fields = ['obj', 'status', 'avg_temp', 'pwm', 'is_active']
        _h_lbls = [f'h{h:02d}' for h in range(n_htrs)]

        DP = []
        t_data = heat_dict.get("time")
        timestamp = self.timestamp4db(t_data)

        for i, h in enumerate(_h_lbls):
            fields = {}
            for f in _fields:
                col = f"{h}_{f}"
                try:
                    fields[f] = heat_dict[col] # row.get(col)
                except KeyError:
                    print(f"[W] no data for htr {h} field {f}")

            tag_dict = {**self.metadata, "actuator_instance":h}  
            dp = {"measurement": meas, "tags": tag_dict, "fields": fields, "time": timestamp}
            DP.append(dp)

        return DP

    def _prep_point_from_dict(self, data_dict:dict, meas:str, debug:bool=False) -> dict:
        '''
        provide a dictionary that includes
        - data fields
        - datetime timestamp (field "time")
        - valid flag (field "valid")

        and this generates a point in consistent format
        '''
        # Extract the data as the measurment part
        fields = {
            k: v for k, v in data_dict.items() if k not in ["valid", "time"]
        }
        t_data = data_dict.get("time")

        tags_from_data = {"valid": data_dict.get("valid")}
        # TODO: qc flags here too
        tag_dict = {**self.metadata, **tags_from_data}

        point = {
            "time": self.timestamp4db(t_data),
            "tags": tag_dict,
            "measurement": meas,
            "fields": fields,
        }
        if debug:
            print(f"DBG|{point}")

        return point

    # }}}

    def dump_point(self, point:dict) -> str:
        """Convert a point-dict to (the influxDB-native) line format.

        The point dictionary should be in JSON format.
        """
        pt = Point.from_dict(point, write_precision=self.write_precision)
        return pt.to_line_protocol() + "\n"


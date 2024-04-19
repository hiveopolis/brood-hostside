from typing import Union, Tuple
from configparser import ConfigParser
from pathlib import Path
from datetime import datetime, timedelta, timezone
import time
import signal
import re
import inspect
import shutil
import json

from serial.tools import list_ports
import numpy as np

#import brood_hostside.libdb as libdb
from brood_hostside import libdb
from brood_hostside.libbase import ABCBase, BackoffCtr
from brood_hostside.liblog import ABCLogger, get_heater_field_keys

from .src import pyboard

# TODO: On write fails, we currently just add a log line. The goal
#       should be to buffer failed writes to file, and periodically
#       try to inject them later on. (The later injection can be
#       independent from this runtime tool.)

HEADER = '\033[95m'
ENDC = '\033[0m'

DBG_GC = False

# {{{ general housekeeping
class ABCBaseError(Exception):                  # noqa: E302
    ''' base class for errors 
    
    '''
    pass
class ABCTooShortRespError(ABCBaseError):       # noqa: E302
    '''
    response length was shorter than expected

    '''
    pass
class ABCGarbledRespError(ABCBaseError):        # noqa: E302
    '''
    response included unexpected elements
    - garbage collection responses
    - ...

    '''
    pass

class PyboardError(Exception):                  # noqa: E302
    pass
class TimedOutException(Exception):             # noqa: E302
    pass


def handler(signum, _):
    raise TimedOutException("0000000000 | ERR: timeout!")


def func_timeout(times=0):
    def decorator(func):
        if not times:
            return func

        def wraps(*args, **kwargs):
            signal.alarm(times)
            result = func(*args, **kwargs)
            signal.alarm(0)
            return result

        return wraps

    return decorator


signal.signal(signal.SIGALRM, handler)

def _parse_valid(m, ix=-1):
    ''' from a string element (expected last), boolean in text, return a
    true boolean variable. '''
    _v = m[-1].strip(',')
    if _v == "False":
        valid = False
    elif _v == "True":
        valid = True
    else:
        valid = None
    return valid


def fmt_dict_w_date(d, _date, valid) -> str:
    _all = [_date] + list(d.values()) + [int(valid)]
    return ", ".join([str(e) for e in _all])

# }}}


# {{{ specific parser functions
def parse_pwr(m):
    '''
    data comes from `get_power_ui()`

    ```
    timestamp, volt, shuntvm, amps, power, bool(valid)
    date, time,
    (2021, 6, 19),(15, 49, 31)
    12.0 [bus V]
    0.0005549999 [shunt V]
    0.05548096  [current, amps]
    0.6660461 [power, W]
    True [valid, boolean]
    ```

    '''
    P = np.array([float(x.rstrip(',')) for x in m[1:5]])
    p_d = {
        'voltage': P[0],
        'shunt_voltage': P[1],
        'current': P[2],
        'power': P[3]
    }
    return p_d


def parse_co2(m):
    '''
    date comes from s.get_co2_rht
    timestamp, rh, co2ppm, tmp, valid
    '''
    P = np.array([float(x.rstrip(',')) for x in m[1:4]])
    co2_d = {
        'temperature': P[2],
        'rel_humid': P[0],
        'co2': P[1],
    }

    return co2_d


def parse_rht(m, numeric_only=True):
    '''
    date comes from s.get_rht
    ts, _conv_rh(rh), _conv_temp(t), _get_mode(mode), bool(valid)
    '''
    P = np.array([float(x.rstrip(',')) for x in m[1:3]])
    rh_d = {
        'temperature': P[1],
        'rel_humid': P[0],
    }

    if not numeric_only:
        mode = m[3].strip(',')
        rh_d['mode'] = mode

    return rh_d
# }}}


class HtrReadings:
    ''' simple container for the multi-dimensional heater data'''
    def __init__(self):
        self.up_to_date = None
        self.clear()

    def clear(self):
        ''' clear the values from all subfields '''
        self.h_avg_temp = None
        self.h_obj      = None
        self.h_pwm      = None
        self.h_on       = None
        self.h_status   = None
        self.timestamp = None
        self.up_to_date = False

    def update(self, data:list, timestamp:datetime) -> None:
        [h_obj, h_status, h_avg_temp, h_pwm, h_on] = data
        
        self.h_avg_temp = h_avg_temp
        self.h_obj      = h_obj
        self.h_pwm      = h_pwm
        self.h_on       = h_on
        self.h_status   = h_status

        self.timestamp = timestamp
        self.up_to_date = True


# {{{ ABCHandle - interacts with brood nest board
class ABCHandle(ABCBase):
    """Host-side interaction handle for a brood nest board.

    Supply the config file name to load settings.
    """
    # {{{ class variables (mainly constant-like things)
    # CONSTS
    NUM_T_SENSORS = 64
    NUM_HEATERS   = 10  # noqa: E221

    _HTR_IDX_INVALID = -98
    _GET_HTR_STATUS_FAILED = -99

    temperature_field_keys = [f"t{i:02d}" for i in range(NUM_T_SENSORS)]
    heater_field_keys = get_heater_field_keys(NUM_HEATERS)
    # }}}

    # {{{ initialisation
    def __init__(self, cfgfile, **kwargs):
        super().__init__(**kwargs)

        self._cfgfile = Path(cfgfile).expanduser()  # accepts str or Path obj


        # Initialize variables
        self.upy_status = False
        self.heaters_status = False
        self.i = 0
        self.t_idle = 0
        self.cnt_errors = 0
        self.cnt_caught_exceptions = 0
        self.cnt_toolong_loops = 0
        self.cnt_dumped_points = 0

        self._pyb: pyboard.Pyboard = None

        # Values that should be fetched from the pcb side
        self._uuid = 0
        self._board_id = "0"
        self._serial_id = 0
        self._sensor_periods: dict = {}
        self.read_cfg()
        self.logger = ABCLogger(self._cfgfile)
        # Log the config we are running with
        self.log(f"Config file loaded: {str(self._cfgfile)}", level='INI')
        self.archive_cfg()

        self.t_start_iter = self.utcnow()
        self.t_init       = self.utcnow()  # noqa: E221
        self.dt_today = self.get_dt_day(self.utcnow()) # get date for rolling log files
        self.t_end = self.t_init + self.td_loop_delay # we do this here as a failsafe

        if self.log2db:
            self.db_handle = libdb.DBInjector(credfile=self._cfgfile)
            self.db_handle.attach_client()
            mm = self.db_handle.get_measurements()
            msg = (f"Checking bucket '{self.db_handle.if2bucket}'. "
                   f"{len(mm)} measurements: {mm}")
            self.log(msg, level="INI")
            self.init_needs_action_file()
        else:
            self.db_handle = None

        # Debugging values to be filled by interaction with ABC side
        self._last_pyb_resp = ""
        self._last_pyb_fields = []
        self._last_pyb_ntries = -1
        self._pyb_cmd_cnt = 0
        self._mem_usage = {'free': 0, 'alloc': 0, 'total': 0, 'pct': 100.0}

        # lists of the data fetched from each sensor type 
        self.last_pwr_list = None
        self.last_tmp_list = None  
        self.last_rht_list = None
        self.last_co2_list = None
        self.last_htr_list = None 
        # and more complex data structures for external access 
        # (note: only those with a need have been implemented & instantiated)
        self.last_pwr_dict = None
        self.last_htr_data = HtrReadings()

        # Flags to write data or not
        self._newdata2csv_pwr = False
        self._newdata2csv_tmp = False
        self._newdata2csv_rht = False
        self._newdata2csv_co2 = False
        self._newdata2csv_htr = False

        # Ctrs to ignore too many repeated warnings (min: hourly by default)
        self._cntr_wrn_pwr = BackoffCtr()
        self._cntr_wrn_tmp = BackoffCtr()
        self._cntr_wrn_rht = BackoffCtr()
        self._cntr_wrn_co2 = BackoffCtr()
        self._cntr_wrn_htr = BackoffCtr()
    
    def archive_cfg(self):
        ''' archive the config of the present run to log directory'''
        # basic implementation: just copy cfgfile with datestamp
        # advanced: also generate a file with some other metadata, e.g. cmdline args, user, git status.
        # form of config file: in frequent usage we have <hostname>.cfg (esp using -a flag)
        #   but for special cases, e.g. closedloop setups, development, etc, they deviate. 
        # so here let's ensure we are doing something manageable
        self.log(f"Repo info: {self.git_info_str()}")

        if self._cfgfile.stem == self.hostname:
            tgt_stem = self._cfgfile.stem
        else:
            tgt_stem = f"{self.hostname}_ran_{self._cfgfile.stem}"

        #_fmt = "%Y%m%d-%H%M%S"
        _fmt = "%Y%m%d-%Hh"
        start_str = self.utcnow().strftime(_fmt)
        ext = self._cfgfile.suffix # includes the "."
        f_tgt = self.logger.logroot / f"{tgt_stem}-{start_str}{ext}"
        dst = self.safename(f_tgt, p_type='file')

        OKCYAN =  '\033[96m'

        self.log(OKCYAN + f"[DEV] for file {self._cfgfile.stem} will archive at {dst}" +ENDC)
        src = self._cfgfile
        try:
            # Copy file to NAS
            result = Path(shutil.copy2(src, dst))
            print(result)
            result.touch() # give the cfg file a timestamp matching runtime
        except Exception as err:
            self.log(f"Archiving cfg '{src.name}' failed with "
                        f"'{repr(err)}'.", level='ERR')
            return None
        




        pass

    def prepare_heaters(self, activate_any:bool=False):
        ''' prepare the heaters to be used in current session

        prepare the 'base state':
        - disable each individual heater
        - set each individual objective to `heater_def_tmp` (typically 0'C)
        - enable the global heater thread

        if `activate_any` is set:
        - for each entry in `self.activate_heaters`, 
           - set objective 
           - activate that heater
        
        '''
        # Enable heaters
        self.heaters_ini()
        # Set heaters' default temperature
        #for i in range(self.NUM_HEATERS):
        #    self.set_heater_objective(i, self.heater_def_tmp)
        #    time.sleep(0.5)
        self.reset_htr_objectives()

        # readback status
        # [NOTE: probably too soon, the state is not propagated immediately] 
        self.log(self.get_heaters_active(), level='DBG')
        self.log(self.get_heaters_avg_temp(), level='DBG')
        self.log(self.get_heaters_objective(), level='DBG')
        # set specific objectives and activate, if defined in cfg file
        if activate_any:
            self._activate_dict_of_heaters(self.active_heaters)

    def _activate_dict_of_heaters(self, activation_dict:dict):
        """Turn on heaters to temperatures specified in `activation_dict`.
        
        format: {heater_i:int => objective_i:float, ... }
        """
        for hi in activation_dict:
            # Set target temperature
            self.set_heater_objective(hi, activation_dict[hi])
            # Activate heater
            rv = self.set_heater_active(True, hi)
            if rv:
                self.log(f"Heater {hi} activated.")
            else:
                self.log(f"Heater {hi} activation requested but failed",
                         level='WRN')

        self.log(self.get_heaters_active(), level='DBG')
        self.log(self.get_heaters_avg_temp(), level='DBG')
        self.log(self.get_heaters_objective(), level='DBG')

    def read_cfg(self):
        """Read configuration for connection and logging."""
        cfg = ConfigParser()
        cfg.read(self._cfgfile)  # _cfgfile is a canonical path
        sec = 'robot'
        self.addr = cfg.get(sec, 'addr')
        self._board_id = self.parse_boardname(self.addr)
        self.baud = cfg.get(sec, 'baud')
        self.tol_clockdrift_s = cfg.getfloat(sec, 'tol_clockdrift_s', fallback=1.2)
        # self.td_tol_clockdrift = timedelta(seconds=self.tol_clockdrift_s)
        self.loop_delay_s = cfg.getint(sec, 'loop_delay_s')
        self.td_loop_delay = timedelta(seconds=self.loop_delay_s)
        self.sample_co2 = cfg.getboolean(sec, 'sample_co2')
        self.sample_pwr = cfg.getboolean(sec, 'sample_pwr')
        self.sample_rht = cfg.getboolean(sec, 'sample_rht')
        self.sample_tmp = cfg.getboolean(sec, 'sample_tmp')
        self.sample_htr = cfg.getboolean(sec, 'sample_htr')

        # Heater config
        self.heater_def_tmp = cfg.getint(sec, 'heater_def_tmp', fallback=0)
        active_str = cfg.get(sec, 'heaters_active')
        target_tmp_str = cfg.get(sec, 'heater_targets')
        active_heaters = [int(hi) for hi in active_str.split()]
        target_tmps = [float(ti) for ti in target_tmp_str.split()]
        if len(active_heaters) == len(target_tmps):
            htr_dict = dict(zip(active_heaters, target_tmps))
        else:
            # TODO: Use a custom-made error class CfgError
            raise ValueError("CfgError: Different number of `active_heaters` "
                             "and `target_tmps`!")
        self.active_heaters = htr_dict

        sec = 'logging'
        self.verb_debug = cfg.getboolean(sec, 'verb_debug')
        self.log2db     = cfg.getboolean(sec, 'log2db')  # noqa: E221
        self.debug2file = cfg.getboolean(sec, 'debug2file')

        sec = 'InfluxDB'
        self.still_to_inject_path = Path(
            cfg.get(sec, 'still_to_inject_dir')).expanduser()

    def reinit(self):
        # setup new logfiles
        m_reason = "Connection continuing, reinit logfiles due to day rollover"
        self.logger.reinit(m_reason)
        self.init_needs_action_file('reinit due to day rollover|')

        # add base info into new (main) log
        self.log(f"Repo info: {self.git_info_str()}")
        # Add MCU info to new logfile (is there any chance we don't know yet?)
        if self._uuid == 0:
            self.get_mcu_id()  # method gets and logs it
        else:
            # we already know, log it here
            msg = f" MCU UUID {self._uuid} (0x{self._uuid:x})"
            self.log(msg, level='INI')
        # add usb properties to logfile
        self.get_usb_props()

        # also log the config we are running with
        self.log(f"cfgfile loaded: {str(self._cfgfile)}", level='INI')


    def init_needs_action_file(self, create_prefix:str=""):
        if not self.log2db:
            # Nothing to do
            return True

        # Make sure logfolder exists
        path_to_inject = self.still_to_inject_path  # / self.board_id

        if not path_to_inject.is_dir():
            if path_to_inject.exists():  # it is a file already, give up
                raise FileExistsError(
                    f"[F] path_to_inject '{path_to_inject}' is a file!"
                )
            try:
                path_to_inject.mkdir(parents=True)
            except PermissionError as err:
                print(f"[F] user not permitted to write to {path_to_inject}!")
                raise(err)

            msg = f"Created path for files to inject '{path_to_inject}'."
            self.log(msg)

        # Set up filename for not-yet-injected data
        daystr = self.utcnow().strftime(self._fmt_day)
        prefix = self._board_id
        ext = "lineprotocol"
        self.to_inject_file = path_to_inject / f"{prefix}_missing_data_{daystr}.{ext}"
        msg = (f"[I]{create_prefix} 'leftover data' (not yet injected do DB) "
               f"will be written to file '{self.to_inject_file}'.")
        self.log(msg)
    # }}}

    # {{{ helper functions
    def log(self, msg="", level='INF'):
        self.logger.logline(msg, level)

    def log_listdata(self, lst, field, add_date=True):
        if lst is not None:
            self.logger.logdatalst(lst, field, add_date=add_date)
        else:
            self.log(
                f"attempted logging None for field {field}. skipped.",
                level="ERR")

    def uptime(self):
        """Generate string report of uptime."""
        dt_now = self.utcnow()
        elap = dt_now - self.t_init
        days, secs = elap.days, elap.seconds
        hours, rem = divmod(secs, 3600)
        minutes, seconds = divmod(rem, 60)

        s = "up for "
        cont = False
        if days > 0:
            s += f"{days:03d}d"
            cont = True

        if cont or hours > 0:
            s += f"{hours:02d}h"
            cont = True

        if cont or minutes > 0:
            s += f"{minutes:02d}m"

        s += f"{seconds:02d}s"

        return s
    # }}}

    # {{{ open connection and also log a bit more info
    def first_conn(self):
        """Collect status after connection."""
        #
        self.get_mcu_id()
        msg = f" MCU UUID {self._uuid} (0x{self._uuid:x})"
        self.log(msg, level='INI')
        _interval_info = self.get_sensor_interval()
        msg = f" Sensor sampling interval: {_interval_info}"
        self.log(msg, level='INI')

        self.get_usb_props()
        self.log(f"ABC device |board_id|{self._board_id}")

        if self.log2db:
            # add some metadata (tags) to be sent to the DB
            self.db_handle.set_meta_uuid(uuid=self._uuid)
            self.db_handle.set_meta_serial(sid=self._serial_id)
            self.db_handle.set_meta_board(board_id=self._board_id)


    def get_usb_props(self):
        '''grab and log properties from the USB serial interface'''
        v_id, p_id = 0x1d50, 0x6018
        comports = list_ports.comports()
        pvs = [(p.vid, p.pid) for p in comports]
        if not (v_id, p_id) in pvs:
            msg = "Somehow we are running but no ABC MCU can be found"
            self.log(msg, level='WRN')
            return False
            
        ix = pvs.index((v_id, p_id))
        abc_port = comports[ix]
        keyprops = ['serial_number', 'name', 'location', ]
        for prop in keyprops:
            val = getattr(abc_port, prop)
            self.log(f"ABC device |{prop}|{val}")
        
        # we know the USB serial is a composed string, let's parse it a bit.
        # example: 'SER BroodFW-revA2-N11'
        # - we can drop the first 2 elements, just keep rev and serial number.
        sn = abc_port.serial_number.split()[-1]
        self._serial_id = "-".join(sn.replace(' ', '-').split('-')[2:])

        return True
        


    def check_newday_and_roll_logfiles(self):
        ''' roll over logfiles on first sample of new day.  '''
        dt_maybe_tomorrow = self.get_dt_day(self.utcnow())

        if self.dt_today < dt_maybe_tomorrow:
            self.dt_today = dt_maybe_tomorrow
            self.reinit()
            return True
        return False

    # }}}

    # {{{ wrappers to sensor sampling
    '''
    the main loop was a bit too messy to follow the logic simply, so here we
    wrap all the logic for each sensor into one method. Each one
    - interrogates ABC for response data
    - interprets the string accordingly
    - logs the response
    - pushes a data point to the database

    '''
    def sample_temp_sensors(self):
        """Top level wrapper to get temp data from MCU, logging to file + DB"""
        # Get 64 temp vals, and convert
        t_date, t_vals, valid = self.get_int_temperatures()
        # Some massaging to print np array as a csv list, no [] enclosing it.
        #msg = "{}|{}, {}, {}".format(
        #    "tmp", t_date, ", ".join(map(lambda t: f"{t:.1f}", t_vals.tolist())), int(valid))
 
        if DBG_GC: # simplify / shorten output (to focus on the GC debug output)
            msg = "{}|{}, min: {}, mean: {}, max: {} valid: {}".format(
                "tmp", t_date, t_vals.min(), t_vals.mean(), t_vals.max(), str(valid))
        else:
            msg = "{}|{}, {}, {}".format(
                "tmp", t_date, ", ".join(map(lambda t: f"{t:.1f}", t_vals.tolist())), int(valid))

        self.log(msg, level='SNR')
        t_vals[np.where(np.isnan(t_vals))] = -273.0

        thetemps = dict(zip(self.temperature_field_keys, t_vals))
        temp_dict = {"time": t_date, "valid": valid, **thetemps}

        if self.log2db:
            _pt = self.db_handle.prep_point_temp(temp_dict)
            try:
                rv = self.db_handle.write_points([_pt])
            except libdb.DBBaseError as err:
                # Write failed - log and continue
                msg = ("ERR|tmp|failed to inject data. cnt: "
                       f"({self.cnt_dumped_points+1}). "
                       f"Exception - {str(err)}")
                rv = False
                self.log(msg, level='DBE')
                # Wasn't injected, put into the excess file for injecting later

            if not rv:
                self.dump_point_to_file(_pt)

            msg = "{}|{}|{}|mnT={:.2f}|mxT={:.1f}".format(
                "dbItmp", rv, str(t_date), t_vals.mean(), t_vals.max())
            # msg = ( f"{'dbItmp'}|{rv}|{str(t_date)}|"
            #     f"mnT={t_vals.mean():.2f}|mxT={t_vals.max():.1f}")
            self.log(msg, level='DBI')

        if self._newdata2csv_tmp:
            self.log_listdata(t_vals.tolist(), field="tmp", add_date=True)
            self._newdata2csv_tmp = False
            self._cntr_wrn_tmp.hitok()
        else:
            msg = (f"TMP| read unsuccessful ({self._cntr_wrn_tmp._n} similar"
                   "suppressed). No entries to csv or DB")
            doprint = self._cntr_wrn_tmp.hitwarn()
            if doprint:
                self.log(msg, level='WRN')



    def sample_pwr_sensors(self):
        pwr_d_str, pwr_dict = self.get_power_str()
        # msg = "{}|{}".format("pwr", str(pwr_d_str))
        msg = f"{'pwr'}|{str(pwr_d_str)}"
        self.log(msg, level='SNR')
        # Have power data, now inject into db
        if self.log2db:
            _pt = self.db_handle.prep_point_pwr(pwr_dict)
            try:
                rv = self.db_handle.write_points([_pt])
            except libdb.DBBaseError as err:
                # Write failed - log and continue
                msg = ("ERR|pwr|failed to inject data. cnt: "
                       f"({self.cnt_dumped_points+1}). "
                       f"Exception - {str(err)}")
                rv = False
                self.log(msg, level='DBE')

            if not rv:
                self.dump_point_to_file(_pt)

            # msg = "{}|{}|{}".format("dbIpwr", rv, str(pwr_d_str))
            msg = f"{'dbIpwr'}|{rv}|{str(pwr_d_str)}"
            self.log(msg, level='DBI')

        if self._newdata2csv_pwr:
            self.last_pwr_dict = pwr_dict.copy()
            self.log_listdata(self.last_pwr_list, field="pwr", add_date=False)
            self._newdata2csv_pwr = False
            self._cntr_wrn_pwr.hitok()
        else:
            msg = (f"PWR| read unsuccessful ({self._cntr_wrn_tmp._n} similar"
                   "suppressed). No entries to csv or DB")
            doprint = self._cntr_wrn_pwr.hitwarn()
            if doprint:
                self.log(msg, level='WRN')

    def sample_rht_sensors(self):
        rht_d_str, rht_dict = self.get_rht_str()
        if rht_d_str is not None:
            # msg = "{}|{}".format("rht", str(rht_d_str))
            msg = f"{'rht'}|{str(rht_d_str)}"
            self.log(msg, level='SNR')
            if self.log2db:
                _pt = self.db_handle.prep_point_rht(rht_dict)
                try:
                    rv = self.db_handle.write_points([_pt])
                except libdb.DBBaseError as err:
                    # Write failed - log and continue
                    msg = ("ERR|rht|failed to inject data. cnt: "
                           f"({self.cnt_dumped_points+1}). "
                           f"Exception - {str(err)}")

                    rv = False
                    self.log(msg, level='DBE')

                if not rv:
                    self.dump_point_to_file(_pt)

                # msg = "{}|{}|{}".format("dbIrht", rv, str(rht_d_str))
                msg = f"{'dbIrht'}|{rv}|{str(rht_d_str)}"
                self.log(msg, level='DBI')

        if self._newdata2csv_rht:
            self.log_listdata(self.last_rht_list, field="rht", add_date=False)
            self._newdata2csv_rht = False
            self._cntr_wrn_rht.hitok()
        else:
            msg = (f"RHT| read unsuccessful ({self._cntr_wrn_rht._n}) similar"
                   "suppressed). No entries to csv or DB")
            doprint = self._cntr_wrn_rht.hitwarn()
            if doprint:
                self.log(msg, level='WRN')


    def sample_co2_sensors(self):
        co2_d_str, co2_dict = self.get_co2_str()
        # msg = "{}|{}".format("scd", str(co2_d_str))
        msg = f"{'scd'}|{str(co2_d_str)}"
        self.log(msg, level='SNR')

        # TODO: this should also be skipped if the _newdata flag is false (one
        # step at a time)
        if self.log2db:
            _pt = self.db_handle.prep_point_co2(co2_dict)
            try:
                rv = self.db_handle.write_points([_pt])
            except libdb.DBBaseError as err:
                # Write failed - log and continue
                msg = ("ERR|co2|failed to inject data. cnt: "
                       f"({self.cnt_dumped_points+1}). "
                       f"Exception - {str(err)}")
                rv = False
                self.log(msg, level='DBE')

            if not rv:
                self.dump_point_to_file(_pt)

            # msg = "{}|{}|{}".format("dbIco2", rv, str(co2_d_str))
            msg = f"{'dbIco2'}|{rv}|{str(co2_d_str)}"
            self.log(msg, level='DBI')

        if self._newdata2csv_co2:
            self.log_listdata(self.last_co2_list, field="co2", add_date=False)
            self._newdata2csv_co2 = False
            self._cntr_wrn_co2.hitok()

        else:
            n = self._cntr_wrn_co2._n
            msg = f"CO2 read tried, valid=False (rpt {n}). Nothing to csv or DB"
            doprint = self._cntr_wrn_co2.hitwarn()
            if doprint:
                self.log(msg, level='WRN')




    def sample_htr_sensors(self):
        """Read heater data.

        Get a heater string and a heater dict,
        log the str, inject the dict, log to CSV
        (by passing str to get_htr_str()).
        """
        timestamp = self.dt_to_unix(self.utcnow())
        h_obj, h_status, h_temp, h_pwm, h_on = self.get_heaters_status()
        # All should be NUM_HEATERS-long numpy arrays
        #
        # h_obj ....... target temperature
        # h_status .... ?? not quite sure, whether heating or not?
        # h_temp ...... average temperature as sensed by the temp-sensors
        # h_pwm ....... how much power the heater is consuming?
        # h_on ........ bool whether heater is set to active in the config

        # TODO: Make sure the CRC stuff is settled.. --> can be removed (2023-08-24)
        # NOTE: RM 2023-08-24 no CRC data emitted from MCU for htrs. Nothing to do

        # Concatenate them to one big list
        # NOTE: This casts all to float!
        # TODO: Rewrite this to keep integers integers in the CSV.
        h_vals = np.hstack((h_obj, h_status, h_temp, h_pwm, h_on))

        # Compose msg to log
        h_str = ", ".join(map(str, h_vals.tolist()))
        msg = f"htr|{timestamp}, {h_str}"
        self.log(msg, level='SNR')

        theheats = dict(zip(self.heater_field_keys, h_vals))
        heat_dict = {"time": timestamp, **theheats}

        if self.log2db:
            # make a point for each heater, containing the 5 subfields
            _pts = self.db_handle.prep_htr_pointlist(heat_dict)
            try:
                rv = self.db_handle.write_points(_pts)
            except libdb.DBBaseError as err:
                # Write failed - log and continue
                err_msg = ("ERR|htr|failed to inject data. cnt: "
                           f"({self.cnt_dumped_points+1}). "
                           f"Exception - {str(err)}")
                rv = False
                self.log(err_msg, level='DBE')
                # Wasn't injected, put into the excess file for injecting later

            if not rv:
                for _pt in _pts:
                    self.dump_point_to_file(_pt)

            msg = "{}|{}|{}|{}".format(
                "dbIhtr", rv, str(timestamp), h_str)
            # msg = ( f"{'dbItmp'}|{rv}|{str(t_date)}|"
            #     f"mnT={t_vals.mean():.2f}|mxT={t_vals.max():.1f}")
            self.log(msg, level='DBI')


        # Log line to CSV
        if self._newdata2csv_htr:
            self.log_listdata(h_vals.tolist(), field="htr", add_date=True)
            self._newdata2csv_htr = False
            self._cntr_wrn_htr.hitok()
        else:
            n = self._cntr_wrn_htr._n
            msg = f"Htr status read unsuccessful (rpt {n}), Nothing to csv or DB"
            doprint = self._cntr_wrn_htr.hitwarn()
            if doprint:
                self.log(msg, level='WRN')

    # }}}

    # {{{ heater functions
    def _ensure_con(self):
        if self.upy_status is False:
            self.upy_ini()

    def _is_valid_heater(self, idx:int) -> bool:
        # TODO: Should this raise an error?
        if idx is None:
            self.log("Heater index 'None' is invalid.",
                     level='ERR')
            return False

        if idx < 0 or idx >= self.NUM_HEATERS:
            self.log(f"Heater index '{idx}' is out of range (0-9).",
                     level='ERR')
            return False
        else:
            return True

    def heaters_ini(self):
        '''
        Put each individual heater to de-activated, and enable the global
        heater thread. --> Heaters will be ready to activate
        '''
        if not self.heaters_status:
            # ini uPy, if needed
            self._ensure_con()

            # we do several interactions here, let's manually clean up memory
            self.check_mem_maybe_gcollect(watermark=50, _cmd='heaters_ini')
            retries = 3

            for i in range(self.NUM_HEATERS):  # Disable heaters individually
                cmd = f"h.activate(False, {i})"
                self.safe_exec_abc(cmd, retries=retries, watermark=None) # since we manually GC above, ignore here
                self.log(f"Heater {i} deactivated.") # TODO: (rmm 14.01) validate the change (read-back here?)
                time.sleep(0.1)

            cmd = "h.activate(True)"
            self.safe_exec_abc(cmd, retries=retries)
            self.log("All heaters enabled. Ready to be activated.")

            self.heaters_status = True


    def get_heaters_status(self):
        """Returns a numpy array of all heaters for each measurement."""
        self._newdata2csv_htr = False
        self.last_htr_data.clear()
        # ini uPy, if needed
        self._ensure_con()

        cmd = 'hf.callformatprint(h.status)'
        minlen, nfields = None, None  # TODO
        _dat = self.safe_exec_abc(cmd, minlen=minlen, nfields=nfields, retries=3)
        _dat = _dat.decode('utf-8').replace('\r\n', ',')

        # TODO: Remove that once it's clear
        #self.log(f"Heater _dat={_dat}", level='DBG')

        # check for GC fail.
        gc_err = "bad heaters_status response (mixed with garbage collector?)"
        if "GC: " in _dat:
            _msg = f"{gc_err} {_dat}"
            self.logger.debuglogline(_msg, 'ERR', func="get_heaters_status")
            raise ABCGarbledRespError("get_heaters_status", _dat)

        # NOTE: Use raw string
        mm = re.findall(r'\$(.+?)\*', _dat)

        # Mean temperature over each heater
        h_avg_temp = mm[0][1:].split(',')
        h_avg_temp = np.array([float(h) for h in h_avg_temp])

        # Check if the number of temp values is correct
        if len(h_avg_temp) != self.NUM_HEATERS:
            msg = (f"Other than {self.NUM_HEATERS} temp values received "
                   f"for heaters (n={len(h_avg_temp)}).")
            self.log(msg, level='ERR')
            return [False, False, False, False, False]

        h_obj = mm[1].split(',')
        h_obj = np.array([float(o) for o in h_obj])

        h_status = mm[2].split(',')
        h_status = np.array([int(s) for s in h_status])

        h_pwm = mm[3].split(',')
        h_pwm = np.array([int(w) for w in h_pwm])

        # Check if the number of statuses is correct
        if len(h_status) != self.NUM_HEATERS:
            msg = (f"Other than {self.NUM_HEATERS} heater statuses "
                   f"received (n={len(h_status)}).")
            self.log(msg, level='ERR')
            # return [False, False, h_avg_temp, False]
            return [False, False, False, False, False]

        # Boolean array of which heater is set active in the config
        h_on = np.array([1 if hi in self.active_heaters else 0
                         for hi in range(self.NUM_HEATERS)])


        # Write these data to member variables 
        self._newdata2csv_htr = True
        self.last_htr_list = [h_obj, h_status, h_avg_temp, h_pwm, h_on]
        # - this is a complex datatype so use a class
        self.last_htr_data.update(self.last_htr_list, timestamp=self.utcnow())
        
        # TODO: Why return them as a list? 
        return self.last_htr_list

    def get_heaters_active(self, _idx:int=None):
        '''return status of heater [idx], or whole vector of 10 status if None'''
        # ini uPy, if needed
        self._ensure_con()

        try:
            status = self.get_heaters_status()[1]
        except ABCGarbledRespError as e:
            _f = 'get_heaters_active'
            _msg = f"GC error (htr stat) in {_f} (_idx:{_idx}). "
            self.logger.debuglogline(_msg, 'ERR', func=_f)
            return self._GET_HTR_STATUS_FAILED

        if _idx is None:
            return status
        elif self._is_valid_heater(_idx):
            return status[_idx]
        else:
            return self._HTR_IDX_INVALID 


    def heater_activate(self, h_idx:int, warn_below_deg:float=None):
        if not self._is_valid_heater(h_idx):
            return False

        if not self.get_heaters_active(h_idx):
            self.set_heater_active(_state=True, _idx=h_idx, warn_below_deg=warn_below_deg )
            return True
        else:
            self.log(f"Heater {h_idx} already activated. "
                     "No action performed.", level='DBG')
            return False

    def heater_deactivate(self, h_idx:int):
        # NOTE: This is not used
        if not self._is_valid_heater(h_idx):
            return False

        if self.get_heaters_active(h_idx) is True:
            # NOTE: This is False, when the heater is not ACTIVELY
            #       heating, i.e. when the target temperature is reached
            #       --> the heater will stay active and heat as soon as
            #           its patch cools down below the target temperature!
            self.set_heater_active(_state=False, _idx=h_idx)
            return True
        else:
            self.log(f"Heater {h_idx} already deactivated. "
                     "No action performed.", level='DBG')
            return False

    def set_heater_active(self, _state:bool, _idx:int, warn_below_deg:float=None, clear_t_obj:bool=True) -> bool:
        '''
        Set the activated/deactivated state of heater `idx` to `_state`.

        emits a warning if an actuator is set to be activated but the objective 
        temperature is too low (skip if `warn_below_deg` is None)

        if setting `_state` to False, also clear the objective by default.

        '''

        # Check if the heater index exists
        if not self._is_valid_heater(_idx):
            return False

        # Initialize heaters, if needed
        # TODO: Is `upy_ini()` enough here?
        if self.heaters_status is False:
            self.heaters_ini()

        # Activate heater
        if _state is True:
            # Desired temperature for that heater is...
            h_t_obj = self.get_heaters_objective(_idx)

            if warn_below_deg is not None:
                # only run these checks if we were asked to verify
                if h_t_obj in [self._HTR_IDX_INVALID, self._GET_HTR_STATUS_FAILED] :
                    self.log(f"Could not assert objective of heater {_idx}.",
                            level='ERR')
                    return False
                elif h_t_obj < warn_below_deg: 
                    self.log(f"Heater {_idx} objective {h_t_obj} < {warn_below_deg:2.f} C!",
                            level='WRN')

            cmd = f"h.activate({_state}, {_idx})"
            self.safe_exec_abc(cmd, retries=3)

            self.log(f"Heater {_idx} was activated (T_obj = {h_t_obj:.1f} C).")

        elif _state is False:
            cmd = f"h.activate({_state}, {_idx})"
            self.safe_exec_abc(cmd, retries=3)
            self.log(f"Heater {_idx} was deactivated.")

            if clear_t_obj:
                cmd = f"h.objective({self.heater_def_tmp}, idx={_idx})"
                self.safe_exec_abc(cmd, retries=3)
                self.log(f"Heater {_idx} objective reset => {self.heater_def_tmp}.")
        return True

    def heaters_deactivate_all(self):
        """Deactivate all heaters (consecutively) & deactivate heater thread.

        !!! The heaters can not be deactivated all at the same time.
        For some reason the simultaneous deactivation is creating a
        current spike, leading to a reboot of the ABC.
        Deactivation should be done one by one.

        All heater objectives are also reset back to default value (normally=0)

        Note: individual heaters' activate/de-activate state persists
        through any global activate/deactivate changes. That is, whether
        the global state is enabled or disabled, the individual state 
        changes can be made. 
        """
        # deactivate each individual actuator
        for i in range(self.NUM_HEATERS):
            self.set_heater_active(False, i, clear_t_obj=False) # clear obj is applied globally after
            time.sleep(0.1)
        
        # clear all of the objectives 
        self.reset_htr_objectives()
        # disable global heater thread
        self.disable_heater_global_thread()

        self.log(f"All heaters deactivated; t_obj => {self.heater_def_tmp}")
    

    def disable_heater_global_thread(self):
        '''turns off the global heater thread. '''
        cmd = "h.activate(False)"
        self.safe_exec_abc(cmd, retries=3)

        self.log("Global heater thread de-activated.")
        self.heaters_status = False



    def reset_htr_objectives(self, t_obj:float=None):
        '''reset all heater objectives to `self.heater_def_tmp`,
         
          override the default (from cfgfile) by setting t_obj
        '''
        if t_obj is None:
            t_obj = self.heater_def_tmp
        cmd = f"h.objective({t_obj}, idx=None)"
        self.safe_exec_abc(cmd, retries=3)


    def get_heaters_objective(self, _idx:int=None) -> Union[float, np.ndarray]:
        '''return objective of heater [idx], or whole vector of 10 status if None'''
        # ini uPy, if needed
        self._ensure_con()

        try:
            obj = self.get_heaters_status()[0]
        except ABCGarbledRespError as e:
            _f = 'get_heaters_objective'
            _msg = f"GC error (htr objs) in {_f} (_idx:{_idx})."
            self.logger.debuglogline(_msg, 'ERR', func=_f)
            return self._GET_HTR_STATUS_FAILED

        if _idx is None: # return entire vector
            return obj
        elif self._is_valid_heater(_idx): # return one T_obj
            return obj[_idx]
        else: # bad index, return error code
            # NOTE: Already logged by self._is_valid_heater(idx)
            return self._HTR_IDX_INVALID

    def set_heater_objective(self, _idx=None, _new_obj=0.0):
        # Check if the heater index exists
        if not self._is_valid_heater(_idx):
            return False

        # Initialize heaters, if needed
        if self.heaters_status is False:
            self.heaters_ini()

        cmd = f"h.objective({_new_obj}, idx={_idx})"
        self.safe_exec_abc(cmd, retries=3)
        self.log(f"Heater {_idx} objective adjusted to {_new_obj:.1f} C).")
        return True

    def get_heaters_avg_temp(self, _idx:int=None):
        # # Initialize uPy, if needed - done inside get_heaters_status

        try:
            tmp = self.get_heaters_status()[2]
        except ABCGarbledRespError as e:
            _f = 'get_heaters_avg_temp'
            _msg = f"GC error (htr temps) in {_f} (_idx:{_idx}). "
            self.logger.debuglogline(_msg, 'ERR', func=_f)
            return self._GET_HTR_STATUS_FAILED 

        if _idx is None:
            return tmp
        elif self._is_valid_heater(_idx):
            return tmp[_idx]
        else:
            return self._HTR_IDX_INVALID

    def get_heaters_pwm(self, _idx=None):
        # # Initialize uPy, if needed - done inside get_heaters_status

        try:
            pwm = self.get_heaters_status()[3]
        except ABCGarbledRespError as e:
            _f = 'get_heaters_pwm'
            _msg = f"GC error (htr pwm) in {_f} (_idx:{_idx}). "
            self.logger.debuglogline(_msg, 'ERR', func=_f)
            return self._GET_HTR_STATUS_FAILED 

        if _idx is None:
            return pwm
        elif self._is_valid_heater(_idx):
            return pwm[_idx]
        else:
            return self._HTR_IDX_INVALID 
    # }}}

    def dump_point_to_file(self, pt:dict):
        self.cnt_dumped_points += 1
        try:
            with open(self.to_inject_file, 'a') as f:
                s = self.db_handle.dump_point(pt)  # with \n
                f.write(s)
        except (OSError, IOError) as err:
            # could not open the file! not totally clear what to do since this
            # is already in a backup mechanism. Add to an in-memory queue and
            # try dumping periodically?
            func_name = inspect.currentframe().f_code.co_name
            msg = (f"[E][{func_name}][1] {self.i} error while trying to write "
                    f"non-injected points to file \nEXC|[{func_name}][2]{err}")
            self.log(msg, level='EXC')
            self.cnt_caught_exceptions += 1

    # --- main loop - one step --- #
    # {{{ main loop

    def loop(self, consume=True):
        """Grab all data from ABC comb.

        If `consume` is true, also consume remaining time in sampling cycle.

        """
        # Timing and info msg at startloop
        self.t_start_iter = self.utcnow()
	# TODO: rmm 18.01 --> flag here to allow the internal timing variant?
        #self.t_end = self.t_start_iter + self.td_loop_delay
        # Iteration info for the user
        print(f"    {self.ftime()} - {self.i}")
        _t_avail = (self.t_end - self.t_start_iter).total_seconds()
        msg = f"[T]{self.i} Avail: {_t_avail:.3f}s | starting at {self.t_start_iter.strftime('%H:%M:%S.%f')}. until {self.t_end.strftime('%H:%M:%S.%z')}."
        self.log(HEADER + "--- " + msg + ENDC)

        # Sample sensors
        snsr_funcs = [self.sample_temp_sensors, self.sample_pwr_sensors,
                      self.sample_rht_sensors, self.sample_co2_sensors,
                      self.sample_htr_sensors]
        # subject to setting in config file
        snsr_sel_flags = [self.sample_tmp, self.sample_pwr,
                          self.sample_rht, self.sample_co2,
                          self.sample_htr]

        for snsr_func, do_snsr in zip(snsr_funcs, snsr_sel_flags):
            if do_snsr:
                try:
                    snsr_func()
                except (ABCTooShortRespError, ABCGarbledRespError) as e:
                    # Accumulate problem count for each type of sensor?
                    # There should be some tolerance, but if n in a row
                    # occur, we could either a) give up on that sensor,
                    # or b) put some refractory period before trying again.
                    # msg = (
                    #     "[I] exception is due to bad read from host, "
                    #     "attempt to continue. "
                    #     f"\nEXC|{self._last_pyb_resp}\nEXC|{e}"
                    # )
                    func_name = inspect.currentframe().f_code.co_name
                    s_func_name = snsr_func.__name__
                    msg = (
                        f"[I][{func_name}][1] [{self.i}] exception due to bad read from host."
                        f"continuing. [func: {s_func_name}]"
                        f"\nEXC|[{func_name}][2]{self._last_pyb_resp} \nEXC|[{func_name}][3]{e}"
                    )
                    self.log(msg, level='EXC')
                    self.cnt_caught_exceptions += 1

        # TODO: Check whether that is useful:
        # # Ensure heater activity as per config?
        # self._activate_dict_of_heaters(self, self.active_heaters)

        # Check clock drift
        self.check_update_datetime()

        if consume:
            self.consume_idle_time()

        self.i += 1

    def consume_idle_time(self):
        """Separate function in case other steps added to the main loop."""
        # Compute time left, and consume the rest of the cycle
        now = self.utcnow()
        t_idle = self.t_end - now
        t_used = (now - self.t_start_iter).total_seconds()
        msg = f"[T]{self.i} finished ({self.uptime()}). Loop used {t_used:.2f}s. remaining: {t_idle}"
        self.log(HEADER + "--- " + msg + ENDC)
        #self.log("--- " + msg)
        if t_idle.total_seconds() < 0:
            msg = f"[W][T]{self.i} took too long! {t_idle.total_seconds():.4f}s negative! Start {self.t_start_iter}|End {self.t_end}|Now: {now}"
            #self.log("---" + msg, level='WRN')
            self.log(HEADER + "--- " + msg + ENDC, level='WRN')
            self.cnt_toolong_loops += 1

        # Be ultra-precise and compute it again
        t_idle = self.t_end - self.utcnow()
        # NOTE: One could store a 'self._td0 = timedelta(seconds=0)'
        #       and test 'if t_idle > self._td0:'
        if t_idle.total_seconds() > 0:
            time.sleep(t_idle.total_seconds())

        self.t_end = self.utcnow() + self.td_loop_delay
        msg = f"[T]{self.i} next loop start at: {self.t_end.strftime('%Y-%m-%dT%H:%M:%S.%fZ')}"
        self.log("--- " + msg, level='DBG')

    def prepare_initial_loop_timer(self, ref:datetime = None):
        '''Define now as the intended reference time for loop time counting

        This method is useful if the ABCHandle instance is expected to be 
        instantiated a significant period before the main loop might start. It
        just sets the next time point, `t_end` for loop(consume=True). '''
        if ref is None:
            self.t_end = self.utcnow() + self.td_loop_delay
        else:
            self.t_end = ref + self.td_loop_delay

    def stop(self, end_msg:str = None):
        # TODO: Turn off heaters here?
        self.upy_end()

        msg = f"{self.uptime()}, {self.i} iterations."
        if self.cnt_caught_exceptions:
            msg += f" caught {self.cnt_caught_exceptions} exceptions."
        if self.cnt_errors:
            msg += f" {self.cnt_errors} errors occurred."
        if self.cnt_toolong_loops:
            msg += f" {self.cnt_toolong_loops} loops did not finish on time."

        if self.cnt_dumped_points:
            msg += f" {self.cnt_dumped_points} points not injected"
            msg += f"& dumped to file {self.to_inject_file}"


        self.log(msg)

        if self.log2db:
            self.db_handle.closedown()

        ts = self.dt_to_unix(self.utcnow())
        print(f"INF|{ts}|logfiles written in {self.logger.path_log}")

        if end_msg is not None:
            self.log(end_msg)

    # }}}

    # --- interactions with the board --- #
    # {{{ open and close connection

    # @classmethod
    @func_timeout(3)
    def upy_ini(self):

        self.log(f"Connecting to the Brood PCB {self.addr}.")

        self._pyb = pyboard.Pyboard(self.addr, baudrate=self.baud)

        # Retry up to 3 times
        for _ in range(3):
            try:
                self._pyb.enter_raw_repl()
                self.log("Connection (repl) ok.")
                self.upy_status = True
                break
            except TimedOutException:
                msg_err = f"Failed to connect to ABC board at addr {self.addr}"

                print(f"[F] {msg_err}. Terminating!")
            except Exception as e:
                print(e)

        # Run all the needed imports for general interaction, and
        # set time to s (defaults to ms) 
        for cmd in ["import sensors as s", "import heaters as h",
                    "import tmp117 as t", "import host_format as hf",
                    "import gc",
                    "s.print_ms(False)"]:
            self.safe_exec_abc(cmd, minlen=0, watermark=None) # can't run watermark check before libs imported...

        self.log("Connection established.")

        return self._pyb

    def upy_end(self):
        if self.upy_status is True:
            self._pyb.exit_raw_repl()
            self._pyb.close()
            self.upy_status = False

    # }}}

    def get_mem_status(self) -> dict:
        '''get the current memory status (allocated, free, total)'''
        cmd = 'print(gc.mem_free(), gc.mem_alloc())'
        #resp = self._pyb.exec(cmd) 
        resp = self.safe_exec_abc(cmd, retries=2, watermark=None, loglvl='CMG') # this doesn't expect GC so we can filter
        _resp = str(resp.decode('utf-8')).rstrip('\r\n')
        elems = _resp.split()
        if not len(elems) == 2:
            raise ABCGarbledRespError(_resp) # quite harsh response?

        ielems = [int(e) for e in elems]
        m = {'free':  ielems[0], 
             'alloc': ielems[1],
             'total': ielems[0]+ielems[1]}
            
        m['pct'] = round(m['alloc'] / float(m['total']) * 100, 2)

        self._mem_usage = m.copy()

        return m
    
    def request_garbage_collection(self, info:str="") -> bytes:
        # NOTE: cannot use safe_abc_exec, not compatible with gc.collect.
        #       we have to use _pyb.exec directly.
        #       we include a minimal parsing and dbg entry, plus cmd log entry
        #       try not to let this get out of sync with `safe_abc_exec`
        cmd = 'gc.collect()'
        self.log(cmd, level='CMD')
        resp = self._pyb.exec(cmd) 
        _resp = str(resp.decode('utf-8')).rstrip('\r\n').replace('\r\n', ' ')
        elems = _resp.split()
        nf = len(elems)
        ml = len(resp)

        if self.debug2file:
            _msg = (f"cmd {cmd} --> {ml:3} bytes | "
                    f"{nf:2} fields |{_resp}")
            self.logger.debuglogline(_msg, 'LOG', func="request_garbage_collection")

        msg = f"{cmd}|{_resp}"
        msg += f"|{self._pyb_cmd_cnt} total cmds"
        if info:
            msg += "|" + info
        self.log(msg, level='GCX')
        return _resp
        
    def check_mem_maybe_gcollect(self, watermark:float=80.0, _cmd:str=None) -> bool:
        '''
        check current memory usage, and if usage is above `watermark`
        then a garbage collection is requested.

        return value: True if collection was done.

        '''
        try:
            m = self.get_mem_status()
        except ABCGarbledRespError as e:
            msg = f"Got garbage collector garbling during 'get_mem_status'. ({_cmd})"
            self.log(msg, level='EXC')
            return False
        
        # default=100 means we trigger the collection even if the getter failed
        pct = m.get('pct', 100.0)
        if pct > watermark: 
            self.request_garbage_collection(info=f'gc requested at {pct:.2f}% (cmd:{_cmd})')
            return True

        return False

    # {{{ exec_abc - thin wrapper around _pyb.exec
    def safe_exec_abc(self, cmd:str, retries:int=1, 
                      minlen:int=None, nfields:int=None,
                      watermark:float=80.0, loglvl:str='CMD'
                      ) -> bytes:
        '''Execute a command on the ABC microcontroller

        - retry on failure (e.g. if garbage collector interrupts response)
            if retries is exceeded, ABCGarbledRespError is raised
        - optionally provide minimum expected response lengths
            if not met, ABCTooShortRespError is raised

        - internally this parses the content for validation, but the 
          returned data is the raw bytestring received from the ABC.

        - if `watermark` is set, this method also checks the
          memory status, and if usage is above watermark, a garbage 
          collection is requested. To unset, define as None.
        
        '''
        n_tries = 0
        data_ok = False
        did_gc = False

        if watermark is not None:
            did_gc = self.check_mem_maybe_gcollect(watermark, _cmd=cmd)

        while n_tries < retries:
            self.log(cmd, level=loglvl)
            resp = self._pyb.exec(cmd) 
            self._pyb_cmd_cnt += 1
            ml = len(resp) # byte count of recieved response
            # decode, clean a bit
            _resp = str(resp.decode('utf-8')).replace('\r\n', ',')
            if not "GC: total" in _resp:
                data_ok = True
                break

            msg = f"try {n_tries:3}/{retries:3} of '{cmd}' -> GC in resp {_resp}"
            msg += f"|{self._pyb_cmd_cnt} total cmds"
            self.log(msg, level='GCI')

            n_tries += 1
        self._last_pyb_ntries = n_tries
        
        if not data_ok:
            msg = f"GC error when trying cmd '{cmd}' (after {n_tries}). resp: {_resp}"
            msg += f"|{self._pyb_cmd_cnt} total cmds"
            self.log(msg, level='GCX')
            raise ABCGarbledRespError(msg) # TODO: could be useful to add inspect info here?
        
        # first level of validation passed OK, let's check length
        ## look for groups contained in $...* tokens
        m = re.findall(r'\$(.+?)\*', _resp)
        nf = len(m)

        self._last_pyb_resp = _resp
        self._last_pyb_fields = m

        if minlen is None:
            leninfo = ""
        else:
            if ml < minlen:
                leninfo = f"(W : <{minlen}!!)"
            else:
                leninfo = f"(OK: >={minlen})"

        if nfields is None:
            nfinfo = ""
        else:
            if nfields != nf:
                nfinfo = f"(W : !={nfields})"
            else:
                nfinfo = f"(OK : =={nfields})"

        if self.debug2file:
            # Dump entire response line to debuf file.
            _msg = (f"cmd {cmd} --> {ml:3} bytes {leninfo}| "
                    f"{nf:2} fields {nfinfo}|{_resp}")
            self.logger.debuglogline(_msg, 'LOG', func="safe_exec_abc")
            pct = self._mem_usage.get('pct', -1)
            #self.log(f"did GC:? {did_gc:6} {pct:.1f}%|" + _msg, level='GCX') # extra just for dev work

        if DBG_GC:
            pct = self._mem_usage.get('pct', -1)
            self.log(f"[{self.i}]|{pct:.2f}% mem|[after {cmd}]", level='GCD')

        if minlen is not None:
            if ml < minlen:
                raise ABCTooShortRespError
        if nfields is not None:
            if nfields != nf:
                raise ABCTooShortRespError

        return resp



    def exec_abc(self, cmd, minlen=None, nfields=None):
        """Use pyb.exec on the MCU side to obtain results.

        Optionally provide min expected response length,
        if not met raises ABCTooShortRespError.
        Log to debug as needed.
        """
        raise DeprecationWarning("[W] use safe_exec_abc instead, with retries and GC handling")
        self.log(cmd, level='CMD')
        resp = self._pyb.exec(cmd)
        ml = len(resp)
        # Decode and parse message to find nfields.
        _resp = str(resp.decode('utf-8')).replace('\r\n', ',')
        m = re.findall(r'\$(.+?)\*', _resp)
        nf = len(m)

        self._last_pyb_resp = _resp
        self._last_pyb_fields = m

        if minlen is None:
            leninfo = ""
        else:
            if ml < minlen:
                leninfo = f"(W : <{minlen}!!)"
            else:
                leninfo = f"(OK: >={minlen})"

        if nfields is None:
            nfinfo = ""
        else:
            if nfields != nf:
                nfinfo = f"(W : !={nfields})"
            else:
                nfinfo = f"(OK : =={nfields})"

        if self.debug2file:
            # Dump entire response line to debuf file.
            _msg = (f"cmd {cmd} --> {ml:3} bytes {leninfo}| "
                    f"{nf:2} fields {nfinfo}|{_resp}")
            self.logger.debuglogline(_msg, 'LOG', func="exec_abc")

        if minlen is not None:
            if ml < minlen:
                raise ABCTooShortRespError
        if nfields is not None:
            if nfields != nf:
                raise ABCTooShortRespError

        return resp
    # }}}

    # {{{ get_mcu_id
    def get_mcu_id(self):
        """Read UUID from MCU."""
        if self.upy_status is False:
            self.upy_ini()

        cmd = 'hf.callformatprint(s.get_mcu_uuid)'
        minlen = 26  # should be at least 26 chars (typically 63)
        _id = self.safe_exec_abc(cmd, minlen=minlen, retries=3)

        if _id is not None:
            _id = str(_id.decode('utf-8')).replace(',', '')
            # NOTE: Use raw string!
            m = re.findall(r'\$(.+?)\*', _id)
            m[0] = m[0].replace('$', '')

            m = [format(int(v, 16), '08b') for v in m]
            self._uuid = int(m[0] + m[1] + m[2], 2)

        return self._uuid
    # }}}

    # {{{ temperature
    def get_temp_offset(self):
        """Get temperature offsets for each of the 64 sensors.

        Returns: List of floats
        """
        if self.upy_status is False:
            self.upy_ini()

        cmd = 'hf.callformatprint(t.offset)'
        minlen = None  # TODO: Should be at least ?? chars (typically ??)
        _dat = self.safe_exec_abc(cmd, minlen=minlen, retries=3)

        _dat = str(_dat.decode('utf-8')).replace(
            '\r\n', ',').replace('$', '').replace('*', '')[:-2].split(',')
        _t_offsets = [float(d) for d in _dat]
        return _t_offsets

    def reset_temp_offsets(self) -> bool:
        """Returns: boolean success status"""
        if self.upy_status is False:
            self.upy_ini()

        cmd = 't.reset_all_offset()'
        minlen = None  # TODO: should be at least ?? chars (typically ??)
        raw = self.safe_exec_abc(cmd, minlen=minlen, retries=3)
        dat = raw.decode('utf-8').rstrip()
        # Expected response: 'Reseting all offsets... OK'
        if "OK" in dat:
            return True
        else:
            return False

    def set_sensor_interval(self, _period_in_s):
        """Set temperature interval."""
        if self.upy_status is False:
            self.upy_ini()

        cmd = f"s.sensors_periods({_period_in_s})"
        self.log(cmd, level='CMD')
        raise NotImplementedError("[E] function changed for rev A2.")
        # _dat = self.exec_abc(cmd, minlen=minlen)

    def get_sensor_interval(self) -> dict:
        """Get interval for sampling each sensor class."""
        if self.upy_status is False:
            self.upy_ini()
        cmd = 'print(s.sensors_periods())'
        #cmd = 'hf.callformatprint(s.sensors_periods)'
        minlen = 45 # at least 45 chars (typically 57)
        raw = self.safe_exec_abc(cmd, minlen=minlen, retries=3)
        resp = raw.decode('utf-8').rstrip().replace("'", '"')
        try:
            periods = json.loads(resp)
        except json.JSONDecodeError as e:
            msg = f"[E] problem converting s.sensors_periods(). Logging raw resp only: '{resp}'"
            self.log(msg, level='EXC')
            return resp
        
        self._sensor_periods = periods
        return periods



    def get_int_temperatures(self):
        """Get temp data from all sensors, using integer values on retrieval.

        This function converts to floats in Celsius.

        Returns: timestamp      (datetime object),
                 temperatures   (np array of floats),
                 valid status   (boolean)
        """
        self._newdata2csv_tmp = False
        # ini uPy, if needed
        if self.upy_status is False:
            self.upy_ini()

        cmd = 'hf.callformatprint(s.get_int_temperature)'
        minlen = 286  # should be at least 286 chars (typically ~470)
        nfields = 3
        _dat = self.safe_exec_abc(cmd, minlen=minlen, nfields=nfields, retries=3)

        _dat = str(_dat.decode('utf-8')).replace('\r\n', ',')[:-1]

        # check for GC fail.
        gc_err = "bad int_temperatures response (mixed with garbage collector?)"
        if "GC: " in _dat:
            _msg = f"{gc_err} {_dat}"
            self.logger.debuglogline(_msg, 'ERR', func="get_int_temperatures")
            raise ABCGarbledRespError("get_int_temperatures", _dat)

        # NOTE: Use raw string
        m = re.findall(r'\$(.+?)\*', _dat)

        # Clean and convert sample date & time
        _t_date = self._clean_datetime(m[0])
        _t_date = self.dt_to_unix(_t_date)

        # Extract sample values
        _t_vals = m[1].split(',')
        _t_vals = np.array([int(v) for v in _t_vals])

        # NOTE in fw rev A2, the crc is checked on the MCU but not sent to the
        # host; we only get the per-sensor sensor status flag.
        # Retain the valid variable for downstream compatibility
        valid = True

        # Convert to float values
        # TODO: Store t_k somewhere more prominently?
        t_k = 0.0078125
        _t_vals = np.array([v*t_k for v in _t_vals])

        # Check if there are 64 temp values
        if len(_t_vals) != self.NUM_T_SENSORS:
            msg = (f"Less than {self.NUM_T_SENSORS} temp values received -> "
                   f"{len(_t_vals)}")
            valid = False
            self.log(msg, level='ERR')

            return [_t_date, False, valid]

        # Check sensor status
        _t_status = m[2].split(',')
        _t_status = np.array([int(s) for s in _t_status])

        # Change to NaN the temperature values: -30 > t > +180
        extreme_idx = np.argwhere(np.logical_or(
                _t_vals < -30.0, _t_vals > 180)
        )
        _t_vals[extreme_idx] = np.nan

        # Change to NaN the temperature values that can't be trusted
        zero_idx = np.argwhere(_t_status == 0)
        _t_vals[zero_idx] = np.nan

        if np.isin(0, _t_status):
            _s = str(zero_idx.squeeze())
            msg = f"Sensor(s) {_s} could not be pooled."
            self.log(msg, level='ERR')

        self.last_tmp_list = _t_vals
        self._newdata2csv_tmp = True

        return [_t_date, _t_vals, valid]

    def get_temperatures(self):
        raise NotImplementedError("[E] use get_int_temperatures() instead.")

    # Heaters
    def get_htr_str(self):
        raise NotImplementedError("[E] use get_heaters_status() instead.")
    # }}}

    # {{{ other sensors
    def get_power_str(self) -> Tuple[str, dict]:
        self._newdata2csv_pwr = False
        if self.upy_status is False:
            self.upy_ini()

        cmd = 'hf.callformatprint(s.get_power_ui)'
        # Should be at least 39 chars (typically 88-92)
        minlen = 39
        nfields = 6
        _dat = self.safe_exec_abc(cmd, minlen=minlen, nfields=nfields, retries=3)

        _dat = str(_dat.decode('utf-8')).replace('\r\n', ',')[:-1]
        gc_err = "Bad pwr response from ABC (mixed with garbage collector?)."
        if "GC: " in _dat:
            _msg = f"{gc_err} {_dat}"
            self.logger.debuglogline(_msg, 'ERR', func="get_power_str")
            raise ABCGarbledRespError("get_power_str", _dat)

        mp = re.findall(r'\$(.+?)\*', _dat)
        p_date = self._clean_datetime(mp[0])
        p_date_str = self.dt_to_isofmt(p_date)
        valid = _parse_valid(mp)
        d_p = parse_pwr(mp)

        p_date = self.dt_to_unix(p_date)

        s = fmt_dict_w_date(d_p, p_date, valid)
        d_p_db = dict({"valid": valid, "time": p_date}, **d_p)

        self._newdata2csv_pwr = True
        self.last_pwr_list = [p_date, p_date_str] + list(d_p.values()) + [int(valid)]  # noqa: E501

        return s, d_p_db

    def get_co2_str(self):
        self._newdata2csv_co2 = False # wipe most recent data
        if self.upy_status is False:
            self.upy_ini()

        cmd = 'hf.callformatprint(s.get_co2_rht)'
        minlen = None  # TODO: Should be at least ?? chars (typically ??)
        nfields = None  # TODO
        _dat = self.safe_exec_abc(cmd, minlen=minlen, nfields=nfields, retries=3)

        # co2_dat = str(co2_dat.decode('utf-8')).replace('\r\n', ',')[:-1]
        _dat = str(_dat.decode('utf-8')).replace('\r\n', ',')[:-1]
        # look for the 'expected' error
        gc_err = "bad scd30 response from ABC (mixed with garbage collector?)."
        if "GC: " in _dat:
            _msg = f"{gc_err} {_dat}"
            self.logger.debuglogline(_msg, 'ERR', func="get_co2_str")
            raise ABCGarbledRespError("get_co2_str", _dat)

        m = re.findall(r'\$(.+?)\*', _dat)
        valid = _parse_valid(m)
        if not valid:
            # Construct return dict with dummy data (sentinel values)
            _date = self.dt_to_unix(self.utcnow())
            d = {'co2': -1, 'temp': -273, 'rh': -1}
            s = fmt_dict_w_date(d, _date, valid)
            d_co2 = dict({"valid": valid, "time": _date}, **d)
            return s, d_co2


        _date = self._clean_datetime(m[0])
        _date_str = self.dt_to_isofmt(_date)

        d = parse_co2(m)
        _date = self.dt_to_unix(_date)

        s = fmt_dict_w_date(d, _date, valid)
        d_co2 = dict({"valid": valid, "time": _date}, **d)
        # successfully read if we got this far, buffer data to be logged
        self._newdata2csv_co2 = True
        self.last_co2_list = [_date, _date_str] + list(d.values()) + [int(valid)]  # noqa: E501
        return s, d_co2

    def get_rht_str(self):
        self._newdata2csv_rht = False
        if self.upy_status is False:
            self.upy_ini()

        cmd = 'hf.callformatprint(s.get_rht)'
        minlen = 44  # Should be at least 44 chars (typically 68-70).
        nfields = 5
        rht_dat_o = self.safe_exec_abc(cmd, minlen=minlen, nfields=nfields, retries=3)
        rx_len = len(rht_dat_o)

        rht_dat = str(rht_dat_o.decode('utf-8')).replace('\r\n', ',')[:-1]
        '''
        INJECT_ERROR = True
        if INJECT_ERROR:
            # Simulate a bad string.
            i1 = rht_dat.find("*")
            if i1 is not -1:
                e0 = rht_dat[0:i1+2]
                e1 = "GC: total: 123,"
                e2 = rht_dat[i1+2:]
                rht_dat = e0 + e1 + e2
                self._last_pyb_resp = rht_dat
        '''

        # TODO: rmm push rht dat and stats into DBG log
        #       Tue 03 Aug 2021 11:11:09 CEST
        if self.debug2file:
            _msg = f"Cmd s.get_rht --> {rx_len} bytes: {rht_dat}"
            self.logger.debuglogline(_msg, 'DBG', func="get_rht_str")

        gc_err = "Bad rht response from ABC (mixed with garbage collector?)."
        if "GC: total" in rht_dat:
            _msg = f"{gc_err} {rht_dat}"
            self.logger.debuglogline(_msg, 'ERR', func="get_rht_str")
            raise ABCGarbledRespError("get_rht_str", rht_dat)

        # NOTE: Use raw string!
        m = re.findall(r'\$(.+?)\*', rht_dat)
        nf = len(m)  # expect 5

        if self.debug2file:
            _msg = f"Cmd re.findall --> {nf} fields: {str(m)}"
            self.logger.debuglogline(_msg, 'DBG', func="get_rht_str")

        if rx_len < minlen or nf < nfields:
            if self.debug2file:
                _msg = f"Bad input from rht ABC side. {rx_len} {nf}"
                self.logger.debuglogline(_msg, 'ERR', func="get_rht_str")

            # data not valid/interesting, don't invoke a log
            self._newdata2csv_rht = False
            return None, None

        else:

            _date = self._clean_datetime(m[0])
            _date_str = self.dt_to_isofmt(_date)
            valid = _parse_valid(m)
            d = parse_rht(m)

            _date = self.dt_to_unix(_date)

            s = fmt_dict_w_date(d, _date, valid)
            d_rht = dict({'valid': valid, 'time': _date}, **d)
            self._newdata2csv_rht = True
            self.last_rht_list = [_date, _date_str] + list(d.values()) + [int(valid)]  # noqa: E501
            return s, d_rht

    # }}}

    # {{{ time-related funcs
    # {{{ get_datetime using strptime parsing
    def get_datetime(self) -> datetime:
        """Parse datetime from ABC timestamp.

        Returns: Datetime object = RTC time

        `bytestring e.g.: b'$$2021,11,5*$17,3,11**\r\n'`
        `decoded ->        '$$2021,11,5*$17,3,11**'`
        """
        if self.upy_status is False:
            self.upy_ini()

        try:
            cmd = 'hf.callformatprint(s.get_datetime)'
            minlen = 19  # should be at least 19 chars (typically 23-26)
            _date_b = self.safe_exec_abc(cmd, minlen=minlen, retries=3)

        except TimedOutException:
            # NOTE: Do sth here?
            return None

        _date = str(_date_b.decode('utf-8')).replace('\r\n', '')
        # self.log(f"Datestring in get_datetime: {_date}", level='DBG')
        gc_err = "Bad get_datetime response from ABC (mixed with garbage collector?)."
        if "GC: total" in _date:
            _msg = f"{gc_err} {_date}"
            self.logger.debuglogline(_msg, 'ERR', func="get_datetime")
            raise ABCGarbledRespError("get_datetime", _date)

        # NOTE: this date format is different than the sensor strings, so
        #       here we use an alternative formatter (_fmt_gdt)
        dt_abc = self._clean_datetime(_date, utc=True, fmt=self._fmt_gdt)

        return dt_abc
    # }}}


    def compare_datetime(self, ):
        """Return time diff between the ABC PCB and the RPi."""
        pcb_time = self.get_datetime()
        rpi_time = self.utcnow()
        if pcb_time is not None:
            _dt = (rpi_time - pcb_time).total_seconds()
            s_rpi = rpi_time.strftime("%H:%M:%S") + f".{rpi_time.microsecond // 1000:03.0f}"
            msg = f"PCB time: {pcb_time} (dt:{_dt:.2f}s). Hosttime: {s_rpi}."
            self.log(msg, level='DBG')
            
            # TODO: Maybe return the timedelta and compare against that?
            return _dt
        else:
            self.log(f"PCB time: {str(pcb_time)}", level='DBG')
            # TODO: Shouldn't this issue a warning?
            return 0

    def check_update_datetime(self):
        """Check clock drift on the ABC and reset if necessary."""
        try:
            delta_t = self.compare_datetime()
            if abs(delta_t) >= self.tol_clockdrift_s:
                # Set date & time
                now = self.utcnow()
                cmd = f's.set_date({now.year:d},{now.month:d},{now.day:d})'
                _ = self.safe_exec_abc(cmd, minlen=0)  # no response expected

                cmd = f's.set_time({now.hour:d},{now.minute:d},{now.second:d})'
                _ = self.safe_exec_abc(cmd, minlen=0)  # no response expected
                msg = (f"Brood RTC adjusted to: {self.get_datetime()} "
                       f"(dif={delta_t:.1f}s)")
                self.log(msg)

            else:
                if self.verb_debug:
                    msg = (f"Brood RTC not adjusted: {self.get_datetime()} "
                           f"(dif={delta_t:.1f}s)")
                    self.log(msg, level='DBG')

        except ABCGarbledRespError as e:
            func_name = inspect.currentframe().f_code.co_name
            msg = (f"[I][{func_name}][1][{self.i}] exception due to GC in `check_update_datetime`. Cont."
                   f"\nEXC|[{func_name}][2]{self._last_pyb_resp} \nEXC|[{func_name}][3]{e}")
            self.log(msg, level='EXC')
            self.cnt_caught_exceptions += 1

    # }}}

# }}}


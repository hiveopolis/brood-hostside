from configparser import ConfigParser
import csv
import getpass
from pathlib import Path
from .libbase import ABCBase

def get_heater_field_keys(n_heaters:int=10) -> list:
    """Generate the header for the heater csv."""
    heater_strs = [f"h{i:02}" for i in range(n_heaters)]
    heater_fields = ['obj', 'status', 'avg_temp', 'pwm', 'is_active']
    heater_header = []

    # Sort first by measurement, then by heater
    for hf in heater_fields:
        for hs in heater_strs:
            heater_header.append(f'{hs}_{hf}')
    return heater_header

# {{{ logger class
class ABCLogger(ABCBase):
    """Logger for broodnest interactions.

    Log files are written to the folder `logroot` (specified in the
    configfile), e.g. "/home/pi/log/abc_logs/" as of writing.

    E.g., on hive5-rpi4, which controls the ABC board 'abc08', today,
    these 7 files are produced upon initialization of an ABCLogger:

        abc08_2021-11-04.dbg
        abc08_2021-11-04.log
        abc08_co2_2021-11-04.csv
        abc08_htr_2021-11-04.csv
        abc08_pwr_2021-11-04.csv
        abc08_rht_2021-11-04.csv
        abc08_tmp_2021-11-04.csv

    If the files exist, they will be appended to; if not, they are
    created. New CSV files are initialized with a header.

    This class is agnostic of rollover-intervals (as of now).

    """

    """
    # TODO: Move this to ABCHandle, where it is actually done!
    This class also creates the folder `needs_action` (as a subfolder
    to `logroot`) to host data that couldn't be injected into the
    InfluxDB during live-mode. Files in that folder are currently
    named `missing_data_<day>` (without suffix) and accumulate there,
    if not manually uploaded (or otherwise handled, e.g. by injecting
    to DB once live again).
    But this is handled by other parts of the code (DBInjector, and
    used in ABCHandle), here only the folder is created, if need be.
    """
    LEVELS_TO_LOGDATA = ['SNR']
    LEVELS_TO_LOG1    = ['INF', 'ERR', 'DBG', 'CMD', 'REP',  # noqa: E221
                         'DBI', 'DBQ', 'DBE', 'WRN', 'EXC', 'INI',
                         'GCX', 'GCD', 'CMG',
                         ]
    LEVELS_SKIP_STDOUT = ['CMG']

    CSV_DTYPES = ['tmp', 'rht', 'co2', 'pwr', 'htr']
    # NOTE: Key values must correspond to the entries in CSV_DTYPES!
    CSV_DICT = {
        'tmp': ['timestamp', 'datetime', *(f't{i:02d}' for i in range(64))],
        'rht': ['timestamp', 'datetime', 'temperature',
                'rel_humidity', 'is_valid'],
        'co2': ['timestamp', 'datetime', 'temperature',
                'rel_humidity', 'co2', 'is_valid'],
        'pwr': ['timestamp', 'datetime', 'voltage', 'shunt_voltage',
                'current', 'power', 'is_valid'],
        'htr': ['timestamp', 'datetime', *(get_heater_field_keys(10))],
    }
    # TODO: Move NUM_T_SENSORS and NUM_HEATERS to ABCBase to access here?

    LOG_SUFFIXES = ['.log', '.dbg']

    CLRS = {
        1: '\033[34m',
        2: '\033[92m',
        3: '\033[95m',
    }
    ENDC = '\033[0m'

    def __init__(self, path_cfg, **kwargs):
        super().__init__(**kwargs)

        # Read config
        if path_cfg is None:
            path_cfg = self.lookfor_cfgfile()
        # Accepts str or Path object:
        self.cfgfile = Path(path_cfg).expanduser()
        #
        if self.cfgfile.is_file():
            self.read_cfg()
        else:
            raise FileNotFoundError(f"No config found at '{self.cfgfile}'!")

        create_msg = self.init_logpath()
        self.init_logfiles(create_msg)
        self.init_csvs()


    def read_cfg(self):
        cfg = ConfigParser()
        cfg.read(self.cfgfile)  # cfgfile is a canonical path
        # Not sure whether we need to use addr or not
        sec = 'robot'
        self._addr = cfg.get(sec, 'addr')
        self.board_id = self.parse_boardname(self._addr)

        sec = 'logging'
        self.verb_debug = cfg.getboolean(sec, 'verb_debug')
        self.debug2file = cfg.getboolean(sec, 'debug2file')
        self.log2stdout = cfg.getboolean(sec, 'LOG_2_STDOUT')
        self.dbg_csv2stdout = cfg.getboolean(sec, 'DBG_ALL_CSVDATA_2_STDOUT', fallback=False)
        self.logroot = Path(cfg.get(sec, 'logroot')).expanduser()
        self.uploadroot = Path(cfg.get(sec, 'uploadroot')).expanduser()

        #self.upload2nas = cfg.getboolean(sec, 'upload2nas')

        self.log_clr = cfg.getint(sec, 'log_clr', fallback=0)
        # self.log_clr = int(cfg.get(sec, 'log_clr'))
        if self.log_clr == 0:
            self._clr = ""
            self._endc = ""
        else:
            # Get the colour header code, with a default (for purple)
            self._clr = self.CLRS.get(self.log_clr, '\033[95m')
            self._endc = self.ENDC

    def init_logpath(self) -> str:
        # Make sure, logfolders exist
        self.path_log = self.logroot
        # create_t = 0
        create_msg = ""
        usr = getpass.getuser()

        if not self.path_log.is_dir():
            # NOTE: Error msgs are to screen only, since logs don't exist yet!
            if self.path_log.exists():
                # It is a file already, not a path, give up!
                raise FileExistsError(f"[F] logpath '{self.path_log}' is a file!")
            try:
                self.path_log.mkdir(parents=True)
            except PermissionError as err:
                print(f"[F] user {usr} not permitted to write to {self.path_log}!")
                raise(err)
            else:
                dt_now = self.utcnow()
                str_now = dt_now.strftime(self._fmt_iso8601)
                create_msg += (f"Created path to logfiles '{self.path_log}' "
                               f"at {str_now}.")
            # create_t = self.utcnow()

        return create_msg

    def init_logfiles(self, create_msg: str = ""):
        """Initialize the logfiles."""
        # Take time
        dt_now = self.utcnow()
        self.day_str = dt_now.strftime(self._fmt_day)
        self.month_str = dt_now.strftime(self._fmt_month)

        # Set filenames for logfiles
        prefix = self.board_id
        self.logname    = self.path_log / f"{prefix}_{self.day_str}.log"
        self.debugfname = self.path_log / f"{prefix}_{self.day_str}.dbg"
        # Ready to log!

        # Initialize .log & .dbg files
        self.logline("Begin logging.", level='INF')
        self.debuglogline("Begin debugging.", level='INF',
                          func="ABCLogger.init_files")
        if len(create_msg) > 0:
            # c_ts = self.dt_to_unix(create_t)
            self.logline(create_msg, level='INF')

        # self.init_csvs(day_str)

    def init_csvs(self):
        # Produce a dict of csv file names for each datatype
        p_log = self.path_log
        prefix = self.board_id
        self.csvdatafnames = {
            dtype: p_log / f"{prefix}_{dtype}_{self.day_str}.csv"
                           for dtype in self.CSV_DTYPES}

        # Initialize all csv files with a header
        for dtype, fp in self.csvdatafnames.items():
            if not fp.is_file():
                with open(fp, 'w', newline='') as csvfile:
                    csvwriter = csv.writer(csvfile)
                    # Write header to the file
                    csvwriter.writerow(self.CSV_DICT.get(dtype))
                    # # TODO: Should those print() commands also be logged?
                    # if self.log2stdout:
                    #     print(f"Initialized CSV file '{fp}'.")
                    self.logline(f"Initialized CSV file '{fp}'.",
                                 level='INF')
            else:
                # if self.log2stdout:
                #     print(f"Today's CSV file '{fp}' already exists, "
                #           "continuing with that one.")
                self.logline(f"Today's CSV file '{fp}' already exists, "
                             "continuing with that one.", level='INF')

    def reinit(self, reason=''):
        """Reinitialize all logfiles after a rollover.

        The path `self.logroot` (`==self.path_log`) does not change,
        so there is no need to reinitialize it.
        """
        self.init_logfiles(reason)
        self.init_csvs()


    def logline(self, msg, level='INF'):
        """Writes `msg` to the logfile, including some metadata.

        The formatted output uses `|` as the separator, and includes:
        - a three-letter code indicating the severity or other info (e.g. ERR)
        - the unix timestamp, in UTC [e.g. 1636149191]
        - a human-readable timestamp (iso8601) [e.g. 2021-11-05T21:53:11Z]
        - the message itself, which could in principle contain further
          separators

        """
        # ts = self.dt_to_unix(self.utcnow())
        dt_now = self.utcnow()
        dt_str = self.dt_to_isofmt(dt_now)
        ts = self.dt_to_unix(dt_now)

        msg = f"{level}|{ts}|{dt_str}|{msg}"
        if self.log2stdout:
            if level not in self.LEVELS_SKIP_STDOUT:
                print(self._clr + msg + self._endc)
        if level in self.LEVELS_TO_LOGDATA:
            # NOTE: Now these data go directly to csvfiles,
            #       just render to stdout!
            # with open(self.dataname, 'a') as f:
            #    f.write(m + "\n")
            pass

        elif level in self.LEVELS_TO_LOG1:
            with open(self.logname, 'a') as f:
                f.write(msg + "\n")
        else:
            print(f"WARNING --- LEVEL {level} UNRECOGNISED!! ---")
            with open(self.logname, 'a') as f:
                f.write(msg + "\n")

    def debuglogline(self, msg, level, func):
        if self.debug2file:
            # ts = self.dt_to_unix(self.utcnow())
            dt_now = self.utcnow()
            dt_str = self.dt_to_isofmt(dt_now)
            ts = self.dt_to_unix(dt_now)

            # m = "{}|{}|{}|{}".format(field, ts, func, msg)
            msg = f"{level}|{ts}|{dt_str}|{func}|{msg}"
            with open(self.debugfname, 'a') as f:
                f.write(msg + "\n")

    def logdatalst(self, lst, field, add_date=True):
        """Log data from list into csv form.

        If add_date is set, also add a UTC unix timestamp at the start.
        """
        dt_now = self.utcnow()
        dt_str = self.dt_to_isofmt(dt_now)
        ts = self.dt_to_unix(dt_now)

        msg = f"{field}|{ts}|{str(lst)}"
        if field not in self.CSV_DTYPES:
            raise ValueError(
                f"[E] cannot log '{msg}' - unknown datatype {field}"
                f"    known types: {str(self.CSV_DTYPES)}"
            )

        # TODO: an extra debug flag here? rmm 18.01.23
        if self.dbg_csv2stdout:
        #if self.log2stdout:
            print("csv|" + msg)

        fp = self.csvdatafnames.get(field)
        # with open(fp, 'a') as f:
        #     _csv = ",".join(map(str, lst))  # no [], just csv :)
        #     if add_date:  # include the logging time
        #         f.write(f"{ts},{_csv}\n")
        #     else:  # assume incoming data has the sample time
        #         f.write(f"{_csv}\n")
        #     # f.write("{}\n".format(str(lst))) # includes []
        with open(fp, 'a', newline='') as csvfile:
            csvwriter = csv.writer(csvfile)
            if add_date:  # include the logging time
                csvwriter.writerow([ts, dt_str, *lst])
            else:  # assume incoming data has the sample time
                csvwriter.writerow(lst)


# }}}


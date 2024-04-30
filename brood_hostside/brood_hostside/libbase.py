#!/usr/bin/env python3
import platform
from pathlib import Path
from datetime import datetime, timezone  # , timedelta
import subprocess

class ABCBase(object):
    """Provide basic functionalities for the ABC classes.

    Contains all basic time functions as well as hostname-
    related methods.

    """

    # _fmt_iso8601 = "%Y-%m-%dT%H:%M:%S%z"
    _fmt_iso8601 = "%Y-%m-%dT%H:%M:%SZ"  # UTC shorthand
    # _fmt_iso8601 = "%Y-%m-%dT%H:%M:%S.%f%z"  # Full

    # _fmt_abc = "$$(%Y, %m, %d),(%H, %M, %S)"
    _fmt_abc_re = "$(%Y, %m, %d),(%H, %M, %S)"
    # _fmt_gdt = "$$2021,8,13*$10,14,58**"
    _fmt_gdt = "$$%Y,%m,%d*$%H,%M,%S**"

    # _fmt_day = "%y%m%d"
    _fmt_day = "%Y-%m-%d"
    _fmt_month = "%Y-%m"

    def __init__(self, **kwargs):
        """Instantiate an ABCBase object.
        
        """
        super().__init__(**kwargs)

        self.hostname = platform.node()

    def _clean_datetime(self, t_str: str,
                        utc: bool = True,
                        fmt: str = _fmt_abc_re) -> datetime:
        """Clean and convert sample date and time. 

        If UTC is false, do not set tzinfo.

        cmd = 'hf.callformatprint(s.get_rht)'
        rht_dat = self.exec_abc(cmd, minlen=minlen, nfields=nfields)

        rht_dat ->
        "$$(2021, 8, 13),(10, 14, 47)*$57.9614,*$26.06279,*$m,p,m*$True,**"

        m = re.findall(r'\$(.+?)\*', rht_dat)  # noqa: W605
        print(m)
        [
            '$(2021, 8, 13),(10, 14, 47)',
            '57.9614,',
            '26.06279,',
            'm,p,m',
            'True,',
        ]

        t_str = m[0]
        """
        tzinfo = timezone.utc
        if not utc:
            tzinfo = None

        # # Original version:
        # _t_date = m[0][1:].replace(
        #     '(', ' '
        # ).replace(
        #     ')', ' '
        # ).strip().split(',')
        # _t_date = [int(t) for t in _t_date]
        # dt_sample = datetime(*_t_date[:6], tzinfo=tzinfo)

        dt_sample = datetime.strptime(t_str, fmt).replace(tzinfo=tzinfo)

        return dt_sample

    def utcnow(self):
        """Return TZ-aware datetime object of current time.

        Use this wrapper to ensure consistent use of
        timestamps throughout logs.
        """
        # ALT: return datetime.utcnow()  # naive!
        return datetime.now(timezone.utc)

    def get_dt_day(self, dt: datetime) -> datetime:
        """Return datetime object of the day at midnight."""
        dt_day = dt.replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )
        return dt_day

    def dt_to_isofmt(self, dt: datetime, abbrev_utc: bool = True) -> str:
        """Format datetime object `dt` as per ISO8601 / rfc3339 format.

        - dt should be tz-aware
        - output will be of the form
        2021-08-12T12:43:05+01:00
        in the special case of UTC we use the shorter 'Z' notation
        2021-08-12T11:43:05Z
        """
        t_str = dt.isoformat(timespec="seconds")
        if abbrev_utc:
            t_str = t_str.replace('+00:00', 'Z').replace('+0000', 'Z')
        return t_str

    def dt_to_unix(self, dt: datetime) -> int:
        """Convert datetime object `dt` to a unix timestamp in seconds.

        Returns the timestamp as UTC - so long as `dt` is aware.
        """
        # return calendar.timegm(ts.utctimetuple())
        tstamp = dt.replace(tzinfo=timezone.utc).timestamp()
        return int(round(tstamp))

    def ftime(self, dt: datetime = None) -> str:
        """Generate HH:MM:SS representation of a datetime `t`.

        if no arg is supplied, generate current (UTC) time.
        """
        fmt = "%H:%M:%S"
        if dt is None:
            dt = self.utcnow()
        return dt.strftime(fmt)

    def timestamp4db(self, ts: float) -> str:
        """Convert datetime to influxDB-format.

        Assumes input of a TZ-aware datetime object
         a unix timestamp (sec since 1970),
        generates UTC timestamp of iso-8601 format"""
        # NOTE: If libabc is used, the time set on the ABC is in UTC!
        dt = datetime.fromtimestamp(ts, timezone.utc)
        t_str = self.dt_to_isofmt(dt)
        return t_str

    def parse_hostname(self):
        self.hiveloc, self.hive_str, self.rpi_str = (
            self.hostname.split("-")[0:3]
        )
        # Also get the numbers in case we need those?
        self.hive_num = int(''.join(filter(str.isdigit, self.hive_str)))
        self.rpi_num = int(''.join(filter(str.isdigit, self.rpi_str)))

        return self.hiveloc, self.hive_num, self.rpi_num

    def parse_boardname(self, addr: str) -> str:
        """Return the board name from the ``addr`` string.

        The expected boardname, if udev rules are installed correctly is:

           /dev/abc01 (current version of rules)
        /dev/brood_abc01 (earlier version of rules)

        --> method will yield ``abc01``

        Without rules implemented, we might also see:
        /dev/ttyACM0 (no rule matching the specific ID installed, linux)

        --> method will yield ``ttyACM1``

        /dev/cu.usbmodem?? (macOS)

        --> method will yield ``cu.usbmodem11``

        """
        # NOTE: This is a choice to be verified with others!
        board_id = addr.split("/")[-1].split("_")[-1]
        # self.board_id = board_id
        return board_id

    def safename(self, fp: Path, p_type: str = "file") -> Path:
        """Append stuff to a file or folder if it already exists.

        Check whether a given file or folder 's' exists, return a non-existing
        filename.

        fp ....... (full) filename or directory
        p_type ... 'file' or 'f' for files,
        -           'directory' or 'dir' or 'd' for folders

        Returns a file- or pathname that is supposedly safe to save
        without overwriting data.

        """
        # Ensure fp is a Path object
        p = Path(fp).expanduser().resolve()

        # if s_type.lower().startswith("f"):
        low_type = p_type.lower()
        if low_type.startswith("f"):  # File
            # if os.path.isfile(ss):
            if p.is_file():
                stem = p.stem
                suffix = p.suffix
                counter = 0
                while p.is_file():
                    p = p.with_name(f"{stem}_{counter:02d}{suffix}")
                    counter += 1

        # elif low_type == "directory" or low_type == "dir" or low_type == "d":
        elif low_type.startswith("d"):  # Directory
            if p.is_dir():
                stem = p.stem
                counter = 0
                while p.is_dir():
                    # s = s_base + "-{:02d}".format(counter)
                    p = p.with_name(f"{stem}_{counter:02d}")
                    counter += 1
        return p

    def lookfor_cfgfile(self, pth: Path = None, debug: bool = False) -> Path:
        """Return the location of the config file.

        Default location is '<dir of tool>/cfg'.
        Expected filename pattern is <pth>/<hostname>[.somext],
        where the extension might be .ini, .conf, .cfg, but is not
        required.

        File default pattern is `hostname`.

        Returns a Path object, or None if not found
        """
        if pth is None:
            tool_dir = Path(__file__).parent.resolve()
            pth = tool_dir / "cfg"
            if debug:
                print(f"[D] Tool executed from dir {Path().resolve()}")
                print(f"[D] Identified search path for config files as {pth}")

        candidates = [f for f in Path(pth).glob("*") if f.is_file()]
        if debug:
            msg = "\n\t".join([str(f) for f in candidates])
            print(f"   [D] candidate files are: \n\t{msg}")
        hostname = platform.node()
        cfgfile = None
        for f in candidates:
            if f.stem == hostname:
                cfgfile = f
                sz = cfgfile.stat().st_size
                print(f"[I] automatically identified {cfgfile} ({sz} bytes)")
                return cfgfile

        print("[W] failed to identify config for "
              f"host {hostname} in path {pth}")
        return None

    def git_info_str(self, compact:bool=False) -> str:
        '''look up git repository info (branch, commit, clean/dirty state)
        '''
        # make a very coarse exception handler, just adding info and if it fails we 
        # don't want to crash normal mcu operation.
        try:
            return self._git_info_str(compact=compact)
        except Exception as e:
            self.log(f"Error in git lookup {e.errno} {e}", level='EXC')
            return "(problem with git lookup)"
    
    def _git_info_str(self, compact:bool=False) -> str:
        '''look up git repository info (branch, commit, clean/dirty state)

        (function internals)
        '''
        # repo name available here: basename -s .git `git config --get remote.origin.url`

        try:
            short_hash = subprocess.check_output(['git', 'describe', '--always', '--dirty']).decode('ascii').strip()
        except subprocess.CalledProcessError as e:
            if e.returncode == 127: # git not installed?
                short_hash = "(unknown, git not installed)"
            elif e.returncode == 128: # not in a git repo? 
                short_hash = "(unknown, no git repo)"
            #if short_hash.startswith('fatal'): # could look for $? != 0 perhaps?
            #    short_hash = "(unknown)"
            return short_hash
        except FileNotFoundError as e:
            self.log(f"Error in git lookup {e.errno} {e}", level='EXC')
            short_hash = "(unknown, problem executing git)"
            return short_hash
            
        try: 
            branch = subprocess.check_output(['git', 'rev-parse', '--abbrev-ref', 'HEAD']).decode('ascii').strip() 
        except subprocess.CalledProcessError as e:
            if e.returncode == 127: # git not installed?
                branch = "(unknown, git not installed)"
            elif e.returncode == 128: # not in a git repo? 
                branch = "(unknown, no git repo)"
            #if branch.startswith('fatal'): # could look for $? != 0 perhaps?
            #    branch = "(unknown)"
            # not sure how we got here but the short-hash was ok. let's combine the output 

        if compact:
            info = f"{branch}-{short_hash}"
        else:
            info = f"branch: {branch} rev: {short_hash}"
        return info
        
        
class BackoffCtr:
    '''
    Counter to increase duration between yielding True

    It could be used to help emitting messages only infrequently if the same
    action occurs repeatedly.

    By default, it implements an exponential increase in between messages.


    '''
    def __init__(self, per_level=1, max_count=360):
        '''
        initialise counter

        `per_level` number of triggers at a given level before moving to next
        `max_count` highest value of ramp, e.g. at most one messge per day

        #`ramp` method of ramping up

        '''

        self.per_level = per_level
        self.max_count = max_count
        self.reset()

    def hit(self):
        self._n += 1
        if self._n >= (self.cur_level * self.per_level):
            self._climb_level()
            return True
        else:
            return False

    def _climb_level_forever(self):
        '''exponentially increment the waiting time'''
        self._n = 0
        self.cur_level *= 2

    def _climb_level(self):
        '''exponentially increment the waiting time until max_count'''
        self._n = 0
        self.cur_level *= 2
        if self.cur_level > self.max_count:
            self.cur_level = self.max_count

    def reset(self):
        self._n = 0
        self.cur_level = 1
        return True

    def hitok(self):
        '''tell the counter the condition was ok'''
        return self.reset()

    def hitwarn(self):
        '''increment counter and tell the counter the condition was bad'''
        return self.hit()

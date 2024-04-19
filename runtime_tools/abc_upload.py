#!/usr/bin/env python3
import shutil
# import platform
from pathlib import Path
from liblog import ABCLogger


class ABCUploader(ABCLogger):
    """Class to handle uploading to NAS.

    (Alphabetically) earlier files of each type are
    moved to the path `uploadroot` (spec. in config), e.g.
    "/home/pi/NAS/abc_data/".
    If the folder is online, the files are placed in subfolders, e.g.:

        ./hive5/rpi4/co2/
        ./hive5/rpi4/dbg/
        ./hive5/rpi4/log/
        ./hive5/rpi4/pwr/
        ./hive5/rpi4/rht/
        ./hive5/rpi4/tmp/

    where they accumulate. If a file with the same name already exists
    at the destination, the filename gets appended with a number such
    that the filename is unique and no data gets overwritten or lost.
    (Possible duplication is a much lesser danger,)
    """

    _prefix_append = "-upload"

    def __init__(self, path_cfg=None, **kwargs):
        super().__init__(path_cfg, **kwargs)

    def log(self, msg="", level='INF'):
        """Wrap `self.logline()` with default values."""
        self.logline(msg, level)

    def init_logfiles(self, create_msg: str = ""):
        """Overwrite method from parent."""
        # print("Inside overwritten init_logfiles().")

        # Take time
        dt_now = self.utcnow()
        self.day_str = dt_now.strftime(self._fmt_day)
        self.month_str = dt_now.strftime(self._fmt_month)

        # Set filenames for logfiles
        prefix = self.board_id + self._prefix_append
        self.logname = self.logroot / f"{prefix}_{self.month_str}.log"
        # Ready to log!

        # Initialize .log file
        self.log("Begin logging.")
        if len(create_msg) > 0:
            # c_ts = self.dt_to_unix(create_t)
            self.log(create_msg)

    def init_csvs(self):
        """Overwrite method from parent."""
        # print("Dummy init_csvs().")
        return True

    def _move_file(self, src: Path, dir_dst: Path) -> Path:
        """Upload file at path `src` to a folder on the NAS."""
        # Check whether the folder is mounted
        # Move this filename to the config?
        self.log("Checking NAS status.", level='DBG')
        f_online = self.uploadroot / "online"
        # TODO: Wrap that in try/except:
        if not f_online.is_file():
            self.log("NAS seems offline!", level='WRN')
            return None

        # Make sure folder exists
        # TODO: Wrap that in try/except:
        if not dir_dst.is_dir():
            if dir_dst.exists():
                err_msg = f"Output folder '{dir_dst}' is already a file!"
                self.log(err_msg, level='ERR')
                raise FileExistsError(err_msg)
            try:
                dir_dst.mkdir(parents=True)
                self.log(f"Created folder '{dir_dst}'.")
            except Exception as err:
                self.log("Exception occured while trying to create "
                         f"a folder on the NAS: {repr(err)}", level='ERR')
                return None

        # Upload the file
        dst = self.safename(dir_dst / src.name, 'file')
        result = None
        if src.is_file() and f_online.is_file():
            try:
                # Copy file to NAS
                result = Path(shutil.copy2(src, dst))
            except Exception as err:
                self.log(f"Uploading '{src.name}' failed with "
                         f"'{repr(err)}'.", level='ERR')
                return None

            # Successfully copied file to NAS
            if (result is not None) and result.is_file():
                self.log(f"Uploaded '{result}'.")

                # Delete the file from the RPi
                src.unlink()
                self.log(f"Deleted '{src}' (src.is_file(): {src.is_file()})",
                         level='DBG')
            else:
                self.log("Uploaded file seemingly corrupt? "
                         f"Check '{src}' and '{result}'! "
                         "Not deleting local file!", level='ERR')
                return None
        else:
            self.log("Either NAS is offline or src-file not found.",
                     level='ERR')
            return None

        # self.log("Uploading file done.", level='DBG')
        return Path(result).resolve()

    def upload_files(self, dir_up: Path, pattern: str,
                     # nkeep: int = 1) -> Tuple[bool, int]:
                     nkeep: int = 1):
        """Upload all files from `dir_up` matching `pattern`.

        `nkeep` .... number of most recent files to keep locally
                        (defaults to '1')
        """
        exit = False

        # NOTE: We leave the latest file on the RPi!
        files2upload = sorted(self.path_log.rglob(pattern))[:-nkeep]
        self.log(
            f"Found {len(files2upload)} files matching "
            f"pattern '{pattern}' in folder '{self.path_log}' to upload.",
            level='DBG')

        # Iterate over all files very cautiously
        fsizes = []
        # fsize_total = 0
        for fp in files2upload:
            fsize = fp.stat().st_size
            try:
                fp_up = self._move_file(fp, dir_up)
            except Exception as err:
                self.log(
                    f"Error moving file '{fp.name}' to '{dir_up}': "
                    f"'{type(err).__name__}', msg: '{repr(err)}'.",
                    level='ERR')
                exit = True
                break
            else:
                if fp_up is None:
                    exit = True
                    break
                else:
                    # fsize_total += fsize
                    fsizes.append(fsize)
                    # TODO: Check fsize of `fp_up`?
                    self.log(
                        f"Successfully uploaded '{fp.name}' "
                        f"({round(fsize / 1000, 2)} KB) to '{fp_up}'.",
                        level='DBG')

        fsize_total = sum(fsizes)
        # fsize_max = max(fsizes)
        # fsize_min = min(fsizes)
        self.log(
            f"Uploaded {round(fsize_total / 1e6, 2)} MB "
            f"of '{pattern}'-files to '{dir_up}'.")

        if exit:
            self.log("Stopping upload!", level='WRN')

        return exit, fsize_total

    def upload_old_logs(self):
        """Upload older logfiles to the NAS or PC."""
        hive, rpi = self.parse_hostname()[1:3]
        dir_upload = self.uploadroot / f"hive{hive}/rpi{rpi}/"

        # Upload ABC data CSVs
        # exit = False
        # files2upload = []
        fsize_collect = []
        for dtype in self.CSV_DTYPES:
            pattern = f"{self.board_id}_{dtype}_*.csv"
            dir_up = dir_upload / dtype
            exit, fsizes = self.upload_files(dir_up, pattern)
            if exit:
                # break
                return None
            else:
                fsize_collect.append(fsizes)

        # Upload ABC logfiles
        for logtype in self.LOG_SUFFIXES:
            suffix_nodot = logtype[1:]
            pattern = f"{self.board_id}_*-*-*.{suffix_nodot}"
            dir_up = dir_upload / suffix_nodot
            exit, fsizes = self.upload_files(dir_up, pattern)
            if exit:
                return None
            else:
                fsize_collect.append(fsizes)

        # Upload self-logs
        pattern = f"{self.board_id}{self._prefix_append}_*-*.log"
        dir_up = dir_upload / "upl"
        exit, fsizes = self.upload_files(dir_up, pattern)
        if exit:
            return None
        else:
            fsize_collect.append(fsizes)

        # Upload configs
        pattern = f"{self.hostname}*.cfg"
        dir_up = dir_upload / "cfg"
        exit, fsizes = self.upload_files(dir_up, pattern)
        if exit:
            return None
        else:
            fsize_collect.append(fsizes)

        # Upload source code (+ configs? then scrap above..)
        # ...

        # Aggregate values and log
        fsize_total = sum(fsize_collect)
        # fsize_max = max(fsize_collect)
        # fsize_min = min(fsize_collect)
        self.log(f"Uploaded a total of {round(fsize_total / 1e6, 2)} MB.")

        return None


if __name__ == "__main__":
    # # Find config
    # path_cfg = lookfor_cfgfile()

    uploader = ABCUploader()

    uploader.upload_old_logs()
    # try:
    #     uploader.upload_old_logs()
    # except Exception as err:
    #     uploader.logline(
    #         "Uploading to NAS failed with "
    #         f"'{type(err).__name__}', msg: '{repr(err)}'",
    #         level='ERR'
    #    )

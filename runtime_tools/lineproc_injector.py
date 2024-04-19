'''
Script to push data saved in lineprotocol files to DB

- load influxDB credentials from file
- load data to inject from logfile filled when DB connection was unavailable

- todo: move the file after successful transfer  [to where?]
 

'''
import argparse
from pathlib import Path
from configparser import ConfigParser
from datetime import datetime, timedelta

import libdb


def check_data(infile, maxpts:int=None, filt:str=None, comment:str='#'):
    cnt_lines = 0
    meas_map = {}
    with open(infile) as f:
        for _line in f:
            lp = _line.strip()
            if lp.startswith(comment): # skip commented lines
                continue
            cnt_lines += 1

            meas = lp.split(',')[0]
            meas_map.setdefault(meas, 0)
            meas_map[meas] += 1

            if filt is not None and meas != filt:
                print(f"[I] skipping point with meas = {meas}")
                continue
            print(lp)
    print(f"[I] read {cnt_lines} lines with points (excluding comments)")
    return meas_map

#{{{ load_needs_action_data
def load_needs_action_data(DBH, infile, args, verb=True, filt="tmp"):
    # no facility to skip rows by some step - don't know the types that are
    # here. just have an upper limit args.num
    cnt_try = 0
    cnt_suc = 0
    cnt_lines = 0

    i = 0
    with open(args.infile) as f:
        for _line in f:
            lp = _line.strip()
            if lp.startswith("#"): # skip commented lines
                continue
            elems = lp.split(" ")
            meas = elems[0].split(",")[0]
            tags = ",".join(elems[0].split(",")[1:])
            tags += ",src=post_inj"

            fields = elems[1]
            ts = elems[2]
            lp2 = f"{meas},{tags} {fields} {ts}"
            if args.verb: print(f"[D] line {i} meas: {meas} @ {ts}.")

            if meas != filt:
                print(f"[I] skipping meas {meas}")
                continue


            # inject the point in line protocol.
            # TODO: we need this to take care of the return values, but
            # check first whether it works ok here)
            print(lp2)
            #rv = write_pt(DBH, lp2)
            rv = DBH.write_points([lp2,])
            #DBH.write_api.write(bucket=DBH.if2bucket, org=DBH.if2org,
            #                    write_precision='s', record=lp)
            if rv:
                cnt_suc += 1
            if args.verb:
                print(f"[I] injected +1 points. RVal:{rv}")

            #
            i += 1
            if i >= args.num:
                break

    print(f"[I] {cnt_lines} lines processed. "
          f"{cnt_try} points created, {cnt_suc} points injected.")
    

class UnpushedInjector:
    _fmt_day = "%Y-%m-%d"
    def __init__(self, cfgfile:str) -> None:
        self._cfgfile = Path(cfgfile).expanduser()  # accepts str or Path obj

        self.read_cfg()
        self.attach_db()


    def attach_db(self, cfgfile:str=None):
        if cfgfile is None:
            self.dbh = libdb.BaseDBInjector(self._cfgfile)


        
    def read_cfg(self):
        cfg = ConfigParser()
        cfg.read(self._cfgfile)  # _cfgfile is a canonical path
        sec = 'InfluxDB'
        self.still_to_inject_path = Path(
            cfg.get(sec, 'still_to_inject_dir')).expanduser()

    def lookup_lineprotoc(self, age_d:int=1) -> Path:
        today = datetime.utcnow()
        td = timedelta(days=age_d)
        dt_tgt = today - td
        dt_str = dt_tgt.strftime(self._fmt_day)

        pattern = f"*_missing_data_{dt_str}.lineprotocol"
        files = list(self.still_to_inject_path.glob(pattern))
        print(f"[I] in directory {self.still_to_inject_path}, found {len(files)} hits")
        print (files)

        #pattern = "{board}_missing_data_{date_str}.lineprotocol"
        #abc21_missing_data_2023-08-30.lineprotocol

        self._last_pattern = pattern
        self._files = files

        return files
    
    def check_data(self, infile, maxpts:int=None, filt:str=None, comment:str='#'):
        cnt_lines = 0
        meas_map = {}
        with open(infile) as f:
            for _line in f:
                lp = _line.strip()
                if lp.startswith(comment): # skip commented lines
                    continue
                cnt_lines += 1

                meas = lp.split(',')[0]
                meas_map.setdefault(meas, 0)
                meas_map[meas] += 1

                if filt is not None and meas != filt:
                    print(f"[I] skipping point with meas = {meas}")
                    continue
                print(lp)
        print(f"[I] read {cnt_lines} lines with points (excluding comments)")
        return meas_map

    def push_datafile(self, infile, maxpts:int=None, filt:str=None, comment:str='#', verb:bool=False):
        cnt_lines = 0
        cnt_pts = 0
        cnt_success = 0
        meas_map = {}
        with open(infile) as f:
            for _line in f:
                lp = _line.strip()
                if lp.startswith(comment): # skip commented lines
                    continue
                cnt_lines += 1

                meas = lp.split(',')[0]
                meas_map.setdefault(meas, 0)
                meas_map[meas] += 1

                if filt is not None and meas != filt:
                    if verb: print(f"[I] skipping point with meas = {meas}")
                    continue
                cnt_pts += 1
                print(lp)

                # passed the filter, let's transmit to DB
                rv = self.dbh.write_linepoints([lp], verb=True)
                if rv:
                    cnt_success += 1

        if cnt_pts:
            pct_succ = (cnt_success / cnt_pts) * 100.0
        else:
            pct_succ = 0.0
        print(f"[I] read {cnt_lines} lines, filter kept {cnt_pts} points.\n[I]Pushed {cnt_success} pts ({pct_succ:.1f}%)")
        return meas_map


if __name__ == "__main__":
    #{{{ input args
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--inject', action='store_true', help="inject the data. ")
    parser.add_argument('--credfile', type=Path, default=None)
    parser.add_argument('-i', '--infile', type=Path, default=None,
                        help="'needs-action' file with data in line protocol")
    parser.add_argument('-n', '--num', type=int, default=4)
    parser.add_argument('-f', '--filt', type=str, default="hkl")
    parser.add_argument('-r', '--startrow', type=int, default=1)
    parser.add_argument('-v', '--verb', action='store_true')
    args = parser.parse_args()
    #}}}
    UI = UnpushedInjector(args.credfile)

    flist = UI.lookup_lineprotoc(age_d=0)
    for f in flist:
        print(f)
    if args.verb and len(flist):
        m2 = UI.check_data(f)
    
    if args.inject:
        m3 = UI.push_datafile(f, filt='rht')

    #UI.dbh.write_linepoints(points)


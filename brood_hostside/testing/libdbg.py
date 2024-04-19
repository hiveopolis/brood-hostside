'''
A library of extra functions to use during probing and debugging the ABC.

I'm not certain this is the best way to do it, but I want to find a way to
avoid littering libabc, libui, top-level run scripts with too much
interrogation-only code.

'''
import time
from libabc import ABCTooShortRespError, ABCGarbledRespError
from libabc import ABCHandle, HtrReadings

def cprint(s:str):
    '''debug print lines colourful for visibility'''
    print("{}{}{}".format('\033[94m', s, '\033[0m'))

# {{{ some debugging code
def dbg_inject_delay(ABC, dly:float = 2.5):
    '''
    inject a delay and check impact on the ABC loop timing
    '''
    time.sleep(dly)
    now = ABC.utcnow()
    t_left = ABC.t_end - now
    cprint(f"[D] delayed a bit more, time remaining for loop now: {t_left}s ")



def get_extra_pwr_data(ABC, dly:float = 1.25):
    try:
        ABC.sample_pwr_sensors()
        # display
        _d = ABC.last_pwr_dict
        if _d is not None:
            s_pwr = f"   : {_d['time']:15} | {_d['voltage']:.2f}V | {_d['current']*1000:.2f} mA"
            cprint(s_pwr)
    except ABCGarbledRespError as e:
        msg = ( "[I] exception due to bad read from host, continuing"
                f"\nEXC|{ABC._last_pyb_resp} \nEXC|{e}")
        ABC.log(msg, level='EXC')
        ABC.cnt_caught_exceptions += 1

    time.sleep(dly)

def get_extra_htr_data(ABC:ABCHandle, dly:float = 1.25):
    _d = None
    try:
        ABC.get_heaters_status()
        _d = ABC.last_htr_data
    except ABCGarbledRespError as e:
        msg = ( "[I] exception due to bad read from host, continuing"
                f"\nEXC|{ABC._last_pyb_resp} \nEXC|{e}")
        ABC.log(msg, level='EXC')
        ABC.cnt_caught_exceptions += 1
    
    disp_htr_data(_d)
    time.sleep(dly)
    

def get_one_htr_data(ABC:ABCHandle, idx:int, refresh:bool=False):
    if idx >= 0 and idx < 10:
        data = ABC.last_htr_data
        vals = (data.h_avg_temp[idx], data.h_obj[idx], data.h_pwm[idx])
        return vals

def disp_htr_data(data:HtrReadings, idx:int=None):
    '''show a table of heater data '''
    if data is not None and data.up_to_date:
        if idx is None:
            cprint(f"[I] data from {data.timestamp}")
            cprint("\t tmp" + "  ".join([f"{v:6.1f}" for v in data.h_avg_temp]))
            cprint("\t obj" + "  ".join([f"{v:6.1f}" for v in data.h_obj]))
            cprint("\t pwm" + "  ".join([f"{v:6d}" for v in data.h_pwm]))
        elif idx >= 0 and idx < 10:
            cprint(f"[I] data from {data.timestamp} for htr {idx}")
            vals = (data.h_avg_temp[idx], data.h_obj[idx], data.h_pwm[idx])
            lbls = ('tmp', 'obj', 'pwm')
            for v, lbl in zip(vals, lbls):
                cprint(f"   {lbl:5} {v:6.1f}")
        # else warning - bad input
    
def disp_all_fields(ABC:ABCHandle, skip:list=[]):
    dlist = {
        'co2': ABC.last_co2_list,
        'htr': ABC.last_htr_list,
        'pwr': ABC.last_pwr_list,
        'rht': ABC.last_rht_list,
        'tmp': ABC.last_tmp_list
    }
    for field, data in dlist.items():
        if field in skip:
            continue
        msg = str(field) + "\t" + str(data)
        cprint(msg)

def disp_buffered_tmp(ABC:ABCHandle, dp:int=2, spatial:bool=False):
    if dp < 0:
        return
    d = ABC.last_tmp_list
    if d is None:
        return

    msg = ", ".join([f"{v:.{dp}f}" for v in d])
    cprint(msg)

import re
def decode_abc_pkt(raw:str):
    mm = re.findall(r'\$(.+?)\*', raw)
    return mm
        
#}}}

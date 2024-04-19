#!/usr/bin/env python3
'''
Interface script to execute actuators, and sample & log from ABC board periodically.

This variant checks a series of interactions with the board, either
automatically or manually validating the response or change.

Supply a configuration file or use -a flag to lookup based on hostname
'''

from typing import Tuple, List, Callable
from libabc import ABCHandle 
import libui
import libdbg
import inspect
import time
import numpy as np

RED = '\033[91m'
ENDC = '\033[0m'
GREEN = '\033[92m'

def tprint(msg, ok:bool=True):
    if ok: c = GREEN
    else: c = RED
    print(c + msg + ENDC)

def test_get_temp_offset(ABC:ABCHandle, dbg:bool=True) -> bool:
    ok = False
    ret = ABC.get_temp_offset()
    assert isinstance(ret, list)
    assert len(ret) == 64

    cframe = inspect.currentframe()
    #.f_code.co_name
    ok = True
    tprint(f"{cframe.f_code.co_name} {cframe.f_code.co_varnames} passed", ok)
    
    return ok


def test_reset_temp_offsets(ABC:ABCHandle, dbg:bool=True) -> bool:
    ok = False
    t0 = time.time()
    ret = ABC.reset_temp_offsets()
    t1 = time.time()
    elap = t1 - t0
    assert isinstance(ret, bool)
    assert ret == True
    assert elap < 2.0

    ok = True
    cframe = inspect.currentframe()
    tprint(f"{cframe.f_code.co_name} {cframe.f_code.co_varnames} passed in {elap:.2f}s", ok)
    
    return ok

def test_get_sensor_interval(ABC:ABCHandle, dbg:bool=True) -> bool:
    tgt_keys = ['rht', 'temp', 'power', 'co2']
    ok = False
    t0 = time.time()
    dct = ABC.get_sensor_interval()
    elap = time.time() - t0
    assert isinstance(dct, dict)
    assert all(k in dct for k in tgt_keys)
    #assert 'temp' 'rht' 'co2' 'power' in keys... [when #112 resolved]
    # b"{'rht': 1000, 'temp': 1000, 'power': 1000, 'co2': 2000}\r\n"
    ok = True
    cframe = inspect.currentframe()
    tprint(f"{cframe.f_code.co_name} passed in {elap:.2f}s", ok)
    return ok

def test_get_power_str(ABC:ABCHandle, dbg:bool=True) -> bool:
    tgt_keys = ['valid', 'time', 'voltage', 'shunt_voltage', 'current', 'power']
    ok = False
    t0 = time.time()
    ret = ABC.get_power_str()
    elap = time.time() - t0
    assert len(ret) == 2, f"expecting 2 elements, got {len(ret)}"
    txt, dct = ret
    assert len(txt.split(',')) == 6
    assert isinstance(txt, str)
    assert isinstance(dct, dict)
    assert all(k in dct for k in tgt_keys)
    # not sure how to test further than this.
    ok = True
    cframe = inspect.currentframe()
    tprint(f"{cframe.f_code.co_name} passed in {elap:.2f}s", ok)
    return ok

def test_get_co2_str(ABC:ABCHandle, dbg:bool=True) -> bool:
    tgt_keys = ['valid', 'time', 'co2', 'temp', 'rh' ]
    ok = False
    t0 = time.time()
    ret = ABC.get_co2_str()

    elap = time.time() - t0
    assert len(ret) == 2, f"expecting 2 elements, got {len(ret)}"
    txt, dct = ret
    assert len(txt.split(',')) == 5
    assert isinstance(txt, str)
    assert isinstance(dct, dict)
    assert all(k in dct for k in tgt_keys), f"Expecting {tgt_keys}, got {dct.keys()}"
    # not sure how to test further than this.
    ok = True
    cframe = inspect.currentframe()
    tprint(f"{cframe.f_code.co_name} passed in {elap:.2f}s", ok)
    return ok


def test_get_rht_str(ABC:ABCHandle, dbg:bool=True) -> bool:
    cframe = inspect.currentframe()
    fname = cframe.f_code.co_name
    tgt_keys = ['valid', 'time', 'temperature', 'rel_humid' ]
    ok = False
    t0 = time.time()
    ret = ABC.get_rht_str()
    elap = time.time() - t0
    if dbg:
        print(f"[D] {fname}, {ret}")
    assert len(ret) == 2, f"expecting 2 elements, got {len(ret)}"
    txt, dct = ret
    assert len(txt.split(',')) == 4, f"expecting 4 elems in txt, got {len(txt.split(','))}"
    assert isinstance(txt, str)
    assert isinstance(dct, dict)
    assert all(k in dct for k in tgt_keys), f"Expecting {tgt_keys}, got {dct.keys()}"
    # not sure how to test further than this.
    ok = True
    tprint(f"{fname} passed in {elap:.2f}s", ok)
    return ok

def test_get_mcu_id(ABC:ABCHandle, dbg:bool=True) -> bool:
    cframe = inspect.currentframe()
    fname = cframe.f_code.co_name
    ok = False
    t0 = time.time()
    ret = ABC.get_mcu_id()
    elap = time.time() - t0
    if dbg:
        print(f"[D] {fname}, {ret}")
    #assert len(ret) == 1, f"expecting 1 element, got {len(ret)}"
    assert isinstance(ret, int), f"expecting int, got {type(ret)}"

    ok = True
    tprint(f"{fname} passed in {elap:.2f}s", ok)
    return ok

def test_get_int_temps(ABC:ABCHandle, dbg:bool=True) -> bool:
    from numpy import ndarray
    cframe = inspect.currentframe()
    fname = cframe.f_code.co_name
    ok = False
    t0 = time.time()
    ret = ABC.get_int_temperatures()
    elap = time.time() - t0
    if dbg:
        print(f"[D] {fname}, {ret}")
    assert len(ret) == 3, f"expecting 3 elements, got {len(ret)}"
    timestamp, tmps, valid = ret
    assert(isinstance(timestamp, int)), "expecting timestamp to be int"
    assert isinstance(tmps, ndarray)
    assert isinstance(valid, bool)
    assert len(tmps) == 64

    ok = True
    tprint(f"{fname} passed in {elap:.2f}s", ok)
    return ok 

def test_get_heaters_status(ABC:ABCHandle, dbg:bool=True) -> bool:
    from numpy import ndarray
    cframe = inspect.currentframe()
    fname = cframe.f_code.co_name
    ok = False
    t0 = time.time()
    ret = ABC.get_heaters_status()
    elap = time.time() - t0
    if dbg:
        print(f"[D] {fname}, {ret}")
    assert len(ret) == 5, f"expecting 5 elements, got {len(ret)}"
    for elem in ret:
        assert isinstance(elem, ndarray), f"expecting np.ndarray, got {type(elem)}"
        assert len(elem) == 10, f"expecting 10 points, got {len(elem)}"

    ok = True
    tprint(f"{fname} passed in {elap:.2f}s", ok)
    return ok 

def test_get_one_htr_obj(ABC:ABCHandle, idx:int=5, dbg:bool=True) -> bool:
    '''
    set an objective, try reading it back, validate the value is the same
    '''
    cframe = inspect.currentframe()
    fname = cframe.f_code.co_name

    t0 = time.time()
    ABC.get_heaters_status() # refresh data
    restore_t_obj = ABC.last_htr_data.h_obj[idx]

    t_obj = 15.2
    cmd = f"h.objective({t_obj}, idx={idx})"
    ABC.safe_exec_abc(cmd, retries=3)
    time.sleep(0.65)
    _ = ABC.get_heaters_status() # refresh info on heater status
    t_obj_new = ABC.last_htr_data.h_obj[idx]
    dTobj = np.abs(t_obj_new - t_obj)
    assert dTobj < 1/256, f"tried setting t_obj[{idx}] to {t_obj:.2f}, got {t_obj_new}"
    if dbg:
        print(f"tried setting t_obj[{idx}] to {t_obj:.2f}, got {t_obj_new}")
        libdbg.disp_htr_data(ABC.last_htr_data)
    
    rv = ABC.get_heaters_objective(15) # should fail, code -98
    assert (rv == ABC._HTR_IDX_INVALID), f"[return value of invalid fetch {rv}, expected {ABC._HTR_IDX_INVALID}]"

    cmd = f"h.objective({restore_t_obj}, idx={idx})"
    ABC.safe_exec_abc(cmd, retries=3)
    elap = time.time() - t0
    
    tprint(f"{fname} passed in {elap:.2f}s")
    return True

def _prep_htr_set_one_objective_raw(ABC:ABCHandle, idx:int, t_obj:float, dbg:bool=True) -> None:
    ''' set the objective of one heater `idx` to `t_obj` '''
    cmd = f"h.objective({t_obj}, idx={idx})"
    ABC.safe_exec_abc(cmd, retries=3)
    time.sleep(0.65)

    
def _prep_htr_objectives_to_base_raw(
        ABC:ABCHandle, dbg:bool=True, basetmp:float=0.0, validate:bool=False
        ) -> Tuple[float, bool]:
    ''' put all heater objectives to `basetmp`, and if `validate`, also 
        validate whether the temperatures were set correctly on the MCU.
        Using raw cmds, not ABC wrappers.

        returns: previous base temperature, and valid status (None if not requested, 
        True if all 10 objectives reset to `basetmp`, False if any are not reset)
    '''
    _restore_tmp = float(ABC.heater_def_tmp)
    ABC.heater_def_tmp = basetmp
    cmd = f"h.objective({ABC.heater_def_tmp}, idx=None)"
    ABC.safe_exec_abc(cmd, retries=3)
    time.sleep(0.65)
    valid = None
    if validate:
        # --- note: next 4 lines are repeating a test, we need for setup only
        ret = ABC.get_heaters_status() # update info on heater status
        dTobj = np.abs(ABC.last_htr_data.h_obj -  ABC.heater_def_tmp)
        valid = np.all(dTobj < 1/256)
        if not valid: 
            print(f"expected all Tobj close to {ABC.heater_def_tmp}, worst is {dTobj.max()}")
        
    return _restore_tmp, valid

def _prep_htr_deactivate_one_raw(ABC:ABCHandle, idx:int, dbg:bool=True): 
    '''
    Deactivate heater `idx` (leave global heater thread untouched)
    Using raw cmds, not ABC wrappers.
    '''
    cmd = f"h.activate(False, {idx})"
    ABC.safe_exec_abc(cmd, retries=3, watermark=None)
    time.sleep(0.1)

def _prep_htr_activate_one_raw(ABC:ABCHandle, idx:int, dbg:bool=True): 
    '''
    Activate heater `idx` (leave global heater thread untouched)
    Using raw cmds, not ABC wrappers.
    '''
    cmd = f"h.activate(True, {idx})"
    ABC.safe_exec_abc(cmd, retries=3, watermark=None)
    time.sleep(0.1)


def _helper_htr_measure_deactivated_one(
        ABC:ABCHandle, idx:int, timeout_s:int=8, dbg:bool=True
        ) -> List[int]:
    '''
    check whether a de-activation occurred by measuring
    PWM data (->0), for up to `timeout_s` cycles.
    Using raw cmds, not ABC wrappers.
    '''
    # then check the pwm for whether it responded ok
    results = _helper_htr_measure_change(
        ABC, idx, lambda pwm_ix: (pwm_ix == 0),
        timeout_s, dbg)
    return results

def _helper_htr_measure_activated_one(
        ABC:ABCHandle, idx:int, timeout_s:int=8, dbg:bool=True
        ) -> List[int]:
    '''
    Activate a heater, then check whether activation occurred by measuring
    PWM data, for up to `timeout_s` cycles.
    Using raw cmds, not ABC wrappers.
    '''
    # first, turn on the heater
    _prep_htr_activate_one_raw(ABC, idx, dbg)

    # then check the pwm for whether it responded ok
    results = _helper_htr_measure_change(
        ABC, idx, lambda pwm_ix: (pwm_ix > 0),
        timeout_s, dbg)
    return results

    '''
    results = []
    for t in range(timeout_s):
        _ = ABC.get_heaters_status() # update info on heater status
        v = libdbg.get_one_htr_data(ABC, idx)
        pwm_ix = ABC.last_htr_data.h_pwm[idx]
        results.append(pwm_ix)
        if dbg: print(f"[{t}s][{idx}] pwm value {pwm_ix} ({v})")
        if dbg: libdbg.disp_htr_data(ABC.last_htr_data)
        if pwm_ix > 0:
            break

        time.sleep(1.0)
    
    return results
    '''

def _helper_htr_measure_change(
    ABC:ABCHandle, idx:int, ok_func:Callable, timeout_s:int=8, dbg:bool=True
    ) -> List[int]:
    '''
    measure PWM values for heater `idx`, in a loop until some condition is met,
    defined by `ok_func`. 

    pass in a comparator that returns true when the loop should exit early.
    for example `ok_func=lambda v: (v > 0)` or `lambda v: (v == 0)`.

    returns the list of PWM 
    '''
    hit_ok = False
    results = []
    for t in range(timeout_s):
        _ = ABC.get_heaters_status() # update info on heater status
        v = libdbg.get_one_htr_data(ABC, idx)
        pwm_ix = ABC.last_htr_data.h_pwm[idx]
        results.append(pwm_ix)
        if dbg: print(f"[{t:2}s][{idx}] pwm value {pwm_ix} ({v})")
        if dbg: libdbg.disp_htr_data(ABC.last_htr_data)
        if ok_func(pwm_ix):
            hit_ok = True
            if dbg: print(f"    [{idx}] exit condition ok after {t}s... ")
            break

        time.sleep(1.0)

    if not hit_ok and dbg: print(f"    [{idx}] exit condition not met after {t}s... ")
    
    return results


def _helper_reset_board(ABC:ABCHandle, msg:str=''):
    '''mini freak out response-> soft reset of whole board'''
    # mini freak out, the heater didn't disable. trigger a soft reset?
    if msg:
        libdbg.cprint(f"{RED}{msg}")
    libdbg.cprint(f"{RED} resetting board now...")

    ABC.logger.log2stdout = True
    cmd = 'reset_mcu()'
    ABC.safe_exec_abc(cmd, retries=3)
    ABC.stop()




def _prep_htr_deactivate_all_raw( ABC:ABCHandle, dbg:bool=True):
    '''
    Deactivate all heaters and disable global heater thread. 
    Using raw cmds, not ABC wrappers.
    '''
    cmd = "h.activate(False)"
    ABC.safe_exec_abc(cmd, retries=3)
    time.sleep(0.65)
    for i in range(ABC.NUM_HEATERS):
        cmd = f"h.activate(False, {i})"
        ABC.safe_exec_abc(cmd, retries=3, watermark=None)
        time.sleep(0.1)
    # can't directly validate this - no observability of activate states :(

def _prep_htr_enable_global_thread_raw(ABC:ABCHandle, dbg:bool=True, enable:bool=True):
    cmd = "h.activate(True)"
    ABC.safe_exec_abc(cmd, retries=3)
    time.sleep(0.65)
    # can't directly validate this - no observability of activate states :(
    if enable:
        ABC.heaters_status = True
    
def _prep_htr_disable_global_thread_raw(ABC:ABCHandle, dbg:bool=True, disable:bool=True):
    cmd = "h.activate(False)"
    ABC.safe_exec_abc(cmd, retries=3)
    time.sleep(0.65)
    # since we deactivated the global thead, we should turn this off
    if disable:
        ABC.heaters_status = False 
    
def _prep_htr_set_obj_above_amb_raw(ABC:ABCHandle, idx:int, dT:float=3, dbg:bool=True) -> Tuple[float, float]:
    '''
    set the objective of heater `idx` to its current ambient temp + `dT`
    return sufficient info to run assertion externally.
    Using raw cmds, not ABC wrappers.
    '''
    t_0 = ABC.last_htr_data.h_avg_temp[idx]
    t_obj = t_0 + dT # set a bit above current avg to see an effect
    cmd = f"h.objective({t_obj}, idx={idx})"
    ABC.safe_exec_abc(cmd, retries=3)
    time.sleep(0.65)
    _ = ABC.get_heaters_status() # update info on heater status
    dTobj1 = np.abs(ABC.last_htr_data.h_obj[idx] - t_obj)
    return dTobj1, t_obj


def test_set_heater_inactive(ABC:ABCHandle, dbg:bool=True, idx:int=5) -> bool:
    '''
    explicitly test deactivation with the method `ABC.set_heater_active`. 
    
    (cf test_set_htr_active which does all the operations at a low level,
        test_set_heater_active which activates the state )
    '''
    # expected operation
    # - heater idx is deactivated; (others are not)
    # - heater t_obj is set to default (=0)
    # observability:
    # - t_obj is reflected with a short delay
    # - deactivation is only validatable with some explicit calls to
    #   individual commands. such as:
    #   h.objective(t_avg + 3);
    #   for n=8, watch for pwm stays at 0.
    # initial state: 
    # - have an activated state and a non-zero t_obj.
    cframe = inspect.currentframe()
    fname = cframe.f_code.co_name
    t_obj = 25.0
    idx = 5
    timeout_s = 8
    dT_tol = 1/256
    n_passed = 0
    dT = 3.0
    ok = True

    # 0 - enable global thread, 1 heaters, and 1 objectives -- some things for deactivate to turn off
    _prep_htr_activate_one_raw(ABC, idx=idx)
    _prep_htr_set_one_objective_raw(ABC, idx, t_obj)
    # global activate, and status=>True
    _prep_htr_enable_global_thread_raw(ABC, enable=True)

    ret = ABC.get_heaters_status() # update info on heater status
    if dbg: libdbg.disp_htr_data(ABC.last_htr_data)
    t_exp = np.ones_like(ABC.last_htr_data.h_obj) * ABC.heater_def_tmp
    t_exp[idx] = t_obj

    dTobj = np.abs(ABC.last_htr_data.h_obj -  t_exp)
    if dbg and 0:
        print(f"---expected: {t_exp}")
        print(f"---measured: {ABC.last_htr_data.h_obj}")
    assert np.all(dTobj < dT_tol), f"expected all Tobj close to {ABC.heater_def_tmp}, worst is {dTobj.max()}"
    n_passed += 1
    tprint(f"{fname} initial setup done", True)

    # 1 - run function under test
    ABC.set_heater_active(_state=False, _idx=idx, clear_t_obj=True)
    # should not touch global state
    assert ABC.heaters_status == True, f"ABC.heaters_status should be true"
    n_passed += 1
    # should touch t_obj
    time.sleep(0.65)
    ret = ABC.get_heaters_status() # update info on heater status
    dTobj = np.abs(ABC.last_htr_data.h_obj[idx] -  ABC.heater_def_tmp)
    if dbg :
        print(f"---expected: {ABC.heater_def_tmp}")
        print(f"---measured: {ABC.last_htr_data.h_obj[idx]}")
    assert (dTobj < 1/256), f"expected Tobj close to {ABC.heater_def_tmp}, got {dTobj}"
    n_passed += 1
    # should deactivate node. So now we set t_obj high again, watch pwm ! >=0
    dTobj1, t_obj = _prep_htr_set_obj_above_amb_raw(ABC, idx, dT=dT, dbg=dbg)

    # 2 - check pwm stays == 0 for n steps. (ensure getting n steps data, set ok_test to always False)
    results_stayed_off = _helper_htr_measure_change(
        ABC, idx, lambda pwm_ix: False, 
        timeout_s//2, dbg)
    # what to do if it turned on? first, turn it off anyway.
    if max(results_stayed_off) > 0:
        msg = f"htr {idx} did not stay off! {results_stayed_off}."
        _prep_htr_objectives_to_base_raw(ABC)
        ok = False
    # then run assertion    
    assert max(results_stayed_off) == 0, f"expected htr {idx} to not heat, it was not activated! Got {results_stayed_off}"

    # 3 - cleanup [clear obj[idx], deactivate(idx)
    _prep_htr_deactivate_one_raw(ABC, idx, dbg)
    _prep_htr_objectives_to_base_raw(ABC, basetmp=ABC.heater_def_tmp)
    _prep_htr_disable_global_thread_raw(ABC, dbg)
    # be sure that it turned off again
    results_turned_off = _helper_htr_measure_deactivated_one(ABC, idx, timeout_s, dbg)
    
    if min(results_turned_off) > 0:
        # mini freak out, the heater didn't disable. trigger a soft reset?
        msg = f"htr {idx} did not turn off! {results_turned_off}."
        ok = False
        _helper_reset_board(ABC, msg)

    elif dbg:
        ret = ABC.get_heaters_status() # update info on heater status
        libdbg.disp_htr_data(ABC.last_htr_data)
    
    # 7 - run assertion on heating phase
    if dbg:
        print("[I] testing disable_all by re-enabling one heater while global thread is disabled.")
        print("[I] expect all pwm values to be 0..")
    if dbg: print(f"results of pwm [idx {idx}] (before activate):", results_stayed_off)
    assert (min(results_turned_off) == 0), f"expecting zero pwm on {idx}, after {timeout_s} sec still [{results_turned_off}]"
    if dbg: print(f"results of pwm [idx {idx}] (after  activate):", results_turned_off)

    return ok



def test_set_heater_active(ABC:ABCHandle, dbg:bool=True, idx:int=5) -> bool:
    '''
    explicitly test activation with the method `ABC.set_heater_active`. 
    (cf test_set_htr_active which does all the operations at a low level)
    '''
    # expected operation: 
    # - call method with new state and index; 
    # - if index is [0,9) we get True return value, else not.
    # - the activation state should change to set. This is only 
    #   observable with PWM checking.
    # test steps:
    # a) base state (obj=0, all nodes deactivated, global deactivate)
    # b) set heater obj[idx] = htr_tmp[idx] + 3
    #    - check htr obj ok
    # c) call method ABC.set_heater_active(True, idx)
    #    - observe pwm[idx] > 0
    # d) restore base state 

    # all steps should be the same as `test_set_htr_active` except 
    # the step c. And the order is a bit differnt.

    dT = 3
    timeout_s = 8
    dT_tol = 1/256

    t0 = time.time()

    n_passed = 0
    # part (a) -> base state: all off; wait; check
    _restore_tmp, valid = _prep_htr_objectives_to_base_raw(ABC, dbg, basetmp=0, validate=True)
    n_passed += 1
    if dbg: libdbg.disp_htr_data(ABC.last_htr_data)

    # part (b) -> deactivate everything
    _prep_htr_deactivate_all_raw(ABC, dbg)
    _prep_htr_enable_global_thread_raw(ABC, dbg)
    # can't directly validate this - no observability of activate states :(

    # part (c) -> idx to T_amb + 3; wait; check
    dTobj1, t_obj = _prep_htr_set_obj_above_amb_raw(ABC, idx, dT=dT, dbg=dbg)
    assert dTobj1 < dT_tol, f"expected Tobj[{idx}] close to {t_obj}, got {dTobj1}"
    n_passed += 1
    if dbg: libdbg.disp_htr_data(ABC.last_htr_data)

    # part (d) => the ACTUAL TEST! activate the heater [idx], test pwm>0
    #    - after 1s,2s,... - check htr_pwm[idx] > 0
    ABC.set_heater_active(True, idx)
    
    # then check the pwm for whether it responded ok
    pwm_results = _helper_htr_measure_change(ABC, idx, lambda pwm_ix: (pwm_ix > 0),
        timeout_s, dbg)
    # NOTE: only apply assertion on part (d) after turning off the heater again! (part e)

    # part (e) => put back to original condition
    _prep_htr_deactivate_one_raw(ABC, idx, dbg)
    _prep_htr_objectives_to_base_raw(ABC, basetmp=_restore_tmp)
    _prep_htr_disable_global_thread_raw(ABC, dbg)
    # be sure that it turned off again
    results_turned_off = _helper_htr_measure_deactivated_one(ABC, idx, timeout_s, dbg)
    
    if min(results_turned_off) > 0:
        # mini freak out, the heater didn't disable. trigger a soft reset?
        msg = f"htr {idx} did not turn off! {results_turned_off}."
        _helper_reset_board(ABC, msg)

    elif dbg:
        ret = ABC.get_heaters_status() # update info on heater status
        libdbg.disp_htr_data(ABC.last_htr_data)

    # *test* for part (d)
    assert (max(pwm_results) > 0), f"expecting nonzero pwm on {idx}, after {timeout_s} sec still [{pwm_results}]"
    if dbg: print(f"results of pwm [idx {idx}]:", pwm_results)
    assert (min(results_turned_off) == 0), f"expecting zero pwm on {idx}, after {timeout_s} sec still [{results_turned_off}]"
    if dbg: print(f"results of pwm [idx {idx}]:", results_turned_off)


    elap = time.time() - t0
    cframe = inspect.currentframe()
    fname = cframe.f_code.co_name
    tprint(f"{fname} passed in {elap:.2f}s")
    return True


def test_set_htr_active(ABC:ABCHandle, dbg:bool=True, idx:int=3) -> bool:
    # 5 parts to this test:
    # a) put to base state, htr_obj=0, h.activate(False, idx=None)
    #    - check htr_obj ok (? that is already part of test_set_htr_obj)
    # b) h.activate(False, i) for i in range(10); h.activate(True, None)
    #    - cannot check this part.
    # c) set htr_obj[idx] = htr_tmp[idx] + 3 
    #    - check obj OK
    # d) set h.activate(True, idx)
    #    - wait 1s,2s,3s,4s -> check htr_pwm[idx] > 0
    # e) restore base state again
    dT = 3
    timeout_s = 8
    dT_tol = 1/256

    n_passed = 0
    # part (a) -> base state: all off; wait; check
    _restore_tmp, valid = _prep_htr_objectives_to_base_raw(ABC, dbg, basetmp=0, validate=True)
    n_passed += 1
    if dbg: libdbg.disp_htr_data(ABC.last_htr_data)

    # part (b) -> deactivate everything
    _prep_htr_deactivate_all_raw(ABC, dbg)
    _prep_htr_enable_global_thread_raw(ABC, dbg)
    # can't directly validate this - no observability of activate states :(

    # part (c) -> idx to T_amb + 3; wait; check
    dTobj1, t_obj = _prep_htr_set_obj_above_amb_raw(ABC, idx, dT=dT, dbg=dbg)
    assert dTobj1 < dT_tol, f"expected Tobj[{idx}] close to {t_obj}, got {dTobj1}"
    n_passed += 1
    if dbg: libdbg.disp_htr_data(ABC.last_htr_data)

    # part (d) => the ACTUAL TEST! activate the heater [idx], test pwm>0
    #    - after 1s,2s,... - check htr_pwm[idx] > 0
    pwm_results = _helper_htr_measure_activated_one(ABC, idx, timeout_s, dbg)
    # NOTE: only apply assertion on part (d) after turning off the heater again! (part e)

    # part (e) => put back to original condition
    _prep_htr_deactivate_one_raw(ABC, idx, dbg)
    _prep_htr_objectives_to_base_raw(ABC, basetmp=_restore_tmp)
    _prep_htr_disable_global_thread_raw(ABC, dbg)
    # be sure that it turned off again
    results_turned_off = _helper_htr_measure_deactivated_one(ABC, idx, timeout_s, dbg)
    
    if min(results_turned_off) > 0:
        # mini freak out, the heater didn't disable. trigger a soft reset?
        msg = f"htr {idx} did not turn off! {results_turned_off}."
        _helper_reset_board(ABC, msg)

    elif dbg:
        ret = ABC.get_heaters_status() # update info on heater status
        libdbg.disp_htr_data(ABC.last_htr_data)

    # *test* for part (d)
    assert (max(pwm_results) > 0), f"expecting nonzero pwm on {idx}, after {timeout_s} sec still [{pwm_results}]"
    if dbg: print(f"results of pwm [idx {idx}]:", pwm_results)
    assert (min(results_turned_off) == 0), f"expecting zero pwm on {idx}, after {timeout_s} sec still [{results_turned_off}]"
    if dbg: print(f"results of pwm [idx {idx}]:", results_turned_off)


    return True

def test_set_htr_obj(ABC:ABCHandle, dbg:bool=True) -> bool:
    # 3 parts to this test:
    # a) put to base state, set objective globally to some value
    #    - check that value is reflected in MCU readback for all t_obj
    # b) put one index to Tamb + 3 (for example)
    #    - check that value is reflected for t_obj[idx]
    # c) restore to base state with t_obj = previous value

    import numpy as np
    idx = 3
    n_passed = 0
    # part (a) -> base state: all off; wait; check
    _restore_tmp = float(ABC.heater_def_tmp)
    ABC.heater_def_tmp = 1.1 # a bit arbitrary, recognisable after
    cmd = f"h.objective({ABC.heater_def_tmp}, idx=None)"
    ABC.safe_exec_abc(cmd, retries=3)
    time.sleep(0.65)
    ret = ABC.get_heaters_status() # update info on heater status
    #libdbg.cprint(ABC.last_htr_data.h_obj)
    dTobj = np.abs(ABC.last_htr_data.h_obj -  ABC.heater_def_tmp)
    assert np.all(dTobj < 1/256), f"expected all Tobj close to {ABC.heater_def_tmp}, worst is {dTobj.max()}"
    n_passed += 1
    
    if dbg: libdbg.disp_htr_data(ABC.last_htr_data)

    # part (b) -> idx to T_amb + 3; wait; check
    v_prev = v = libdbg.get_one_htr_data(ABC, idx) # tmp, obj, pwm
    t_obj = v[0] + 3.0 # set a bit above current avg to see an effect
    cmd = f"h.objective({t_obj}, idx={idx})"
    ABC.safe_exec_abc(cmd, retries=3)
    time.sleep(0.65)
    ret = ABC.get_heaters_status() # update info on heater status
    v = libdbg.get_one_htr_data(ABC, idx)
    dTobj1 = np.abs(ABC.last_htr_data.h_obj[idx] - t_obj)
    assert dTobj1 < 1/256, f"expected Tobj[{idx}] close to {t_obj}, got {dTobj1}"
    n_passed += 1
    

    if dbg: libdbg.disp_htr_data(ABC.last_htr_data)
    # part (c) => put all back to original condition
    ABC.heater_def_tmp = _restore_tmp
    cmd = f"h.objective({ABC.heater_def_tmp}, idx=None)"
    ABC.safe_exec_abc(cmd, retries=3)
    time.sleep(0.65)
    if dbg:
        ret = ABC.get_heaters_status() # update info on heater status
        libdbg.disp_htr_data(ABC.last_htr_data)

    if n_passed == 2:
        print(f"{n_passed} -- OK")
        return True
    else:
        print(f"{n_passed} -- <2, failures")
        return False

def test_heaters_ini(ABC:ABCHandle, dbg:bool=True, idx:int=7) -> bool:
    # the state changes that `heaters_ini` performs are in relation
    # to the activation state, which is not directly observable.
    # 
    # what to test? the method a) should have all heaters de-activated
    # but b) the global thread activated; and c) ABC.heaters_status is True
    # 
    # for (a/b) We could do a sample-based test of one index:
    # - 1 call heaters_ini
    # - 2 set obj[idx] = T_amb+3
    # - 3 watch, check that pwm != 0 for n steps.
    # - 4 activate(idx)
    # - 5 watch, check that pwm rises within n steps
    # - 6 cleanup [deactivate(idx), check pwm stops]
    dT = 3
    timeout_s = 8
    dT_tol = 1/256
    n_passed = 0
    ok = True

    t0 = time.time()
    cframe = inspect.currentframe()
    fname = cframe.f_code.co_name
    # 1 - function under test, and test (c)
    tprint(f"--- starting {fname} --- ")
    ABC.heaters_ini()
    assert ABC.heaters_status == True, f"ABC.heaters_status should be true"
    n_passed += 1

    # 2 - set objective on one heater 
    # set all objectives off to be ready
    _restore_tmp, valid = _prep_htr_objectives_to_base_raw(ABC, dbg, basetmp=0, validate=True)

    # idx to T_amb + 3; wait; check
    dTobj1, t_obj = _prep_htr_set_obj_above_amb_raw(ABC, idx, dT=dT, dbg=dbg)
    assert dTobj1 < dT_tol, f"expected Tobj[{idx}] close to {t_obj}, got {dTobj1}"
    n_passed += 1
    if dbg: libdbg.disp_htr_data(ABC.last_htr_data)

    # 3 - check pwm stays == 0 for n steps. (ensure getting n steps data, set ok_test to always False)
    results_stayed_off = _helper_htr_measure_change(
        ABC, idx, lambda pwm_ix: False, 
        timeout_s//2, dbg)
    # what to do if it turned on? first, turn it off anyway.
    if max(results_stayed_off) > 0:
        msg = f"htr {idx} did not stay off! {results_stayed_off}."
        _prep_htr_objectives_to_base_raw(ABC)
        ok = False
    # then run assertion    
    assert max(results_stayed_off) == 0, f"expected htr {idx} to not heat, it was not activated! Got {results_stayed_off}"

    # 4 - activate the individual heater, and 5 - watch for heating
    pwm_results = _helper_htr_measure_activated_one(ABC, idx, timeout_s, dbg)

    # 6 - cleanup
    # part (e) => put back to original condition
    _prep_htr_deactivate_one_raw(ABC, idx, dbg)
    _prep_htr_objectives_to_base_raw(ABC, basetmp=_restore_tmp)
    _prep_htr_disable_global_thread_raw(ABC, dbg)
    # be sure that it turned off again
    results_turned_off = _helper_htr_measure_deactivated_one(ABC, idx, timeout_s, dbg)
    
    if min(results_turned_off) > 0:
        # mini freak out, the heater didn't disable. trigger a soft reset?
        msg = f"htr {idx} did not turn off! {results_turned_off}."
        ok = False
        _helper_reset_board(ABC, msg)

    elif dbg:
        ret = ABC.get_heaters_status() # update info on heater status
        libdbg.disp_htr_data(ABC.last_htr_data)

    # 7 - run assertion on heating phase
    if dbg: print(f"results of pwm [idx {idx}] (before activate):", results_stayed_off)
    assert (max(pwm_results) > 0), f"expecting nonzero pwm on {idx}, after {timeout_s} sec still [{pwm_results}]"
    if dbg: print(f"results of pwm [idx {idx}] (during activate):", pwm_results)
    assert (min(results_turned_off) == 0), f"expecting zero pwm on {idx}, after {timeout_s} sec still [{results_turned_off}]"
    if dbg: print(f"results of pwm [idx {idx}] (after  activate):", results_turned_off)

    elap = time.time() - t0
    tprint(f"{fname} passed in {elap:.2f}s")
    return ok


def test_heaters_deactivate_all(ABC:ABCHandle, dbg:bool=True) -> bool:
    '''
    what to expect? 
    - all heaters are deactivated
    - global thread is deactivated
    - self.heaters_status is False
    - all obj are 0

    # for (a/b) We could do a sample-based test of one index:
    # - 1 call disable_all
    # - 2 set obj[idx] = T_amb+3
    # - 3 watch, check that pwm != 0 for n steps.
    # - 4 activate(idx)
    # - 5 watch, check that pwm != 0 for n steps.
    # - 6 cleanup [clear obj[idx], deactivate(idx)]
    '''
    dT = 3
    timeout_s = 8
    dT_tol = 1/256
    idx = 5
    n_passed = 0
    ok = True
    t0 = time.time()
    cframe = inspect.currentframe()
    fname = cframe.f_code.co_name

    # 0 - enable global thread, 2 heaters, and 2 objectives -- some things for deactivate to turn off
    t_obj = 25.0
    idxs = [3,7]
    for i in idxs:
        _prep_htr_activate_one_raw(ABC, idx=i)
        _prep_htr_set_one_objective_raw(ABC, i, t_obj)
        # global activate, and status=>True
        _prep_htr_enable_global_thread_raw(ABC, enable=True)

    ret = ABC.get_heaters_status() # update info on heater status
    if dbg: libdbg.disp_htr_data(ABC.last_htr_data)
    t_exp = np.ones_like(ABC.last_htr_data.h_obj) * ABC.heater_def_tmp
    for i in idxs:
        t_exp[i] = t_obj

    dTobj = np.abs(ABC.last_htr_data.h_obj -  t_exp)
    assert np.all(dTobj < 1/256), f"expected all Tobj close to {ABC.heater_def_tmp}, worst is {dTobj.max()}"
    n_passed += 1
    tprint(f"{fname} initial setup done", True)


    # 1 - function under test, and test (c)
    ABC.heaters_deactivate_all()
    assert ABC.heaters_status == False, f"ABC.heaters_status should be false"
    n_passed += 1
    # 1.1 - check t_obj are all 0 (or whatever heater_def_tmp set to) 
    time.sleep(0.65)
    ret = ABC.get_heaters_status() # update info on heater status
    dTobj = np.abs(ABC.last_htr_data.h_obj -  ABC.heater_def_tmp)
    assert np.all(dTobj < 1/256), f"expected all Tobj close to {ABC.heater_def_tmp}, worst is {dTobj.max()}"
    n_passed += 1

    # 2 - set objective on one heater 
    # set all objectives off to be ready
    _restore_tmp, valid = _prep_htr_objectives_to_base_raw(ABC, dbg, basetmp=0, validate=True)

    # idx to T_amb + 3; wait; check
    dTobj1, t_obj = _prep_htr_set_obj_above_amb_raw(ABC, idx, dT=dT, dbg=dbg)
    assert dTobj1 < dT_tol, f"expected Tobj[{idx}] close to {t_obj}, got {dTobj1}"
    n_passed += 1
    if dbg: libdbg.disp_htr_data(ABC.last_htr_data)

    # 3 - check pwm stays == 0 for n steps. (ensure getting n steps data, set ok_test to always False)
    results_stayed_off = _helper_htr_measure_change(
        ABC, idx, lambda pwm_ix: False, 
        timeout_s//2, dbg)
    # what to do if it turned on? first, turn it off anyway.
    if max(results_stayed_off) > 0:
        msg = f"htr {idx} did not stay off! {results_stayed_off}."
        _prep_htr_objectives_to_base_raw(ABC)
        ok = False
    # then run assertion    
    assert max(results_stayed_off) == 0, f"expected htr {idx} to not heat, it was not activated! Got {results_stayed_off}"

    # 4 - activate the individual heater *but global thread is off*, and 5 - watch for no heating
    _prep_htr_activate_one_raw(ABC, idx, dbg)
    results_stayed_off_2 = _helper_htr_measure_change(
        ABC, idx, lambda pwm_ix: False, 
        timeout_s//2, dbg)
    # what to do if it turned on? first, turn it off anyway.
    if max(results_stayed_off_2) > 0:
        msg = f"htr {idx} did not stay off! {results_stayed_off_2}."
        _prep_htr_objectives_to_base_raw(ABC)
        ok = False
    # then run assertion    
    assert max(results_stayed_off_2) == 0, f"expected htr {idx} to not heat, it was not activated! Got {results_stayed_off_2}"

    # - 6 cleanup [clear obj[idx], deactivate(idx)
    _prep_htr_deactivate_one_raw(ABC, idx, dbg)
    _prep_htr_objectives_to_base_raw(ABC, basetmp=_restore_tmp)
    _prep_htr_disable_global_thread_raw(ABC, dbg)
    # be sure that it turned off again
    results_turned_off = _helper_htr_measure_deactivated_one(ABC, idx, timeout_s, dbg)
    
    if min(results_turned_off) > 0:
        # mini freak out, the heater didn't disable. trigger a soft reset?
        msg = f"htr {idx} did not turn off! {results_turned_off}."
        ok = False
        _helper_reset_board(ABC, msg)

    elif dbg:
        ret = ABC.get_heaters_status() # update info on heater status
        libdbg.disp_htr_data(ABC.last_htr_data)

    # 7 - run assertion on heating phase
    if dbg:
        print("[I] testing disable_all by re-enabling one heater while global thread is disabled.")
        print("[I] expect all pwm values to be 0..")
    if dbg: print(f"results of pwm [idx {idx}] (before activate):", results_stayed_off)
    assert (min(results_stayed_off_2) == 0), f"expecting pwm on {idx}, after {timeout_s} sec still [{results_stayed_off_2}]"
    if dbg: print(f"results of pwm [idx {idx}] (during activate):", results_stayed_off_2)
    assert (min(results_turned_off) == 0), f"expecting zero pwm on {idx}, after {timeout_s} sec still [{results_turned_off}]"
    if dbg: print(f"results of pwm [idx {idx}] (after  activate):", results_turned_off)

    tprint(f"{fname} tests done", {ok})
    return ok

def test_disable_all(ABC:ABCHandle, dbg:bool=True) -> bool:
    '''
    what to expect? 
    - all heaters are deactivated
    - global thread is deactivated
    - self.heaters_status is False

    # for (a/b) We could do a sample-based test of one index:
    # - 1 call disable_all
    # - 2 set obj[idx] = T_amb+3
    # - 3 watch, check that pwm != 0 for n steps.
    # - 4 activate(idx)
    # - 5 watch, check that pwm != 0 for n steps.
    # - 6 cleanup [clear obj[idx], deactivate(idx)]
    '''
    dT = 3
    timeout_s = 8
    dT_tol = 1/256
    idx = 5
    n_passed = 0
    ok = True

    # 1 - function under test, and test (c)
    ABC.disable_all()
    assert ABC.heaters_status == False, f"ABC.heaters_status should be false"
    n_passed += 1

    # 2 - set objective on one heater 
    # set all objectives off to be ready
    _restore_tmp, valid = _prep_htr_objectives_to_base_raw(ABC, dbg, basetmp=0, validate=True)

    # idx to T_amb + 3; wait; check
    dTobj1, t_obj = _prep_htr_set_obj_above_amb_raw(ABC, idx, dT=dT, dbg=dbg)
    assert dTobj1 < dT_tol, f"expected Tobj[{idx}] close to {t_obj}, got {dTobj1}"
    n_passed += 1
    if dbg: libdbg.disp_htr_data(ABC.last_htr_data)

    # 3 - check pwm stays == 0 for n steps. (ensure getting n steps data, set ok_test to always False)
    results_stayed_off = _helper_htr_measure_change(
        ABC, idx, lambda pwm_ix: False, 
        timeout_s//2, dbg)
    # what to do if it turned on? first, turn it off anyway.
    if max(results_stayed_off) > 0:
        msg = f"htr {idx} did not stay off! {results_stayed_off}."
        _prep_htr_objectives_to_base_raw(ABC)
        ok = False
    # then run assertion    
    assert max(results_stayed_off) == 0, f"expected htr {idx} to not heat, it was not activated! Got {results_stayed_off}"

    # 4 - activate the individual heater *but global thread is off*, and 5 - watch for no heating
    _prep_htr_activate_one_raw(ABC, idx, dbg)
    results_stayed_off_2 = _helper_htr_measure_change(
        ABC, idx, lambda pwm_ix: False, 
        timeout_s//2, dbg)
    # what to do if it turned on? first, turn it off anyway.
    if max(results_stayed_off_2) > 0:
        msg = f"htr {idx} did not stay off! {results_stayed_off_2}."
        _prep_htr_objectives_to_base_raw(ABC)
        ok = False
    # then run assertion    
    assert max(results_stayed_off_2) == 0, f"expected htr {idx} to not heat, it was not activated! Got {results_stayed_off_2}"

    # - 6 cleanup [clear obj[idx], deactivate(idx)
    _prep_htr_deactivate_one_raw(ABC, idx, dbg)
    _prep_htr_objectives_to_base_raw(ABC, basetmp=_restore_tmp)
    _prep_htr_disable_global_thread_raw(ABC, dbg)
    # be sure that it turned off again
    results_turned_off = _helper_htr_measure_deactivated_one(ABC, idx, timeout_s, dbg)
    
    if min(results_turned_off) > 0:
        # mini freak out, the heater didn't disable. trigger a soft reset?
        msg = f"htr {idx} did not turn off! {results_turned_off}."
        ok = False
        _helper_reset_board(ABC, msg)

    elif dbg:
        ret = ABC.get_heaters_status() # update info on heater status
        libdbg.disp_htr_data(ABC.last_htr_data)

    # 7 - run assertion on heating phase
    if dbg:
        print("[I] testing disable_all by re-enabling one heater while global thread is disabled.")
        print("[I] expect all pwm values to be 0..")
    if dbg: print(f"results of pwm [idx {idx}] (before activate):", results_stayed_off)
    assert (min(results_stayed_off_2) == 0), f"expecting pwm on {idx}, after {timeout_s} sec still [{results_stayed_off_2}]"
    if dbg: print(f"results of pwm [idx {idx}] (during activate):", results_stayed_off_2)
    assert (min(results_turned_off) == 0), f"expecting zero pwm on {idx}, after {timeout_s} sec still [{results_turned_off}]"
    if dbg: print(f"results of pwm [idx {idx}] (after  activate):", results_turned_off)

    return ok


    

def test_prepare_heaters(ABC:ABCHandle, dbg:bool=True) -> bool:
    raise NotImplementedError('coverage in test_heaters_ini')

    cframe = inspect.currentframe()
    fname = cframe.f_code.co_name
    ok = False
    ABC.heater_def_tmp = 1.1 # a bit arbitrary, recognisable after
    # expecting:
    # - all heaters to be disabled, 
    # - all objectives to be _def_tmp
    # - global thread to be enabled.
    # but the only thing we can directly check is the objective.
    # we can do a longer test:
    # 1. prepare_heaters()
    # 2. set obj_i = X, (X>ambient)
    # 3. activate htr_i = True 
    # 4. wait at least 2s, possibly 4s
    # 5. check pwm > 0
    # 6. 

    t0 = time.time()
    ret = ABC.prepare_heaters()
    elap = time.time() - t0
    if dbg:
        print(f"[D] {fname}, {ret}")
    assert len(ret) == 5, f"expecting 5 elements, got {len(ret)}"
    #for elem in ret:
    #    assert isinstance(elem, ndarray), f"expecting np.ndarray, got {type(elem)}"
    #    assert len(elem) == 10, f"expecting 10 points, got {len(elem)}"

    ok = True
    tprint(f"{fname} passed in {elap:.2f}s", ok)
    return ok 

def test_upy_ini(ABC:ABCHandle, dbg:bool=True) -> bool:
    # expecting:
    # - self.upy_status = True
    # - self._pyb to be Pyboard obj [not None]
    # - and all the other comands / tests that interact with board will work...
    # - check version to ensure that sthg is repsonsive on the MCU?
    #   micropython -c 'import sys ; print("PyLang", sys.version_info, ";", sys.implementation)'
    from src import pyboard
    cframe = inspect.currentframe()
    fname = cframe.f_code.co_name
    ok = False

    t0 = time.time()
    resp = ABC.upy_ini()
    elap1 = time.time() - t0
    assert isinstance(resp, pyboard.Pyboard)
    assert isinstance(ABC._pyb, pyboard.Pyboard)
    assert ABC.upy_status == True 
    cmd = 'import sys; print(sys.version_info, ";", sys.implementation)'
    expt_resp = "(3, 4, 0) ; (name='micropython', version=(1, 12, 0))"

    raw = ABC.safe_exec_abc(cmd, watermark=None)
    elap2 = time.time() - t0
    resp = raw.decode('utf-8').strip()
    if dbg:
        print(raw, resp, cmd)
    assert resp == expt_resp, f"ver check returned {resp}, expected ABC to respond with {expt_resp}"
    
    ok = True
    tprint(f"{fname} passed in {elap1:.2f} + {elap2:.2f}s", ok)
    
    return ok

def test_get_dt(ABC:ABCHandle, dbg:bool=True) -> bool:
    ok = False
    # expect a datetime object
    from datetime import datetime
    dt = ABC.get_datetime()
    assert isinstance(dt, datetime)

    ok = True

    return ok

def test_check_update_datetime(ABC:ABCHandle, dbg:bool=True) -> bool:
    # here we validate the fully-wrapped ABC method, which automatically
    # looks up the hostside time, compares, and re-defines on the mcu if
    # needed. 
    # See also `test_set_get_datetime` and `test_set_get_time` 
    #
    # a) put date into future
    # b) run `check_update_datetime`
    # c) compare whether current date/time is ok
    from datetime import timedelta
    # part (a): set date to be wrong
    tol = 1.5
    long_future = timedelta(days=3, minutes=0)
    _really_now = ABC.utcnow().replace(microsecond=0)
    now = _really_now + long_future
    
    cmd = f's.set_date({now.year:d},{now.month:d},{now.day:d})'
    _ = ABC.safe_exec_abc(cmd, minlen=0)  # no response expected
    cmd = f's.set_time({now.hour:d},{now.minute:d},{now.second:d})'
    _ = ABC.safe_exec_abc(cmd, minlen=0)  # no response expected
    time.sleep(0.2) 
    newtime = ABC.get_datetime()
    dt = now - newtime
    msg = f"Test setup: Brood RTC adjusted to {long_future}: {newtime}, tgt: {now}, diff: {dt} "
    libdbg.cprint(msg)

    # part (b) => run automatic method
    ABC.check_update_datetime()

    # part (c) => compare if the date is basically now.
    now = ABC.utcnow().replace(microsecond=0)
    mcu_now = ABC.get_datetime()
    dt2 = (now-mcu_now).total_seconds()
    if dbg: libdbg.cprint(f"ABC timestamp now {mcu_now}, delta: {dt2:.3f}")

    assert abs(dt2) < tol, f"expecting time to be closer than {tol}, got {dt2}"

    return True

def test_set_get_datetime(ABC:ABCHandle, dbg:bool=True) -> bool:
    # only difference from test_set_get_time is that here we 
    #  must adjust the date and the time

    # set the date to future (days)
    # read back the date
    # check it is within tol seconds of the set date.
    # set it back to really now
    from datetime import datetime, timedelta
    tol = 1.5
    long_future = timedelta(days=3, minutes=0)
    _really_now = ABC.utcnow().replace(microsecond=0)
    now = _really_now + long_future
    
    cmd = f's.set_date({now.year:d},{now.month:d},{now.day:d})'
    _ = ABC.safe_exec_abc(cmd, minlen=0)  # no response expected
    cmd = f's.set_time({now.hour:d},{now.minute:d},{now.second:d})'
    _ = ABC.safe_exec_abc(cmd, minlen=0)  # no response expected
    time.sleep(0.2) 
    newtime = ABC.get_datetime()
    dt = now - newtime
    msg = f"Brood RTC adjusted to: {newtime}, tgt: {now}, diff: {dt} "
    libdbg.cprint(msg)

    assert abs(dt.total_seconds()) < tol, f"expecting time to be closer than {tol}, got {dt}"

    now = _really_now
    cmd = f's.set_date({now.year:d},{now.month:d},{now.day:d})'
    _ = ABC.safe_exec_abc(cmd, minlen=0)  # no response expected
    cmd = f's.set_time({now.hour:d},{now.minute:d},{now.second:d})'
    _ = ABC.safe_exec_abc(cmd, minlen=0)  # no response expected
    time.sleep(0.2) 
    newtime = ABC.get_datetime()
    dt = now - newtime
    msg = f"Brood RTC adjusted back to: {newtime}, diff: {dt} "
    libdbg.cprint(msg)
    return True 

def test_set_get_time(ABC:ABCHandle, dbg:bool=True) -> bool:
    # set the date to future in the future
    # read back the date
    # check it is within tol seconds of the set date.
    # set it back to really now
    from datetime import datetime, timedelta
    tol = 1.5
    short_future = timedelta(minutes=5)
    _really_now = ABC.utcnow().replace(microsecond=0)
    now = _really_now + short_future
    
    cmd = f's.set_time({now.hour:d},{now.minute:d},{now.second:d})'
    _ = ABC.safe_exec_abc(cmd, minlen=0)  # no response expected
    time.sleep(0.2) 
    newtime = ABC.get_datetime()
    dt = now - newtime
    msg = f"Brood RTC adjusted to: {newtime}, tgt: {now}, diff: {dt} "
    libdbg.cprint(msg)

    assert abs(dt.total_seconds()) < tol, f"expecting time to be closer than {tol}, got {dt}"

    now = _really_now
    cmd = f's.set_time({now.hour:d},{now.minute:d},{now.second:d})'
    _ = ABC.safe_exec_abc(cmd, minlen=0)  # no response expected
    time.sleep(0.2) 
    newtime = ABC.get_datetime()
    dt = now - newtime
    msg = f"Brood RTC adjusted back to: {newtime}, diff: {dt} "
    libdbg.cprint(msg)
    return True 





def consume_mem_pct(ABC:ABCHandle, tgt_pct:float=95):
    # 'hf.callformatprint(h.status)', -> 12%
    # 1.09%	(s.get_rht) 
    # 1.09%	(s.get_mcu_uuid)
    #m_prev = ABC.get_mem_status()
    m_now = ABC.get_mem_status()
    m_prev = m_now.copy()

    while m_now['pct'] < tgt_pct - 12.0:
        cmd = 'hf.callformatprint(h.status)'
        resp_raw = ABC.safe_exec_abc(cmd, retries=3, watermark=None)
        m_now = ABC.get_mem_status()
        dx = m_now['pct'] - m_prev['pct']
        print(f"{m_now['pct']:.2f}% (dx {dx:.2f}%)")
        m_prev = m_now.copy()
    
    while m_now['pct'] < tgt_pct:
        cmd = 'hf.callformatprint(s.get_rht)'
        resp_raw = ABC.safe_exec_abc(cmd, retries=3, watermark=None)
        m_now = ABC.get_mem_status()
        dx = m_now['pct'] - m_prev['pct']
        print(f"{m_now['pct']:.2f}% (dx {dx:.2f}%)")
        m_prev = m_now.copy()
    
    return m_now['pct']


    


    pass

if __name__ == "__main__":
    parser = libui.abc_parser() # use default ABC parser
    parser.add_argument('-s', '--silent', action='store_true')
    parser.add_argument('-g', '--test_gc', action='store_true')
    args = parser.parse_args()

    libui.verify_abc_cfg_file(args) # lookup config based on hostname

    ABC = ABCHandle(args.cfg) # instantiate ABC object

    t_htr_list = [
        test_set_htr_obj,
        test_set_htr_active,
        test_set_heater_active,
        test_set_heater_inactive,
        test_heaters_ini,
        #test_disable_all,
        test_heaters_deactivate_all,

    ]
    t_new_list = [
        #test_heaters_deactivate_all, 
        test_set_heater_inactive] 

    t_v_slow_snsr_list = [
        #test_reset_temp_offsets,
        test_get_sensor_interval,
    ]

    t_base_list = [test_get_temp_offset, 
               test_get_power_str, test_get_co2_str, test_get_rht_str,
               test_get_int_temps, 
               test_get_heaters_status,
               test_get_one_htr_obj,
               test_upy_ini,
               test_get_mcu_id,
               test_get_dt,
              # test_set_get_time, test_set_get_datetime,
              # test_check_update_datetime,

              ]
    #t_list = t_base_list + t_v_slow_snsr_list
    t_list = t_base_list + t_htr_list
    #t_list = t_htr_list
    #t_list = t_new_list 
    n_passed = 0
    n_tests = len(t_list)
    #outcomes = [None for i in range(n_tests)]
    outcomes = {}

    dbg = True

    try:
        ABC.first_conn()
        if args.silent:
            ABC.logger.log2stdout = False
        
        tprint(f"==== starting {len(t_list)} tests ====")

        for i, tst in enumerate(t_list):
            # TODO: pre-fill the mem to 95% [different type of test]
            if args.test_gc: 
                consume_mem_pct(ABC, 97)
            r = False
            try:
                r = tst(ABC=ABC, dbg=dbg)
            except AssertionError as e:
                print(f"{RED}[W]{tst.__name__} failed '{e}' {ENDC}")
            if r:
                n_passed += 1
            #outcomes[i] = r
            outcomes[tst.__name__] = r

        tprint(f"==== finished {len(t_list)} tests ====")


    except KeyboardInterrupt:
        ABC.log("Stopping collection - ctrl-c pressed.", level="INF")

    finally:
        # Disconnect from ABC gracefully
        ABC.stop(end_msg='Done.')

        for k, v in outcomes.items():
            print(f"  {k:30} : {v}")

        #print(outcomes)
        print(f"[I] {n_passed} of {n_tests} passed.")
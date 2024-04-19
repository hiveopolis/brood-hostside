'''
Some functions and boiler-plate code used in interfaces for ABC instances.


'''
import argparse
import platform
from pathlib import Path

from .libabc import ABCTooShortRespError, ABCGarbledRespError

# {{{ handle_known_exceptions
def handle_known_exceptions(e, logger=None, verb=True):
    '''
    various errors come up with long interactions with the upy board, here
    we try to handle some of the harmless ones.

    - print a message to logger.
    - return False if ok to continue, True if fatal and we should halt

    '''
    # if stream is None:
    #     stream = sys.stdout
    if isinstance(e, ABCTooShortRespError):
        msg = f"[I][hke] exception is due to bad read from host, attempt to continue.\n\t{e}"  # noqa: E501
        if verb:
            print(msg)

        if logger is not None:
            logger(msg, level="EXC")

        return False
    
    elif isinstance(e, ABCGarbledRespError):
        msg = f"[I][hke] exception is due to bad read (garbage collection), attempt to continue\n\t{e}" # noqa: E501
        if verb:
            print(msg)

        if logger is not None:
            logger(msg, level="EXC")

        return False

    elif len(e.args):
        if "GC:" in e.args[0]:
            msg = f"[I][hke] exception comes from garbage collection on uPython MCU. Ignoring. \n\t{e.args[0]}"  # noqa: E501
            if verb:
                print(msg)

            if logger is not None:
                logger(msg, level="EXC")

            return False

        elif "exception int() argument must be a" in e.args[0]:
            # exception int() argument must be a string, a bytes-like object or a number, not 'NoneType' occured in loop 1052  # noqa: E501

            msg = f"[I][hke] exception comes from a single bad read, we can try continue.Ignoring. \n\t{e.args[0]}"  # noqa: E501
            if verb:
                print(msg)

            if logger is not None:
                logger(msg, level="EXC")

            return False

    return True
# }}}

# {{{ lookfor_cfgfile
def lookfor_cfgfile(pth=None, debug=False):
    '''
    default location is <dir of tool>/cfg
    expected filename pattern is <pth>/<hostname>[.somext],
    (where the extension might be .ini, .conf, .cfg, but is not required.)

    file default pattern is hostname
    returns a Path object, or None if not found

    '''
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

    print(f"[W] failed to identify config for host {hostname} in path {pth}")
    return None
# }}}

# from libabc import ABCHandle
# def reconnect_abc(ABC: ABCHandle, fp_cfg: Path) -> ABCHandle:
#     """Reconnect the board."""
#     ABC.stop()
#     ABC = ABCHandle(fp_cfg)
#     ABC.first_conn()
#     return ABC

def abc_parser():
    ''' construct argparse object for ABC configs '''
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--debug', action='store_true')
    parser.add_argument('-v', '--verb', action='store_true')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-c', '--cfg', type=Path, default=None)
    group.add_argument('-a', '--auto-config-lookup', action="store_true")
    parser.add_argument('-n', '--num', type=int, default=4)

    return parser

def verify_abc_cfg_file(args): 
    ''' Check if config file exists, or attempt to lookup based on hostname '''
    if args.cfg is None:
        args.cfg = lookfor_cfgfile(debug=args.debug)

    if args.cfg is not None:
        args.cfg = args.cfg.expanduser()
        if not args.cfg.is_file():
            raise FileNotFoundError(f"No config file found at '{args.cfg}'!")
    else:
        raise FileNotFoundError("No config file found!")

    return True


def process_exception(is_bad_err, e, ABC):
    '''
    if the exception is unknown, or known to be very bad, log it and re-raise
    else, just print some information to the user. (The latter case includes 
    ABCGarbledRespError, for example).
    '''
    if is_bad_err:
        msg = f"    exception {e} occured in loop {ABC.i}"
        ABC.log(msg, level='EXC')
        print("[F] " + "==="*20) # get some attention... only to screen
        print(msg)
        raise(e)
        return False # wouldn't ever reach here...

    else:
        # Not critical, let's continue.
        msg = f"    harmless exception {e} occured in loop {ABC.i}"
        ABC.log(msg, level='EXC')
        print("[I] " + "==="*20)
        print(msg)
        return True

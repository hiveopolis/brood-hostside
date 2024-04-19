#!/usr/bin/env python3
'''
Interface script to sample & log from ABC board periodically, as per config.

Supply a configuration file or use -a flag to lookup based on hostname
'''

from brood_hostside.libabc import ABCHandle 
from brood_hostside import libui

if __name__ == "__main__":
    parser = libui.abc_parser() # use default ABC parser
    args = parser.parse_args()

    libui.verify_abc_cfg_file(args) # lookup config based on hostname

    ABC = ABCHandle(args.cfg) # instantiate ABC object

    dt_today = ABC.get_dt_day(ABC.utcnow()) # get date for rolling log files

    try:
        ABC.first_conn()
        while True:
            # Check for new day (to roll over logfiles)
            ABC.check_newday_and_roll_logfiles()

            try:
                ABC.loop()
            except Exception as e:
                # Try catching everything, so it can continue if not critical
                is_bad_err = libui.handle_known_exceptions(e, logger=ABC.log)
                libui.process_exception(is_bad_err, e, ABC)

    except KeyboardInterrupt:
        ABC.log("Stopping collection - ctrl-c pressed.", level="INF")

    finally:
        # Disconnect from ABC gracefully
        ABC.stop(end_msg='Done.')


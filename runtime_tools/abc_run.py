#!/usr/bin/env python3
'''
Interface script to execute actuators, and sample & log from ABC board periodically.

Supply a configuration file or use -a flag to lookup based on hostname
'''

from brood_hostside.libabc import ABCHandle 
from brood_hostside import libui


if __name__ == "__main__":
    parser = libui.abc_parser() # use default ABC parser
    args = parser.parse_args()

    libui.verify_abc_cfg_file(args) # lookup config based on hostname

    ABC = ABCHandle(args.cfg) # instantiate ABC object

    try:
        ABC.first_conn()
        # Prepare heaters to be activated...
        ABC.prepare_heaters(False)
        # ...and start any defined in cfgfile
        if len(ABC.active_heaters) > 0:
            ABC.log(f"Will activate {len(ABC.active_heaters)}", level="DBG")
            ABC._activate_dict_of_heaters(ABC.active_heaters)
        else:
            ABC.log(f"No heaters activated - {len(ABC.active_heaters)} in cfg",
                    level="DBG")

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
        # Deactivate heaters
        # NOTE: This causes more harm than good during an
        #       experiment, when e.g. the script fails due
        #       to the SD card becoming unwritable:
        #       The ABC will be unnecessarily deactivated!
        ABC.log("Deactivating all heaters before stop.")
        ABC.heaters_deactivate_all()
        # Disconnect from ABC gracefully
        ABC.stop(end_msg='Done.')



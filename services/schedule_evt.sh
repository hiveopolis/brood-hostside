#!/bin/bash

# Working directory
# wd="/home/pi/"
# wd="${HOME}"
wd="/home/pi/repo-abc/services"

# Help message
# https://stackoverflow.com/questions/10969953/how-to-output-a-multiline-string-in-bash
__usage="
Usage: bash $(basename $0) TIME_UTC COMMAND

Arguments:
  TIME_UTC      time (in UTC) when to trigger the event
                (format: \"YYYY-MM-DD HH:MM:SS\")
  COMMAND       command to execute at the specified time
                (working directory is \"${wd}\")

Examples:
  To run a bash-script '${wd}/update_cfg.sh' at 12:34:56 UTC
  on 24 Dec 2021:

    bash $(basename $0) \"2023-12-24 12:34:56\" \"bash update_cfg.sh\"

  To check on the timer, run (NOTE: Don't use 'sudo'!):

    systemctl --user status run-r....timer

  To stop it, you can similarly run:

    systemctl --user stop run-r....timer
"

function show_help() {
    # str1="Usage: bash `basename $0` "
    # str1+="TIME_UTC [format: \"YYYY-MM-DD HH:MM:SS\"] "
    # str1+="COMMAND [e.g. \"bash switch_default.sh\"]"

    # str2+="(Working directory is \"${wd}\".)"
    # # echo -e "${str1}\n\n${str2}"
    # printf "${str1}\n\n${str2}\n"
    printf "${__usage}"
}

# If called without args, show help
if [ "$1" = "" ]; then
    show_help
    # printf "${__usage}"
    exit
else
    # Parse args and schedule command
    # t_trigger="2021-12-13 10:59:59 UTC"
    t_trigger="$1 UTC"
    cmd="$2"

    echo "Scheduling command \"${cmd}\" for ${t_trigger}."

    # Set up a transient systemd-timer to schedule the command
    systemd-run --user \
        --on-calendar "${t_trigger}" \
        --timer-property=AccuracySec=100ms \
        --working-directory="${wd}" \
        ${cmd}
fi

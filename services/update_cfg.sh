#!/bin/bash

# Use this in conjunction with `schedule_evt.sh`

# Example:
# bash schedule_evt.sh "2023-01-13 23:59:00" "bash update_cfg.sh"

timestamp="$(date +%y%m%d-%H%M%S)-utc"
dir_repo=/home/pi/repo-abc/
#dir_repo="~/repo-abc/"

# Update repository
logdir=/home/pi/log/scheduling
mkdir -p $logdir
fn_gitlog=${logdir}/log-git_${timestamp}.log
cd "${dir_repo}"
# git pull
git pull -v >> "${fn_gitlog}"
echo -e "\nBranch: ${git branch}\n\n" >> "${fn_gitlog}"
cd ~

# Restart service
# sudo systemctl restart abc_run.service > "log-sysd_${timestamp}-utc.log"
fn_sysdlog=${logdir}/log-sysd_${timestamp}.log
#fn_sysdlog="~/log-sysd_${timestamp}.log"
sudo systemctl status -l abc_run.service >> "${fn_sysdlog}"
sudo systemctl restart abc_run.service >> "${fn_sysdlog}"
echo -e "\nRestarted abc_run.service.\n\n" >> "${fn_sysdlog}"
sudo systemctl status -l abc_run.service >> "${fn_sysdlog}"

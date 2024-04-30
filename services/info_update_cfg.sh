#!/bin/bash

# Use this in conjunction with `schedule_evt.sh`
#
# NOTE: should have OK_WEBHOOK_URL defined in the environment

# Example:
# bash schedule_evt.sh "2023-01-13 23:59:00" "bash update_cfg.sh"

#"color": "#34808c"
# see gist https://gist.github.com/apfzvd/300346dae55190e022ee49a1001d26af
generate_post_data() {
  cat <<EOF
{
  "content": "$1",
  "embeds": [{
    "title": "OK update_cfg.sh (on $(hostname))",
    "description": "$2 ",
    "color": "3440780"
  }]
}
EOF
}

timestamp="$(date +%y%m%d-%H%M%S)-utc"
dir_repo=/home/pi/repo-abc/
#dir_repo="~/repo-abc/"

# Update repository
logdir=/home/pi/log/scheduling
mkdir -p $logdir
fn_gitlog=${logdir}/log-git_${timestamp}.log
echo "[I] cd to ${dir_repo}"
cd "${dir_repo}"
echo "[I] now in pwd: $(pwd)"

# git pull
git pull -v >> "${fn_gitlog}"
br=$(git rev-parse --abbrev-ref HEAD)
hash=$(git rev-parse --short HEAD)

echo -e "\nBranch: ${br}\n\n" >> "${fn_gitlog}"
cd ~

#exit 0

# Restart service
# sudo systemctl restart abc_run.service > "log-sysd_${timestamp}-utc.log"
fn_sysdlog=${logdir}/log-sysd_${timestamp}.log
#fn_sysdlog="~/log-sysd_${timestamp}.log"
sudo systemctl status -l abc_run.service >> "${fn_sysdlog}"
sudo systemctl restart abc_run.service >> "${fn_sysdlog}"
echo -e "\nRestarted abc_run.service.\n\n" >> "${fn_sysdlog}"
sudo systemctl status -l abc_run.service >> "${fn_sysdlog}"


text="[I] config updated (branch: ${br}). $(hostname). ${timestamp}"
t2="$0 -> ${hash}"
# quote it here, to keep it as arg 1
msg=$(generate_post_data "$text" "$t2")
echo "[D] the message to transmit is: \n\t${msg}"

if [[ ! -z "${OK_WEBHOOK_URL}" ]]; then
    # webhook defined, let's send
    # POST request to Discord Webhook
    curl -H "Content-Type: application/json" -X POST -d "${msg}" $OK_WEBHOOK_URL
    rv=$?
    echo "[I] curl push: $?"
fi







Usage notes for library
=======================

The package is well managed using systemd service units, and automatic selection
of configuration files (implemented via hostname lookup).  However, if one
desires a simpler interaction, e.g. for prototyping a new controller, it is
possible to run the code directly on a host. For session persistence, we suggest
using `screen` or `tmux`.


Basic usage for prototyping
---------------------------

Typically run this inside a screen or tmux session

```bash
# login to host with the robotic frame attached
ssh <hostname> 
# start a new, named screen session
screen -S board04
# go to runtime code directory
cd software/broodnest/runtime_tools
python3 abc_read.py -c cfg/my_cfg04.cfg
```

Stop recording with <kbd>ctrl-C</kbd>, it exits cleanly.


Some quick notes about `screen`:
--------------------------------


* detach from session, leaving it running: <kbd>ctrl-A</kbd>, <kbd>d</kbd>
* close session, especially if behaving badly: <kbd>ctrl-A</kbd>, <kbd>k</kbd>, then <kbd>y</kbd>
* close session: <kbd>ctrl-D</kbd> (as per closing any shell)

* check what sessions are running: `screen -ls`
* reattach to a specific screen session: `screen -r <session name>`, e.g. `screen -r board04`
* reattach to a specific session, if somehow it is still open `screen -Dr <session name>`

* scroll up within session (see history!/more than a few lines of error!):
     * <kbd>ctrl-A</kbd>, <kbd>q</kbd>, use mouse wheel or arrow keys. 
     * Press <kbd>Esc</kbd>, to go back to regular mode.


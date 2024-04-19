# udev rules for consistent tty port mappings


## What it does

When the specific brood board is plugged into that linux machine, a symlink will be
generated inside /dev. This allows consistently attaching to a specific brood board,
even if the ttyACMx or ttyUSBx or ttyAMAx value changes (this can happen when other
devices are plugged in first, or a device is reset, etc).

For example, the first board will appear as

        /dev/brood_abc01

On inspection, we see the link is simply to /dev/ttyACM0 in this case.

        ll /dev/brood_abc01
        lrwxrwxrwx 1 root root 7 Jul 27 10:20 /dev/brood_abc01 -> ttyACM0


## Installation

The rules contained in 99-usb-mobots.rules should be placed into `/etc/udev/rules.d/`.

        # Put rules in place
        sudo cp 99-usb-mobots.rules /etc/udev/rules.d/
        # Trigger them
        sudo udevadm control --reload-rules && sudo udevadm trigger

If any changes are made to the config rules, they can be reloaded without a restart
using

        sudo udevadm control --reload-rules && sudo udevadm trigger

However note that any connected devices will not have shortcuts generated until
they are next re-connected (or the system is restarted).

### Trigger one device recognition

Note that the rules can be tested for a specific device, and on RPi it seems to 
persist (not just report test results; a symlink shortcut appears, e.g. /dev/abc99).

        sudo udevadm test $(udevadm info --query=path --name=ttyACM0)

**However WARNING**: if multiple udev rules are used (e.g. multiple modules in
the HO core system), using this test will clear all other symlinks. So you can
only have one device of interest with this way.  If there are many, just
re-plug the devices (or if not feasible, maybe a reboot is possible).




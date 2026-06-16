#!/usr/bin/env python3
"""Map Mycroft Mark II SJ-201 top buttons to MPD (FIP radio) controls."""
import os, subprocess, time
from evdev import InputDevice, ecodes, list_devices

DEVNAME = "soc:sj201_buttons"
ACT = "/run/fip-activity"   # idle-watchdog interaction stamp (bandwidth saver)


def mpc(*args):
    try:
        subprocess.run(["mpc", *args], timeout=5,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


def stamp():
    try:
        os.utime(ACT, None)
    except Exception:
        pass


def is_stopped():
    """True only when MPD is fully stopped (idle auto-stop), not just paused."""
    try:
        out = subprocess.run(["mpc", "status"], capture_output=True, text=True,
                             timeout=5).stdout
        return "[playing]" not in out and "[paused]" not in out
    except Exception:
        return False


def find_dev():
    for path in list_devices():
        try:
            d = InputDevice(path)
            if d.name == DEVNAME:
                return d
        except Exception:
            pass
    return None


def main():
    dev = None
    while dev is None:                      # wait for the input device to appear
        dev = find_dev()
        if dev is None:
            time.sleep(2)
    print(f"listening on {dev.path} ({dev.name})", flush=True)
    for ev in dev.read_loop():
        if ev.type != ecodes.EV_KEY:
            continue
        # value: 1=down, 2=autorepeat, 0=up
        if ev.value not in (1, 2):
            continue
        stamp()                          # any press counts as "someone's here"
        if ev.code == ecodes.KEY_VOLUMEUP:
            if is_stopped():
                mpc("play")              # resume from idle auto-stop
            mpc("volume", "+5")
        elif ev.code == ecodes.KEY_VOLUMEDOWN:
            if is_stopped():
                mpc("play")
            mpc("volume", "-5")
        elif ev.code == ecodes.KEY_VOICECOMMAND and ev.value == 1:   # top action button
            mpc("toggle")                # from stopped -> plays; from playing -> pauses
        elif ev.code == ecodes.KEY_MICMUTE and ev.value == 1:        # mute slider
            mpc("toggle")


if __name__ == "__main__":
    main()

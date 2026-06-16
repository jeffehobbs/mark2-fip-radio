#!/usr/bin/env python3
"""Bandwidth saver: stop the FIP stream after a stretch with no button/touch
interaction, so we're not streaming to an empty room. `mpc stop` (not pause)
actually closes the connection. Any button/tap resumes it (see buttons/pygame).

Idle timeout (seconds) is read from /opt/fipradio/idle_timeout if present,
else defaults to 2 hours.
"""
import os, time, subprocess

ACT = "/run/fip-activity"
DEFAULT_IDLE = 2 * 3600


def idle_secs():
    try:
        return int(open("/opt/fipradio/idle_timeout").read().strip())
    except Exception:
        return DEFAULT_IDLE


def mpc(*a):
    try:
        return subprocess.run(["mpc", *a], capture_output=True, text=True,
                              timeout=6).stdout
    except Exception:
        return ""


def main():
    # World-writable stamp so root (buttons) and the desktop user (touch) can both update it.
    if not os.path.exists(ACT):
        try:
            open(ACT, "a").close()
        except Exception:
            pass
    try:
        os.chmod(ACT, 0o666)
        os.utime(ACT, None)        # start the clock now, not at epoch 0
    except Exception:
        pass
    while True:
        time.sleep(60)
        try:
            if "[playing]" in mpc("status") and \
               time.time() - os.path.getmtime(ACT) > idle_secs():
                mpc("stop")        # release the FIP connection
        except Exception:
            pass


if __name__ == "__main__":
    main()

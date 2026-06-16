#!/usr/bin/env python3
"""Mark II SJ-201 LED ring: shows MPD volume as a 12-LED gauge (100%=all 12,
0%=none), and mutes the TAS5806 amp (HiZ) when not playing to avoid idle hiss.
Run as a short-lived process so HwPwmAwareLed restores the fan PWM on exit."""
import sys, subprocess
sys.path.insert(0, "/opt/fipradio/sj201-interface")
from sj201_interface.led import R10Led, HwPwmAwareLed

PINK = (230, 0, 90)
OFF = (0, 0, 0)
N = 12


def mpd_state():
    try:
        out = subprocess.run(["mpc", "status"], capture_output=True, text=True,
                             timeout=5).stdout
    except Exception:
        return False, 0
    playing = "[playing]" in out
    vol = 0
    for line in out.splitlines():
        if line.startswith("volume:"):
            tok = line.split()[1].rstrip("%")
            if tok.isdigit():
                vol = int(tok)
    return playing, vol


def set_amp(playing):
    state = "0x03" if playing else "0x02"   # PLAY vs HiZ(mute)
    try:
        subprocess.run(["i2cset", "-y", "1", "0x2f", "0x03", state], timeout=5,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else "auto"
    playing, vol = mpd_state()
    if arg == "off":            # service stop: dark + mute
        playing, vol = False, 0
    set_amp(playing)
    lit = int(round(vol / 100.0 * N))
    led = HwPwmAwareLed(R10Led())
    for i in range(N):
        led.set_led(i, PINK if i < lit else OFF, immediate=False)
    led.show()


if __name__ == "__main__":
    main()

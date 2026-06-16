#!/usr/bin/env python3
"""Deterministic fan controller for Mycroft Mark II SJ-201.

PWM is inverted (255=off, 0=full). Keeps the fan OFF during normal use and
only ramps it when the chip gets genuinely hot, so the unit stays silent.
Honors a manual override written by the `fan` CLI at /run/fipfan.
"""
import glob, os, time

OFF_BELOW = 68.0     # °C — fan fully off below this
FULL_ABOVE = 80.0    # °C — fan full speed above this
OVERRIDE = "/run/fipfan"


def hwmon():
    for d in glob.glob("/sys/class/hwmon/hwmon*"):
        try:
            if open(d + "/name").read().strip() == "pwmfan":
                return d
        except Exception:
            pass
    return None


def cpu_temp():
    try:
        return int(open("/sys/class/thermal/thermal_zone0/temp").read()) / 1000.0
    except Exception:
        return 50.0


def auto_pwm(t):
    if t < OFF_BELOW:
        return 255
    if t >= FULL_ABOVE:
        return 0
    frac = (t - OFF_BELOW) / (FULL_ABOVE - OFF_BELOW)   # 0..1 hot
    return int(round(255 * (1 - frac)))                 # inverted


def raise_kernel_trips():
    # Stop the kernel pwm-fan cooling device from fighting us at idle.
    for p in glob.glob("/sys/class/thermal/thermal_zone0/trip_point_*_temp"):
        try:
            if int(open(p).read()) < 90000:   # leave the 110°C critical trip alone
                open(p, "w").write("85000")
        except Exception:
            pass


def write(path, val):
    try:
        open(path, "w").write(str(val))
    except Exception:
        pass


def main():
    h = hwmon()
    if not h:
        return
    raise_kernel_trips()
    while True:
        mode = "auto"
        try:
            if os.path.exists(OVERRIDE):
                mode = open(OVERRIDE).read().strip().lower()
        except Exception:
            pass
        if mode == "off":
            pwm = 255
        elif mode == "full":
            pwm = 0
        elif mode.isdigit():
            pct = max(0, min(100, int(mode)))
            pwm = 255 - round(pct * 255 / 100)
        else:
            pwm = auto_pwm(cpu_temp())
        write(h + "/pwm1_enable", 1)   # manual: we own the PWM
        write(h + "/pwm1", pwm)
        time.sleep(5)


if __name__ == "__main__":
    main()

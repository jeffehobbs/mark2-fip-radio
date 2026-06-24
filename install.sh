#!/usr/bin/env bash
#
# mark2-fip-radio installer — turns a Mycroft Mark II (SJ-201 Rev10, Raspberry Pi 4)
# running stock Raspberry Pi OS into a FIP internet radio with a now-playing screen.
#
# Brings up BOTH layers in one shot:
#   1. Hardware: speakers (TAS5806 amp), fan control, top buttons, LED ring, DSI screen
#   2. App: MPD playing FIP + pygame now-playing display + LED volume gauge
#
# Run as root on the device:  sudo ./install.sh
#
set -euo pipefail

REPO="$(cd "$(dirname "$0")" && pwd)"
APP=/opt/fipradio
DKMS_VER=0.0.2
BOOT=/boot/firmware/config.txt
[ -f "$BOOT" ] || BOOT=/boot/config.txt   # older layouts

if [ "$(id -u)" -ne 0 ]; then echo "Run with sudo."; exit 1; fi
USER_NAME="${SUDO_USER:-pi}"
USER_UID="$(id -u "$USER_NAME")"
echo ">> Installing for desktop user: $USER_NAME (uid $USER_UID)"

echo ">> [1/9] Installing packages..."
apt-get update -qq
apt-get install -y -qq \
  git curl build-essential device-tree-compiler dkms i2c-tools \
  "linux-headers-$(uname -r)" raspberrypi-kernel-headers \
  mpd mpc \
  python3-venv python3-pygame python3-pil python3-numpy fonts-inter \
  || true   # one of the headers package names will not exist; that's fine

echo ">> [2/9] Building the SJ-201 audio driver (vocalfusion-soundcard, DKMS)..."
if ! dkms status | grep -q vocalfusion-soundcard; then
  rm -rf /tmp/VocalFusionDriver
  git clone --depth 1 https://github.com/OpenVoiceOS/VocalFusionDriver /tmp/VocalFusionDriver
  SRC=/usr/src/vocalfusion-soundcard-$DKMS_VER
  mkdir -p "$SRC"
  cp /tmp/VocalFusionDriver/driver/{Makefile,vocalfusion-soundcard.c,dkms.conf} "$SRC/"
  dkms add     -m vocalfusion-soundcard -v $DKMS_VER || true
  dkms build   -m vocalfusion-soundcard -v $DKMS_VER
  dkms install -m vocalfusion-soundcard -v $DKMS_VER
fi
echo vocalfusion-soundcard > /etc/modules-load.d/vocalfusion-soundcard.conf

echo ">> [3/9] Compiling device-tree overlays..."
OVL=$(dirname "$BOOT")/overlays
for f in sj201 sj201-rev10-pwm-fan-overlay sj201-buttons-overlay; do
  dtc -@ -H epapr -O dtb -o "$OVL/$f.dtbo" -Wno-unit_address_vs_reg "$REPO/overlays/$f.dts"
done

echo ">> [4/9] Patching $BOOT..."
cp -n "$BOOT" "$BOOT.mark2.bak" || true
sed -i 's/^display_auto_detect=1/display_auto_detect=0/' "$BOOT"   # DSI panel is pinned below
if ! grep -q "Mycroft Mark II SJ-201 (FIP radio)" "$BOOT"; then
  cat "$REPO/config/config.txt.block" >> "$BOOT"
fi

echo ">> [5/9] Installing the app to $APP..."
install -d "$APP"
install -m755 "$REPO"/app/*.py "$REPO"/app/*.sh "$APP/"
# default idle timeout (seconds) for the bandwidth saver — 5m; tune by editing this file
[ -f "$APP/idle_timeout" ] || echo 300 > "$APP/idle_timeout"
if [ ! -d "$APP/venv" ]; then
  python3 -m venv --system-site-packages "$APP/venv"
fi
"$APP/venv/bin/pip" install -q --upgrade pip
"$APP/venv/bin/pip" install -q -r "$REPO/requirements.txt"
# LED ring helper (HwPwmAwareLed) — keeps LED PWM from disturbing the fan PWM
if [ ! -d "$APP/sj201-interface" ]; then
  git clone --depth 1 -b dev https://github.com/NeonGeckoCom/sj201-interface "$APP/sj201-interface"
fi

echo ">> [6/9] Installing CLI tools (fan, tas5806-init)..."
install -m755 "$REPO/bin/fan" "$REPO/bin/tas5806-init" /usr/local/bin/

echo ">> [7/9] Installing systemd services..."
for s in "$REPO"/systemd/*.service; do
  sed -e "s/@USER@/$USER_NAME/g" -e "s/@UID@/$USER_UID/g" "$s" \
    > "/etc/systemd/system/$(basename "$s")"
done
systemctl daemon-reload
systemctl enable fipradio-ui fip-screen fip-led fip-fan fip-play fip-buttons fip-idle tas5806-init >/dev/null

echo ">> [8/9] Configuring MPD with FIP..."
cp -n /etc/mpd.conf /etc/mpd.conf.mark2.bak 2>/dev/null || true
install -m644 "$REPO/config/mpd.conf" /etc/mpd.conf
systemctl enable mpd >/dev/null
systemctl restart mpd
sleep 2
mpc clear >/dev/null 2>&1 || true
mpc add "https://icecast.radiofrance.fr/fip-hifi.aac"  >/dev/null 2>&1 || true
mpc add "https://icecast.radiofrance.fr/fip-midfi.mp3" >/dev/null 2>&1 || true
mpc volume 40 >/dev/null 2>&1 || true

echo ">> [9/9] Disabling screen blanking..."
raspi-config nonint do_blanking 1 2>/dev/null || true

echo
echo "================================================================"
echo " Done. REBOOT to finish:   sudo reboot"
echo
echo " After reboot you'll have FIP playing through the speakers with"
echo " a now-playing screen. Controls:"
echo "   - top buttons: volume / play-pause / mic-mute"
echo "   - LED ring shows volume"
echo "   - fan CLI:  fan off | auto | full | <0-100> | status"
echo "================================================================"

#!/usr/bin/env bash
# Reverse mark2-fip-radio. Run as root:  sudo ./uninstall.sh
set -uo pipefail
[ "$(id -u)" -eq 0 ] || { echo "Run with sudo."; exit 1; }
BOOT=/boot/firmware/config.txt; [ -f "$BOOT" ] || BOOT=/boot/config.txt

echo ">> Stopping & removing services..."
SERVICES="fipradio-ui fip-screen fip-led fip-fan fip-play fip-buttons tas5806-init"
for s in $SERVICES; do
  systemctl disable --now "$s" 2>/dev/null || true
  rm -f "/etc/systemd/system/$s.service"
done
systemctl daemon-reload

echo ">> Removing app, CLI tools, module-load..."
rm -rf /opt/fipradio
rm -f /usr/local/bin/fan /usr/local/bin/tas5806-init
rm -f /etc/modules-load.d/vocalfusion-soundcard.conf

echo ">> Removing DKMS audio driver..."
dkms remove -m vocalfusion-soundcard -v 0.0.2 --all 2>/dev/null || true

echo ">> Reverting $BOOT (removing the Mark II block)..."
# delete from our marker to end of file
sed -i '/# === Mycroft Mark II SJ-201 (FIP radio) hardware ===/,$d' "$BOOT"
sed -i 's/^display_auto_detect=0/display_auto_detect=1/' "$BOOT"

echo ">> Restoring MPD config..."
[ -f /etc/mpd.conf.mark2.bak ] && mv /etc/mpd.conf.mark2.bak /etc/mpd.conf || true

echo "Done. A backup of config.txt remains at $BOOT.mark2.bak. Reboot to finish."

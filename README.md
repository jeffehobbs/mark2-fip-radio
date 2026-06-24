# mark2-fip-radio

Turn a **Mycroft Mark II** into a [**FIP**](https://www.radiofrance.fr/fip) internet radio with a now-playing
touchscreen — running on **stock Raspberry Pi OS**, no custom image required.

![now playing](docs/screen.png)

Everything you'd expect from the hardware just works, and the unit boots straight
into the radio:

- 🔊 **Speakers** — the SJ-201's TAS5806 amplifier, fully driven
- 📺 **Now-playing screen** — album art, track, artist, and an accurate progress bar on the built-in display
- 🎛️ **Top buttons** — volume up/down, play/pause, mic-mute
- 💡 **LED ring** — shows the current volume as a 12-LED gauge
- 🌡️ **Quiet fan** — off during normal use, ramps only when genuinely hot
- 🔇 **No idle hiss** — the amp mutes itself when paused
- 💾 **Remembers volume** across reboots
- 📉 **Bandwidth-aware** — stops streaming after a few hours with no button/touch interaction (no point streaming to an empty room); any button or tap resumes it

It's deliberately lightweight: the screen is a small Python/pygame app, **not** a
browser.

## Hardware target

This is pinned to the **production Mark II**: **SJ-201 Rev10** daughterboard on a
**Raspberry Pi 4**, running Raspberry Pi OS (Bookworm/Trixie, 64-bit). It does not
attempt to detect other revisions.

## Install

On the Mark II (or over SSH):

```bash
git clone https://github.com/jeffehobbs/mark2-fip-radio
cd mark2-fip-radio
sudo ./install.sh
sudo reboot
```

After the reboot it comes up playing FIP with the now-playing screen. To remove
everything: `sudo ./uninstall.sh`.

## Controls

| What | How |
|------|-----|
| Volume | top **+ / –** buttons (LED ring follows) |
| Play / pause | top **action** button (or tap the screen) |
| Fan | `fan off` · `fan auto` · `fan full` · `fan 0-100` · `fan status` |

## How it works

| Layer | Pieces |
|-------|--------|
| **Audio** | `vocalfusion-soundcard` DKMS driver + `sj201` overlay → ALSA card `sj201`; `tas5806-init` brings the amp out of shutdown |
| **Fan** | `sj201-rev10-pwm-fan-overlay` (PWM on GPIO13, inverted); a small daemon keeps it off below 68 °C and ramps to 80 °C |
| **Buttons** | `sj201-buttons-overlay` (gpio-keys) → `fip-buttons` maps them to MPD |
| **LEDs** | WS2812 ring on GPIO12; `fip-led` shows volume, using OVOS's PWM-aware helper so it doesn't disturb the fan |
| **Screen** | `vc4-kms-dsi-7inch` (pinned), then a pygame app polling the FIP API and rendering with PIL + Inter |
| **Radio** | MPD streaming FIP HiFi AAC; now-playing from `api.radiofrance.fr/livemeta/pull/7` |
| **Bandwidth** | `fip-idle` watches for button/touch activity and `mpc stop`s the stream (releasing the connection) after the timeout in `/opt/fipradio/idle_timeout` (default 5m) |

All services live in `/opt/fipradio/` and are managed by systemd
(`fipradio-ui`, `fip-screen`, `fip-led`, `fip-fan`, `fip-play`, `fip-buttons`,
`fip-idle`, `tas5806-init`).

## Credits

Stands on the shoulders of the [OpenVoiceOS](https://github.com/OpenVoiceOS) project,
which figured out the Mark II hardware. This repo ports that work onto stock Pi OS and
adds the radio app. At install time it pulls in:

- [`OpenVoiceOS/VocalFusionDriver`](https://github.com/OpenVoiceOS/VocalFusionDriver) — the audio driver + overlays (Apache-2.0)
- [`NeonGeckoCom/sj201-interface`](https://github.com/NeonGeckoCom/sj201-interface) — the `HwPwmAwareLed` LED helper (BSD-3)

## License

MIT — see [LICENSE](LICENSE). The bundled overlay sources and the dependencies pulled
at install time retain their own licenses (Apache-2.0 / BSD-3, as noted above).

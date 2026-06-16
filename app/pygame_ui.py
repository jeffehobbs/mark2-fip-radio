#!/usr/bin/env python3
"""FIP now-playing display as a lightweight Wayland client (pygame, no browser).

Reuses the PIL renderer in display.py. Runs fullscreen under labwc, polls the
local FIP backend, and supports tap-to-play/pause on the touchscreen.
"""
import os, sys, time, subprocess

os.environ.setdefault("SDL_VIDEODRIVER", "wayland")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, "/opt/fipradio")

import pygame
from display import render, fetch

W, H = 800, 480


def main():
    pygame.init()
    screen = pygame.display.set_mode((W, H), pygame.FULLSCREEN)
    pygame.mouse.set_visible(False)
    clock = pygame.time.Clock()
    last_fetch = last_render = 0
    data = {"title": "FIP", "artist": "", "album": "", "year": "",
            "cover": "", "start": 0, "end": 0, "playing": False}
    running = True
    while running:
        try:
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    running = False
                elif e.type in (pygame.MOUSEBUTTONDOWN, pygame.FINGERDOWN):
                    try:
                        os.utime("/run/fip-activity", None)   # idle-watchdog stamp
                    except Exception:
                        pass
                    subprocess.run(["mpc", "toggle"], stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL)
                    last_fetch = 0          # refresh immediately after toggle
            now = time.time()
            if now - last_fetch > 4:
                data = fetch()
                last_fetch = now
            if now - last_render >= 1:
                img = render(W, H, data)            # PIL RGB image
                surf = pygame.image.frombuffer(img.tobytes(), (W, H), "RGB")
                screen.blit(surf, (0, 0))
                pygame.display.flip()
                last_render = now
            clock.tick(20)
        except Exception as e:
            sys.stderr.write(f"loop error (continuing): {e}\n")
            sys.stderr.flush()
            time.sleep(1)
    pygame.quit()


if __name__ == "__main__":
    try:
        main()
    except BaseException:
        import traceback
        tb = traceback.format_exc()
        sys.stderr.write(tb)
        sys.stderr.flush()
        try:
            open("/tmp/pygame-crash.log", "w").write(tb)
        except Exception:
            pass
        raise

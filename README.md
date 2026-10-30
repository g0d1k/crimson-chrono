# Crimson Chrono

A sleek, unique red-neon clock app built with CustomTkinter.

## Features
- Digital / Analog clock toggle
- Light / Dark mode
- Searchable World Clocks (any IANA timezone)
- Advanced Alarms: multiple, recurring (Once / Daily / Weekdays / Weekends), Snooze
- Timer & Stopwatch (with laps)
- Persistence (settings, alarms, world clocks saved to `~/.crimson_chrono.json`)
- In-app alarm popups + sound

## Download (Linux AppImage)

Grab the latest `Crimson_Chrono-*-x86_64.AppImage` from the
[Releases page](https://github.com/g0d1k/crimson-chrono/releases), then:

```bash
chmod +x Crimson_Chrono-*-x86_64.AppImage
./Crimson_Chrono-*-x86_64.AppImage
```

If it complains about FUSE, install `libfuse2` (`sudo apt install libfuse2t64` on newer Ubuntu)
or run it with `--appimage-extract-and-run`.

## Install & Run from source

```bash
pip install -r requirements.txt
python3 crimson_chrono.py
```

On Linux for better alarm sound, ensure `paplay` is available (`sudo apt install pulseaudio-utils`).

## Notes
- World clock search matches city/region names (e.g. "tokyo", "london", "new york").
- Alarms check every second and respect recurrence rules.
- Analog clock uses a clean neon-styled face with red hands.
- Theme and clock mode are remembered between runs.

## Building the AppImage

```bash
./build_appimage.sh            # output: dist/Crimson_Chrono-dev-x86_64.AppImage
```

The script creates a venv in `build/`, freezes the app with PyInstaller, and packages it with
appimagetool. An AppImage only runs on distros with a glibc at least as new as the build machine's,
so official releases are built by GitHub Actions on Ubuntu 22.04: push a tag like `v1.0.1` and the
`Release AppImage` workflow builds, smoke-tests, and publishes it to Releases.


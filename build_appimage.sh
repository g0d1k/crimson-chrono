#!/usr/bin/env bash
# Build Crimson Chrono as a Linux AppImage.
# Output: dist/Crimson_Chrono-<version>-x86_64.AppImage
# The AppImage runs on distros whose glibc is at least as new as the build machine's,
# so release builds are made on an older distro (see .github/workflows/release.yml).
set -euo pipefail

cd "$(dirname "$0")"
VERSION="${VERSION:-dev}"
ARCH="x86_64"
BUILD="build"
APPDIR="$BUILD/AppDir"
PY="${PYTHON:-python3}"

# 1. Isolated venv with the build tools
if [ ! -x "$BUILD/venv/bin/python" ]; then
    "$PY" -m venv "$BUILD/venv"
fi
"$BUILD/venv/bin/pip" install --quiet --upgrade pip
"$BUILD/venv/bin/pip" install --quiet -r requirements.txt pyinstaller tzdata

# 2. Freeze the app (one folder, bundled icon, customtkinter themes and tz database)
"$BUILD/venv/bin/pyinstaller" --noconfirm --clean --windowed \
    --name crimson-chrono \
    --distpath "$BUILD/pyinstaller" --workpath "$BUILD/work" --specpath "$BUILD" \
    --add-data "$(pwd)/icon.png:." \
    --collect-all customtkinter \
    --collect-data tzdata \
    crimson_chrono.py

# 3. Assemble the AppDir
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin" "$APPDIR/usr/share/applications" "$APPDIR/usr/share/icons/hicolor/256x256/apps"
cp -r "$BUILD/pyinstaller/crimson-chrono/." "$APPDIR/usr/bin/"

"$BUILD/venv/bin/python" - <<'EOF'
import tkinter as tk
root = tk.Tk(); root.withdraw()
img = tk.PhotoImage(file="icon.png")
# 1254px source -> ~251px, close enough for the 256x256 slot
img.subsample(max(1, img.width() // 256)).write("build/AppDir/crimson-chrono.png", format="png")
EOF
cp "$APPDIR/crimson-chrono.png" "$APPDIR/usr/share/icons/hicolor/256x256/apps/crimson-chrono.png"
ln -sf crimson-chrono.png "$APPDIR/.DirIcon"

cat > "$APPDIR/crimson-chrono.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=Crimson Chrono
Comment=Red neon clock with world clocks, alarms, timer and stopwatch
Exec=crimson-chrono
Icon=crimson-chrono
Categories=Utility;Clock;
StartupWMClass=Crimson-chrono
Terminal=false
EOF
cp "$APPDIR/crimson-chrono.desktop" "$APPDIR/usr/share/applications/"

cat > "$APPDIR/AppRun" <<'EOF'
#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/usr/bin/crimson-chrono" "$@"
EOF
chmod +x "$APPDIR/AppRun"

# 4. Package with appimagetool (extract-and-run avoids needing FUSE at build time)
TOOL="$BUILD/appimagetool-$ARCH.AppImage"
if [ ! -x "$TOOL" ]; then
    curl -fsSL -o "$TOOL" \
        "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-$ARCH.AppImage"
    chmod +x "$TOOL"
fi
mkdir -p dist
OUT="dist/Crimson_Chrono-$VERSION-$ARCH.AppImage"
ARCH="$ARCH" APPIMAGE_EXTRACT_AND_RUN=1 "$TOOL" --no-appstream "$APPDIR" "$OUT"
echo "Built $OUT"

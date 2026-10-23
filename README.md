# Wallpaper Library

Browse wallpapers, preview them, and set one as your desktop. The app is Python and PyQt5. A portable Windows build is published on GitHub Releases. macOS and Linux run it from source.

The interface is Simplified Chinese or English. The first launch follows the system locale (`QLocale`: `zh*` uses Chinese, anything else uses English). Settings can pin a language; the choice is stored in `preferences.json` and applies the next time the app starts.

## Features

- Browse 360 Wallpapers (Birdpaper) by the service’s own categories, and search in Chinese.
- Wallhaven (general, anime, people), Bing daily wallpapers, and NASA Astronomy Picture of the Day.
- Cards show a small thumbnail. Preview and “set wallpaper” download the original.
- Favorites and recently set wallpapers.
- Close the window and the app stays in the tray. A second launch brings the existing window back.
- On Windows, startup makes sure a Start Menu shortcut exists so the taskbar uses the app icon (`WallpaperLibrary.App`). The shortcut name follows the interface language.

## Screenshots

Screenshots are not in the repository yet. Add them here when you have them:

- Library, with a category selected
- Preview
- Settings, including the language switch

## Download the Windows app

Open **Releases** and download `WallpaperLibrary-windows.zip` from a `v*` tag. Unzip it and run `WallpaperLibrary.exe`. No Python install is required.

The folder is portable. Config, cache, and favorites are stored next to the exe when that folder is writable. If it is not, they go under `%LOCALAPPDATA%\WallpaperLibrary`.

A tag named `v*` (for example `v1.0.0`) builds that zip on GitHub Actions (`windows-latest`) and attaches it to the release.

## Run from source

Python 3.11 or newer. On Windows, `pythonw` is used by the launcher so no console window stays open.

```bash
pip install -r requirements.txt
python wallpaper_app_qt.py
```

On Windows you can double-click `启动壁纸库.bat` instead. It runs:

```bat
start "" pythonw "%~dp0wallpaper_app_qt.py"
```

When you run from source, `cache\`, `preferences.json`, `favorites.json`, and `history.json` stay in the program folder, next to the script. An existing `cache` folder is reused.

## Build the Windows exe yourself

On Windows:

```bat
build_windows.bat
```

That script creates a fresh `.build-venv`, installs `requirements.txt` and PyInstaller there, then runs `WallpaperLibrary.spec`. It does not use other packages from the system Python. The exe is `dist\WallpaperLibrary\WallpaperLibrary.exe`. It is windowed (no console) and uses `assets\app.ico`. PyInstaller is a build tool only; it is not listed in `requirements.txt`.

## Platform support

| | Windows | macOS | Linux |
| --- | --- | --- | --- |
| Browse, search, download, favorites | Yes | Yes | Yes |
| Set as wallpaper | Yes | Best effort, via `osascript` | Best effort: GNOME `gsettings`, KDE `qdbus`, XFCE `xfconf-query` |
| Autostart and shortcuts | Yes | Hidden. Not available. | Hidden. Not available. |
| Portable exe | Yes | No. Run from source. | No. Run from source. |

If the desktop cannot be changed, the image is still saved and the app shows a message. It does not crash.

## Data sources

The app loads images from these services:

- Bing daily wallpapers
- Wallhaven
- 360 Wallpapers (Birdpaper)
- NASA Astronomy Picture of the Day

Images belong to their providers. This project does not claim copyright on any wallpaper.

Chinese keywords still search 360 directly. On Wallhaven, a Chinese word is mapped to an English tag when one is known.

## Tests

```bash
python -m unittest tests.test_core tests.test_gui
```

## License

[MIT](LICENSE)

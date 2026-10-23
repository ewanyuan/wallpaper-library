# -*- mode: python ; coding: utf-8 -*-
"""Portable Windows build. Onedir, no console, icon from assets/app.ico.

Build from a clean virtualenv (see build_windows.bat). Excludes drop packages
that a full Python install would otherwise drag in, and unused Qt modules.
"""

EXCLUDES = [
    "sip",
    "numpy",
    "pandas",
    "matplotlib",
    "scipy",
    "cryptography",
    "bcrypt",
    "yaml",
    "_yaml",
    "pygame",
    "tkinter",
    "unittest",
    "pydoc",
    "doctest",
    "PIL.ImageTk",
    "PIL.ImageQt",
    "PIL.ImageGrab",
    "PIL.ImageFilter",
    "PIL.ImageFont",
    "PIL.ImageCms",
    "PIL._tkinter_finder",
    "PIL._avif",
    "PIL._imagingft",
    "PIL._imagingcms",
    "PIL._imagingtk",
    "PIL._imagingmath",
    "PIL._imagingmorph",
    "PIL.AvifImagePlugin",
    "PyQt5.QtWebEngine",
    "PyQt5.QtWebEngineCore",
    "PyQt5.QtWebEngineWidgets",
    "PyQt5.QtWebChannel",
    "PyQt5.QtQml",
    "PyQt5.QtQuick",
    "PyQt5.QtQuickWidgets",
    "PyQt5.QtMultimedia",
    "PyQt5.QtMultimediaWidgets",
    "PyQt5.QtSql",
    "PyQt5.QtBluetooth",
    "PyQt5.Qt3DCore",
    "PyQt5.Qt3DRender",
    "PyQt5.Qt3DInput",
    "PyQt5.Qt3DLogic",
    "PyQt5.Qt3DAnimation",
    "PyQt5.Qt3DExtras",
    "PyQt5.QtDesigner",
    "PyQt5.QtTest",
    "PyQt5.QtNfc",
    "PyQt5.QtPositioning",
    "PyQt5.QtSensors",
    "PyQt5.QtSerialPort",
    "PyQt5.QtLocation",
    "PyQt5.QtHelp",
    "PyQt5.QtOpenGL",
]

DROP_SEGMENTS = {
    "numpy",
    "pandas",
    "matplotlib",
    "scipy",
    "cryptography",
    "bcrypt",
    "pygame",
    "tkinter",
    "yaml",
    "_yaml",
    "qt5webengine",
    "qt5webenginecore",
    "qt5webenginewidgets",
    "qtwebengine",
    "qtwebenginecore",
    "qtwebenginewidgets",
    "qt5webchannel",
    "qtwebchannel",
    "qt5qml",
    "qt5quick",
    "qt5quickwidgets",
    "qtqml",
    "qtquick",
    "qtquickwidgets",
    "qt5multimedia",
    "qt5multimediawidgets",
    "qtmultimedia",
    "qtmultimediawidgets",
    "qt5sql",
    "qtsql",
    "qt5bluetooth",
    "qtbluetooth",
    "qt53dcore",
    "qt53drender",
    "qt53dinput",
    "qt53dlogic",
    "qt53danimation",
    "qt53dextras",
    "qt3dcore",
    "qt3drender",
    "qt5designer",
    "qtdesigner",
    "sqldrivers",
    "mediaservice",
    "playlistformats",
    "geoservices",
    "webview",
    "qmltooling",
    "sceneparsers",
    "geometryloaders",
}

PIL_DROP = {
    "PIL.ImageTk",
    "PIL.ImageQt",
    "PIL.ImageGrab",
    "PIL.ImageFilter",
    "PIL.ImageFont",
    "PIL.ImageCms",
    "PIL._tkinter_finder",
    "PIL._avif",
    "PIL._imagingft",
    "PIL._imagingcms",
    "PIL._imagingtk",
    "PIL._imagingmath",
    "PIL._imagingmorph",
    "PIL.AvifImagePlugin",
}
# JPEG, PNG, and BMP are inside _imaging. WebP is _webp.
# Pillow 13's Windows wheel: _avif is 7.9 MB and _imagingft is 2.3 MB.
PIL_NATIVE_DROP_PREFIXES = (
    "_avif.",
    "_imagingft.",
    "_imagingcms.",
    "_imagingtk.",
    "_imagingmath.",
    "_imagingmorph.",
)


def _entry_name(entry):
    return str(entry[0]).replace("\\", "/")


def _keep(entry):
    name = _entry_name(entry)
    lower = name.lower()
    base = lower.rsplit("/", 1)[-1]
    if base.endswith(".qm"):
        return ("zh" in base) or ("en" in base)
    dotted = name[:-3] if name.endswith(".py") else name
    dotted = dotted.replace("/", ".")
    if dotted in PIL_DROP or dotted.startswith(tuple(item + "." for item in PIL_DROP)):
        return False
    stem = base.split(".")[0]
    if stem in {prefix[:-1] for prefix in PIL_NATIVE_DROP_PREFIXES}:
        return False
    segments = [part.split(".")[0] for part in lower.split("/")]
    if any(part in DROP_SEGMENTS for part in segments):
        return False
    return True


def _filter_inplace(toc):
    toc[:] = [entry for entry in list(toc) if _keep(entry)]


a = Analysis(
    ["wallpaper_app_qt.py"],
    pathex=[],
    binaries=[],
    datas=[("assets", "assets")],
    hiddenimports=["wallpaper_core", "i18n", "PIL.Image", "PyQt5.sip"],
    hookspath=["pyi_hooks"],
    hooksconfig={},
    runtime_hooks=[],
    excludes=EXCLUDES,
    noarchive=False,
)
_filter_inplace(a.pure)
_filter_inplace(a.binaries)
_filter_inplace(a.datas)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="WallpaperLibrary",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="assets/app.ico",
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="WallpaperLibrary",
)

# Replaces PyInstaller's PyQt5 hook so it does not request the standalone "sip" module.
# PyQt5 5.11+ ships PyQt5.sip. Asking for "sip" prints "Hidden import sip not found".

from PyInstaller.utils.hooks.qt import ensure_single_qt_bindings_package, pyqt5_library_info

ensure_single_qt_bindings_package("PyQt5")

if pyqt5_library_info.version is not None:
    hiddenimports = ["PyQt5.sip", "pkgutil"]
    binaries = pyqt5_library_info.collect_extra_binaries()

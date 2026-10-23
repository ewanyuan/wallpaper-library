# -*- coding: utf-8 -*-
"""壁纸库。用 pythonw 启动，见同目录的 bat。

分类和搜索规则在 wallpaper_core.py。这个文件只负责窗口、托盘和单实例。
"""

from __future__ import annotations

import os
import queue
import sys
import threading
import traceback
import webbrowser

import i18n
import wallpaper_core as core

try:
    from PyQt5.QtCore import QEvent, QPoint, QRect, QRectF, QSize, Qt, QTimer
    from PyQt5.QtGui import (
        QColor,
        QFont,
        QFontDatabase,
        QIcon,
        QKeySequence,
        QPainter,
        QPainterPath,
        QPen,
        QPixmap,
    )
    from PyQt5.QtNetwork import QLocalServer, QLocalSocket
    from PyQt5.QtWidgets import (
        QApplication,
        QButtonGroup,
        QCheckBox,
        QComboBox,
        QDialog,
        QFrame,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QListView,
        QMainWindow,
        QMenu,
        QMessageBox,
        QPushButton,
        QScrollArea,
        QShortcut,
        QStackedWidget,
        QSystemTrayIcon,
        QVBoxLayout,
        QWidget,
    )
    from PyQt5.QtCore import QAbstractListModel, QModelIndex, QObject, pyqtSignal
except ImportError:
    core.log(traceback.format_exc())
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.user32.MessageBoxW(
            0,
            i18n.tr("app.missing_qt"),
            i18n.tr("app.name"),
            0x10,
        )
    raise


INSTANCE_NAME = os.environ.get("WALLPAPER_INSTANCE") or "WallpaperLibrary.single"
# 卡片再窄就不舒服。Qt 的图标模式在「列宽正好铺满」时会少排一列，所以留 2 像素。
MIN_CARD_WIDTH = 240
GRID_SLACK = 2
CARD_TEXT_BLOCK = 118
THUMB_ROLE = Qt.UserRole + 1
CATEGORY_ROLE = Qt.UserRole + 2
RESOLUTION_ROLE = Qt.UserRole + 3
FAILED_ROLE = Qt.UserRole + 4

STYLE = """
QMainWindow, QWidget#content { background: #f4f1eb; color: #221f1b; }
QWidget#sidebar { background: #1c1b19; }
QLabel { color: #221f1b; }
QLabel#heading { font-size: 22px; font-weight: 600; }
QLabel#muted { color: #746e66; }
QWidget#sidebar QLabel { color: #f3efe8; }
QWidget#sidebar QLabel#muted { color: #a39e94; }
QLabel#footer { color: #746e66; }
QFrame#banner { background: #fff4ec; border: 1px solid #f0d2c2; border-radius: 10px; }
QLineEdit#search {
    background: #fffcf8; border: 1px solid #e6e0d6; border-radius: 10px;
    padding: 0 14px; min-height: 40px; font-size: 14px; color: #221f1b;
}
QLineEdit#search:focus { border: 1px solid #d86b2a; }
QPushButton#primary {
    background: #d86b2a; color: white; border: none; border-radius: 10px;
    padding: 0 16px; min-height: 40px; font-weight: 600;
}
QPushButton#primary:hover { background: #c45e20; }
QPushButton#primary:disabled { background: #eadfd4; color: #a3988c; }
QPushButton#nav {
    background: transparent; color: #f3efe8; border: none; border-radius: 8px;
    text-align: left; padding: 0 12px; min-height: 40px;
}
QPushButton#nav:hover { background: #2a2926; }
QPushButton#nav:checked {
    background: #34322e; color: #ffd7c2; border-left: 3px solid #d86b2a; padding-left: 9px;
}
QPushButton#chip {
    background: #fffcf8; color: #3c3833; border: 1px solid #e6e0d6;
    border-radius: 15px; padding: 0 14px; min-height: 30px;
}
QPushButton#chip:hover { border-color: #d86b2a; }
QPushButton#chip:checked { background: #1c1b19; color: #fffcf8; border-color: #1c1b19; }
QPushButton#ghost, QPushButton#text {
    background: #fffcf8; color: #3c3833; border: 1px solid #e6e0d6;
    border-radius: 8px; padding: 6px 12px; min-height: 32px;
}
QPushButton#ghost:hover, QPushButton#text:hover { border-color: #d86b2a; }
QComboBox {
    background: #fffcf8; border: 1px solid #e6e0d6; border-radius: 8px;
    padding: 4px 10px; min-height: 30px; color: #221f1b;
}
QListView { background: transparent; border: none; outline: none; }
QListView::item { border: none; outline: none; }
QScrollArea { background: transparent; border: none; }
QScrollBar:vertical {
    background: transparent; width: 8px; margin: 0; border: none;
}
QScrollBar::handle:vertical {
    background: #d4cbc0; border: none; border-radius: 4px; min-height: 24px;
}
QScrollBar::groove:vertical { background: transparent; border: none; }
QScrollBar:horizontal { background: transparent; height: 0px; margin: 0; border: none; }
QScrollBar::handle:horizontal { background: transparent; height: 0px; border: none; }
QScrollBar::add-line, QScrollBar::sub-line,
QScrollBar::add-page, QScrollBar::sub-page,
QScrollBar::up-arrow, QScrollBar::down-arrow,
QScrollBar::left-arrow, QScrollBar::right-arrow {
    background: transparent; border: none; width: 0px; height: 0px;
}
QDialog { background: #f4f1eb; }
"""


def card_grid(viewport_width, spacing=0, min_card=MIN_CARD_WIDTH):
    """按视口宽度算列数，并把每列拉到同一宽度。

    返回 (列数, 单元格宽, 单元格高)。宽为 0 表示现在还排不了。
    缩略图区域保持 16:9。单元格宽乘以列数必须小于视口，否则 Qt 会把最后一列折下去。
    """
    width = int(viewport_width or 0)
    if width < 80:
        return 0, 0, 0
    spacing = max(0, int(spacing))
    cols = 1
    while cols < 8:
        needed = (cols + 1) * min_card + cols * spacing + GRID_SLACK
        if needed > width:
            break
        cols += 1
    usable = width - GRID_SLACK - (cols - 1) * spacing
    cell_w = usable // cols
    if cell_w < min_card and cols > 1:
        cols -= 1
        usable = width - GRID_SLACK - (cols - 1) * spacing
        cell_w = max(1, usable // cols)
    image_h = max(1, int((cell_w - 16) * 9 / 16))
    return cols, cell_w, image_h + CARD_TEXT_BLOCK


def choose_font():
    families = set(QFontDatabase().families())
    for name in (
        "Microsoft YaHei UI",
        "Microsoft YaHei",
        "PingFang SC",
        "Noto Sans CJK SC",
        "Noto Sans SC",
        "Source Han Sans SC",
        "WenQuanYi Micro Hei",
        "WenQuanYi Zen Hei",
        "Droid Sans Fallback",
    ):
        if name in families:
            font = QFont(name)
            font.setPointSize(10)
            return font
    font = QFont()
    font.setPointSize(10)
    return font


def make_icon():
    icon = QIcon()
    ico = core.app_icon_path()
    png = core.app_icon_png_path()
    if os.path.isfile(ico):
        icon = QIcon(ico)
    if os.path.isfile(png):
        icon.addPixmap(QPixmap(png))
    if not icon.isNull():
        return icon
    pix = QPixmap(64, 64)
    pix.fill(Qt.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor("#221f1c"))
    painter.drawRoundedRect(2, 2, 60, 60, 14, 14)
    painter.setBrush(QColor("#d86b2a"))
    painter.drawEllipse(QRectF(38, 12, 14, 14))
    path = QPainterPath()
    path.moveTo(12, 48)
    path.lineTo(26, 30)
    path.lineTo(36, 40)
    path.lineTo(48, 26)
    path.lineTo(54, 48)
    path.closeSubpath()
    painter.setBrush(QColor("#f4f1eb"))
    painter.drawPath(path)
    painter.end()
    return QIcon(pix)


class Pool:
    def __init__(self, workers):
        self._queue = queue.Queue()
        for _ in range(workers):
            threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        while True:
            job = self._queue.get()
            try:
                job()
            except Exception:
                core.log(traceback.format_exc())
            finally:
                self._queue.task_done()

    def submit(self, job):
        self._queue.put(job)


class Bus(QObject):
    categories = pyqtSignal(object, str)
    page = pyqtSignal(int, int, object)
    thumb = pyqtSignal(int, str, str, str)
    task = pyqtSignal(str, bool, object)
    preview = pyqtSignal(int, str, str)


class WallpaperModel(QAbstractListModel):
    def __init__(self):
        super().__init__()
        self.items = []
        self.thumbs = {}
        self.failed = set()

    def rowCount(self, parent=QModelIndex()):
        if parent.isValid():
            return 0
        return len(self.items)

    def item(self, row):
        if 0 <= row < len(self.items):
            return self.items[row]
        return None

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self.items):
            return None
        item = self.items[index.row()]
        if role == Qt.DisplayRole:
            return item.title
        if role == THUMB_ROLE:
            return self.thumbs.get(item.thumb_url, "")
        if role == CATEGORY_ROLE:
            return item.category
        if role == RESOLUTION_ROLE:
            return item.resolution
        if role == FAILED_ROLE:
            return item.thumb_url in self.failed
        if role == Qt.ToolTipRole:
            return "%s\n%s · %s" % (
                item.title,
                i18n.source_name(item.source_key) or item.source,
                i18n.category_name(item.category),
            )
        return None

    def reset(self, items):
        self.beginResetModel()
        self.items = list(items)
        self.endResetModel()

    def append(self, items):
        if not items:
            return
        start = len(self.items)
        self.beginInsertRows(QModelIndex(), start, start + len(items) - 1)
        self.items.extend(items)
        self.endInsertRows()

    def set_thumb(self, url, path):
        self.thumbs[url] = path
        self.failed.discard(url)
        self._touch(url)

    def mark_failed(self, url):
        self.failed.add(url)
        self._touch(url)

    def _touch(self, url):
        rows = [index for index, item in enumerate(self.items) if item.thumb_url == url]
        if rows:
            self.dataChanged.emit(self.index(min(rows), 0), self.index(max(rows), 0))


class CardDelegate(QObject):
    """QListView 的绘制和按钮位置。cell 由视图在改变宽度时写入。"""

    def __init__(self, view):
        super().__init__(view)
        self.view = view
        self.cell = (280, 250)
        self.pixmaps = {}
        self.favorite_text = lambda row: i18n.tr("card.fav")

    def size_hint(self):
        return QSize(*self.cell)

    def button_rects(self, rect):
        card = rect.adjusted(8, 8, -8, -8)
        top = card.bottom() - 42
        fav_w = 96
        apply_rect = QRect(card.left() + 12, top, max(40, card.width() - 24 - fav_w - 8), 30)
        fav_rect = QRect(apply_rect.right() + 8, top, fav_w, 30)
        return apply_rect, fav_rect

    def paint(self, painter, option, index):
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        card = option.rect.adjusted(8, 8, -8, -8)
        path = QPainterPath()
        path.addRoundedRect(QRectF(card), 12, 12)
        painter.setClipPath(path)
        painter.fillRect(card, QColor("#fffcf8"))

        image_bottom = card.bottom() - 96
        image = QRect(card.left(), card.top(), card.width(), max(40, image_bottom - card.top()))
        path_str = index.data(THUMB_ROLE) or ""
        pix = self._pixmap(path_str)
        if pix is not None and not pix.isNull():
            scaled = pix.scaled(image.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            sx = max(0, (scaled.width() - image.width()) // 2)
            sy = max(0, (scaled.height() - image.height()) // 2)
            painter.drawPixmap(image, scaled, QRect(sx, sy, image.width(), image.height()))
        else:
            painter.fillRect(image, QColor("#ebe4da"))
            painter.setPen(QColor("#8a8176"))
            message = i18n.tr("card.failed") if index.data(FAILED_ROLE) else i18n.tr("card.loading")
            painter.drawText(image, Qt.AlignCenter, message)

        painter.setClipping(False)
        hover = self.view.hover_row == index.row()
        painter.setPen(QPen(QColor("#d86b2a" if hover else "#e6e0d6"), 1))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(card, 12, 12)

        painter.setFont(option.font)
        metrics = painter.fontMetrics()
        cat = i18n.category_name(index.data(CATEGORY_ROLE) or "")
        res = index.data(RESOLUTION_ROLE) or ""
        cat_rect = QRect(card.left() + 12, image.bottom() + 8, max(20, card.width() // 2 - 8), 18)
        res_rect = QRect(card.center().x(), image.bottom() + 8, card.width() // 2 - 16, 18)
        painter.setPen(QColor("#d86b2a"))
        painter.drawText(cat_rect, Qt.AlignLeft | Qt.AlignVCenter, metrics.elidedText(cat, Qt.ElideRight, cat_rect.width()))
        painter.setPen(QColor("#8a8176"))
        painter.drawText(res_rect, Qt.AlignRight | Qt.AlignVCenter, metrics.elidedText(res, Qt.ElideRight, res_rect.width()))

        bold = QFont(option.font)
        bold.setBold(True)
        painter.setFont(bold)
        title_rect = QRect(card.left() + 12, cat_rect.bottom() + 2, card.width() - 24, 22)
        painter.setPen(QColor("#221f1b"))
        painter.drawText(
            title_rect,
            Qt.AlignLeft | Qt.AlignVCenter,
            painter.fontMetrics().elidedText(index.data(Qt.DisplayRole) or "", Qt.ElideRight, title_rect.width()),
        )

        apply_rect, fav_rect = self.button_rects(option.rect)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#c45e20" if hover else "#d86b2a"))
        painter.drawRoundedRect(apply_rect, 7, 7)
        painter.setBrush(QColor("#fffcf8"))
        painter.setPen(QPen(QColor("#e6e0d6"), 1))
        painter.drawRoundedRect(fav_rect, 7, 7)
        painter.setPen(QColor("#fffcf8"))
        painter.drawText(apply_rect, Qt.AlignCenter, i18n.tr("card.set"))
        painter.setPen(QColor("#3c3833"))
        painter.drawText(fav_rect, Qt.AlignCenter, self.favorite_text(index.row()))
        painter.restore()

    def _pixmap(self, path):
        if not path:
            return None
        cached = self.pixmaps.get(path)
        if cached is not None:
            return cached
        pix = QPixmap(path)
        if pix.isNull():
            return None
        self.pixmaps[path] = pix
        if len(self.pixmaps) > 180:
            self.pixmaps.pop(next(iter(self.pixmaps)))
        return pix


class WallpaperView(QListView):
    applyRequested = pyqtSignal(int)
    favoriteRequested = pyqtSignal(int)
    previewRequested = pyqtSignal(int)
    menuRequested = pyqtSignal(int, QPoint)
    nearEnd = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.hover_row = -1
        self.cell = (280, 250)
        self._in_relayout = False
        self.delegate = CardDelegate(self)
        self.setViewMode(QListView.IconMode)
        self.setFlow(QListView.LeftToRight)
        self.setWrapping(True)
        self.setResizeMode(QListView.Adjust)
        self.setMovement(QListView.Static)
        self.setSpacing(0)
        self.setUniformItemSizes(True)
        self.setSelectionMode(QListView.NoSelection)
        self.setFrameShape(QFrame.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollMode(QListView.ScrollPerPixel)
        self.setMouseTracking(True)
        self.setItemDelegate(_BridgeDelegate(self))
        self.verticalScrollBar().valueChanged.connect(self._on_scroll)
        self.verticalScrollBar().rangeChanged.connect(self._relayout_after_scroll)
        self.viewport().setContextMenuPolicy(Qt.CustomContextMenu)
        self.viewport().customContextMenuRequested.connect(self._menu)

    def relayout(self):
        if self._in_relayout:
            return
        self._in_relayout = True
        try:
            # 滚动条出现后视口会变窄，再算一次列宽。
            for _ in range(2):
                _cols, cell_w, cell_h = card_grid(self.viewport().width(), self.spacing())
                if cell_w <= 0:
                    return
                if self.cell == (cell_w, cell_h) and self.gridSize().width() == cell_w:
                    return
                self.cell = (cell_w, cell_h)
                self.delegate.cell = self.cell
                self.setGridSize(QSize(cell_w, cell_h))
        finally:
            self._in_relayout = False

    def _relayout_after_scroll(self, *_args):
        self.relayout()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.relayout()

    def showEvent(self, event):
        super().showEvent(event)
        self.relayout()

    def viewportEvent(self, event):
        if event.type() == QEvent.MouseMove:
            index = self.indexAt(event.pos())
            row = index.row() if index.isValid() else -1
            if row != self.hover_row:
                self.hover_row = row
                self.viewport().update()
        elif event.type() == QEvent.Leave:
            self.hover_row = -1
            self.viewport().update()
        elif event.type() == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton:
            index = self.indexAt(event.pos())
            if index.isValid():
                rect = self.visualRect(index)
                apply_rect, fav_rect = self.delegate.button_rects(rect)
                if apply_rect.contains(event.pos()):
                    self.applyRequested.emit(index.row())
                elif fav_rect.contains(event.pos()):
                    self.favoriteRequested.emit(index.row())
                else:
                    self.previewRequested.emit(index.row())
                return True
        return super().viewportEvent(event)

    def _on_scroll(self, value):
        bar = self.verticalScrollBar()
        if bar.maximum() > 0 and value >= bar.maximum() - 280:
            self.nearEnd.emit()

    def _menu(self, pos):
        index = self.indexAt(pos)
        if index.isValid():
            self.menuRequested.emit(index.row(), self.viewport().mapToGlobal(pos))


class _BridgeDelegate(object):
    """QStyledItemDelegate 的薄封装，避免把绘制逻辑再写进 Qt 的类层次。"""

    def __new__(cls, view):
        from PyQt5.QtWidgets import QStyledItemDelegate

        class Bridge(QStyledItemDelegate):
            def __init__(self, parent):
                super().__init__(parent)
                self.view = parent

            def sizeHint(self, option, index):
                return self.view.delegate.size_hint()

            def paint(self, painter, option, index):
                self.view.delegate.paint(painter, option, index)

        return Bridge(view)


class ChipBar(QWidget):
    chosen = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.buttons = []
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 4, 12, 4)
        self._layout.setSpacing(8)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self.setFixedHeight(40)

    def set_items(self, pairs, selected):
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                self._group.removeButton(widget)
                widget.deleteLater()
        self.buttons = []
        self._group.setExclusive(False)
        for cid, label in pairs:
            button = QPushButton(label)
            button.setObjectName("chip")
            button.setCheckable(True)
            button.setCursor(Qt.PointingHandCursor)
            button.setProperty("cid", cid)
            button.setChecked(cid == selected)
            button.setFocusPolicy(Qt.NoFocus)
            button.clicked.connect(lambda _checked, c=cid: self.chosen.emit(c))
            self._group.addButton(button)
            self._layout.addWidget(button)
            # 窗口已经显示时，未 show 的按钮 sizeHint 只有 12x8，整行会缩成一条空白。
            button.show()
            self.buttons.append(button)
        self._group.setExclusive(True)
        self._layout.addStretch(1)
        hint = self.sizeHint()
        self.setMinimumWidth(hint.width())
        self.resize(max(hint.width(), 1), max(self.height(), hint.height()))

    def labels(self):
        return [button.text() for button in self.buttons]

    def select(self, cid):
        self._group.setExclusive(False)
        for button in self.buttons:
            button.setChecked(button.property("cid") == cid)
        self._group.setExclusive(True)


class HScroll(QScrollArea):
    def __init__(self):
        super().__init__()
        self.setWidgetResizable(False)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setFrameShape(QFrame.NoFrame)
        self.setFixedHeight(44)

    def wheelEvent(self, event):
        pixel = event.pixelDelta()
        angle = event.angleDelta()
        delta = pixel.x() or pixel.y() or angle.y() or angle.x()
        bar = self.horizontalScrollBar()
        bar.setValue(bar.value() - delta)
        event.accept()


class PreviewDialog(QDialog):
    applyRequested = pyqtSignal()
    saveRequested = pyqtSignal()
    favoriteRequested = pyqtSignal()
    stepRequested = pyqtSignal(int)

    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle(i18n.tr("preview.title"))
        self.resize(980, 700)
        self._pix = QPixmap()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)
        self.image = QLabel(i18n.tr("preview.loading"))
        self.image.setAlignment(Qt.AlignCenter)
        self.image.setMinimumHeight(360)
        self.image.setStyleSheet("background:#1c1b19; color:#d9d0c4; border-radius:12px;")
        layout.addWidget(self.image, 1)
        self.title = QLabel("")
        self.title.setObjectName("heading")
        self.title.setWordWrap(True)
        self.meta = QLabel("")
        self.meta.setObjectName("muted")
        self.meta.setWordWrap(True)
        layout.addWidget(self.title)
        layout.addWidget(self.meta)
        row = QHBoxLayout()
        self.count = QLabel("")
        self.count.setObjectName("muted")
        row.addWidget(self.count)
        row.addStretch(1)
        prev_button = QPushButton(i18n.tr("preview.prev"))
        next_button = QPushButton(i18n.tr("preview.next"))
        prev_button.setObjectName("ghost")
        next_button.setObjectName("ghost")
        prev_button.clicked.connect(lambda: self.stepRequested.emit(-1))
        next_button.clicked.connect(lambda: self.stepRequested.emit(1))
        row.addWidget(prev_button)
        row.addWidget(next_button)
        layout.addLayout(row)
        actions = QHBoxLayout()
        apply_button = QPushButton(i18n.tr("preview.set"))
        save_button = QPushButton(i18n.tr("preview.save"))
        fav_button = QPushButton(i18n.tr("preview.fav"))
        link_button = QPushButton(i18n.tr("preview.copy"))
        apply_button.setObjectName("primary")
        save_button.setObjectName("ghost")
        fav_button.setObjectName("ghost")
        link_button.setObjectName("ghost")
        self.fav_button = fav_button
        apply_button.clicked.connect(self.applyRequested.emit)
        save_button.clicked.connect(self.saveRequested.emit)
        fav_button.clicked.connect(self.favoriteRequested.emit)
        link_button.clicked.connect(lambda: parent.copy_link(parent.preview_row) if parent.preview_row >= 0 else None)
        actions.addWidget(apply_button)
        actions.addWidget(save_button)
        actions.addWidget(fav_button)
        actions.addWidget(link_button)
        layout.addLayout(actions)

    def show_item(self, item, index, total, favorite):
        self.title.setText(item.title)
        bits = [i18n.source_name(item.source_key) or item.source, i18n.category_name(item.category) or i18n.tr("preview.uncat")]
        if item.resolution:
            bits.append(item.resolution)
        if item.tags and item.tags != item.title:
            bits.append(item.tags)
        self.meta.setText(" · ".join(bits))
        self.count.setText(i18n.tr("preview.count", index=index + 1, total=total))
        self.fav_button.setText(i18n.tr("preview.unfav") if favorite else i18n.tr("preview.fav"))
        self._pix = QPixmap()
        self.image.setPixmap(QPixmap())
        self.image.setText(i18n.tr("preview.loading"))
        self.show()
        self.raise_()
        self.activateWindow()

    def set_message(self, text):
        if text:
            self.image.setPixmap(QPixmap())
            self.image.setText(text)

    def set_pixmap(self, pix):
        self._pix = pix
        self.image.setText("")
        self._rescale()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._rescale()

    def _rescale(self):
        if self._pix.isNull():
            return
        scaled = self._pix.scaled(self.image.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.image.setPixmap(scaled)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Left:
            self.stepRequested.emit(-1)
        elif event.key() == Qt.Key_Right:
            self.stepRequested.emit(1)
        elif event.key() == Qt.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)


def _native_window_visible(widget):
    """操作系统是否真的把窗口显示出来了。

    非 Windows 没有 SW_HIDE 这种启动状态，Qt 的可见标记就是准的。
    Windows 上要以 HWND 为准：启动时的 SW_HIDE 会让 Qt 标成可见，窗口却是藏着的。
    """
    if not widget.isVisible():
        return False
    if sys.platform != "win32":
        return True
    import ctypes

    hwnd = int(widget.winId())
    if hwnd == 0:
        return False
    return bool(ctypes.windll.user32.IsWindowVisible(hwnd))


class MainWindow(QMainWindow):
    def __init__(self, start_hidden=False):
        super().__init__()
        self.setWindowTitle(i18n.tr("app.name"))
        self.resize(1180, 760)
        self.setMinimumSize(880, 560)
        self.icon = make_icon()
        self.setWindowIcon(self.icon)
        self._alive = True
        self.settings = core.load_settings()
        self.source = self.settings.get("source") or "birdpaper"
        if self.source not in {item.key for item in core.SOURCES}:
            self.source = "birdpaper"
        self.category_id = str(self.settings.get("category_id") or core.DEFAULT_CATEGORY_ID)
        self.wh_categories = self.settings.get("wh_categories") or "111"
        if self.wh_categories not in core.WALLHAVEN_CATEGORY_PARAM:
            self.wh_categories = "111"
        self.wh_sorting = self.settings.get("wh_sorting") or "date_added"
        self.wh_atleast = self.settings.get("wh_atleast") or "1920x1080"
        self.close_to_tray = bool(self.settings.get("close_to_tray", True))
        self.query = ""
        self.page_no = 0
        self.has_more = False
        self.loading = False
        self.busy = False
        self.quitting = False
        self.gen = 0
        self.preview_row = -1
        self.preview_req = 0
        self._tray_index = -1
        self._apply_when_ready = False
        self.pending = set()
        self.categories = list(core.FALLBACK_CATEGORIES)
        self.category_table = core.category_table(self.categories)
        if self.category_id not in self.category_table:
            self.category_id = core.DEFAULT_CATEGORY_ID
        self.favorites = core.load_wallpaper_list(core.favorites_path())
        self.history = core.load_wallpaper_list(core.history_path())

        self.bus = Bus(self)
        self.bus.categories.connect(self._on_categories)
        self.bus.page.connect(self._on_page)
        self.bus.thumb.connect(self._on_thumb)
        self.bus.task.connect(self._on_task)
        self.bus.preview.connect(self._on_preview)
        self.page_pool = Pool(1)
        # 缩略图和大图分开。大图只有两条，避免一张原图占住卡片加载。
        self.thumb_pool = Pool(8)
        self.image_pool = Pool(2)
        self.model = WallpaperModel()

        self._build()
        self._setup_tray()
        self._apply_source_chrome()
        self._sync_copy()
        QShortcut(QKeySequence.Find, self, activated=self.search.setFocus)
        if core.network_allowed():
            self.page_pool.submit(self._load_categories_job)
        self.reload()
        if start_hidden and self.tray_ok:
            self.hide()
        else:
            self.show()
            # 第一次 show() 可能被进程启动时的 SW_HIDE 吃掉：Qt 已标成可见，
            # 窗口却没出来。立刻再用 show_normal() 把它打开。
            if not _native_window_visible(self):
                self.show_normal()

    def _build(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_sidebar())
        root.addWidget(self._build_content(), 1)
        self.preview = PreviewDialog(self)
        self.preview.applyRequested.connect(lambda: self.apply_item(self.preview_row))
        self.preview.saveRequested.connect(lambda: self.save_item(self.preview_row))
        self.preview.favoriteRequested.connect(lambda: self.toggle_fav(self.preview_row))
        self.preview.stepRequested.connect(self.step_preview)

    def _build_sidebar(self):
        side = QFrame()
        side.setObjectName("sidebar")
        side.setFixedWidth(196)
        layout = QVBoxLayout(side)
        layout.setContentsMargins(16, 18, 16, 16)
        layout.setSpacing(6)
        brand_row = QHBoxLayout()
        mark = QLabel()
        mark.setPixmap(self.icon.pixmap(28, 28))
        brand_row.addWidget(mark)
        brand = QLabel(i18n.tr("app.name"))
        brand.setObjectName("heading")
        brand_row.addWidget(brand)
        brand_row.addStretch(1)
        layout.addLayout(brand_row)
        hint = QLabel(i18n.tr("app.hint"))
        hint.setObjectName("muted")
        layout.addWidget(hint)
        layout.addSpacing(12)
        self.nav_buttons = []
        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        for info in core.SOURCES:
            button = QPushButton(i18n.source_name(info.key))
            button.setObjectName("nav")
            button.setCheckable(True)
            button.setCursor(Qt.PointingHandCursor)
            button.setProperty("source", info.key)
            button.clicked.connect(lambda _checked, key=info.key: self.select_source(key))
            self.nav_group.addButton(button)
            self.nav_buttons.append(button)
            layout.addWidget(button)
        layout.addStretch(1)
        settings = QPushButton(i18n.tr("nav.settings"))
        settings.setObjectName("ghost")
        settings.setCursor(Qt.PointingHandCursor)
        settings.clicked.connect(self.open_settings)
        layout.addWidget(settings)
        return side

    def _build_content(self):
        content = QWidget()
        content.setObjectName("content")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(22, 18, 22, 10)
        layout.setSpacing(10)
        self.heading = QLabel(i18n.tr("app.name"))
        self.heading.setObjectName("heading")
        self.subheading = QLabel("")
        self.subheading.setObjectName("muted")
        self.subheading.setWordWrap(True)
        layout.addWidget(self.heading)
        layout.addWidget(self.subheading)

        search_row = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setObjectName("search")
        self.search.returnPressed.connect(self.submit_search)
        self.search_button = QPushButton(i18n.tr("search.button"))
        self.search_button.setObjectName("primary")
        self.search_button.setCursor(Qt.PointingHandCursor)
        self.search_button.clicked.connect(self.submit_search)
        search_row.addWidget(self.search, 1)
        search_row.addWidget(self.search_button)
        layout.addLayout(search_row)

        self.chips = ChipBar()
        self.chips.chosen.connect(self.on_chip)
        self.chip_scroll = HScroll()
        self.chip_scroll.setWidget(self.chips)
        layout.addWidget(self.chip_scroll)

        self.hot = ChipBar()
        self.hot.chosen.connect(self.on_hot)
        self.hot_scroll = HScroll()
        self.hot_scroll.setWidget(self.hot)
        self.hot_caption = QLabel(i18n.tr("search.hot"))
        self.hot_caption.setObjectName("muted")
        hot_row = QHBoxLayout()
        hot_row.setSpacing(8)
        hot_row.addWidget(self.hot_caption)
        hot_row.addWidget(self.hot_scroll, 1)
        layout.addLayout(hot_row)

        self.wallhaven_tools = QWidget()
        tools = QHBoxLayout(self.wallhaven_tools)
        tools.setContentsMargins(0, 0, 0, 0)
        sort_label = QLabel(i18n.tr("wh.sort_label"))
        sort_label.setObjectName("muted")
        self.sort_box = QComboBox()
        for key, _label in core.WALLHAVEN_SORTS:
            self.sort_box.addItem(i18n.tr("wh.sort." + key), key)
        size_label = QLabel(i18n.tr("wh.size_label"))
        size_label.setObjectName("muted")
        self.size_box = QComboBox()
        for key, _label in core.WALLHAVEN_SIZES:
            self.size_box.addItem(i18n.tr("wh.size." + key), key)
        self._select_combo(self.sort_box, self.wh_sorting)
        self._select_combo(self.size_box, self.wh_atleast)
        self.sort_box.currentIndexChanged.connect(self._sort_changed)
        self.size_box.currentIndexChanged.connect(self._size_changed)
        tools.addWidget(sort_label)
        tools.addWidget(self.sort_box)
        tools.addSpacing(8)
        tools.addWidget(size_label)
        tools.addWidget(self.size_box)
        tools.addStretch(1)
        layout.addWidget(self.wallhaven_tools)

        self.banner = QFrame()
        self.banner.setObjectName("banner")
        banner_row = QHBoxLayout(self.banner)
        self.banner_label = QLabel("")
        self.banner_label.setWordWrap(True)
        retry = QPushButton(i18n.tr("action.retry"))
        retry.setObjectName("ghost")
        retry.clicked.connect(self.reload)
        banner_row.addWidget(self.banner_label, 1)
        banner_row.addWidget(retry)
        self.banner.hide()
        layout.addWidget(self.banner)

        self.stack = QStackedWidget()
        self.view = WallpaperView()
        self.view.setModel(self.model)
        self.view.delegate.favorite_text = self._favorite_text
        self.view.applyRequested.connect(self.apply_item)
        self.view.favoriteRequested.connect(self.toggle_fav)
        self.view.previewRequested.connect(self.open_preview)
        self.view.menuRequested.connect(self.open_menu)
        self.view.nearEnd.connect(self.load_more)
        self.view.verticalScrollBar().valueChanged.connect(lambda _v: self.queue_visible())
        self.stack.addWidget(self.view)

        self.loading_page, self.loading_label = self._message_page(i18n.tr("status.loading"))
        self.empty_page, self.empty_label = self._message_page(i18n.tr("status.none"))
        empty_retry = QPushButton(i18n.tr("action.reload"))
        empty_retry.setObjectName("ghost")
        empty_retry.clicked.connect(self.reload)
        self.empty_page.layout().insertWidget(2, empty_retry, 0, Qt.AlignHCenter)
        self.error_page, self.error_label = self._message_page(i18n.tr("status.fail"))
        error_retry = QPushButton(i18n.tr("action.retry"))
        error_retry.setObjectName("primary")
        error_retry.clicked.connect(self.reload)
        self.error_page.layout().insertWidget(2, error_retry, 0, Qt.AlignHCenter)
        self.stack.addWidget(self.loading_page)
        self.stack.addWidget(self.empty_page)
        self.stack.addWidget(self.error_page)
        layout.addWidget(self.stack, 1)

        self.footer = QLabel(i18n.tr("footer.hint"))
        self.footer.setObjectName("footer")
        layout.addWidget(self.footer)
        return content

    def _message_page(self, text):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addStretch(1)
        label = QLabel(text)
        label.setAlignment(Qt.AlignCenter)
        label.setWordWrap(True)
        label.setObjectName("muted")
        layout.addWidget(label)
        layout.addStretch(1)
        return page, label

    def _setup_tray(self):
        self.tray_ok = QSystemTrayIcon.isSystemTrayAvailable()
        self.tray = QSystemTrayIcon(self.icon, self)
        self.tray.setToolTip(i18n.tr("app.name"))
        menu = QMenu()
        menu.addAction(i18n.tr("tray.open"), self.show_normal)
        menu.addAction(i18n.tr("tray.next"), self.next_wallpaper)
        menu.addAction(i18n.tr("tray.folder"), self.open_folder)
        menu.addSeparator()
        menu.addAction(i18n.tr("tray.quit"), self.quit_app)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._tray_activated)
        if self.tray_ok:
            self.tray.show()

    def _tray_activated(self, reason):
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.show_normal()

    def show_normal(self):
        # 用 SW_HIDE 启动时（Start-Process -WindowStyle Hidden 等），Qt 认为窗口
        # 已经可见，后面的 show() 直接返回。先 hide() 清掉这个标记，再真正显示。
        preview = getattr(self, "preview", None)
        preview_open = preview is not None and preview.isVisible()
        if self.isVisible():
            self.hide()
        self.setWindowState((self.windowState() & ~Qt.WindowMinimized) | Qt.WindowActive)
        self.showNormal()
        self.raise_()
        self.activateWindow()
        if preview_open:
            preview.show()
            preview.raise_()
            preview.activateWindow()

    def category_labels(self):
        return self.chips.labels()

    def select_source(self, key):
        self.source = key
        self.query = ""
        self.search.clear()
        for button in self.nav_buttons:
            button.setChecked(button.property("source") == key)
        self._apply_source_chrome()
        self._sync_copy()
        self.reload()
        self._save_settings()

    def _apply_source_chrome(self):
        info = core.source_info(self.source)
        for button in self.nav_buttons:
            button.setChecked(button.property("source") == self.source)
        self.search.setEnabled(info.searchable)
        self.search.setPlaceholderText(i18n.tr("placeholder." + info.key))
        self.search_button.setVisible(info.searchable)
        self.wallhaven_tools.setVisible(self.source == "wallhaven")
        if self.source == "birdpaper":
            self.chip_scroll.show()
            selected = None if self.query else self.category_id
            self.chips.set_items([(item.id, i18n.category_name(item.name)) for item in self.categories], selected)
            self._show_hot_tags()
        elif self.source == "wallhaven":
            self.chip_scroll.show()
            self.chips.set_items(
                [(key, i18n.category_name(label)) for key, label in core.WALLHAVEN_CATEGORY_PARAM.items()],
                self.wh_categories,
            )
            self.hot_caption.hide()
            self.hot_scroll.hide()
        else:
            self.chip_scroll.hide()
            self.hot_caption.hide()
            self.hot_scroll.hide()

    def _show_hot_tags(self):
        tags = ()
        if self.source == "birdpaper" and not self.query:
            category = self.category_table.get(self.category_id)
            tags = category.hot_tags if category else ()
        if tags:
            self.hot.set_items([(tag, i18n.tag_name(tag)) for tag in tags], None)
            self.hot.select(None)
            self.hot_caption.show()
            self.hot_scroll.show()
        else:
            self.hot_caption.hide()
            self.hot_scroll.hide()

    def on_chip(self, cid):
        if self.source == "wallhaven":
            self.wh_categories = cid
        else:
            self.category_id = cid
            self.query = ""
            self.search.clear()
        self._show_hot_tags()
        self._sync_copy()
        self.reload()
        self._save_settings()

    def on_hot(self, tag):
        self.search.setText(tag)
        self.submit_search()

    def submit_search(self):
        if not core.source_info(self.source).searchable:
            return
        self.query = self.search.text().strip()
        if self.source == "birdpaper":
            if self.query:
                self.chips.select(None)
            else:
                self.chips.select(self.category_id)
        self._show_hot_tags()
        self._sync_copy()
        self.reload()

    def _sort_changed(self):
        self.wh_sorting = self.sort_box.currentData() or "date_added"
        if self.source == "wallhaven":
            self.reload()
            self._save_settings()

    def _size_changed(self):
        self.wh_atleast = self.size_box.currentData() or "1920x1080"
        if self.source == "wallhaven":
            self.reload()
            self._save_settings()

    def _select_combo(self, box, value):
        index = box.findData(value)
        if index >= 0:
            box.setCurrentIndex(index)

    def _sync_copy(self, note=""):
        if self.source == "birdpaper":
            category = self.category_table.get(self.category_id)
            name = "" if self.query else (category.name if category else "")
            title, subtitle = core.describe_view("birdpaper", name, self.query, note)
        elif self.source == "wallhaven":
            name = core.WALLHAVEN_CATEGORY_PARAM.get(self.wh_categories, "")
            title, subtitle = core.describe_view("wallhaven", name, self.query, note)
        else:
            title, subtitle = core.describe_view(self.source, "", self.query, note)
        self.heading.setText(title)
        self.subheading.setText(subtitle)

    def _spec(self, page):
        return core.FetchSpec(
            source=self.source,
            category_id=self.category_id,
            query=self.query,
            page=page,
            wh_categories=self.wh_categories,
            wh_sorting=self.wh_sorting,
            wh_atleast=self.wh_atleast,
        )

    def reload(self):
        self.gen += 1
        generation = self.gen
        self.page_no = 0
        self.has_more = True
        self.loading = False
        self.pending.clear()
        self.model.failed.clear()
        self.model.reset([])
        self.banner.hide()
        if self.preview.isVisible():
            self.preview.hide()
        self._sync_copy()
        if not core.network_allowed() and self.source in ("birdpaper", "wallhaven", "bing", "nasa"):
            self._show_empty(i18n.tr("status.offline"))
            return
        self._fetch(generation, 1)

    def load_more(self):
        if self.loading or not self.has_more or self.page_no <= 0:
            return
        self._fetch(self.gen, self.page_no + 1)

    def _fetch(self, generation, page):
        if generation != self.gen:
            return
        self.loading = True
        if page == 1 and self.model.rowCount() == 0:
            self._show_loading()
        else:
            self.set_status(i18n.tr("status.loading_more"))
        spec = self._spec(page)
        if spec.source in ("favorites", "history"):
            result = core.load_page(spec, self.category_table, self.favorites, self.history)
            self._apply_page(generation, page, result)
            return

        def work():
            try:
                result = core.load_page(spec, self.category_table, self.favorites, self.history)
            except core.SourceError as exc:
                result = core.PageResult([], False, error=str(exc))
            except Exception as exc:
                core.log(traceback.format_exc())
                result = core.PageResult([], False, error=i18n.tr("err.load", error=exc))
            self.bus.page.emit(generation, page, result)

        self.page_pool.submit(work)

    def _on_page(self, generation, page, result):
        self._apply_page(generation, page, result)

    def _apply_page(self, generation, page, result):
        if not self._alive or generation != self.gen:
            return
        self.loading = False
        self._sync_copy(result.note)
        if result.error and page == 1 and not result.items:
            self._show_error(result.error)
            return
        if result.error:
            self.banner_label.setText(result.error)
            self.banner.show()
        else:
            self.banner.hide()
        fresh = result.items if page == 1 else core.dedupe_items(self.model.items, result.items)
        if page == 1:
            self.model.reset(fresh)
        elif fresh:
            self.model.append(fresh)
        if page > 1 and not fresh:
            self.has_more = False
        else:
            self.has_more = bool(result.has_more and fresh)
        self.page_no = page
        count = self.model.rowCount()
        if count == 0:
            self._show_empty(self._empty_message(result.note, result.error))
        else:
            self._show_grid()
            more = i18n.tr("status.more") if self.has_more else ""
            self.set_status(i18n.tr("status.shown", count=count, more=more))
            QTimer.singleShot(0, self.queue_visible)
        if self._apply_when_ready and count:
            self._apply_when_ready = False
            self._tray_index = 0
            self.apply_item(0)

    def _empty_message(self, note, error):
        if error:
            return error
        if note:
            return note
        if self.query:
            return i18n.tr("status.empty_query", query=self.query)
        return i18n.tr("status.empty")

    def _show_grid(self):
        self.stack.setCurrentWidget(self.view)

    def _show_loading(self):
        if self.query:
            text = i18n.tr("status.searching", query=self.query)
        elif self.source == "birdpaper":
            category = self.category_table.get(self.category_id)
            name = i18n.category_name(category.name) if category else i18n.tr("app.name")
            text = i18n.tr("status.loading_cat", name=name)
        else:
            text = i18n.tr("status.loading")
        self.loading_label.setText(text)
        self.stack.setCurrentWidget(self.loading_page)

    def _show_empty(self, text):
        self.empty_label.setText(text)
        self.stack.setCurrentWidget(self.empty_page)
        self.set_status(text)

    def _show_error(self, text):
        self.error_label.setText(text)
        self.stack.setCurrentWidget(self.error_page)
        self.set_status(text)

    def show_items(self, items, note=""):
        """测试和手动注入用。不访问网络。"""
        self.model.reset(list(items))
        self.has_more = False
        self.loading = False
        self._sync_copy(note)
        if items:
            self._show_grid()
        else:
            self._show_empty(note or i18n.tr("status.none"))
        self.set_status(i18n.tr("status.shown", count=len(items), more=""))
        self.view.relayout()
        self.queue_visible()

    def queue_visible(self):
        if not self._alive:
            return
        count = self.model.rowCount()
        if count == 0:
            return
        viewport = self.view.viewport().rect().adjusted(0, -120, 0, 360)
        queued = 0
        any_rect = False
        for row in range(count):
            rect = self.view.visualRect(self.model.index(row, 0))
            if rect.isValid() and rect.height() > 0:
                any_rect = True
            if not any_rect:
                continue
            if rect.intersects(viewport):
                self.ensure_thumb(row)
                queued += 1
        if not any_rect:
            for row in range(min(count, 12)):
                self.ensure_thumb(row)

    def ensure_thumb(self, row):
        item = self.model.item(row)
        if item is None:
            return
        url = item.thumb_url
        if not url or url in self.model.thumbs or url in self.pending or url in self.model.failed:
            return
        aliases = core.thumb_cache_aliases(item)
        cached = core.find_thumb(url, aliases=aliases)
        if cached:
            self.model.set_thumb(url, cached)
            return
        self.pending.add(url)
        generation = self.gen
        fallbacks = core.thumb_fallback_urls(item)

        def work(url=url, generation=generation, aliases=aliases, fallbacks=fallbacks):
            if generation != self.gen:
                self.bus.thumb.emit(generation, url, "", "stale")
                return
            try:
                path = core.ensure_thumb(url, aliases=aliases, fallback_urls=fallbacks)
                self.bus.thumb.emit(generation, url, path, "")
            except Exception as exc:
                self.bus.thumb.emit(generation, url, "", str(exc))

        self.thumb_pool.submit(work)

    def _on_thumb(self, generation, url, path, error):
        self.pending.discard(url)
        if not self._alive or generation != self.gen or error == "stale":
            return
        if error or not path:
            self.model.mark_failed(url)
            return
        self.model.set_thumb(url, path)

    def _load_categories_job(self):
        try:
            categories = core.fetch_categories()
            self.bus.categories.emit(categories, "")
        except Exception as exc:
            core.log(traceback.format_exc())
            self.bus.categories.emit(list(core.FALLBACK_CATEGORIES), str(exc))

    def _on_categories(self, categories, error):
        if not self._alive or not categories:
            return
        self.categories = list(categories)
        self.category_table = core.category_table(self.categories)
        if self.category_id not in self.category_table:
            self.category_id = (
                core.DEFAULT_CATEGORY_ID
                if core.DEFAULT_CATEGORY_ID in self.category_table
                else self.categories[0].id
            )
        if self.source == "birdpaper":
            selected = None if self.query else self.category_id
            self.chips.set_items([(item.id, i18n.category_name(item.name)) for item in self.categories], selected)
            self._show_hot_tags()
            self._sync_copy()
        if error:
            self.set_status(i18n.tr("status.categories_fallback"))

    def _favorite_text(self, row):
        item = self.model.item(row)
        if item is None:
            return i18n.tr("card.fav")
        return i18n.tr("card.faved") if core.is_favorite(self.favorites, item) else i18n.tr("card.fav")

    def toggle_fav(self, row):
        item = self.model.item(row)
        if item is None:
            return
        self.favorites, added = core.toggle_favorite(self.favorites, item)
        core.save_wallpaper_list(core.favorites_path(), self.favorites)
        self.set_status(i18n.tr("status.fav_on") if added else i18n.tr("status.fav_off"))
        if self.preview.isVisible():
            self.preview.fav_button.setText(i18n.tr("preview.unfav") if added else i18n.tr("preview.fav"))
        if self.source == "favorites":
            self.reload()
        else:
            self.view.viewport().update()

    def open_preview(self, row):
        item = self.model.item(row)
        if item is None:
            return
        self.preview_row = row
        self.preview_req += 1
        request_id = self.preview_req
        self.preview.show_item(item, row, self.model.rowCount(), core.is_favorite(self.favorites, item))

        def work(item=item, request_id=request_id):
            try:
                path = core.download_original(item.full_url)
                self.bus.preview.emit(request_id, path, "")
            except Exception as exc:
                self.bus.preview.emit(request_id, "", str(exc))

        self.image_pool.submit(work)

    def step_preview(self, delta):
        count = self.model.rowCount()
        if count <= 0 or self.preview_row < 0:
            return
        self.open_preview((self.preview_row + delta) % count)

    def _on_preview(self, request_id, path, error):
        if not self._alive or request_id != self.preview_req:
            return
        if error or not path:
            self.preview.set_message(i18n.tr("preview.failed", error=error or i18n.tr("err.unknown")))
            return
        pix = QPixmap(path)
        if pix.isNull():
            self.preview.set_message(i18n.tr("preview.bad"))
            return
        self.preview.set_pixmap(pix)
        self._prefetch_next()

    def _prefetch_next(self):
        count = self.model.rowCount()
        if count <= 1 or self.preview_row < 0:
            return
        item = self.model.item((self.preview_row + 1) % count)
        if item is None:
            return

        def work(url=item.full_url):
            try:
                core.download_original(url)
            except Exception:
                core.log(traceback.format_exc())

        self.image_pool.submit(work)

    def open_menu(self, row, global_pos):
        item = self.model.item(row)
        if item is None:
            return
        menu = QMenu(self)
        menu.addAction(i18n.tr("menu.preview"), lambda: self.open_preview(row))
        menu.addAction(i18n.tr("menu.set"), lambda: self.apply_item(row))
        menu.addAction(i18n.tr("menu.save"), lambda: self.save_item(row))
        label = i18n.tr("menu.unfav") if core.is_favorite(self.favorites, item) else i18n.tr("menu.fav")
        menu.addAction(label, lambda: self.toggle_fav(row))
        menu.addSeparator()
        menu.addAction(i18n.tr("menu.copy"), lambda: self.copy_link(row))
        menu.addAction(i18n.tr("menu.browser"), lambda: self.open_browser(row))
        menu.exec_(global_pos)

    def copy_link(self, row):
        item = self.model.item(row)
        if item is None:
            return
        QApplication.clipboard().setText(item.page_url or item.full_url)
        self.set_status(i18n.tr("status.copied"))

    def open_browser(self, row):
        item = self.model.item(row)
        if item is None:
            return
        webbrowser.open(item.page_url or item.full_url)

    def apply_item(self, row):
        self._file_task(row, apply=True)

    def save_item(self, row):
        self._file_task(row, apply=False)

    def _file_task(self, row, apply):
        item = self.model.item(row)
        if item is None:
            return
        if self.busy:
            self.set_status(i18n.tr("status.busy"))
            return
        self.busy = True
        action = i18n.tr("action.set") if apply else i18n.tr("action.save")
        self.set_status(i18n.tr("status.working", action=action, title=item.title))

        def work(item=item, apply=apply):
            try:
                path = core.materialize_wallpaper(item)
                if apply:
                    ok = core.set_wallpaper(path)
                    if ok:
                        message = i18n.tr("toast.wallpaper_set", name=os.path.basename(path))
                    else:
                        note = core.last_wallpaper_note() or i18n.tr("toast.wallpaper_unsupported")
                        message = i18n.tr("toast.saved_only", path=path, note=note)
                        if sys.platform == "win32":
                            message = i18n.tr("toast.set_failed", path=path)
                        ok = False
                else:
                    ok = False
                    message = i18n.tr("toast.saved", path=path)
                self.bus.task.emit(message, bool(apply and ok), item.to_dict())
            except Exception as exc:
                core.log(traceback.format_exc())
                self.bus.task.emit(i18n.tr("toast.failed", error=exc), False, None)

        self.image_pool.submit(work)

    def _on_task(self, message, remember, payload):
        if not self._alive:
            return
        self.busy = False
        self.set_status(message)
        if remember and isinstance(payload, dict):
            try:
                item = core.Wallpaper.from_dict(payload)
            except TypeError:
                item = None
            if item is not None:
                self.history = core.remember_history(self.history, item)
                core.save_wallpaper_list(core.history_path(), self.history)
                if self.source == "history":
                    self.reload()
        if not self.isVisible() and self.tray_ok:
            self.tray.showMessage(i18n.tr("app.name"), message, QSystemTrayIcon.Information, 3000)

    def next_wallpaper(self):
        if self.busy:
            self.set_status(i18n.tr("status.busy"))
            return
        count = self.model.rowCount()
        if count == 0:
            self._apply_when_ready = True
            self.set_status(i18n.tr("status.preparing"))
            if not self.loading:
                self.reload()
            return
        self._tray_index = (self._tray_index + 1) % count
        self.apply_item(self._tray_index)

    def open_folder(self):
        try:
            core.open_path(core.SAVE_DIR)
        except Exception as exc:
            self.set_status(i18n.tr("status.folder_fail", error=exc))

    def open_settings(self):
        dialog = QDialog(self)
        dialog.setWindowTitle(i18n.tr("settings.title"))
        dialog.setMinimumWidth(440)
        layout = QVBoxLayout(dialog)
        layout.setSpacing(12)
        intro = QLabel(i18n.tr("settings.intro"))
        intro.setWordWrap(True)
        layout.addWidget(intro)

        lang_row = QHBoxLayout()
        lang_label = QLabel(i18n.tr("settings.language"))
        lang_box = QComboBox()
        for key in ("auto", "zh_CN", "en"):
            lang_box.addItem(i18n.tr("settings.lang." + key), key)
        saved_lang = self.settings.get("language") or "auto"
        if saved_lang not in ("auto", "zh_CN", "en"):
            saved_lang = "auto"
        index = lang_box.findData(saved_lang)
        if index >= 0:
            lang_box.setCurrentIndex(index)
        lang_note = QLabel("")
        lang_note.setObjectName("muted")
        lang_note.setWordWrap(True)

        def on_lang():
            choice = lang_box.currentData() or "auto"
            self.settings["language"] = "" if choice == "auto" else choice
            self._save_settings()
            target = i18n.system_language() if choice == "auto" else choice
            if target != i18n.current():
                lang_note.setText(i18n.tr("settings.restart"))
            else:
                lang_note.setText("")

        lang_box.currentIndexChanged.connect(lambda _i: on_lang())
        lang_row.addWidget(lang_label)
        lang_row.addWidget(lang_box, 1)
        layout.addLayout(lang_row)
        layout.addWidget(lang_note)

        close_box = QCheckBox(i18n.tr("settings.close_tray"))
        close_box.setChecked(self.close_to_tray)
        layout.addWidget(close_box)
        auto = QCheckBox(i18n.tr("settings.autostart"))
        if core.autostart_supported():
            try:
                auto.setChecked(core.read_autostart())
            except OSError:
                auto.setChecked(False)
        else:
            auto.setText(i18n.tr("settings.autostart_other"))
            auto.setEnabled(False)
        layout.addWidget(auto)

        def on_close(checked):
            self.close_to_tray = bool(checked)
            self._save_settings()

        def on_auto(checked):
            try:
                core.write_autostart(bool(checked))
            except core.SourceError as exc:
                QMessageBox.information(dialog, i18n.tr("app.name"), str(exc))
                auto.blockSignals(True)
                auto.setChecked(False)
                auto.blockSignals(False)

        close_box.toggled.connect(on_close)
        auto.toggled.connect(on_auto)

        def make(kind):
            try:
                path = core.create_shortcut(kind)
                QMessageBox.information(dialog, i18n.tr("app.name"), i18n.tr("settings.shortcut_ok", path=path))
            except core.SourceError as exc:
                QMessageBox.information(dialog, i18n.tr("app.name"), str(exc))

        desk = QPushButton(i18n.tr("settings.desktop"))
        start = QPushButton(i18n.tr("settings.start"))
        folder = QPushButton(i18n.tr("settings.folder"))
        for button in (desk, start, folder):
            button.setObjectName("ghost")
        desk.clicked.connect(lambda: make("desktop"))
        start.clicked.connect(lambda: make("startmenu"))
        folder.clicked.connect(self.open_folder)
        if core.autostart_supported():
            layout.addWidget(desk)
            layout.addWidget(start)
        layout.addWidget(folder)
        if core.is_frozen():
            note_key = "settings.note_frozen"
        elif core.autostart_supported():
            note_key = "settings.note"
        else:
            note_key = "settings.note_other"
        note = QLabel(i18n.tr(note_key))
        note.setObjectName("muted")
        note.setWordWrap(True)
        layout.addWidget(note)
        close_button = QPushButton(i18n.tr("settings.close"))
        close_button.setObjectName("primary")
        close_button.clicked.connect(dialog.accept)
        layout.addWidget(close_button)
        dialog.exec_()

    def set_status(self, text):
        self.footer.setText(text)

    def _save_settings(self):
        data = dict(self.settings)
        data.update({
            "source": self.source,
            "category_id": self.category_id,
            "wh_categories": self.wh_categories,
            "wh_sorting": self.wh_sorting,
            "wh_atleast": self.wh_atleast,
            "close_to_tray": self.close_to_tray,
            "language": self.settings.get("language") or "",
            "seen_tray_hint": bool(self.settings.get("seen_tray_hint")),
        })
        self.settings = data
        try:
            core.save_settings(data)
        except OSError as exc:
            core.log(exc)

    def closeEvent(self, event):
        if core.should_minimize_to_tray(self.close_to_tray, self.tray_ok, self.quitting):
            event.ignore()
            self.hide()
            if self.tray_ok and not self.settings.get("seen_tray_hint"):
                self.tray.showMessage(
                    i18n.tr("tray.still"),
                    i18n.tr("tray.still_body"),
                    QSystemTrayIcon.Information,
                    4000,
                )
                self.settings["seen_tray_hint"] = True
                self._save_settings()
            return
        self.quitting = True
        self._alive = False
        self._save_settings()
        event.accept()
        app = QApplication.instance()
        if app is not None:
            app.quit()

    def quit_app(self):
        self.quitting = True
        self.close()


class InstanceGuard(QObject):
    showRequested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.server = None

    def claim(self):
        socket = QLocalSocket()
        socket.connectToServer(INSTANCE_NAME)
        if socket.waitForConnected(250):
            socket.write(b"show")
            socket.flush()
            socket.waitForBytesWritten(250)
            socket.disconnectFromServer()
            return False
        QLocalServer.removeServer(INSTANCE_NAME)
        self.server = QLocalServer(self)
        if not self.server.listen(INSTANCE_NAME):
            core.log("单实例端口监听失败：" + self.server.errorString())
            return True
        self.server.newConnection.connect(self._incoming)
        return True

    def _incoming(self):
        connection = self.server.nextPendingConnection()
        if connection is None:
            return
        connection.waitForReadyRead(200)
        connection.disconnectFromServer()
        self.showRequested.emit()


def main(argv=None):
    argv = list(sys.argv if argv is None else argv)
    os.makedirs(core.cache_dir(), exist_ok=True)
    # 必须在 QApplication 之前。否则任务栏会沿用 pythonw 的图标。
    core.set_explicit_app_user_model_id()
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(argv)
    i18n.activate(core.load_settings().get("language"))
    app.setApplicationName(i18n.tr("app.name"))
    app.setApplicationDisplayName(i18n.tr("app.name"))
    app.setQuitOnLastWindowClosed(False)
    app.setFont(choose_font())
    app.setStyleSheet(STYLE)
    app.setWindowIcon(make_icon())
    guard = InstanceGuard()
    if not guard.claim():
        return 0
    window = MainWindow(start_hidden="--background" in argv)
    guard.showRequested.connect(window.show_normal)
    app._wallpaper_guard = guard
    app._wallpaper_window = window
    if sys.platform == "win32":
        threading.Thread(target=_ensure_windows_shortcut, daemon=True).start()
    return app.exec_()


def _ensure_windows_shortcut():
    try:
        core.ensure_start_menu_shortcut()
    except Exception:
        core.log(traceback.format_exc())


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        core.log(traceback.format_exc())
        raise

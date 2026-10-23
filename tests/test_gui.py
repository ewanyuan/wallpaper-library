# -*- coding: utf-8 -*-
"""离屏启动窗口，确认分类芯片和卡片分类来自数据而不是写死的兴趣名。"""

import os
import tempfile
import time
import unittest

from PIL import Image

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("WALLPAPER_INSTANCE", "wp-test-%s" % os.getpid())

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication

import i18n
import wallpaper_app_qt
import wallpaper_core as core


class GuiSmoke(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["WALLPAPER_NO_NETWORK"] = "1"
        cls.home = tempfile.mkdtemp()
        os.environ["WALLPAPER_HOME"] = cls.home
        os.environ["WALLPAPER_INSTANCE"] = "wp-test-%s" % os.getpid()
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyle("Fusion")
        cls.app.setFont(wallpaper_app_qt.choose_font())
        cls.app.setStyleSheet(wallpaper_app_qt.STYLE)
        i18n.activate("zh_CN")
        cls.window = wallpaper_app_qt.MainWindow()
        cls.window.resize(1180, 760)
        cls.app.processEvents()

    @classmethod
    def tearDownClass(cls):
        cls.window.quitting = True
        cls.window.close()
        os.environ.pop("WALLPAPER_NO_NETWORK", None)
        os.environ.pop("WALLPAPER_HOME", None)

    def test_card_grid_fills_the_viewport(self):
        cols, cell_w, cell_h = wallpaper_app_qt.card_grid(830)
        self.assertEqual(cols, 3)
        self.assertGreaterEqual(cell_w, wallpaper_app_qt.MIN_CARD_WIDTH)
        self.assertLess(cols * cell_w, 830)
        image_h = cell_h - wallpaper_app_qt.CARD_TEXT_BLOCK
        self.assertEqual(image_h, int((cell_w - 16) * 9 / 16))
        self.window.resize(1024, 720)
        self.window.show()
        items = [
            core.Wallpaper(
                id=str(i), title="城市夜景%d" % i, thumb_url="grid-%d" % i, full_url="full-%d" % i,
                source="360壁纸", source_key="birdpaper", category="风景大片", category_id="9",
                resolution="1920x1080",
            )
            for i in range(8)
        ]
        self.window.model.reset(items)
        self.window.stack.setCurrentWidget(self.window.view)
        self.app.processEvents()
        view = self.window.view
        view.relayout()
        self.app.processEvents()
        width = view.viewport().width()
        cols, cell_w, _cell_h = wallpaper_app_qt.card_grid(width, view.spacing())
        self.assertGreaterEqual(cols, 3)
        self.assertEqual(view.gridSize().width(), cell_w)
        xs = []
        for index in range(cols):
            rect = view.visualRect(view.model().index(index, 0))
            xs.append(rect.x())
            self.assertEqual(rect.width(), cell_w)
        self.assertEqual(len(set(xs)), cols)
        right = max(xs) + cell_w
        self.assertLessEqual(right, width)
        self.assertGreaterEqual(right, width - cols - wallpaper_app_qt.GRID_SLACK)
        wrapped = view.visualRect(view.model().index(cols, 0))
        self.assertEqual(wrapped.x(), 0)
        self.assertGreater(wrapped.y(), 0)
        self.assertEqual(self.window.chip_scroll.horizontalScrollBarPolicy(), Qt.ScrollBarAlwaysOff)
        self.assertEqual(self.window.hot_scroll.horizontalScrollBarPolicy(), Qt.ScrollBarAlwaysOff)

    def test_chip_bar_stays_wide_when_categories_arrive(self):
        self.window.show()
        self.app.processEvents()
        pairs = [(item.id, item.name) for item in core.FALLBACK_CATEGORIES]
        self.window.chips.set_items(pairs, "9")
        self.app.processEvents()
        self.assertGreater(len(self.window.chips.buttons), 3)
        self.assertGreater(self.window.chips.width(), 200)

    def test_window_uses_the_app_icon_and_title(self):
        self.assertEqual(self.window.windowTitle(), "壁纸库")
        icon = self.window.windowIcon()
        self.assertFalse(icon.isNull())
        sizes = {(size.width(), size.height()) for size in icon.availableSizes()}
        self.assertIn((32, 32), sizes)
        self.assertIn((256, 256), sizes)

    def test_categories_are_the_real_ones(self):
        labels = self.window.category_labels()
        self.assertIn("风景大片", labels)
        self.assertIn("动漫卡通", labels)
        self.assertIn("萌宠动物", labels)
        self.assertNotIn("最新", labels)
        self.assertNotIn("治愈", labels)
        self.assertNotIn("极简", labels)
        self.assertNotIn("精选推荐", labels)
        self.assertEqual(self.window.heading.text(), "风景大片")
        self.assertIn("都属于「风景大片」", self.window.subheading.text())

    def test_wallhaven_chips_are_its_own_categories(self):
        self.window.select_source("wallhaven")
        self.app.processEvents()
        self.assertEqual(self.window.category_labels(), ["全部", "综合", "动漫", "人物"])
        self.assertIn("自己的分类", self.window.subheading.text())
        self.window.select_source("birdpaper")
        self.app.processEvents()
        self.assertIn("风景大片", self.window.category_labels())

    def test_card_category_comes_from_the_item(self):
        url = "https://example.com/gui-cache-hit.jpg"
        path = core.thumb_cache_path(url)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        Image.new("RGB", (520, 292), (196, 112, 64)).save(path, "JPEG", quality=85)
        item = core.Wallpaper(
            id="gui-1",
            title="山谷里的小屋",
            thumb_url=url,
            full_url=url,
            source="360壁纸",
            source_key="birdpaper",
            resolution="1920x1080",
            category="风景大片",
            category_id="9",
            tags="山谷,小屋",
        )
        self.window.show_items([item])
        self.app.processEvents()
        self.assertEqual(self.window.model.item(0).category, "风景大片")
        self.assertEqual(self.window.model.data(self.window.model.index(0, 0), wallpaper_app_qt.CATEGORY_ROLE), "风景大片")
        self.assertTrue(self.window.model.data(self.window.model.index(0, 0), wallpaper_app_qt.THUMB_ROLE))
        pix = self.window.grab()
        self.assertGreater(pix.width(), 400)
        self.assertGreater(pix.height(), 300)
        pix.save("/tmp/wallpaper_library.png")

    def test_show_normal_reopens_a_hidden_window(self):
        self.window.hide()
        self.app.processEvents()
        self.assertFalse(self.window.isVisible())
        self.window.show_normal()
        self.app.processEvents()
        self.assertTrue(self.window.isVisible())
        self.assertFalse(self.window.windowState() & wallpaper_app_qt.Qt.WindowMinimized)

    def test_show_normal_still_shows_when_qt_already_thinks_it_is_visible(self):
        self.window.show()
        self.app.processEvents()
        self.assertTrue(self.window.isVisible())
        self.window.show_normal()
        self.app.processEvents()
        self.assertTrue(self.window.isVisible())
        self.assertFalse(self.window.isMinimized())

    def test_show_normal_keeps_an_open_preview(self):
        self.window.show_normal()
        self.window.preview.show()
        self.app.processEvents()
        self.assertTrue(self.window.preview.isVisible())
        self.window.show_normal()
        self.app.processEvents()
        self.assertTrue(self.window.isVisible())
        self.assertTrue(self.window.preview.isVisible())
        self.window.preview.hide()
        self.app.processEvents()

    def test_single_instance_second_claim_fails(self):
        first = wallpaper_app_qt.InstanceGuard()
        self.assertTrue(first.claim())
        second = wallpaper_app_qt.InstanceGuard()
        self.assertFalse(second.claim())

    def test_offscreen_window_can_load_a_real_page(self):
        os.environ.pop("WALLPAPER_NO_NETWORK", None)
        self.window.select_source("birdpaper")
        self.window.category_id = "9"
        self.window.query = ""
        self.window.reload()
        deadline = time.time() + 25
        while time.time() < deadline and self.window.model.rowCount() == 0 and self.window.stack.currentWidget() is not self.window.error_page:
            self.app.processEvents()
            time.sleep(0.05)
        self.app.processEvents()
        if self.window.model.rowCount() == 0:
            self.fail(self.window.footer.text())
        for row in range(self.window.model.rowCount()):
            item = self.window.model.item(row)
            self.assertEqual(item.category_id, "9")
            self.assertEqual(item.category, "风景大片")
        os.environ["WALLPAPER_NO_NETWORK"] = "1"


if __name__ == "__main__":
    unittest.main()

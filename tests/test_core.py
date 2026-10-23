# -*- coding: utf-8 -*-
"""分类、搜索和缓存规则。联网用例走真实接口。"""

import hashlib
import io
import os
import tempfile
import unittest
from unittest import mock

import requests
from PIL import Image

import i18n
import wallpaper_core as core


def setUpModule():
    i18n.activate("zh_CN")


class CategoryRules(unittest.TestCase):
    def test_fallback_does_not_call_nine_latest(self):
        names = {item.id: item.name for item in core.FALLBACK_CATEGORIES}
        self.assertEqual(names["9"], "风景大片")
        self.assertNotIn("最新", names.values())
        self.assertEqual(core.category_label("9", "最新", core.category_table(core.FALLBACK_CATEGORIES)), "风景大片")
        self.assertEqual(core.category_label("26", "", core.category_table(core.FALLBACK_CATEGORIES)), "动漫卡通")

    def test_legacy_categories_drop_hidden_and_keep_api_order(self):
        payload = {"data": {
            "a": {"id": "9", "name": "风景大片", "order_num": "98", "mobile_hidden": None},
            "b": {"id": "27", "name": "今日推荐", "order_num": "0", "mobile_hidden": "1"},
            "c": {"id": "1", "name": "限时壁纸", "order_num": "1", "mobile_hidden": "0"},
            "d": {"id": "35", "name": "文字控", "order_num": "9", "mobile_hidden": "0"},
            "e": {"id": "21", "name": "360宝贝活动", "order_num": "0", "mobile_hidden": "1"},
        }}
        categories = core.parse_legacy_360_categories(payload)
        self.assertEqual([item.id for item in categories], ["9", "35"])
        self.assertEqual(categories[0].name, "风景大片")
        self.assertTrue(all(item.name != "最新" for item in categories))

    def test_label_follows_the_image_not_the_selected_tab(self):
        table = core.category_table(core.FALLBACK_CATEGORIES)
        # 用户正在看「动漫卡通」，但这张图的 class_id 是风景。
        self.assertEqual(core.category_label("9", "风景大片", table), "风景大片")
        self.assertNotEqual(core.category_label("9", "风景大片", table), "动漫卡通")

    def test_wallhaven_names_are_its_own_categories(self):
        self.assertEqual(core.WALLHAVEN_CATEGORY_LABEL["general"], "综合")
        self.assertEqual(core.WALLHAVEN_CATEGORY_LABEL["anime"], "动漫")
        self.assertEqual(core.WALLHAVEN_CATEGORY_LABEL["people"], "人物")
        self.assertNotIn("风景", core.WALLHAVEN_CATEGORY_LABEL.values())
        self.assertEqual(core.WALLHAVEN_CATEGORY_PARAM["010"], "动漫")

    def test_view_copy_does_not_invent_a_recommendation_bucket(self):
        title, subtitle = core.describe_view("birdpaper", "风景大片", "")
        self.assertEqual(title, "风景大片")
        self.assertIn("都属于「风景大片」", subtitle)
        self.assertNotIn("最新", title + subtitle)
        self.assertNotIn("精选推荐", title + subtitle)
        search_title, search_subtitle = core.describe_view("birdpaper", "风景大片", "猫")
        self.assertEqual(search_title, "搜索「猫」")
        self.assertIn("这张图自己的", search_subtitle)
        mixed_title, mixed_subtitle = core.describe_view("wallhaven", "全部", "")
        self.assertIn("自己的分类", mixed_subtitle)
        self.assertIn("全部", mixed_title)


class SearchRules(unittest.TestCase):
    def test_rank_prefers_a_real_cat_over_an_owl(self):
        owl = core.Wallpaper(
            id="1", title="猫头鹰", thumb_url="a", full_url="a", source="360壁纸",
            source_key="birdpaper", category="游戏壁纸", category_id="5", tags="蜥蜴,猫头鹰,蜗牛",
        )
        cat = core.Wallpaper(
            id="2", title="两只猫", thumb_url="b", full_url="b", source="360壁纸",
            source_key="birdpaper", category="萌宠动物", category_id="14", tags="喵星人,两只猫",
        )
        ranked = core.rank_search_results([owl, cat], "猫")
        self.assertIs(ranked[0], cat)

    def test_wallhaven_chinese_query_becomes_tags(self):
        query, note = core.prepare_wallhaven_query("猫")
        self.assertEqual(query, "cat")
        self.assertIn("cat", note)
        query, note = core.prepare_wallhaven_query("原神")
        self.assertEqual(query, "genshin impact")
        query, note = core.prepare_wallhaven_query("landscape night")
        self.assertEqual(query, "landscape night")
        self.assertEqual(note, "")
        query, note = core.prepare_wallhaven_query("这是一个完全不认识的句子")
        self.assertEqual(query, "")
        self.assertIn("360壁纸", note)
        query, note = core.prepare_wallhaven_query("猫咪 山")
        self.assertEqual(query, "cat mountain")

    def test_local_filter_matches_title_and_category(self):
        item = core.Wallpaper(
            id="1", title="荒野伙伴", thumb_url="a", full_url="a", source="必应每日",
            source_key="bing", category="每日", tags="狼",
        )
        self.assertEqual(core.local_filter([item], "狼"), [item])
        self.assertEqual(core.local_filter([item], "海洋"), [])


class CacheAndLibrary(unittest.TestCase):
    def test_legacy_thumb_url_matches_the_old_app(self):
        url = "http://p2.qhimg.com/bdr/__85/t019ca75cd449be50c1.jpg"
        full, thumb = core.legacy_360_urls(url)
        self.assertEqual(full, "http://p2.qhimg.com/t019ca75cd449be50c1.jpg")
        self.assertEqual(thumb, "http://p2.qhimg.com/bdm/480_270_85/t019ca75cd449be50c1.jpg")
        self.assertEqual(
            core.thumb_filename(thumb),
            hashlib.md5(thumb.encode("utf-8")).hexdigest() + ".jpg",
        )

    def test_existing_cache_file_is_reused_and_not_deleted(self):
        folder = tempfile.mkdtemp()
        legacy = tempfile.mkdtemp()
        url = "http://p2.qhimg.com/bdm/480_270_85/t019ca75cd449be50c1.jpg"
        path = core.thumb_cache_path(url, folder)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as handle:
            handle.write(b"cached-thumb")
        self.assertEqual(core.ensure_thumb(url, folder=folder, extra_dirs=[]), path)
        self.assertEqual(os.path.getsize(path), len(b"cached-thumb"))

        other = "https://example.com/only-in-old-cache.jpg"
        legacy_path = os.path.join(legacy, core.thumb_filename(other))
        with open(legacy_path, "wb") as handle:
            handle.write(b"old")
        self.assertEqual(core.find_thumb(other, cache_dir=folder, extra_dirs=[legacy]), legacy_path)
        self.assertTrue(os.path.isfile(legacy_path))

    def test_bird_card_uses_an_800_image_and_keeps_the_original(self):
        full = "http://cdn-hsyq-static.shanhutech.cn/bizhi/staticwp/202609/abc.jpg"
        original, thumb = core.bird_image_urls(full)
        self.assertEqual(original, full)
        self.assertIn("x-oss-process=image/resize,m_fill,w_800,h_450/quality,q_80", thumb)
        self.assertTrue(thumb.startswith(full + "?"))
        unknown, same = core.bird_image_urls("https://example.com/a.jpg")
        self.assertEqual(unknown, same)
        qh_full, qh_thumb = core.bird_image_urls("http://p2.qhimg.com/t019ca75cd449be50c1.jpg")
        self.assertEqual(qh_full, "http://p2.qhimg.com/t019ca75cd449be50c1.jpg")
        self.assertEqual(qh_thumb, "http://p2.qhimg.com/bdm/480_270_85/t019ca75cd449be50c1.jpg")

    def test_old_full_url_cache_is_reused_for_the_new_thumb(self):
        folder = tempfile.mkdtemp()
        full = "http://cdn-hsyq-static.shanhutech.cn/bizhi/staticwp/x.jpg"
        _, thumb = core.bird_image_urls(full)
        old = core.thumb_cache_path(full, folder)
        os.makedirs(folder, exist_ok=True)
        with open(old, "wb") as handle:
            handle.write(b"old-thumb")
        item = core.Wallpaper(
            id="1", title="夜景", thumb_url=thumb, full_url=full,
            source="360壁纸", source_key="birdpaper",
        )
        found = core.ensure_thumb(
            thumb, folder=folder, extra_dirs=[], aliases=core.thumb_cache_aliases(item),
            fallback_urls=core.thumb_fallback_urls(item),
        )
        self.assertEqual(found, old)
        self.assertFalse(os.path.exists(core.thumb_cache_path(thumb, folder)))
        saved = core.with_fresh_thumb(core.Wallpaper(
            id="1", title="夜景", thumb_url=full, full_url=full,
            source="360壁纸", source_key="birdpaper",
        ))
        self.assertEqual(saved.full_url, full)
        self.assertEqual(saved.thumb_url, thumb)

    def test_small_thumb_failure_falls_back_to_the_original(self):
        folder = tempfile.mkdtemp()
        full = "https://cdn-hsyq-static.shanhutech.cn/bizhi/a.jpg"
        thumb = core.bird_image_urls(full)[1]
        image = Image.new("RGB", (1600, 900), (20, 40, 60))
        buf = io.BytesIO()
        image.save(buf, "JPEG", quality=85)
        payload = buf.getvalue()
        calls = []

        class Response:
            def __init__(self, content, status):
                self.content = content
                self.status_code = status

            def raise_for_status(self):
                if self.status_code >= 400:
                    raise requests.HTTPError(str(self.status_code))

        def fake_get(url, headers=None, timeout=None, stream=False):
            calls.append(url)
            if url == thumb:
                return Response(b"nope", 404)
            if url == full:
                return Response(payload, 200)
            raise AssertionError(url)

        with mock.patch.object(core._SESSION, "get", side_effect=fake_get):
            path = core.ensure_thumb(thumb, folder=folder, extra_dirs=[], fallback_urls=[full])
        self.assertEqual(calls, [thumb, full])
        self.assertEqual(path, core.thumb_cache_path(thumb, folder))
        with Image.open(path) as saved:
            self.assertLessEqual(saved.size[0], 800)
            self.assertLessEqual(saved.size[1], 450)
            self.assertGreaterEqual(saved.size[0], 700)

    def test_bing_and_nasa_card_urls_are_not_the_original(self):
        bing = core._bing_item({"urlbase": "/th?id=OHR.Test", "title": "狼", "hsh": "1"})
        self.assertTrue(bing.thumb_url.endswith("_800x480.jpg"))
        self.assertTrue(bing.full_url.endswith("_UHD.jpg"))
        nasa = core._nasa_item({
            "media_type": "image",
            "title": "星云",
            "date": "2020-01-01",
            "url": "https://apod.nasa.gov/apod/image/a_1024.jpg",
            "hdurl": "https://apod.nasa.gov/apod/image/a.jpg",
        })
        self.assertEqual(nasa.thumb_url, "https://apod.nasa.gov/apod/image/a_1024.jpg")
        self.assertEqual(nasa.full_url, "https://apod.nasa.gov/apod/image/a.jpg")
        same = core._nasa_item({
            "media_type": "image",
            "title": "星云",
            "date": "2020-01-02",
            "url": "https://apod.nasa.gov/apod/image/only.jpg",
            "hdurl": "https://apod.nasa.gov/apod/image/only.jpg",
        })
        self.assertIn("w=800", same.thumb_url)
        self.assertIn("h=450", same.thumb_url)
        self.assertNotEqual(same.thumb_url, same.full_url)
        wall = core._wallhaven_item({
            "id": "abc",
            "path": "https://w.wallhaven.cc/full/ab/wallhaven-abc.jpg",
            "thumbs": {
                "large": "https://th.wallhaven.cc/lg/ab/abc.jpg",
                "original": "https://th.wallhaven.cc/orig/ab/abc.jpg",
                "small": "https://th.wallhaven.cc/small/ab/abc.jpg",
            },
            "category": "anime",
            "resolution": "1920x1080",
            "purity": "sfw",
        })
        self.assertEqual(wall.thumb_url, "https://th.wallhaven.cc/lg/ab/abc.jpg")
        self.assertEqual(wall.full_url, "https://w.wallhaven.cc/full/ab/wallhaven-abc.jpg")

    def test_library_filename_strips_forbidden_characters(self):
        item = core.Wallpaper(
            id="99", title='海/边*日落', thumb_url="a", full_url="a.jpg",
            source="360壁纸", source_key="birdpaper",
        )
        name = core.library_filename(item, "/tmp/a.jpg")
        self.assertNotRegex(name, r'[\\/:*?"<>|]')
        self.assertTrue(name.endswith(".jpg"))
        self.assertIn("99", name)

    def test_favorites_toggle_and_history_cap(self):
        item = core.Wallpaper(
            id="1", title="一", thumb_url="a", full_url="http://a", source="360壁纸",
            source_key="birdpaper", category="风景大片",
        )
        other = core.Wallpaper(
            id="2", title="二", thumb_url="b", full_url="http://b", source="360壁纸",
            source_key="birdpaper", category="动漫卡通",
        )
        items, added = core.toggle_favorite([], item)
        self.assertTrue(added)
        self.assertTrue(core.is_favorite(items, item))
        items, added = core.toggle_favorite(items, item)
        self.assertFalse(added)
        self.assertEqual(items, [])
        history = []
        for index in range(3):
            current = core.Wallpaper(
                id=str(index), title=str(index), thumb_url="u", full_url="http://u"+str(index),
                source="360壁纸", source_key="birdpaper",
            )
            history = core.remember_history(history, current, cap=2)
        self.assertEqual([item.id for item in history], ["2", "1"])
        self.assertEqual(other.id, "2")

    def test_settings_keep_old_interest_list(self):
        folder = tempfile.mkdtemp()
        path = os.path.join(folder, "preferences.json")
        core.save_settings({"interests": ["风景", "动漫"], "source": "bing"}, path)
        data = core.load_settings(path)
        data["source"] = "birdpaper"
        data["category_id"] = "9"
        core.save_settings(data, path)
        again = core.load_settings(path)
        self.assertEqual(again["interests"], ["风景", "动漫"])
        self.assertEqual(again["category_id"], "9")

    def test_dedupe_stops_a_repeated_page(self):
        item = core.Wallpaper(
            id="1", title="一", thumb_url="a", full_url="a", source="360壁纸", source_key="birdpaper",
        )
        fresh = core.dedupe_items([item], [item])
        self.assertEqual(fresh, [])


class WindowsHelpers(unittest.TestCase):
    def test_autostart_command_uses_pythonw_launcher(self):
        command = core.autostart_command()
        self.assertIn("wallpaper_app_qt.py", command)
        self.assertIn("--background", command)

    def test_shortcut_plan_points_at_the_qt_script(self):
        plan = core.shortcut_plan("desktop")
        self.assertIn("wallpaper_app_qt.py", plan["arguments"])
        self.assertTrue(plan["name"].endswith(".lnk"))
        self.assertEqual(plan["app_id"], "WallpaperLibrary.App")
        self.assertEqual(plan["name"], "壁纸库.lnk")
        self.assertTrue(plan["icon"].endswith(os.path.join("assets", "app.ico")))
        self.assertEqual(plan["folder"], "Desktop")
        start = core.shortcut_plan("startmenu")
        self.assertEqual(start["folder"], "Programs")
        self.assertEqual(start["app_id"], plan["app_id"])
        script = core.shortcut_command_script()
        self.assertIn("IconLocation", script)
        self.assertIn("WP_ICON", script)
        self.assertIn("9F4C2855-9F79-4B39-A8D0-E1D42DE1D5F3", script)
        self.assertIn("SetAppId", script)
        if os.name != "nt":
            self.assertFalse(core.set_explicit_app_user_model_id())
            with self.assertRaises(core.SourceError):
                core.create_shortcut("desktop")
            with self.assertRaises(core.SourceError):
                core.write_autostart(True)

    def test_app_icon_contains_the_windows_sizes(self):
        import struct

        path = core.app_icon_path()
        png = core.app_icon_png_path()
        self.assertTrue(os.path.isfile(path))
        self.assertTrue(os.path.isfile(png))
        with open(path, "rb") as handle:
            data = handle.read()
        _reserved, kind, count = struct.unpack_from("<HHH", data, 0)
        self.assertEqual(kind, 1)
        found = set()
        offset = 6
        for _ in range(count):
            width, height = struct.unpack_from("<BB", data, offset)
            found.add(256 if width == 0 else width)
            self.assertEqual(height, width)
            offset += 16
        self.assertEqual(found, {16, 24, 32, 48, 64, 128, 256})
        with Image.open(png) as image:
            self.assertEqual(image.size, (256, 256))

    def test_tray_close_rule(self):
        self.assertTrue(core.should_minimize_to_tray(True, True, False))
        self.assertFalse(core.should_minimize_to_tray(True, False, False))
        self.assertFalse(core.should_minimize_to_tray(True, True, True))
        self.assertFalse(core.should_minimize_to_tray(False, True, False))

    def test_set_wallpaper_is_windows_only(self):
        if os.name != "nt":
            self.assertFalse(core.set_wallpaper("/tmp/does-not-need-to-exist.jpg"))


class ReleaseRules(unittest.TestCase):
    def tearDown(self):
        i18n.activate("zh_CN")

    def test_english_ui_translates_labels_but_chinese_search_stays_chinese(self):
        i18n.activate("en")
        self.assertEqual(i18n.category_name("风景大片"), "Landscapes")
        self.assertEqual(i18n.tag_name("猫"), "Cats")
        self.assertEqual(i18n.tag_name("蓝天白云"), "Blue sky")
        self.assertEqual(i18n.tag_name("没有收录的词"), "没有收录的词")
        self.assertEqual(set(i18n.STRINGS["zh_CN"]), set(i18n.STRINGS["en"]))
        title, subtitle = core.describe_view("birdpaper", "风景大片", "")
        self.assertEqual(title, "Landscapes")
        self.assertIn("Landscapes", subtitle)
        self.assertEqual(i18n.shortcut_link_name(), "Wallpapers.lnk")
        query, note = core.prepare_wallhaven_query("猫")
        self.assertEqual(query, "cat")
        self.assertNotIn("360壁纸", note)
        self.assertEqual(
            core.category_label("9", "", core.category_table(core.FALLBACK_CATEGORIES)),
            "风景大片",
        )

    def test_source_data_stays_next_to_the_script_unless_frozen(self):
        self.assertFalse(core.is_frozen())
        folder = tempfile.mkdtemp()
        os.environ["WALLPAPER_HOME"] = folder
        try:
            self.assertEqual(core.app_root(), folder)
            self.assertTrue(core.cache_dir().startswith(folder))
        finally:
            os.environ.pop("WALLPAPER_HOME", None)
        frozen_dir = tempfile.mkdtemp()
        exe = os.path.join(frozen_dir, "WallpaperLibrary.exe")
        with mock.patch.object(core, "is_frozen", return_value=True), mock.patch.object(
            core.sys, "executable", exe
        ):
            self.assertEqual(core.app_root(), frozen_dir)
            target, args = core.launch_target(False)
            self.assertEqual(target, exe)
            self.assertEqual(args, "")
            self.assertEqual(core.launch_workdir(), frozen_dir)
            _target, background = core.launch_target(True)
            self.assertEqual(background, "--background")
        self.assertEqual(core.launch_workdir(), core.APP_DIR)

    def test_missing_wallpaper_file_does_not_crash(self):
        self.assertFalse(core.set_wallpaper(os.path.join(tempfile.gettempdir(), "no-such-wallpaper.jpg")))
        self.assertTrue(core.last_wallpaper_note())

    def test_shortcut_skips_same_target_and_rejects_temp_paths(self):
        self.assertTrue(core.ephemeral_path(os.path.join(tempfile.gettempdir(), "_MEI99887", "app.exe")))
        self.assertTrue(core.ephemeral_path(r"C:\Users\me\AppData\Local\Temp\_MEI12345\WallpaperLibrary.exe"))
        self.assertFalse(core.ephemeral_path(r"C:\WallpaperLibrary\WallpaperLibrary.exe"))
        self.assertFalse(core.ephemeral_path(r"D:\apps\WallpaperLibrary\_internal\assets\app.ico"))
        exe = r"C:\WallpaperLibrary\WallpaperLibrary.exe"
        plan = {
            "target": exe,
            "arguments": "",
            "icon": r"C:\WallpaperLibrary\_internal\assets\app.ico",
            "workdir": r"C:\WallpaperLibrary",
            "name": "壁纸库.lnk",
        }
        self.assertTrue(core.shortcut_plan_is_stable(plan))
        self.assertTrue(core.shortcut_same_target({"target": exe, "arguments": ""}, plan))
        self.assertFalse(core.shortcut_same_target(
            {"target": r"C:\Python\pythonw.exe", "arguments": r'"D:\src\wallpaper_app_qt.py"'},
            plan,
        ))
        temp_plan = dict(plan, target=os.path.join(tempfile.gettempdir(), "_MEI1", "app.exe"))
        self.assertFalse(core.shortcut_plan_is_stable(temp_plan))
        self.assertFalse(core.shortcut_needs_rewrite({"target": exe, "arguments": ""}, plan))
        self.assertTrue(core.shortcut_needs_rewrite(
            {"target": exe, "arguments": "", "icon": r"C:\Users\me\AppData\Local\Temp\_MEI9\app.ico"},
            plan,
        ))
        folder = tempfile.mkdtemp()
        link = os.path.join(folder, "壁纸库.lnk")
        with open(link, "wb") as handle:
            handle.write(b"lnk")
        with mock.patch.object(core.sys, "platform", "win32"), mock.patch.object(
            core, "shortcut_plan", return_value=plan
        ), mock.patch.object(core, "start_menu_dir", return_value=folder), mock.patch.object(
            core, "read_shortcut", return_value={"target": exe, "arguments": ""}
        ), mock.patch.object(core, "create_shortcut") as create:
            created = core.ensure_start_menu_shortcut()
        self.assertEqual(created, link)
        create.assert_not_called()


class LiveSources(unittest.TestCase):
    def test_live_categories_match_the_service(self):
        categories = core.fetch_categories()
        table = {item.id: item.name for item in categories}
        self.assertEqual(table.get("9"), "风景大片")
        self.assertEqual(table.get("26"), "动漫卡通")
        self.assertEqual(table.get("14"), "萌宠动物")
        self.assertNotIn("最新", table.values())
        self.assertNotIn("今日推荐", table.values())
        self.assertEqual(categories[0].id, "36")
        self.assertEqual(categories[-1].name, "文字控")
        # 不是按拼音重排。拼音里「动漫卡通」会排在「4K专区」前面。
        self.assertLess(
            [item.id for item in categories].index("26"),
            [item.id for item in categories].index("35"),
        )

    def test_live_category_pages_only_contain_that_category(self):
        table = core.category_table(core.fetch_categories())
        scenery = core.load_page(core.FetchSpec("birdpaper", category_id="9", page=1), table)
        anime = core.load_page(core.FetchSpec("birdpaper", category_id="26", page=1), table)
        self.assertFalse(scenery.error)
        self.assertFalse(anime.error)
        self.assertGreaterEqual(len(scenery.items), 1)
        self.assertGreaterEqual(len(anime.items), 1)
        for item in scenery.items:
            self.assertEqual(item.category_id, "9")
            self.assertEqual(item.category, "风景大片")
        for item in anime.items:
            self.assertEqual(item.category_id, "26")
            self.assertEqual(item.category, "动漫卡通")
        self.assertEqual({item.category for item in scenery.items}, {"风景大片"})
        self.assertNotIn("较早的 360", scenery.note)
        self.assertTrue(scenery.items[0].full_url.startswith("http"))
        for item in scenery.items:
            self.assertNotEqual(item.thumb_url, item.full_url)
            self.assertIn("x-oss-process=image/resize,m_fill,w_800,h_450", item.thumb_url)
            self.assertTrue(item.thumb_url.startswith(item.full_url))

    def test_live_search_keeps_each_images_own_category(self):
        table = core.category_table(core.fetch_categories())
        result = core.load_page(core.FetchSpec("birdpaper", query="原神", page=1), table)
        self.assertFalse(result.error)
        self.assertGreaterEqual(len(result.items), 1)
        for item in result.items:
            self.assertIn("原神", item.tags + item.title)
            self.assertNotEqual(item.category, "原神")
            self.assertEqual(item.category, table[item.category_id].name)
        cats = core.load_page(core.FetchSpec("birdpaper", query="猫", page=1), table)
        self.assertGreaterEqual(len(cats.items), 1)
        for item in cats.items:
            self.assertNotEqual(item.category, "猫")
            self.assertEqual(item.category, table[item.category_id].name)
        self.assertIn("萌宠动物", {item.category for item in cats.items})

    def test_live_wallhaven_category_bits(self):
        anime = core.load_page(core.FetchSpec(
            "wallhaven", wh_categories="010", wh_sorting="date_added", page=1,
        ))
        general = core.load_page(core.FetchSpec(
            "wallhaven", wh_categories="100", wh_sorting="date_added", page=1,
        ))
        self.assertFalse(anime.error)
        self.assertFalse(general.error)
        self.assertGreaterEqual(len(anime.items), 1)
        self.assertGreaterEqual(len(general.items), 1)
        self.assertTrue(all(item.category == "动漫" for item in anime.items))
        self.assertTrue(all(item.category == "综合" for item in general.items))
        self.assertTrue(all(item.thumb_url.startswith("https://th.wallhaven.cc/lg/") for item in anime.items))
        self.assertTrue(all("w.wallhaven.cc" in item.full_url for item in anime.items))
        self.assertTrue(all(item.thumb_url != item.full_url for item in anime.items))

    def test_live_bing_daily_is_not_a_fake_topic(self):
        result = core.load_page(core.FetchSpec("bing", page=1))
        self.assertFalse(result.error)
        self.assertGreaterEqual(len(result.items), 1)
        for item in result.items:
            self.assertEqual(item.category, "每日")
            self.assertTrue(item.thumb_url.endswith("_800x480.jpg"))
            self.assertTrue(item.full_url.endswith("_UHD.jpg"))
            self.assertTrue(item.title)


if __name__ == "__main__":
    unittest.main()

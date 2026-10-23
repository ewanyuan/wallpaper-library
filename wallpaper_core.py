# -*- coding: utf-8 -*-
"""壁纸数据、分类和本机能力。

界面不在这个文件里。分类规则以接口实际返回为准：

- 360 旧接口里 id 9 是「风景大片」，没有名为「最新」的分类。
  旧程序把 9 写死成「最新」，再把所有图都标成当前兴趣，所以分类和图片对不上。
- 旧的 360 搜索接口现在返回 unserialize error，不能用来找图。
- 现在的 360 / 小鸟壁纸库（birdpaper）用同一套分类 id，并且每张图自带 class_id
  和分类名。搜索也走这个库。
- Wallhaven 的分类只有综合 / 动漫 / 人物，由 categories 位标记决定，
  不能用中文关键词假装成分类。
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass, fields, replace
from pathlib import Path
from urllib.parse import quote, urlparse

import requests
from PIL import Image
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

import i18n

APP_DIR = os.path.dirname(os.path.abspath(__file__))
SAVE_DIR = os.path.join(os.path.expanduser("~"), "Pictures", "Wallpapers")


def is_frozen():
    return bool(getattr(sys, "frozen", False))


def bundle_dir():
    """图标等只读资源。打包后在 _MEIPASS，源码运行时在程序目录。"""
    if is_frozen():
        meipass = getattr(sys, "_MEIPASS", None)
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        for folder in (meipass, exe_dir, os.path.join(exe_dir, "_internal")):
            if folder and os.path.isdir(os.path.join(folder, "assets")):
                return folder
        return meipass or exe_dir
    return APP_DIR


def _dir_writable(folder):
    try:
        os.makedirs(folder, exist_ok=True)
        probe = os.path.join(folder, ".wallpaper_write_probe")
        with open(probe, "w", encoding="utf-8") as handle:
            handle.write("")
        os.remove(probe)
        return True
    except OSError:
        return False


def app_root():
    """配置、缓存、收藏的目录。

    测试可设置 WALLPAPER_HOME。源码运行时用程序目录，这样原来的 cache 还能用。
    打包后的 exe 优先放在 exe 旁边（便携）；那个目录不能写时改到 LocalAppData。
    """
    override = os.environ.get("WALLPAPER_HOME")
    if override:
        return override
    if is_frozen():
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        if _dir_writable(exe_dir):
            return exe_dir
        local = os.environ.get("LOCALAPPDATA") or os.path.join(os.path.expanduser("~"), ".local", "share")
        return os.path.join(local, "WallpaperLibrary")
    return APP_DIR


def cache_dir():
    return os.path.join(app_root(), "cache")


def full_cache_dir():
    return os.path.join(cache_dir(), "full")


def preferences_path():
    return os.path.join(app_root(), "preferences.json")


def favorites_path():
    return os.path.join(app_root(), "favorites.json")


def history_path():
    return os.path.join(app_root(), "history.json")


def log_path():
    return os.path.join(app_root(), "wallpaper_app.log")

PAGE_SIZE = 24
# 卡片大约三百到四百像素宽，800 覆盖两倍屏。再大就没有必要。
THUMB_MAX_W = 800
THUMB_MAX_H = 450
DEFAULT_CATEGORY_ID = "9"
UA = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    )
}

BIRD_CATEGORIES = "http://wp.birdpaper.com.cn/intf/getCategory"
BIRD_LIST = "http://wp.birdpaper.com.cn/intf/GetListByCategory"
BIRD_SEARCH = "http://wp.birdpaper.com.cn/intf/search"
LEGACY_360 = "http://wallpaper.apc.360.cn/index.php"
WALLHAVEN_SEARCH = "https://wallhaven.cc/api/v1/search"
BING_ARCHIVE = "https://www.bing.com/HPImageArchive.aspx"
NASA_APOD = "https://api.nasa.gov/planetary/apod"

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE = "WallpaperLibrary"
APP_USER_MODEL_ID = "WallpaperLibrary.App"

WALLHAVEN_CATEGORY_PARAM = {
    "111": "全部",
    "100": "综合",
    "010": "动漫",
    "001": "人物",
}
WALLHAVEN_CATEGORY_LABEL = {
    "general": "综合",
    "anime": "动漫",
    "people": "人物",
}
WALLHAVEN_SORTS = (
    ("date_added", "最新上传"),
    ("toplist", "本月热门"),
    ("favorites", "最多收藏"),
    ("relevance", "最相关"),
    ("random", "随机"),
)
WALLHAVEN_SIZES = (
    ("1920x1080", "1080p 及以上"),
    ("2560x1440", "2K 及以上"),
    ("3840x2160", "4K"),
)

# 整词或短语优先，长词在匹配时排在前面。值是 Wallhaven 的英文标签。
WALLHAVEN_TERMS = {
    "赛博朋克": "cyberpunk",
    "蒸汽朋克": "steampunk",
    "二次元": "anime",
    "英雄联盟": "league of legends",
    "原神": "genshin impact",
    "星空": "stars",
    "夜景": "night city",
    "城市": "city",
    "风景": "landscape",
    "山水": "landscape",
    "海洋": "ocean",
    "海滩": "beach",
    "森林": "forest",
    "建筑": "architecture",
    "动漫": "anime",
    "动画": "anime",
    "游戏": "game",
    "猫咪": "cat",
    "可爱": "cute",
    "动物": "animal",
    "宠物": "animal",
    "樱花": "sakura",
    "汽车": "car",
    "科技": "technology",
    "极简": "minimalism",
    "简约": "minimal",
    "抽象": "abstract",
    "像素": "pixel art",
    "机器人": "robot",
    "太空": "space",
    "宇宙": "space",
    "月亮": "moon",
    "日落": "sunset",
    "冬天": "winter",
    "自然": "nature",
    "女孩": "girl",
    "人物": "people",
    "飞机": "plane",
    "火车": "train",
    "公路": "road",
    "城堡": "castle",
    "火影": "naruto",
    "海贼王": "one piece",
    "鬼灭": "kimetsu",
    "龙珠": "dragon ball",
    "暗黑": "dark",
    "复古": "retro",
    "山": "mountain",
    "海": "ocean",
    "云": "clouds",
    "夜": "night",
    "花": "flower",
    "雪": "snow",
    "雨": "rain",
    "猫": "cat",
    "狗": "dog",
    "车": "car",
    "天空": "sky",
}


class SourceError(Exception):
    """数据源失败。消息可以直接给用户看。"""


@dataclass(frozen=True)
class Category:
    id: str
    name: str
    show_name: str
    hot_tags: tuple = ()


@dataclass(frozen=True)
class SourceInfo:
    key: str
    label: str
    blurb: str
    searchable: bool
    placeholder: str


@dataclass
class Wallpaper:
    id: str
    title: str
    thumb_url: str
    full_url: str
    source: str
    source_key: str
    resolution: str = ""
    category: str = ""
    category_id: str = ""
    tags: str = ""
    page_url: str = ""

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict):
            raise TypeError("wallpaper record must be an object")
        known = {item.name for item in fields(cls)}
        values = {key: data[key] for key in data if key in known}
        for name in ("id", "title", "thumb_url", "full_url", "source", "source_key"):
            values.setdefault(name, "")
        return cls(**values)


@dataclass
class FetchSpec:
    source: str
    category_id: str = ""
    query: str = ""
    page: int = 1
    wh_categories: str = "111"
    wh_sorting: str = "date_added"
    wh_atleast: str = "1920x1080"


@dataclass
class PageResult:
    items: list
    has_more: bool
    note: str = ""
    error: str = ""


SOURCES = (
    SourceInfo("birdpaper", "360壁纸", "按壁纸库真实分类浏览，也可以直接搜中文", True,
               "搜索壁纸，例如：猫、星空、原神"),
    SourceInfo("wallhaven", "Wallhaven", "高清图。分类只有综合、动漫、人物", True,
               "搜索标签，中文会换成英文标签，例如：猫、赛博朋克"),
    SourceInfo("bing", "必应每日", "必应当天和最近的壁纸，没有主题分类", False,
               "必应只有每日壁纸，不能搜索"),
    SourceInfo("nasa", "天文", "NASA 每天一张天文图", False,
               "天文图片不支持搜索"),
    SourceInfo("favorites", "收藏", "你标过星的壁纸", True, "在收藏里搜索"),
    SourceInfo("history", "最近设置", "最近设为桌面的壁纸", True, "在最近设置里搜索"),
)

# 接口暂时打不开时仍用这套已核对过的目录，避免再把 9 显示成「最新」。
FALLBACK_CATEGORIES = (
    Category("36", "4K专区", "4K"),
    Category("6", "美女模特", "美女"),
    Category("30", "爱情美图", "爱情"),
    Category("9", "风景大片", "风景"),
    Category("15", "小清新", "小清新"),
    Category("26", "动漫卡通", "动漫"),
    Category("11", "明星风尚", "明星"),
    Category("14", "萌宠动物", "萌宠"),
    Category("5", "游戏壁纸", "游戏"),
    Category("12", "汽车天下", "汽车"),
    Category("10", "炫酷时尚", "炫酷时尚"),
    Category("29", "月历壁纸", "月历壁纸"),
    Category("7", "影视剧照", "影视剧照"),
    Category("13", "节日美图", "节日美图"),
    Category("22", "军事天地", "军事天地"),
    Category("16", "劲爆体育", "劲爆体育"),
    Category("18", "BABY秀", "BABY秀"),
    Category("35", "文字控", "文字控"),
)

_SESSION = requests.Session()
_RETRY = Retry(total=2, backoff_factor=0.4, status_forcelist=(500, 502, 503, 504))
_SESSION.mount("http://", HTTPAdapter(max_retries=_RETRY, pool_maxsize=16))
_SESSION.mount("https://", HTTPAdapter(max_retries=_RETRY, pool_maxsize=16))


def network_allowed():
    return os.environ.get("WALLPAPER_NO_NETWORK") != "1"


def log(message):
    try:
        path = log_path()
        line = time.strftime("%Y-%m-%d %H:%M:%S") + " " + str(message) + "\n"
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(line)
        if os.path.getsize(path) > 1_000_000:
            with open(path, "r", encoding="utf-8", errors="ignore") as handle:
                tail = handle.readlines()[-200:]
            with open(path, "w", encoding="utf-8") as handle:
                handle.writelines(tail)
    except OSError:
        pass


def source_info(key):
    for item in SOURCES:
        if item.key == key:
            return item
    return SOURCES[0]


def category_table(categories):
    return {str(item.id): item for item in categories}


def category_label(category_id, raw_name, table):
    """图片分类只看这张图自己的 id，不看用户当前点的标签。

    存下来的仍是接口里的中文名。界面显示时再翻译。
    """
    found = table.get(str(category_id or ""))
    if found:
        return found.name
    raw = (raw_name or "").strip()
    return raw or "未分类"


def describe_view(source, category_name, query, note=""):
    """返回 (标题, 说明)。说明必须和卡片上的分类规则一致。"""
    query = (query or "").strip()
    category_name = category_name or ""
    shown = i18n.category_name(category_name) if category_name else ""
    if source == "birdpaper":
        if query:
            title = i18n.tr("view.search", query=query)
            subtitle = i18n.tr("view.bird_search")
        else:
            title = shown or i18n.tr("source.birdpaper")
            subtitle = i18n.tr("view.bird_category", name=title)
        return title, _join_note(note, subtitle)
    if source == "wallhaven":
        if query:
            title = i18n.tr("view.search", query=query)
        else:
            title = shown or i18n.tr("source.wallhaven")
        if category_name == "全部" and not query:
            subtitle = i18n.tr("view.wh_mixed")
        else:
            subtitle = i18n.tr("view.wh_own")
        return title, _join_note(note, subtitle)
    if source == "bing":
        subtitle = i18n.tr("view.bing")
        if query:
            subtitle = i18n.tr("view.bing_query") + subtitle
        return i18n.tr("source.bing"), _join_note(note, subtitle)
    if source == "nasa":
        return i18n.tr("source.nasa"), _join_note(note, i18n.tr("view.nasa"))
    if source == "favorites":
        title = i18n.tr("view.fav_search", query=query) if query else i18n.tr("source.favorites")
        return title, i18n.tr("view.fav")
    if source == "history":
        title = i18n.tr("view.history_search", query=query) if query else i18n.tr("source.history")
        return title, i18n.tr("view.history")
    return i18n.tr("app.name"), note


def _join_note(note, subtitle):
    note = (note or "").strip()
    if not note:
        return subtitle
    return note + " " + subtitle


def _get_json(url, params=None, timeout=20):
    try:
        response = _SESSION.get(url, params=params, headers=UA, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        raise SourceError(i18n.tr("err.network")) from exc
    except ValueError as exc:
        raise SourceError(i18n.tr("err.bad_json")) from exc


def _errno_ok(payload):
    if not isinstance(payload, dict):
        return False
    code = payload.get("errno", payload.get("code", 0))
    return str(code) in ("0", "None", "")


def fetch_categories():
    """返回 360 / 小鸟壁纸的官方分类，顺序保持接口原样。"""
    if not network_allowed():
        return list(FALLBACK_CATEGORIES)
    payload = _get_json(BIRD_CATEGORIES, timeout=(5, 15))
    if not _errno_ok(payload):
        raise SourceError(payload.get("msg") or payload.get("errmsg") or i18n.tr("err.categories"))
    categories = _parse_bird_categories(payload)
    if not categories:
        raise SourceError(i18n.tr("err.categories_empty"))
    return categories


def _parse_bird_categories(payload):
    rows = payload.get("data") or []
    categories = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        cid = str(row.get("old_id") or "").strip()
        name = str(row.get("category") or "").strip()
        if not cid or not name:
            continue
        show = str(row.get("show_name") or name).strip() or name
        tags = []
        for tag in row.get("hot_tag") or []:
            if isinstance(tag, dict):
                label = str(tag.get("show_tag") or tag.get("tag") or "").strip()
            else:
                label = str(tag).strip()
            if label and label not in tags:
                tags.append(label)
        categories.append(Category(cid, name, show, tuple(tags)))
    return categories


def parse_legacy_360_categories(payload):
    """旧 360 分类。去掉接口标记隐藏的项，并按 order_num 而不是拼音排序。

    不会把任何 id 改名成「最新」。id 9 保持「风景大片」。
    """
    data = payload.get("data") or {}
    rows = list(data.values()) if isinstance(data, dict) else list(data)
    ranked = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if str(row.get("mobile_hidden") or "") == "1":
            continue
        try:
            order = int(row.get("order_num") or 0)
        except (TypeError, ValueError):
            order = 0
        if order < 9:
            continue
        cid = str(row.get("id") or "").strip()
        name = str(row.get("name") or "").strip()
        if not cid or not name:
            continue
        ranked.append((order, Category(cid, name, name)))
    ranked.sort(key=lambda item: (-item[0], item[1].id))
    return [item[1] for item in ranked]


def load_page(spec, table=None, favorites=None, history=None):
    table = table or category_table(FALLBACK_CATEGORIES)
    source = spec.source
    if source == "favorites":
        return _local_page(favorites or [], spec.query)
    if source == "history":
        return _local_page(history or [], spec.query)
    if source == "birdpaper":
        return _load_birdpaper(spec, table)
    if source == "wallhaven":
        return _load_wallhaven(spec)
    if source == "bing":
        return _load_bing(spec)
    if source == "nasa":
        return _load_nasa(spec)
    return PageResult([], False, error=i18n.tr("err.unknown_source"))


def _local_page(items, query):
    matched = [with_fresh_thumb(item) for item in local_filter(items, query)]
    return PageResult(matched, False)


def local_filter(items, query):
    text = (query or "").strip().lower()
    if not text:
        return list(items)
    found = []
    for item in items:
        blob = " ".join((item.title, item.category, item.tags, item.resolution)).lower()
        if text in blob:
            found.append(item)
    return found


def _load_birdpaper(spec, table):
    query = (spec.query or "").strip()
    try:
        if query:
            payload = _get_json(BIRD_SEARCH, {
                "content": query,
                "pageno": spec.page,
                "count": PAGE_SIZE,
            })
            items, has_more = _parse_bird_page(payload, table, requested_cid="")
            items = rank_search_results(items, query)
            return PageResult(items, has_more)
        payload = _get_json(BIRD_LIST, {
            "cids": spec.category_id,
            "pageno": spec.page,
            "count": PAGE_SIZE,
        })
        items, has_more = _parse_bird_page(payload, table, requested_cid=spec.category_id)
        return PageResult(items, has_more)
    except SourceError:
        if query:
            raise
        return _load_legacy_360(spec, table)


def _parse_bird_page(payload, table, requested_cid):
    if not isinstance(payload, dict) or not _errno_ok(payload):
        message = ""
        if isinstance(payload, dict):
            message = payload.get("msg") or payload.get("errmsg") or ""
        raise SourceError(message or i18n.tr("err.list"))
    data = payload.get("data") or {}
    rows = data.get("list") or []
    items = []
    for row in rows:
        item = _bird_item(row, table, requested_cid)
        if item is not None:
            items.append(item)
    try:
        page = int(data.get("pageno") or 1)
        total_page = int(data.get("total_page") or 0)
    except (TypeError, ValueError):
        page, total_page = 1, 0
    if total_page:
        has_more = page < total_page and len(items) > 0
    else:
        has_more = len(items) >= PAGE_SIZE
    return items, has_more


def _bird_item(row, table, requested_cid):
    if not isinstance(row, dict):
        return None
    url = str(row.get("url") or "").strip()
    if not url:
        return None
    full, thumb = bird_image_urls(url)
    cid = str(row.get("class_id") or requested_cid or "").strip()
    raw_name = str(row.get("category") or "").strip()
    tags = str(row.get("tag") or "").strip()
    title = tags or ("壁纸 %s" % row.get("id", ""))
    return Wallpaper(
        id=str(row.get("id") or full),
        title=title,
        thumb_url=thumb,
        full_url=full,
        source="360壁纸",
        source_key="birdpaper",
        category=category_label(cid, raw_name, table),
        category_id=cid,
        tags=tags,
        page_url=full,
    )


def _load_legacy_360(spec, table):
    start = (max(spec.page, 1) - 1) * PAGE_SIZE
    payload = _get_json(LEGACY_360, {
        "c": "WallPaper",
        "a": "getAppsByCategory",
        "cid": spec.category_id,
        "start": start,
        "count": PAGE_SIZE,
    })
    if not _errno_ok(payload):
        raise SourceError(i18n.tr("err.list_360"))
    rows = payload.get("data") or []
    items = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        url = str(row.get("url") or "").strip()
        if not url:
            continue
        full, thumb = legacy_360_urls(url)
        cid = str(row.get("class_id") or spec.category_id or "").strip()
        tags = str(row.get("utag") or "").strip()
        items.append(Wallpaper(
            id=str(row.get("id") or url),
            title=tags or ("壁纸 %s" % row.get("id", "")),
            thumb_url=thumb,
            full_url=full,
            source="360壁纸",
            source_key="birdpaper",
            resolution=str(row.get("resolution") or ""),
            category=category_label(cid, "", table),
            category_id=cid,
            tags=tags,
            page_url=full,
        ))
    has_more = len(items) >= PAGE_SIZE
    return PageResult(items, has_more, note=i18n.tr("note.legacy"))


def legacy_360_urls(url):
    """和旧版完全相同的缩略图地址，这样 cache 里的 md5 文件还能对上。"""
    full = url.replace("/bdr/__85/", "/")
    thumb = url.replace("/bdr/__85/", "/bdm/480_270_85/")
    return full, thumb


def bird_image_urls(url):
    """360 卡片用小图，原图留给预览和设为壁纸。

    现在的小鸟图床是阿里云 OSS，列表里只有原图 url，没有 url_thumb / url_mid。
    小图靠 x-oss-process 现裁成 800x450。旧的 qhimg 地址仍走 /bdm/480_270_85/，
    这样以前按这个地址存的缓存还能对上。认不出的地址就用原图。
    """
    text = (url or "").strip()
    if not text:
        return "", ""
    qhimg = _qhimg_image_urls(text)
    if qhimg is not None:
        return qhimg
    if _oss_resizable(text):
        return text, _oss_card_url(text)
    return text, text


def _qhimg_image_urls(url):
    parsed = urlparse(url)
    if not parsed.netloc.lower().endswith("qhimg.com"):
        return None
    if "/bdr/__85/" in parsed.path:
        return legacy_360_urls(url)
    if "/bdm/" in parsed.path:
        return url, url
    name = parsed.path.rsplit("/", 1)[-1]
    if not name:
        return url, url
    thumb = parsed._replace(path="/bdm/480_270_85/" + name).geturl()
    return url, thumb


def _oss_resizable(url):
    host = urlparse(url).netloc.lower()
    if not (host.endswith("shanhutech.cn") or host.endswith("aliyuncs.com")):
        return False
    path = urlparse(url).path.lower()
    return path.endswith((".jpg", ".jpeg", ".png", ".webp"))


def _oss_card_url(url):
    if "x-oss-process=" in url:
        return url
    process = "x-oss-process=image/resize,m_fill,w_%d,h_%d/quality,q_80" % (THUMB_MAX_W, THUMB_MAX_H)
    return url + ("&" if "?" in url else "?") + process


def with_fresh_thumb(item):
    """收藏和历史里可能还存着「缩略图=原图」。打开时改成小图，原图地址不动。"""
    full, thumb = _card_urls(item)
    if full == item.full_url and thumb == item.thumb_url:
        return item
    return replace(item, full_url=full or item.full_url, thumb_url=thumb or item.thumb_url)


def _card_urls(item):
    full = (item.full_url or item.thumb_url or "").strip()
    thumb = (item.thumb_url or full).strip()
    if item.source_key == "birdpaper":
        return bird_image_urls(full or thumb)
    if item.source_key == "bing":
        return _bing_image_urls(full, thumb)
    if item.source_key == "nasa":
        return _nasa_image_urls(full, thumb)
    return full, thumb


def _bing_image_urls(full, thumb):
    base = full or thumb
    for suffix in ("_UHD.jpg", "_1920x1080.jpg", "_1366x768.jpg", "_800x480.jpg", "_640x360.jpg", "_400x240.jpg"):
        if base.endswith(suffix):
            base = base[: -len(suffix)]
            return base + "_UHD.jpg", base + "_800x480.jpg"
    return full, thumb or full


def _nasa_image_urls(full, thumb):
    """hdurl 才是原图。url 和 hdurl 不同时，url 通常已经是展示尺寸，直接当卡片。

    两份地址相同时，卡片改走 800 像素的缩放，避免把原图下进网格。
    """
    if thumb and "images.weserv.nl" not in thumb and thumb != full:
        return full, thumb
    return full, fitted_remote_thumb(full)


def fitted_remote_thumb(url):
    return (
        "https://images.weserv.nl/?url="
        + quote(url, safe="")
        + "&w=%d&h=%d&fit=cover&q=80" % (THUMB_MAX_W, THUMB_MAX_H)
    )


def thumb_cache_aliases(item):
    """同一张卡片以前可能按别的地址存过缩略图。命中就不要重新下载。"""
    aliases = []

    def add(url):
        if url and url not in aliases and url != item.thumb_url:
            aliases.append(url)

    add(item.full_url)
    thumb = item.thumb_url or ""
    if "x-oss-process=" in thumb:
        add(thumb.split("?", 1)[0])
    if thumb.endswith("_800x480.jpg"):
        add(thumb[: -len("_800x480.jpg")] + "_400x240.jpg")
    if item.source_key == "nasa" and item.full_url:
        add(
            "https://images.weserv.nl/?url="
            + quote(item.full_url, safe="")
            + "&w=480&h=270&fit=cover"
        )
    return aliases


def thumb_fallback_urls(item):
    """小图失败时再试更小的已知地址，最后才用原图。"""
    urls = []

    def add(url):
        if url and url not in urls and url != item.thumb_url:
            urls.append(url)

    thumb = item.thumb_url or ""
    if thumb.endswith("_800x480.jpg"):
        add(thumb[: -len("_800x480.jpg")] + "_400x240.jpg")
    add(item.full_url)
    return urls


def rank_search_results(items, query):
    """把更像整词命中的结果排到前面，不丢弃结果。"""
    text = (query or "").strip().lower()
    if not text:
        return list(items)

    def key(pair):
        index, item = pair
        return (_match_score(item, text), index)

    return [item for _, item in sorted(enumerate(items), key=key)]


def _match_score(item, query):
    tags = [part.strip().lower() for part in re.split(r"[,，、\s]+", item.tags or "") if part.strip()]
    scores = [_tag_score(tag, query) for tag in tags]
    scores.append(_tag_score((item.title or "").lower(), query))
    if query and query in (item.category or "").lower():
        scores.append(2)
    return min(scores) if scores else 4


def _tag_score(tag, query):
    """整词最好。以关键词结尾（两只猫、猫咪）也算。

    「猫头鹰」虽然以「猫」开头，但多出来的字更多，只算弱匹配，
    避免猫的搜索被猫头鹰排到前面。
    """
    if not tag or not query or query not in tag:
        return 4
    if tag == query:
        return 0
    extra = len(tag) - len(query)
    if tag.endswith(query):
        return 1
    if tag.startswith(query) and extra <= 1:
        return 1
    return 3


def prepare_wallhaven_query(query):
    """返回 (交给 Wallhaven 的英文查询, 给用户看的说明)。

    说明为空表示查询本来就是 Wallhaven 能直接用的。
    查询为空字符串且说明非空时，不应该发请求。
    """
    text = (query or "").strip()
    if not text:
        return "", ""
    if not _has_cjk(text):
        return text, ""
    phrases = sorted(WALLHAVEN_TERMS, key=len, reverse=True)
    found = []
    unknown = []
    index = 0
    while index < len(text):
        if text[index].isspace() or text[index] in "，、,":
            index += 1
            continue
        matched = ""
        for phrase in phrases:
            if text.startswith(phrase, index):
                matched = phrase
                break
        if matched:
            found.append(WALLHAVEN_TERMS[matched])
            index += len(matched)
            continue
        if ord(text[index]) < 128:
            end = index + 1
            while end < len(text) and not text[end].isspace() and text[end] not in "，、,":
                end += 1
            found.append(text[index:end])
            index = end
            continue
        end = index + 1
        while end < len(text) and _is_cjk(text[end]) and not any(
            text.startswith(phrase, end) for phrase in phrases
        ):
            end += 1
        unknown.append(text[index:end])
        index = end
    if not found:
        return "", i18n.tr("wh.no_chinese")
    note = i18n.tr("wh.mapped", query=" ".join(found))
    if unknown:
        note += i18n.tr("wh.unknown", words="、".join(unknown))
    return " ".join(found), note


def _has_cjk(text):
    return any(_is_cjk(char) for char in text)


def _is_cjk(char):
    code = ord(char)
    return (
        0x4E00 <= code <= 0x9FFF
        or 0x3400 <= code <= 0x4DBF
        or 0xF900 <= code <= 0xFAFF
    )


def _load_wallhaven(spec):
    query, note = prepare_wallhaven_query(spec.query)
    if (spec.query or "").strip() and not query:
        return PageResult([], False, note=note)
    sorting = spec.wh_sorting or "date_added"
    if sorting not in dict(WALLHAVEN_SORTS):
        sorting = "date_added"
    if sorting == "relevance" and not query:
        sorting = "date_added"
    categories = spec.wh_categories if spec.wh_categories in WALLHAVEN_CATEGORY_PARAM else "111"
    params = {
        "q": query,
        "page": spec.page,
        "categories": categories,
        "purity": "100",
        "atleast": spec.wh_atleast or "1920x1080",
        "sorting": sorting,
        "order": "desc",
    }
    if sorting == "toplist":
        params["topRange"] = "1M"
    try:
        payload = _get_json(WALLHAVEN_SEARCH, params, timeout=(5, 25))
    except SourceError:
        raise
    if isinstance(payload, dict) and payload.get("error"):
        raise SourceError(i18n.tr("err.wallhaven", error=payload.get("error")))
    rows = payload.get("data") or []
    items = []
    for row in rows:
        item = _wallhaven_item(row)
        if item is not None:
            items.append(item)
    meta = payload.get("meta") or {}
    try:
        current = int(meta.get("current_page") or spec.page)
        last = int(meta.get("last_page") or current)
    except (TypeError, ValueError):
        current, last = spec.page, spec.page
    has_more = current < last and len(items) > 0
    return PageResult(items, has_more, note=note)


def _wallhaven_item(row):
    if not isinstance(row, dict):
        return None
    if row.get("purity") and row.get("purity") != "sfw":
        return None
    thumbs = row.get("thumbs") or {}
    # large 大约 430 像素，是 Wallhaven 提供的最大预览。
    # original / small 更小，path 才是原图，不能拿来铺网格。
    thumb = str(thumbs.get("large") or thumbs.get("small") or thumbs.get("original") or "").strip()
    full = str(row.get("path") or "").strip()
    if not thumb or not full:
        return None
    raw_category = str(row.get("category") or "")
    wid = str(row.get("id") or "")
    resolution = str(row.get("resolution") or "")
    label = WALLHAVEN_CATEGORY_LABEL.get(raw_category, raw_category or "未分类")
    return Wallpaper(
        id=wid or full,
        title=resolution or wid or "Wallhaven",
        thumb_url=thumb,
        full_url=full,
        source="Wallhaven",
        source_key="wallhaven",
        resolution=resolution,
        category=label,
        category_id=raw_category,
        page_url=("https://wallhaven.cc/w/%s" % wid) if wid else full,
    )


def _load_bing(spec):
    if spec.page > 2:
        return PageResult([], False)
    idx = (max(spec.page, 1) - 1) * 8
    payload = _get_json(BING_ARCHIVE, {
        "format": "js",
        "idx": idx,
        "n": 8,
        "mkt": "zh-CN",
    }, timeout=(5, 20))
    items = []
    for row in payload.get("images") or []:
        item = _bing_item(row)
        if item is not None:
            items.append(item)
    note = ""
    query = (spec.query or "").strip()
    if query:
        items = local_filter(items, query)
        note = i18n.tr("note.bing_search")
    has_more = spec.page < 2 and not query
    return PageResult(items, has_more, note=note)


def _bing_item(row):
    if not isinstance(row, dict) or not row.get("urlbase"):
        return None
    base = "https://www.bing.com" + row["urlbase"]
    title = str(row.get("title") or "必应壁纸")
    copyright_link = str(row.get("copyrightlink") or "")
    return Wallpaper(
        id=str(row.get("hsh") or row.get("fullstartdate") or title),
        title=title,
        thumb_url=base + "_800x480.jpg",
        full_url=base + "_UHD.jpg",
        source="必应每日",
        source_key="bing",
        resolution="UHD",
        category="每日",
        category_id="bing",
        tags=str(row.get("copyright") or ""),
        page_url=copyright_link or (base + "_UHD.jpg"),
    )


def _load_nasa(spec):
    if spec.page > 1:
        return PageResult([], False)
    try:
        response = _SESSION.get(
            NASA_APOD,
            params={"api_key": "DEMO_KEY", "count": 16},
            headers=UA,
            timeout=(5, 12),
        )
        response.raise_for_status()
        rows = response.json()
    except requests.RequestException as exc:
        raise SourceError(i18n.tr("err.nasa")) from exc
    except ValueError as exc:
        raise SourceError(i18n.tr("err.nasa_json")) from exc
    if isinstance(rows, dict):
        rows = [rows]
    items = []
    for row in rows or []:
        item = _nasa_item(row)
        if item is not None:
            items.append(item)
    query = (spec.query or "").strip()
    note = ""
    if query:
        items = local_filter(items, query)
        note = i18n.tr("note.nasa_search")
    return PageResult(items, False, note=note)


def _nasa_item(row):
    if not isinstance(row, dict) or row.get("media_type") != "image" or not row.get("url"):
        return None
    standard = str(row.get("url") or "").strip()
    hd = str(row.get("hdurl") or "").strip()
    full = hd or standard
    given = str(row.get("thumbnail_url") or "").strip()
    if given:
        thumb = given
    elif standard and standard != full:
        thumb = standard
    else:
        thumb = fitted_remote_thumb(full)
    title = "%s %s" % (row.get("date", ""), row.get("title", "APOD"))
    return Wallpaper(
        id=str(row.get("date") or full),
        title=title.strip(),
        thumb_url=str(thumb),
        full_url=full,
        source="天文",
        source_key="nasa",
        category="天文",
        category_id="nasa",
        tags=str(row.get("title") or ""),
        page_url=standard or full,
    )


def dedupe_items(existing, incoming):
    seen = {(item.source_key, item.id) for item in existing}
    fresh = []
    for item in incoming:
        key = (item.source_key, item.id)
        if key in seen:
            continue
        seen.add(key)
        fresh.append(item)
    return fresh


def thumb_filename(url):
    return hashlib.md5(url.encode("utf-8")).hexdigest() + ".jpg"


def thumb_cache_path(url, folder=None):
    return os.path.join(folder or cache_dir(), thumb_filename(url))


def legacy_thumb_dirs():
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        return []
    return [os.path.join(local, "WallpaperApp", "thumbs")]


def find_thumb(url, cache_dir=None, extra_dirs=None, aliases=None):
    urls = [url]
    for alias in aliases or []:
        if alias and alias not in urls:
            urls.append(alias)
    folders = extra_dirs if extra_dirs is not None else legacy_thumb_dirs()
    for candidate in urls:
        paths = [thumb_cache_path(candidate, cache_dir)]
        for folder in folders:
            paths.append(os.path.join(folder, thumb_filename(candidate)))
        for path in paths:
            if os.path.isfile(path) and os.path.getsize(path) > 0:
                return path
    return ""


def ensure_thumb(url, folder=None, extra_dirs=None, aliases=None, fallback_urls=None):
    """返回缩略图文件路径。已有缓存（含旧地址、旧目录）时不重新下载。

    小图地址失败时才按 fallback_urls 再试，最后一项通常是原图。
    新文件仍按请求的缩略图地址命名，下次才能直接命中。
    """
    found = find_thumb(url, cache_dir=folder, extra_dirs=extra_dirs, aliases=aliases)
    if found:
        return found
    folder = folder or cache_dir()
    os.makedirs(folder, exist_ok=True)
    image = _download_thumb_image(url, fallback_urls or [])
    fitted = _fit_thumb(image)
    path = thumb_cache_path(url, folder)
    tmp = path + ".part"
    fitted.save(tmp, "JPEG", quality=85)
    os.replace(tmp, path)
    return path


def _download_thumb_image(url, fallback_urls):
    errors = []
    candidates = [url] + [item for item in fallback_urls if item and item != url]
    for index, candidate in enumerate(candidates):
        if len(candidates) == 1:
            timeout = (5, 40)
        elif index == len(candidates) - 1:
            timeout = (5, 90)
        else:
            timeout = (5, 20)
        try:
            response = _SESSION.get(candidate, headers=UA, timeout=timeout)
            response.raise_for_status()
            image = Image.open(io.BytesIO(response.content))
            image.load()
            return image.convert("RGB")
        except (requests.RequestException, OSError) as exc:
            errors.append(exc)
    raise SourceError(i18n.tr("err.thumb")) from (errors[-1] if errors else None)


def _fit_thumb(image):
    """比卡片所需更大时才缩小。小预览不再放大，避免把 Wallhaven 的小图拉糊。"""
    image = image.convert("RGB")
    if image.width <= THUMB_MAX_W and image.height <= THUMB_MAX_H:
        return image
    scale = max(THUMB_MAX_W / max(image.width, 1), THUMB_MAX_H / max(image.height, 1))
    if scale >= 1:
        return image
    resized = image.resize(
        (max(int(round(image.width * scale)), 1), max(int(round(image.height * scale)), 1)),
        Image.Resampling.LANCZOS,
    )
    left = max((resized.width - THUMB_MAX_W) // 2, 0)
    top = max((resized.height - THUMB_MAX_H) // 2, 0)
    return resized.crop((
        left,
        top,
        min(left + THUMB_MAX_W, resized.width),
        min(top + THUMB_MAX_H, resized.height),
    ))


def full_cache_path(url, folder=None):
    ext = _url_ext(url)
    name = hashlib.md5(url.encode("utf-8")).hexdigest() + ext
    return os.path.join(folder or full_cache_dir(), name)


def _url_ext(url):
    path = urlparse(url).path.lower()
    for ext in (".jpg", ".jpeg", ".png", ".webp", ".bmp"):
        if path.endswith(ext):
            return ".jpg" if ext == ".jpeg" else ext
    return ".jpg"


def download_original(url, folder=None):
    folder = folder or full_cache_dir()
    os.makedirs(folder, exist_ok=True)
    path = full_cache_path(url, folder)
    if os.path.isfile(path) and os.path.getsize(path) > 0:
        return path
    tmp = path + ".part"
    try:
        response = _SESSION.get(url, headers=UA, timeout=(5, 90), stream=True)
        response.raise_for_status()
        with open(tmp, "wb") as handle:
            for chunk in response.iter_content(1 << 16):
                if chunk:
                    handle.write(chunk)
        os.replace(tmp, path)
    except requests.RequestException as exc:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise SourceError(i18n.tr("err.full")) from exc
    except OSError as exc:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise SourceError(i18n.tr("err.full_save")) from exc
    return path


def library_filename(item, cached_path):
    ext = os.path.splitext(cached_path)[1].lower() or ".jpg"
    if ext == ".jpeg":
        ext = ".jpg"
    if ext == ".webp":
        ext = ".jpg"
    prefix = {
        "birdpaper": "360",
        "wallhaven": "wallhaven",
        "bing": "bing",
        "nasa": "apod",
    }.get(item.source_key, "wall")
    title = re.sub(r'[\\/:*?"<>|\s]+', "_", item.title or "壁纸").strip("._") or "壁纸"
    name = "%s_%s_%s%s" % (prefix, title, item.id or "img", ext)
    if len(name) > 140:
        name = name[:120] + ext
    return name


def materialize_wallpaper(item, save_dir=None, full_dir=None):
    """下载原图并复制到图片库。返回图片库里的路径。"""
    cached = download_original(item.full_url, full_dir)
    folder = save_dir or SAVE_DIR
    os.makedirs(folder, exist_ok=True)
    dest = os.path.join(folder, library_filename(item, cached))
    if os.path.isfile(dest) and os.path.getsize(dest) > 0:
        return dest
    if dest.lower().endswith(".jpg") and cached.lower().endswith(".webp"):
        image = Image.open(cached).convert("RGB")
        tmp = dest + ".part"
        image.save(tmp, "JPEG", quality=92)
        os.replace(tmp, dest)
    else:
        shutil.copyfile(cached, dest)
    return dest


_last_wallpaper_note = ""


def last_wallpaper_note():
    return _last_wallpaper_note


def set_wallpaper(path):
    """铺满桌面。Windows 用系统接口；macOS / Linux 能设就设，不能设就返回 False。"""
    global _last_wallpaper_note
    _last_wallpaper_note = ""
    path = os.path.abspath(path)
    if not os.path.isfile(path):
        _last_wallpaper_note = i18n.tr("toast.wallpaper_unsupported")
        return False
    try:
        if sys.platform == "win32":
            return _set_wallpaper_windows(path)
        if sys.platform == "darwin":
            return _set_wallpaper_macos(path)
        if sys.platform.startswith("linux"):
            return _set_wallpaper_linux(path)
    except Exception as exc:
        log(exc)
        _last_wallpaper_note = i18n.tr("toast.wallpaper_unsupported")
        return False
    _last_wallpaper_note = i18n.tr("toast.wallpaper_unsupported")
    return False


def _set_wallpaper_windows(path):
    import ctypes
    import winreg

    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, r"Control Panel\Desktop", 0, winreg.KEY_SET_VALUE
        ) as key:
            winreg.SetValueEx(key, "WallpaperStyle", 0, winreg.REG_SZ, "10")
            winreg.SetValueEx(key, "TileWallpaper", 0, winreg.REG_SZ, "0")
    except OSError:
        pass
    return bool(ctypes.windll.user32.SystemParametersInfoW(20, 0, path, 3))


def _set_wallpaper_macos(path):
    global _last_wallpaper_note
    script = 'tell application "System Events" to set picture of every desktop to POSIX file "%s"' % path.replace('"', "")
    ok, detail = _run_command(["osascript", "-e", script])
    if ok:
        return True
    _last_wallpaper_note = detail or i18n.tr("toast.wallpaper_unsupported")
    return False


def _set_wallpaper_linux(path):
    global _last_wallpaper_note
    uri = Path(path).as_uri()
    if shutil.which("gsettings"):
        ok, detail = _run_command(["gsettings", "set", "org.gnome.desktop.background", "picture-uri", uri])
        _run_command(["gsettings", "set", "org.gnome.desktop.background", "picture-uri-dark", uri])
        _run_command(["gsettings", "set", "org.gnome.desktop.background", "picture-options", "zoom"])
        if ok:
            return True
        gnome_detail = detail
    else:
        gnome_detail = ""
    if shutil.which("qdbus"):
        plasma = (
            "var allDesktops = desktops();"
            "for (i=0;i<allDesktops.length;i++) {"
            "d = allDesktops[i];"
            "d.wallpaperPlugin = 'org.kde.image';"
            "d.currentConfigGroup = Array('Wallpaper','org.kde.image','General');"
            "d.writeConfig('Image', '%s');"
            "}"
        ) % uri
        ok, detail = _run_command([
            "qdbus", "org.kde.plasmashell", "/PlasmaShell",
            "org.kde.PlasmaShell.evaluateScript", plasma,
        ])
        if ok:
            return True
    if shutil.which("xfconf-query"):
        ok, detail = _run_command([
            "xfconf-query", "-c", "xfce4-desktop", "-p",
            "/backdrop/screen0/monitor0/workspace0/last-image", "-s", path,
        ])
        if ok:
            return True
    _last_wallpaper_note = gnome_detail or i18n.tr("toast.wallpaper_unsupported")
    return False


def _run_command(cmd, timeout=8):
    try:
        completed = subprocess.run(
            cmd, check=False, capture_output=True, text=True, timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return False, str(exc)
    detail = (completed.stderr or completed.stdout or "").strip()
    return completed.returncode == 0, detail


def toggle_favorite(items, item):
    key = (item.source_key, item.id)
    kept = [current for current in items if (current.source_key, current.id) != key]
    added = len(kept) == len(items)
    if added:
        kept.insert(0, item)
    return kept, added


def remember_history(items, item, cap=40):
    key = (item.source_key, item.id)
    kept = [current for current in items if (current.source_key, current.id) != key]
    kept.insert(0, item)
    return kept[:cap]


def is_favorite(items, item):
    key = (item.source_key, item.id)
    return any((current.source_key, current.id) == key for current in items)


def load_wallpaper_list(path):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return []
    if not isinstance(data, list):
        return []
    items = []
    for row in data:
        try:
            item = Wallpaper.from_dict(row)
        except TypeError:
            continue
        if item.full_url:
            items.append(item)
    return items


def save_wallpaper_list(path, items):
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    tmp = path + ".part"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump([item.to_dict() for item in items], handle, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def load_settings(path=None):
    path = path or preferences_path()
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save_settings(data, path=None):
    path = path or preferences_path()
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    tmp = path + ".part"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def pythonw_executable():
    exe = os.path.abspath(sys.executable)
    if exe.lower().endswith("python.exe"):
        candidate = os.path.join(os.path.dirname(exe), "pythonw.exe")
        if os.path.exists(candidate):
            return candidate
    return exe


def app_script_path():
    return os.path.join(APP_DIR, "wallpaper_app_qt.py")


def app_icon_path():
    return os.path.join(bundle_dir(), "assets", "app.ico")


def app_icon_png_path():
    return os.path.join(bundle_dir(), "assets", "app.png")


def launch_target(background=False):
    """返回 (可执行文件, 参数)。打包后直接启动 exe。"""
    if is_frozen():
        args = "--background" if background else ""
        return os.path.abspath(sys.executable), args
    args = '"%s"' % app_script_path()
    if background:
        args += " --background"
    return pythonw_executable(), args


def launch_workdir():
    """快捷方式的工作目录。打包后是 exe 所在目录，源码运行时是程序目录。"""
    if is_frozen():
        return os.path.dirname(os.path.abspath(sys.executable))
    return APP_DIR


def ephemeral_path(path):
    """PyInstaller 单文件解压目录和系统临时目录都不能写进快捷方式。"""
    text = str(path or "").strip().strip('"')
    if not text:
        return False
    if any(part.upper().startswith("_MEI") for part in re.split(r"[\\/]", text)):
        return True
    try:
        absolute = os.path.abspath(text)
    except OSError:
        return True
    temp = os.path.normcase(os.path.normpath(os.path.abspath(tempfile.gettempdir())))
    norm = os.path.normcase(os.path.normpath(absolute))
    return norm == temp or norm.startswith(temp + os.sep)


def shortcut_icon_path():
    """快捷方式用的图标。只返回会留在磁盘上的路径，不指向 _MEI 临时目录。"""
    exe_dir = os.path.dirname(os.path.abspath(sys.executable)) if is_frozen() else APP_DIR
    candidates = [
        os.path.join(exe_dir, "assets", "app.ico"),
        os.path.join(exe_dir, "_internal", "assets", "app.ico"),
        app_icon_path(),
    ]
    for candidate in candidates:
        if candidate and os.path.isfile(candidate) and not ephemeral_path(candidate):
            return os.path.abspath(candidate)
    source = app_icon_path()
    if not source or not os.path.isfile(source):
        return ""
    dest_root = app_root()
    if ephemeral_path(dest_root):
        return ""
    dest = os.path.join(dest_root, "assets", "app.ico")
    try:
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        if not os.path.isfile(dest):
            shutil.copyfile(source, dest)
    except OSError as exc:
        log(exc)
        return ""
    if not os.path.isfile(dest) or ephemeral_path(dest):
        return ""
    return os.path.abspath(dest)


def _norm_target(path):
    text = str(path or "").strip().strip('"')
    if not text:
        return ""
    text = os.path.normpath(text)
    if os.path.isabs(text):
        text = os.path.abspath(text)
    return os.path.normcase(text)


def _norm_args(args):
    parts = str(args or "").replace('"', " ").split()
    normed = []
    for part in parts:
        if part.startswith("--"):
            normed.append(part)
        elif any(sep in part for sep in ("\\", "/")) or os.path.splitext(part)[1].lower() in (".py", ".exe"):
            normed.append(_norm_target(part))
        else:
            normed.append(part)
    return " ".join(normed)


def shortcut_same_target(existing, plan):
    """目标程序和参数一致时，不需要重写快捷方式。"""
    if not existing or not plan:
        return False
    return (
        _norm_target(existing.get("target")) == _norm_target(plan.get("target"))
        and _norm_args(existing.get("arguments")) == _norm_args(plan.get("arguments"))
    )


def shortcut_needs_rewrite(existing, plan):
    """目标变了，或者旧快捷方式还指着临时目录，才重写。"""
    if not shortcut_same_target(existing, plan):
        return True
    for key in ("icon", "workdir"):
        if ephemeral_path(existing.get(key)):
            return True
    return False


def shortcut_plan_is_stable(plan):
    if ephemeral_path(plan.get("target")):
        return False
    if plan.get("icon") and ephemeral_path(plan.get("icon")):
        return False
    if plan.get("workdir") and ephemeral_path(plan.get("workdir")):
        return False
    for token in str(plan.get("arguments") or "").replace('"', " ").split():
        if ephemeral_path(token):
            return False
    return True


def set_explicit_app_user_model_id(app_id=None):
    """让任务栏把这个程序当成「壁纸库」，用窗口图标而不是 pythonw 的图标。

    必须在创建任何窗口之前调用。不是 Windows 时什么都不做。
    """
    if sys.platform != "win32":
        return False
    import ctypes

    app_id = app_id or APP_USER_MODEL_ID
    try:
        function = ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID
        function.argtypes = [ctypes.c_wchar_p]
        function.restype = ctypes.c_long
        result = int(function(app_id))
    except (AttributeError, OSError) as exc:
        log("设置任务栏应用 ID 失败：%s" % exc)
        return False
    if result < 0:
        log("设置任务栏应用 ID 失败：%s" % result)
        return False
    return True


def autostart_supported():
    return sys.platform == "win32"


def autostart_command():
    exe, args = launch_target(background=True)
    if args:
        return '"%s" %s' % (exe, args)
    return '"%s"' % exe


def read_autostart():
    if not autostart_supported():
        return False
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            value, _ = winreg.QueryValueEx(key, RUN_VALUE)
        return bool(value)
    except OSError:
        return False


def write_autostart(enabled):
    if not autostart_supported():
        raise SourceError(i18n.tr("err.autostart"))
    import winreg

    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, RUN_VALUE, 0, winreg.REG_SZ, autostart_command())
        else:
            try:
                winreg.DeleteValue(key, RUN_VALUE)
            except OSError:
                pass


def shortcut_plan(kind):
    if kind not in ("desktop", "startmenu"):
        raise SourceError(i18n.tr("err.shortcut_kind"))
    target, arguments = launch_target(background=False)
    return {
        "kind": kind,
        "folder": "Desktop" if kind == "desktop" else "Programs",
        "target": target,
        "arguments": arguments,
        "name": i18n.shortcut_link_name(),
        "description": i18n.tr("app.name"),
        "icon": shortcut_icon_path(),
        "workdir": launch_workdir(),
        "app_id": APP_USER_MODEL_ID,
    }


def start_menu_dir():
    appdata = os.environ.get("APPDATA") or ""
    if not appdata:
        return ""
    return os.path.join(appdata, "Microsoft", "Windows", "Start Menu", "Programs")


def read_shortcut(path):
    """读出已有 .lnk 的目标和参数。读不到时返回 None。"""
    if sys.platform != "win32" or not path or not os.path.isfile(path):
        return None
    script = r"""
$shell = New-Object -ComObject WScript.Shell
$link = $shell.CreateShortcut($env:WP_LINK_PATH)
Write-Output ('TARGET=' + $link.TargetPath)
Write-Output ('ARGS=' + $link.Arguments)
Write-Output ('WORKDIR=' + $link.WorkingDirectory)
Write-Output ('ICON=' + $link.IconLocation)
"""
    try:
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
            check=True,
            capture_output=True,
            text=True,
            env={**os.environ, "WP_LINK_PATH": path},
            timeout=20,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        log(exc)
        return None
    found = {}
    for line in (completed.stdout or "").splitlines():
        if line.startswith("TARGET="):
            found["target"] = line[len("TARGET="):]
        elif line.startswith("ARGS="):
            found["arguments"] = line[len("ARGS="):]
        elif line.startswith("WORKDIR="):
            found["workdir"] = line[len("WORKDIR="):]
        elif line.startswith("ICON="):
            found["icon"] = line[len("ICON="):].split(",", 1)[0]
    if "target" not in found:
        return None
    return found


def ensure_start_menu_shortcut():
    """保证开始菜单里只有一个快捷方式，并且应用 ID 是 WallpaperLibrary.App。

    名字跟当前界面语言走。目标没变时不重写。临时目录里的路径不会写进去。
    """
    if sys.platform != "win32":
        return ""
    plan = shortcut_plan("startmenu")
    if not shortcut_plan_is_stable(plan):
        log("跳过开始菜单快捷方式：目标在临时目录里")
        return ""
    folder = start_menu_dir()
    current = plan["name"]
    current_path = os.path.join(folder, current) if folder else ""
    existing = read_shortcut(current_path)
    if existing and not shortcut_needs_rewrite(existing, plan):
        created = current_path
    else:
        created = create_shortcut("startmenu")
    if not folder:
        return created
    for name in ("壁纸库.lnk", "Wallpapers.lnk", "Wallpaper Library.lnk"):
        if name == current:
            continue
        old = os.path.join(folder, name)
        if os.path.isfile(old):
            try:
                os.remove(old)
            except OSError as exc:
                log(exc)
    return created


def shortcut_command_script():
    """PowerShell：快捷方式指向 pythonw，图标用 app.ico，并写上同一个应用 ID。"""
    return r"""
$dir = [Environment]::GetFolderPath($env:WP_FOLDER)
$path = Join-Path $dir $env:WP_LINK_NAME
$shell = New-Object -ComObject WScript.Shell
$link = $shell.CreateShortcut($path)
$link.TargetPath = $env:WP_TARGET
$link.Arguments = $env:WP_ARGS
$link.WorkingDirectory = $env:WP_WORKDIR
$link.Description = $env:WP_DESC
if ($env:WP_ICON) { $link.IconLocation = ($env:WP_ICON + ',0') }
$link.Save()

Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;

public static class WallpaperShortcut {
    [StructLayout(LayoutKind.Sequential, Pack = 4)]
    public struct PropertyKey {
        public Guid fmtid;
        public uint pid;
    }

    [StructLayout(LayoutKind.Explicit)]
    public struct PropVariant {
        [FieldOffset(0)] public ushort vt;
        [FieldOffset(8)] public IntPtr pointer;

        public static PropVariant FromString(string value) {
            PropVariant variant = new PropVariant();
            variant.vt = 31;
            variant.pointer = Marshal.StringToCoTaskMemUni(value);
            return variant;
        }
    }

    [ComImport]
    [Guid("886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99")]
    [InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    public interface IPropertyStore {
        void GetCount(out uint cProps);
        void GetAt(uint iProp, out PropertyKey pkey);
        void GetValue(ref PropertyKey key, out PropVariant pv);
        void SetValue(ref PropertyKey key, ref PropVariant pv);
        void Commit();
    }

    [DllImport("shell32.dll", CharSet = CharSet.Unicode)]
    static extern int SHGetPropertyStoreFromParsingName(
        string pszPath, IntPtr pbc, uint flags, ref Guid riid, out IPropertyStore store);

    [DllImport("ole32.dll")]
    static extern int PropVariantClear(ref PropVariant pvar);

    public static void SetAppId(string shortcutPath, string appId) {
        Guid iid = new Guid("886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99");
        IPropertyStore store;
        int hr = SHGetPropertyStoreFromParsingName(shortcutPath, IntPtr.Zero, 2, ref iid, out store);
        if (hr < 0) throw new System.ComponentModel.Win32Exception(hr);
        PropertyKey key = new PropertyKey();
        key.fmtid = new Guid("9F4C2855-9F79-4B39-A8D0-E1D42DE1D5F3");
        key.pid = 5;
        PropVariant value = PropVariant.FromString(appId);
        try {
            store.SetValue(ref key, ref value);
            store.Commit();
        } finally {
            PropVariantClear(ref value);
        }
    }
}
'@
if ($env:WP_APP_ID) { [WallpaperShortcut]::SetAppId($path, $env:WP_APP_ID) }
Write-Output $path
"""


def create_shortcut(kind):
    """在 Windows 桌面或开始菜单创建快捷方式。"""
    if sys.platform != "win32":
        raise SourceError(i18n.tr("err.shortcut_platform"))
    plan = shortcut_plan(kind)
    if not shortcut_plan_is_stable(plan):
        raise SourceError(i18n.tr("err.shortcut_temp"))
    script = shortcut_command_script()
    env = os.environ.copy()
    env["WP_FOLDER"] = plan["folder"]
    env["WP_LINK_NAME"] = plan["name"]
    env["WP_TARGET"] = plan["target"]
    env["WP_ARGS"] = plan["arguments"]
    env["WP_WORKDIR"] = plan.get("workdir") or launch_workdir()
    env["WP_DESC"] = plan["description"]
    env["WP_ICON"] = plan["icon"]
    env["WP_APP_ID"] = plan["app_id"]
    try:
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
            check=True,
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise SourceError(i18n.tr("err.shortcut", error=exc)) from exc
    path = (completed.stdout or "").strip().splitlines()
    return path[-1] if path else plan["name"]


def open_path(path):
    os.makedirs(path, exist_ok=True)
    if sys.platform == "win32":
        os.startfile(path)  # noqa: PTH123 - Windows 文件夹
        return
    if sys.platform == "darwin":
        subprocess.Popen(["open", path])
        return
    subprocess.Popen(["xdg-open", path])


def should_minimize_to_tray(preference_enabled, tray_available, quitting):
    return bool(preference_enabled and tray_available and not quitting)

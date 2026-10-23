# -*- coding: utf-8 -*-
"""界面文案。zh_CN 与 en 两张表，不使用 Qt Linguist。

分类和热门词在数据里仍是中文，这样 360 搜索不用改。
显示时再翻译；点热门词时，搜索框里放的是原来的中文词。
"""

from __future__ import annotations

import os

_language = None

STRINGS = {
    "zh_CN": {
        "app.name": "壁纸库",
        "app.hint": "找一张，设成桌面",
        "app.missing_qt": "缺少 PyQt5。\n请在程序目录打开命令行，执行：\npip install -r requirements.txt",
        "nav.settings": "设置和快捷方式",
        "search.button": "搜索",
        "search.hot": "试试",
        "wh.sort_label": "排序",
        "wh.size_label": "尺寸",
        "wh.sort.date_added": "最新上传",
        "wh.sort.toplist": "本月热门",
        "wh.sort.favorites": "最多收藏",
        "wh.sort.relevance": "最相关",
        "wh.sort.random": "随机",
        "wh.size.1920x1080": "1080p 及以上",
        "wh.size.2560x1440": "2K 及以上",
        "wh.size.3840x2160": "4K",
        "action.retry": "重试",
        "action.reload": "重新加载",
        "footer.hint": "点击图片预览。关闭窗口后可以从托盘图标打开。",
        "tray.open": "打开壁纸库",
        "tray.next": "换一张壁纸",
        "tray.folder": "打开下载目录",
        "tray.quit": "退出",
        "card.loading": "正在加载",
        "card.failed": "图片加载失败",
        "card.set": "设为壁纸",
        "card.fav": "收藏",
        "card.faved": "已收藏",
        "preview.title": "预览",
        "preview.loading": "正在加载大图…",
        "preview.prev": "上一张",
        "preview.next": "下一张",
        "preview.set": "设为壁纸",
        "preview.save": "只保存图片",
        "preview.fav": "收藏",
        "preview.unfav": "取消收藏",
        "preview.copy": "复制链接",
        "preview.count": "第 %(index)s / %(total)s 张",
        "preview.failed": "大图加载失败：%(error)s",
        "preview.bad": "这张图无法显示",
        "preview.uncat": "未分类",
        "menu.preview": "预览",
        "menu.set": "设为壁纸",
        "menu.save": "只保存图片",
        "menu.fav": "加入收藏",
        "menu.unfav": "取消收藏",
        "menu.copy": "复制图片链接",
        "menu.browser": "在浏览器中打开",
        "status.copied": "已复制图片链接",
        "status.shown": "已显示 %(count)s 张%(more)s",
        "status.more": "，向下滚动加载更多",
        "status.loading_more": "正在加载更多…",
        "status.searching": "正在搜索「%(query)s」…",
        "status.loading_cat": "正在加载「%(name)s」…",
        "status.loading": "正在加载…",
        "status.offline": "当前没有联网加载。",
        "status.empty_query": "没有找到「%(query)s」。可以换个词，或到「360壁纸」里用中文搜。",
        "status.empty": "这里暂时没有壁纸。",
        "status.none": "没有找到壁纸",
        "status.fail": "加载失败",
        "status.fav_on": "已加入收藏",
        "status.fav_off": "已取消收藏",
        "status.busy": "正在处理上一张，请稍候",
        "status.preparing": "正在准备下一张壁纸…",
        "status.folder_fail": "打不开下载目录：%(error)s",
        "status.categories_fallback": "分类接口暂时不可用，已改用内置分类。",
        "status.working": "正在%(action)s：%(title)s",
        "action.set": "设置壁纸",
        "action.save": "保存",
        "toast.wallpaper_set": "已设为桌面壁纸：%(name)s",
        "toast.saved_only": "图片已保存到：%(path)s。%(note)s",
        "toast.set_failed": "图片已下载，但设置桌面失败：%(path)s",
        "toast.saved": "已保存到：%(path)s",
        "toast.failed": "操作失败：%(error)s",
        "toast.wallpaper_unsupported": "当前桌面不能自动更换壁纸。",
        "settings.title": "设置",
        "settings.intro": "关掉窗口以后程序还在。右下角托盘图标可以打开它，也可以直接换一张壁纸。",
        "settings.close_tray": "关闭窗口时留在托盘，不退出",
        "settings.autostart": "登录 Windows 后自动启动",
        "settings.autostart_other": "登录 Windows 后自动启动（只能在 Windows 上设置）",
        "settings.shortcut_ok": "已创建快捷方式：\n%(path)s",
        "settings.desktop": "创建桌面快捷方式",
        "settings.start": "添加到开始菜单",
        "settings.folder": "打开下载目录",
        "settings.note": "快捷方式和开机启动会使用 pythonw，不会弹出黑色命令行窗口。快捷方式用壁纸库自己的图标。",
        "settings.note_frozen": "快捷方式和开机启动会打开这个程序自己的 exe，不会弹出黑色命令行窗口。",
        "settings.note_other": "开机启动和快捷方式只能在 Windows 上创建。",
        "settings.close": "关闭",
        "settings.language": "语言",
        "settings.lang.auto": "跟随系统",
        "settings.lang.zh_CN": "简体中文",
        "settings.lang.en": "English",
        "settings.restart": "语言会在重新打开后生效。",
        "tray.still": "壁纸库仍在运行",
        "tray.still_body": "窗口已隐藏到右下角托盘。双击图标可以打开，也可以直接换一张壁纸。",
        "view.search": "搜索「%(query)s」",
        "view.bird_search": "结果可能跨好几个分类。卡片上的分类是这张图自己的，不是搜索词。",
        "view.bird_category": "下面每张图都属于「%(name)s」。",
        "view.wh_mixed": "这里混合了综合、动漫和人物。每张图仍标着它自己的分类。",
        "view.wh_own": "卡片上的分类来自 Wallhaven：综合、动漫或人物。",
        "view.bing": "必应最近的每日壁纸，没有风景、动漫这种主题分类。",
        "view.bing_query": "必应不能按关键词搜全库。",
        "view.nasa": "这些都是 NASA 的天文图片。",
        "view.fav": "这里是你标过星的图，分类沿用收藏时的分类。",
        "view.fav_search": "搜索收藏「%(query)s」",
        "view.history": "这里是最近设为桌面的图。",
        "view.history_search": "搜索最近设置「%(query)s」",
        "source.birdpaper": "360壁纸",
        "source.wallhaven": "Wallhaven",
        "source.bing": "必应每日",
        "source.nasa": "天文",
        "source.favorites": "收藏",
        "source.history": "最近设置",
        "placeholder.birdpaper": "搜索壁纸，例如：猫、星空、原神",
        "placeholder.wallhaven": "搜索标签，中文会换成英文标签，例如：猫、赛博朋克",
        "placeholder.bing": "必应只有每日壁纸，不能搜索",
        "placeholder.nasa": "天文图片不支持搜索",
        "placeholder.favorites": "在收藏里搜索",
        "placeholder.history": "在最近设置里搜索",
        "err.network": "网络请求失败，请检查网络后重试。",
        "err.bad_json": "壁纸服务返回了无法识别的数据。",
        "err.categories": "分类列表获取失败",
        "err.categories_empty": "分类列表是空的",
        "err.list": "壁纸列表获取失败",
        "err.list_360": "360 壁纸列表获取失败",
        "err.wallhaven": "Wallhaven：%(error)s",
        "err.nasa": "NASA 天文图片暂时获取不到。",
        "err.nasa_json": "NASA 返回了无法识别的数据。",
        "err.thumb": "缩略图下载失败",
        "err.full": "大图下载失败",
        "err.full_save": "大图保存失败",
        "err.autostart": "开机自动启动只能在 Windows 上设置。",
        "err.shortcut_kind": "未知的快捷方式位置",
        "err.shortcut_platform": "快捷方式只能在 Windows 上创建。",
        "err.shortcut": "创建快捷方式失败：%(error)s",
        "err.shortcut_temp": "快捷方式不能指向临时目录。",
        "err.unknown_source": "未知的壁纸来源",
        "err.load": "加载失败：%(error)s",
        "err.unknown": "未知原因",
        "wh.no_chinese": "Wallhaven 不能直接搜中文。请换到「360壁纸」搜索，或改用英文标签。",
        "wh.mapped": "Wallhaven 只认英文标签，已按「%(query)s」搜索。",
        "wh.unknown": "没能对应的词：%(words)s。这些词请到「360壁纸」里搜。",
        "note.bing_search": "必应不能按关键词搜索全库，这里只是在最近的每日壁纸标题里查找。",
        "note.nasa_search": "天文图片不能按关键词搜索全库。",
        "note.legacy": "正在使用较早的 360 图库。",
        "preview.unknown": "未知原因",
    },
    "en": {
        "app.name": "Wallpapers",
        "app.hint": "Find one. Set it as your desktop.",
        "app.missing_qt": "PyQt5 is missing.\nIn this folder, run:\npip install -r requirements.txt",
        "nav.settings": "Settings",
        "search.button": "Search",
        "search.hot": "Try",
        "wh.sort_label": "Sort",
        "wh.size_label": "Size",
        "wh.sort.date_added": "Newest",
        "wh.sort.toplist": "Top this month",
        "wh.sort.favorites": "Most favorites",
        "wh.sort.relevance": "Relevance",
        "wh.sort.random": "Random",
        "wh.size.1920x1080": "1080p and up",
        "wh.size.2560x1440": "1440p and up",
        "wh.size.3840x2160": "4K",
        "action.retry": "Retry",
        "action.reload": "Reload",
        "footer.hint": "Click a picture to preview. Closing the window leaves the app in the tray.",
        "tray.open": "Open Wallpapers",
        "tray.next": "Next wallpaper",
        "tray.folder": "Open download folder",
        "tray.quit": "Quit",
        "card.loading": "Loading",
        "card.failed": "Image failed",
        "card.set": "Set",
        "card.fav": "Save",
        "card.faved": "Saved",
        "preview.title": "Preview",
        "preview.loading": "Loading full image…",
        "preview.prev": "Previous",
        "preview.next": "Next",
        "preview.set": "Set wallpaper",
        "preview.save": "Save image only",
        "preview.fav": "Save",
        "preview.unfav": "Unsave",
        "preview.copy": "Copy link",
        "preview.count": "%(index)s / %(total)s",
        "preview.failed": "Could not load the full image: %(error)s",
        "preview.bad": "This image cannot be shown",
        "preview.uncat": "Uncategorized",
        "menu.preview": "Preview",
        "menu.set": "Set wallpaper",
        "menu.save": "Save image only",
        "menu.fav": "Add to favorites",
        "menu.unfav": "Remove from favorites",
        "menu.copy": "Copy image link",
        "menu.browser": "Open in browser",
        "status.copied": "Link copied",
        "status.shown": "Showing %(count)s%(more)s",
        "status.more": ", scroll for more",
        "status.loading_more": "Loading more…",
        "status.searching": "Searching “%(query)s”…",
        "status.loading_cat": "Loading “%(name)s”…",
        "status.loading": "Loading…",
        "status.offline": "Network loading is turned off.",
        "status.empty_query": "No results for “%(query)s”. Try another word, or search in Chinese under 360 Wallpapers.",
        "status.empty": "Nothing here yet.",
        "status.none": "No wallpapers found",
        "status.fail": "Could not load",
        "status.fav_on": "Saved to favorites",
        "status.fav_off": "Removed from favorites",
        "status.busy": "Still working on the previous picture",
        "status.preparing": "Getting the next wallpaper…",
        "status.folder_fail": "Could not open the download folder: %(error)s",
        "status.categories_fallback": "The category list is unavailable. Using the built-in list.",
        "status.working": "%(action)s: %(title)s",
        "action.set": "Setting wallpaper",
        "action.save": "Saving",
        "toast.wallpaper_set": "Desktop wallpaper set: %(name)s",
        "toast.saved_only": "Saved to %(path)s. %(note)s",
        "toast.set_failed": "Downloaded, but the desktop was not changed: %(path)s",
        "toast.saved": "Saved to %(path)s",
        "toast.failed": "Failed: %(error)s",
        "toast.wallpaper_unsupported": "This desktop cannot be changed automatically.",
        "settings.title": "Settings",
        "settings.intro": "Closing the window leaves the app running. Use the tray icon to open it again or to set another wallpaper.",
        "settings.close_tray": "Keep running in the tray when the window closes",
        "settings.autostart": "Start when Windows starts",
        "settings.autostart_other": "Start when Windows starts (Windows only)",
        "settings.shortcut_ok": "Shortcut created:\n%(path)s",
        "settings.desktop": "Create desktop shortcut",
        "settings.start": "Add to Start Menu",
        "settings.folder": "Open download folder",
        "settings.note": "Shortcuts and startup use pythonw, so no console window appears. The shortcut uses this app's icon.",
        "settings.note_frozen": "Shortcuts and startup open this app's exe, with no console window.",
        "settings.note_other": "Startup and shortcuts can only be created on Windows.",
        "settings.close": "Close",
        "settings.language": "Language",
        "settings.lang.auto": "System language",
        "settings.lang.zh_CN": "简体中文",
        "settings.lang.en": "English",
        "settings.restart": "The language applies after you open the app again.",
        "tray.still": "Wallpapers is still running",
        "tray.still_body": "The window is in the tray. Double-click the icon to open it, or set another wallpaper.",
        "view.search": "Search “%(query)s”",
        "view.bird_search": "Results can span several categories. The label on each picture is that picture's own category, not the search words.",
        "view.bird_category": "Every picture below belongs to “%(name)s”.",
        "view.wh_mixed": "General, Anime, and People are mixed here. Each picture still shows its own category.",
        "view.wh_own": "Categories on the cards come from Wallhaven: General, Anime, or People.",
        "view.bing": "Recent Bing daily wallpapers. There are no topic categories such as landscape or anime.",
        "view.bing_query": "Bing cannot search its whole archive.",
        "view.nasa": "These are NASA astronomy pictures.",
        "view.fav": "Pictures you starred. The category is the one stored when you saved them.",
        "view.fav_search": "Favorites matching “%(query)s”",
        "view.history": "Pictures you recently set as the desktop.",
        "view.history_search": "Recent matches for “%(query)s”",
        "source.birdpaper": "360 Wallpapers",
        "source.wallhaven": "Wallhaven",
        "source.bing": "Bing Daily",
        "source.nasa": "Astronomy",
        "source.favorites": "Favorites",
        "source.history": "Recent",
        "placeholder.birdpaper": "Search in Chinese or English, for example: 猫, stars, 原神",
        "placeholder.wallhaven": "English tags work directly. Chinese words are mapped, for example: 猫, cyberpunk",
        "placeholder.bing": "Bing daily pictures cannot be searched",
        "placeholder.nasa": "Astronomy pictures cannot be searched",
        "placeholder.favorites": "Search favorites",
        "placeholder.history": "Search recently set",
        "err.network": "The request failed. Check the network and try again.",
        "err.bad_json": "The wallpaper service returned data that could not be read.",
        "err.categories": "Could not load the category list",
        "err.categories_empty": "The category list was empty",
        "err.list": "Could not load the wallpaper list",
        "err.list_360": "Could not load the 360 wallpaper list",
        "err.wallhaven": "Wallhaven: %(error)s",
        "err.nasa": "NASA's astronomy picture is unavailable right now.",
        "err.nasa_json": "NASA returned data that could not be read.",
        "err.thumb": "Could not download the thumbnail",
        "err.full": "Could not download the full image",
        "err.full_save": "Could not save the full image",
        "err.autostart": "Starting with Windows can only be set on Windows.",
        "err.shortcut_kind": "Unknown shortcut location",
        "err.shortcut_platform": "Shortcuts can only be created on Windows.",
        "err.shortcut": "Could not create the shortcut: %(error)s",
        "err.shortcut_temp": "The shortcut cannot point at a temporary folder.",
        "err.unknown_source": "Unknown wallpaper source",
        "err.load": "Could not load: %(error)s",
        "err.unknown": "unknown reason",
        "wh.no_chinese": "Wallhaven cannot search Chinese directly. Search under 360 Wallpapers, or use English tags.",
        "wh.mapped": "Wallhaven only accepts English tags. Searched for “%(query)s”.",
        "wh.unknown": "No English tag for: %(words)s. Search those under 360 Wallpapers.",
        "note.bing_search": "Bing cannot search its whole archive. This only looks through recent daily titles.",
        "note.nasa_search": "Astronomy pictures cannot be searched across the whole archive.",
        "note.legacy": "Using the older 360 catalog.",
        "preview.unknown": "unknown reason",
    },
}

# 英文界面下的分类名。键是接口里的中文名，数据本身不改。
CATEGORY_EN = {
    "4K专区": "4K",
    "美女模特": "Models",
    "爱情美图": "Romance",
    "风景大片": "Landscapes",
    "小清新": "Fresh",
    "动漫卡通": "Anime",
    "明星风尚": "Celebrities",
    "萌宠动物": "Pets",
    "游戏壁纸": "Games",
    "汽车天下": "Cars",
    "炫酷时尚": "Style",
    "月历壁纸": "Calendars",
    "影视剧照": "Film & TV",
    "节日美图": "Holidays",
    "军事天地": "Military",
    "劲爆体育": "Sports",
    "BABY秀": "Babies",
    "文字控": "Typography",
    "未分类": "Uncategorized",
    "每日": "Daily",
    "天文": "Astronomy",
    "综合": "General",
    "动漫": "Anime",
    "人物": "People",
    "全部": "All",
    "最新": "Latest",
}

# 常见热门词。没有收录的词仍显示中文，点击后也按中文去搜。
TAG_EN = {
    "猫": "Cats",
    "猫咪": "Cats",
    "狗": "Dogs",
    "萌宠": "Pets",
    "动物": "Animals",
    "风景": "Landscape",
    "星空": "Stars",
    "夜景": "Night",
    "城市": "City",
    "海洋": "Ocean",
    "大海": "Sea",
    "森林": "Forest",
    "雪山": "Snow mountains",
    "樱花": "Cherry blossoms",
    "汽车": "Cars",
    "游戏": "Games",
    "原神": "Genshin",
    "二次元": "Anime",
    "动漫": "Anime",
    "美女": "Portraits",
    "情侣": "Couples",
    "可爱": "Cute",
    "清新": "Fresh",
    "文字": "Typography",
    "节日": "Holidays",
    "体育": "Sports",
    "军事": "Military",
    "4K": "4K",
    "赛博朋克": "Cyberpunk",
    "极简": "Minimal",
    "简约": "Minimal",
    "宇宙": "Space",
    "太空": "Space",
    "月亮": "Moon",
    "日落": "Sunset",
    "建筑": "Architecture",
    "花": "Flowers",
    "雪": "Snow",
    "雨": "Rain",
    "天空": "Sky",
    "海滩": "Beach",
    "公路": "Roads",
    "火车": "Trains",
    "飞机": "Planes",
    "机器人": "Robots",
    "像素": "Pixel art",
    "抽象": "Abstract",
    "复古": "Retro",
    "暗黑": "Dark",
    "城堡": "Castles",
    "自然": "Nature",
    "冬天": "Winter",
    "科技": "Technology",
    "女孩": "Girls",
    "人物": "People",
    "山": "Mountains",
    "海": "Ocean",
    "云": "Clouds",
    "夜": "Night",
    "车": "Cars",
    "清纯": "Fresh looks",
    "欧美女神": "Western portraits",
    "文艺古风": "Classical style",
    "爱情箴言": "Love notes",
    "浪漫手绘": "Romantic sketches",
    "心动创意": "Heartfelt",
    "唯美温馨": "Soft and warm",
    "蓝天白云": "Blue sky",
    "落日余晖": "Sunset glow",
    "春意盎然": "Spring",
    "炎炎夏日": "Summer",
    "秋意正浓": "Autumn",
    "冰天雪地": "Snow and ice",
    "城市夜景": "City nights",
    "海洋天堂": "Ocean",
    "自然风光": "Nature",
    "奇幻梦境": "Fantasy",
    "护眼壁纸": "Easy on the eyes",
    "舒缓压力": "Calm",
    "温馨一刻": "Warm moments",
    "清新淡雅": "Light and fresh",
    "静物写真": "Still life",
    "鸟语花香": "Birds and flowers",
    "动感水果": "Fruit",
    "娇艳欲滴": "Dewy flowers",
    "国漫": "Chinese animation",
    "龙珠": "Dragon Ball",
    "海贼王": "One Piece",
    "火影忍者": "Naruto",
    "秦时明月": "The Legend of Qin",
    "进击巨人": "Attack on Titan",
    "食尸鬼": "Tokyo Ghoul",
    "卡通人物": "Cartoon characters",
    "肖战": "Xiao Zhan",
    "杨幂": "Yang Mi",
    "杨洋": "Yang Yang",
    "杨颖": "Angelababy",
    "杨紫": "Yang Zi",
    "唐嫣": "Tang Yan",
    "刘诗诗": "Liu Shishi",
    "王一博": "Wang Yibo",
    "赵丽颖": "Zhao Liying",
    "张艺兴": "Lay Zhang",
    "迪丽热巴": "Dilraba",
    "古灵精怪": "Quirky",
    "野生动物": "Wildlife",
    "极地物种": "Polar animals",
    "汪星人": "Dogs",
    "喵星人": "Cats",
    "卖萌图": "Cute faces",
    "海底世界": "Under the sea",
    "小鸟天地": "Birds",
    "英雄联盟": "League of Legends",
    "王者荣耀": "Honor of Kings",
    "魔兽世界": "World of Warcraft",
    "守望先锋": "Overwatch",
    "主机游戏": "Console games",
    "手游世界": "Mobile games",
    "热门网游": "Online games",
    "布加迪": "Bugatti",
    "兰博基尼": "Lamborghini",
    "奔驰": "Mercedes-Benz",
    "法拉利": "Ferrari",
    "宝马": "BMW",
    "路虎": "Land Rover",
    "福特": "Ford",
    "宾利": "Bentley",
    "雪佛兰": "Chevrolet",
    "捷豹": "Jaguar",
    "悍马": "Hummer",
    "玛莎拉蒂": "Maserati",
    "奥迪": "Audi",
    "保时捷": "Porsche",
    "劳斯莱斯": "Rolls-Royce",
    "克尔维特": "Corvette",
}


def system_language():
    """zh* 用简体中文，其余用英文。优先看 QLocale。"""
    try:
        from PyQt5.QtCore import QLocale

        name = QLocale.system().name() or ""
        if name:
            return "zh_CN" if name.lower().startswith("zh") else "en"
    except Exception:
        pass
    names = []
    for key in ("LC_ALL", "LC_MESSAGES", "LANG"):
        value = os.environ.get(key) or ""
        if value:
            names.append(value)
    try:
        import locale

        current = locale.getlocale()[0] or ""
        if current:
            names.append(current)
        default = locale.getdefaultlocale()[0] or ""
        if default:
            names.append(default)
    except Exception:
        pass
    for name in names:
        if str(name).lower().startswith("zh"):
            return "zh_CN"
    return "en"


def activate(preference=None):
    """preference 为 zh_CN / en 时固定语言，否则看系统。"""
    global _language
    pref = (preference or "").strip()
    if pref in ("zh_CN", "en"):
        _language = pref
    else:
        _language = system_language()
    return _language


def current():
    if _language is None:
        activate(None)
    return _language


def tr(key, **kwargs):
    lang = current()
    table = STRINGS.get(lang) or STRINGS["en"]
    text = table.get(key)
    if text is None:
        text = STRINGS["en"].get(key, STRINGS["zh_CN"].get(key, key))
    if not kwargs:
        return text
    try:
        return text % kwargs
    except Exception:
        return text


def category_name(name):
    text = (name or "").strip()
    if not text:
        return ""
    if current() == "en":
        return CATEGORY_EN.get(text, text)
    return text


def tag_name(name):
    text = (name or "").strip()
    if not text:
        return ""
    if current() == "en":
        return TAG_EN.get(text, text)
    return text


def source_name(key):
    label = tr("source." + (key or ""))
    if label.startswith("source."):
        return key or ""
    return label


def shortcut_link_name():
    if current() == "zh_CN":
        return "壁纸库.lnk"
    return "Wallpapers.lnk"

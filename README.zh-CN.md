# 壁纸库

找壁纸、预览，然后设成桌面。程序用 Python 和 PyQt5。Windows 可以下载便携版；macOS 和 Linux 从源码运行。

界面有简体中文和英文。第一次打开时跟系统语言走（`QLocale`：`zh*` 用中文，其余用英文）。设置里可以固定语言，写在 `preferences.json` 里，下次打开生效。

英文说明见 [README.md](README.md)。

## 功能

- 360 壁纸（小鸟壁纸库）按网站自己的分类浏览，也可以用中文搜索。
- Wallhaven（综合、动漫、人物）、必应每日壁纸、NASA 每日天文图。
- 卡片用小缩略图。预览和「设为壁纸」才下载原图。
- 收藏，以及最近设为桌面的图。
- 关掉窗口后程序留在托盘里。再打开一次，会唤起已经在运行的窗口。
- 在 Windows 上，启动时会确保开始菜单里有快捷方式，让任务栏使用程序自己的图标（应用 ID 是 `WallpaperLibrary.App`）。快捷方式的名字跟界面语言走。

## 截图

仓库里还没有截图。有图之后可以放在这里：

- 选中分类后的图库
- 预览
- 设置，包括语言开关

## 下载 Windows 程序

打开 **Releases**，在 `v*` 标签下下载 `WallpaperLibrary-windows.zip`。解压后运行 `WallpaperLibrary.exe`。不需要安装 Python。

这个目录是便携的。配置、缓存和收藏优先放在 exe 旁边；那个目录不能写时，改放到 `%LOCALAPPDATA%\WallpaperLibrary`。

推送名为 `v*` 的标签（例如 `v1.0.0`）后，GitHub Actions 会在 `windows-latest` 上打包，并把 zip 挂到对应的 Release。

## 从源码运行

需要 Python 3.11 或更新的版本。Windows 上的启动脚本使用 `pythonw`，不会留下黑色命令行窗口。

```bash
pip install -r requirements.txt
python wallpaper_app_qt.py
```

在 Windows 上也可以双击 `启动壁纸库.bat`。它的内容是：

```bat
start "" pythonw "%~dp0wallpaper_app_qt.py"
```

从源码运行时，`cache\`、`preferences.json`、`favorites.json` 和 `history.json` 都在程序目录里，和脚本放在一起。原来的 `cache` 文件夹会继续使用。

## 自己打包 Windows exe

在 Windows 上运行：

```bat
build_windows.bat
```

脚本会新建一个干净的 `.build-venv`，只在里面安装 `requirements.txt` 和 PyInstaller，再用 `WallpaperLibrary.spec` 打包。不会带上系统 Python 里的其他库。生成的文件是 `dist\WallpaperLibrary\WallpaperLibrary.exe`。没有控制台窗口，图标是 `assets\app.ico`。PyInstaller 只在打包时需要，不写在 `requirements.txt` 里。

## 各系统能做什么

| | Windows | macOS | Linux |
| --- | --- | --- | --- |
| 浏览、搜索、下载、收藏 | 可以 | 可以 | 可以 |
| 设为壁纸 | 可以 | 尽量设置，用 `osascript` | 尽量设置：GNOME 用 `gsettings`，KDE 用 `qdbus`，XFCE 用 `xfconf-query` |
| 开机启动和快捷方式 | 可以 | 不显示。不能设置。 | 不显示。不能设置。 |
| 便携 exe | 可以 | 没有。请从源码运行。 | 没有。请从源码运行。 |

当前桌面不能自动换壁纸时，图片仍会保存，并给出说明。程序不会因此崩溃。

## 图片来源

程序从这些服务取图：

- 必应每日壁纸
- Wallhaven
- 360 壁纸（小鸟壁纸库）
- NASA 每日天文图

图片属于各自的提供者。本项目不主张任何壁纸的版权。

用中文搜索时，360 壁纸仍按中文关键词查找。Wallhaven 会把能对应上的中文词换成英文标签。

## 测试

```bash
python -m unittest tests.test_core tests.test_gui
```

## 许可证

[MIT](LICENSE)

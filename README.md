# Copyboard — Windows 历史剪贴板管理器

一个运行在 Windows 上的轻量剪贴板历史管理工具，自动记录文字、图片、文件及文件夹的复制历史，支持搜索、筛选、收藏和快速回贴。

## ✨ 功能

- **自动记录** — 后台监听剪贴板变化，自动记录文字、图片、文件、文件夹
- **快捷呼出** — 按 `Alt+V` 弹出面板，浏览历史记录
- **一键粘贴** — 点击卡片复制到剪贴板，支持连续复制不关闭面板
- **智能分类** — 文字、图片、文件、文件夹自动识别分类，图片文件按扩展名归类
- **收藏 & 置顶** — 常用条目收藏，重要内容置顶
- **5 套主题** — 浅色 / 深色 / 暖色 / 森林 / 海洋，一键切换
- **存储模式** — 轻量模式（仅路径引用）和完整模式（复制到本地）自由切换
- **数据管理** — 可设保留天数和最大条数，一键清理所有数据
- **开机自启** — 设置中开启，随 Windows 自动启动
- **系统托盘** — 托盘图标右键菜单，最小化到后台运行
- **任务栏可见** — 显示在 Windows 任务栏，方便管理
- **低资源占用** — 轻量模式仅存路径，不复制文件，磁盘占用极小

## 📸 界面预览

![](https://cdn.jsdelivr.net/gh/Ming-Light-Code/Comic-Photos/test/copyboardshow.png)


## 📁 项目结构

```
copyboard/
├── main.py                  # 主应用入口 + 完整 UI
├── database.py              # SQLite 数据库操作
├── clipboard_monitor.py     # 剪贴板监听（低干扰模式）
├── file_store.py            # 轻量文件/图片存储
├── settings_manager.py      # 设置管理 + 开机自启
├── tray_manager.py          # 系统托盘管理
├── hotkey_manager.py        # 全局快捷键（RegisterHotKey API）
├── ui/
│   └── theme_manager.py     # 5 套配色主题
├── assets/
│   └── icon.png             # 应用图标
├── copyboard.spec           # PyInstaller 打包配置
├── requirements.txt         # Python 依赖
└── README.md
```

## 🛠 技术栈

| 组件 | 方案 |
|------|------|
| GUI | tkinter (无边框自绘) |
| 数据库 | SQLite (WAL 模式) |
| 剪贴板 | Windows API (CF_HDROP / CF_DIB) + PIL |
| 托盘 | pystray |
| 快捷键 | `RegisterHotKey` API（不安装钩子） |
| 打包 | PyInstaller |

## 📋 环境要求

- Windows 10 / 11
- Python 3.10+（源码运行时）

## 📄 许可

MIT

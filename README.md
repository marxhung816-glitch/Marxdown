# Marxdown

<img src="resources/icons/marxdown.png" alt="Marxdown 图标" width="96">

Marxdown 是一个使用 Python、PySide6 和 Qt WebEngine 编写的 Windows 桌面 Markdown 阅读与编辑工具。支持中文 UTF-8 文件、文件夹浏览、多标签、文章目录、代码高亮、明暗主题、搜索、自动刷新及 PDF/Word 导出。

## 环境

- Windows 10/11
- Python 3.10 或更新版本（推荐 3.12）

## 安装并运行

在项目根目录打开 PowerShell：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python main.py
```

也可以直接传入文件或文件夹：

```powershell
python main.py "C:\文档\学习笔记.md"
python main.py "C:\文档"
```

如果 PowerShell 阻止激活虚拟环境，可直接使用 `.\.venv\Scripts\python.exe -m pip install -r requirements.txt` 和 `.\.venv\Scripts\python.exe main.py`。

## 使用

- 点击顶部“打开”菜单选择文件或文件夹，也可以把 `.md` 或 `.markdown` 文件拖到窗口。
- 点击“编辑”打开 Markdown 源码和实时预览双栏；修改后点击“保存”或按 Ctrl+S。点击“完成”返回单栏预览。未保存的标签会显示圆点标记。
- 编辑器会把中文输入法候选栏的位置移离当前输入行，方便看清正在修改的文字。
- 顶部“⋯”→“导出”可保存为 PDF 或 Word。导出使用当前编辑内容，包括尚未保存的修改；PDF 采用浅色打印样式，Word 保留可编辑的文字、标题、列表、表格、代码和本地图片。
- 关闭未保存文件时会询问是否保存；编辑期间如磁盘文件被其他程序修改，软件会保留当前输入，保存前询问是否覆盖。
- 顶部左侧按钮可显示或隐藏侧栏；侧栏中的“文件”和“目录”可切换。文件树只显示子文件夹与 Markdown 文件；点击文件会在标签页打开。
- 点击文章目录可跳转至一级至三级标题，也显示更深层标题。单文件阅读时标签栏自动收起，多文件时显示。
- 主题、最近文件和设置位于顶部右侧的“⋯”菜单。
- 相对图片路径按当前 Markdown 文件的目录解析；相对 Markdown 链接在软件内打开，网页链接由系统默认浏览器打开。
- 外部编辑器保存文件后，软件约在 1.2 秒内检测并刷新。
- 最近文件、主题和正文字号会保存在系统设置中。

| 快捷键 | 操作 |
| --- | --- |
| Ctrl+O | 打开文件 |
| Ctrl+Shift+O | 打开文件夹 |
| Ctrl+W | 关闭当前标签页 |
| Ctrl+R | 刷新当前文件 |
| Ctrl+F | 搜索当前文档 |
| Ctrl+E | 切换源码编辑与预览 |
| Ctrl+S | 保存当前文件 |

## 测试

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

## 打包 Windows exe

在 Windows 的项目根目录运行：

```powershell
python -m pip install -r requirements-dev.txt
powershell -ExecutionPolicy Bypass -File build\build.ps1
```

生成的主程序为 `dist\Marxdown\Marxdown.exe`。分发时应保留整个 `dist\Marxdown` 文件夹，因为 Qt WebEngine 需要随程序携带资源与辅助进程。构建脚本排除了本查看器不用的 Qt Quick 资源，并避免从其他已安装工具误收不兼容的 ICU DLL。单文件构建可给脚本加 `-OneFile`，启动时需要先解包，通常更慢。

## 发布到 GitHub

将本项目目录中的源码作为仓库根目录上传。`.gitignore` 已排除虚拟环境、测试缓存和打包产物。Windows 下载包适合放在 GitHub Releases；请把整个 `dist\Marxdown` 文件夹压缩上传，单独的 exe 缺少 Qt WebEngine 资源，无法运行。公开发布前请自行选择并添加合适的开源许可证。

## 项目结构

```text
Marxdown/
├── main.py                       程序入口
├── requirements.txt              运行依赖
├── requirements-dev.txt          测试及打包依赖
├── pytest.ini                     测试目录配置
├── README.md
├── app/
│   ├── main_window.py            主窗口、文件树和快捷键
│   ├── branding.py               程序名称与图标路径
│   ├── tab_widget.py             轻量标签栏
│   ├── tab_manager.py            文档页、WebEngine 和链接处理
│   ├── markdown_editor.py        中文输入法候选栏定位
│   ├── export_manager.py         PDF 与 Word 导出
│   ├── runtime_loader.py         后台加载预览组件
│   ├── markdown_renderer.py      Markdown、目录和 Pygments
│   ├── file_manager.py           UTF-8 文件读取和路径处理
│   └── settings.py               最近文件、主题及设置对话框
├── resources/css/
│   ├── github-light.css
│   └── github-dark.css
├── resources/icons/
│   ├── marxdown.svg
│   ├── marxdown.png
│   └── marxdown.ico
├── build/build.ps1
└── tests/
    ├── test_core.py
    ├── test_gui.py
    ├── test_editor.py
    ├── test_export.py
    ├── test_branding.py
    ├── test_settings.py
    └── test_startup.py
```

预览组件在主窗口显示后加载；第一次打开文件时，界面可能短暂显示“正在准备预览”。渲染结果通过临时 HTML 文件交给 Qt WebEngine，因此不受 `setHtml()` 的大小限制。

# 金水字幕 Pro v2.0 🎬

> 专业级 AI 语音识别字幕工具 — GPU 加速 · 字级对齐 · 一键压制

金水字幕 Pro 是一款基于 Qwen3-ASR 大模型的桌面端字幕制作工具，支持语音识别、字级时间戳对齐、多引擎翻译、双语字幕导出和硬字幕压制。

## ✨ 核心功能

- **🎙️ AI 语音识别** — 基于 Qwen3-ASR-1.7B 大模型，GPU 加速推理，带 VAD 防漏音引擎
- **🎯 字级对齐** — Qwen3-ForcedAligner-0.6B 精确到字的时间戳对齐
- **🌐 多引擎翻译** — DeepSeek AI 语境翻译 / Google 免费翻译 / 百度翻译
- **📝 术语强控** — 自定义术语表，AI 翻译强制替换指定词汇
- **✂️ 智能断句** — 超字数自动回溯断句，按标点智能拆分
- **🎨 样式字幕** — ASS 高级字幕，独立控制原文/译文字体、颜色、大小、位置
- **🎞️ 视频压制** — GPU 硬件编码硬字幕，自动检测 NVENC/AMF/QSV
- **🖥️ 桌面应用** — Tauri + Vue 3 原生桌面，支持拖拽导入

## 📋 系统要求

| 项目 | 最低配置 | 推荐配置 |
|------|---------|---------|
| 操作系统 | Windows 10+ | Windows 11 |
| 内存 | 8 GB | 16 GB+ |
| GPU 显存 | 4 GB (CPU 回退) | 8 GB+ (CUDA 12.1) |
| 磁盘空间 | 10 GB | 15 GB (含模型) |
| Python | 3.11 | 3.11 |

## 🚀 快速开始 (从源码运行)

### 1. 克隆仓库

```bash
git clone https://github.com/jinshui1987/jinshui-subtitle-pro.git
cd jinshui-subtitle-pro
```

### 2. 创建虚拟环境

```bash
python -m venv venv
venv\Scripts\activate   # Windows
# source venv/bin/activate  # Linux/macOS
```

### 3. 安装 PyTorch (CUDA 版本)

```bash
# GPU 版本 (CUDA 12.1)
pip install torch==2.5.1+cu121 torchaudio==2.5.1+cu121 --index-url https://download.pytorch.org/whl/cu121

# 或 CPU 版本 (无 GPU)
# pip install torch==2.5.1 torchaudio==2.5.1 --index-url https://download.pytorch.org/whl/cpu
```

### 4. 安装依赖

```bash
pip install -r requirements.txt
```

### 5. 下载 AI 模型

```bash
# 创建模型目录
mkdir models

# 从 HuggingFace 下载模型 (~6GB)
# 方法1: 使用 huggingface-cli
huggingface-cli download Qwen/Qwen3-ASR-1.7B --local-dir models/Qwen3-ASR-1.7B
huggingface-cli download Qwen/Qwen3-ForcedAligner-0.6B --local-dir models/Qwen3-ForcedAligner-0.6B

# 方法2: 从 ModelScope 下载 (国内更快)
# pip install modelscope
# modelscope download --model Qwen/Qwen3-ASR-1.7B --local_dir models/Qwen3-ASR-1.7B
# modelscope download --model Qwen/Qwen3-ForcedAligner-0.6B --local_dir models/Qwen3-ForcedAligner-0.6B
```

### 6. 安装 FFmpeg

下载 [FFmpeg](https://ffmpeg.org/download.html) 并将 `ffmpeg.exe` 放到项目根目录。

### 7. 启动服务

```bash
# 启动后端 API 服务 (端口 8712)
python api_server.py

# 新终端 — 启动前端开发服务器
cd frontend
npm install
npm run tauri dev
```

## 📦 使用预编译安装包

如果你不想从源码构建，可以直接下载打包好的安装器：

1. 从 [Releases](https://github.com/jinshui1987/jinshui-subtitle-pro/releases) 下载 `金水字幕Pro_Setup_v2.0.0.exe` 和 `.bin` 文件
2. 将两个文件放在同一目录下
3. 运行 `金水字幕Pro_Setup_v2.0.0.exe` 安装
4. 安装完成后双击桌面图标启动

## 🏗️ 项目结构

```
jinshui-subtitle-pro/
├── api_server.py              # FastAPI 后端入口 (端口 8712)
├── api_server.spec            # PyInstaller 打包配置
├── requirements.txt           # Python 依赖清单
├── core/                      # 核心业务模块
│   ├── asr_engine.py          # ASR 引擎 (Qwen3 + VAD 防漏墙)
│   ├── audio_processor.py     # 音频提取与切片
│   ├── translator.py          # 翻译引擎 (DeepSeek/Google/Baidu)
│   ├── exporter.py            # 字幕导出 (SRT/ASS/视频压制)
│   ├── subtitle_model.py      # 字幕数据模型
│   ├── model_manager.py       # AI 模型下载与管理
│   └── license_manager.py     # 离线激活验证
├── frontend/                  # Tauri + Vue 3 桌面应用
│   ├── src-tauri/             # Rust 后端 (窗口管理/引擎启动)
│   │   ├── src/
│   │   │   ├── lib.rs         # 引擎进程管理 + 许可证验证
│   │   │   └── license.rs     # 激活码验证
│   │   ├── Cargo.toml         # Rust 依赖
│   │   └── tauri.conf.json    # Tauri 窗口与打包配置
│   ├── src/                   # Vue 3 前端
│   │   ├── components/
│   │   │   ├── MainEditor.vue # 主编辑器 (字幕列表/时间轴)
│   │   │   ├── StyleDialog.vue # 样式配置对话框
│   │   │   └── ActivationScreen.vue # 激活页面
│   │   └── App.vue            # 根组件
│   └── package.json           # npm 依赖
├── installer/
│   └── setup.iss              # Inno Setup 安装脚本
├── main_cli.py                # CLI 命令行测试入口
├── main_gui.py                # PySide6 桌面界面 (备用)
└── models/                    # AI 模型 (需自行下载)
    ├── Qwen3-ASR-1.7B/        # ~4.5 GB
    └── Qwen3-ForcedAligner-0.6B/  # ~1.75 GB
```

## 🔧 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| 桌面框架 | Tauri v2 (Rust) | 窗口管理、系统托盘、进程管理 |
| 前端 UI | Vue 3 + TypeScript + Vite | TailwindCSS 样式 |
| 后端 API | FastAPI + Uvicorn | 本地 HTTP 服务 (127.0.0.1:8712) |
| AI 推理 | Transformers + PyTorch CUDA | GPU 加速推理 |
| ASR 模型 | Qwen3-ASR-1.7B | 语音识别 |
| 对齐模型 | Qwen3-ForcedAligner-0.6B | 字级时间戳对齐 |
| 翻译 | DeepSeek API / Google / Baidu | 多引擎字幕翻译 |
| 音视频 | ffmpeg-python + PyAV | 音频提取、视频压制 |

## 🔨 构建发布包

完整构建流程 (Nuitka + PyInstaller + Tauri + Inno Setup)：

```bash
# 1. Nuitka 编译核心代码 → .pyd 机器码 (闭源保护)
cd E:\Jinshui_Pro
for f in core/*.py; do
  base=$(basename "$f" .py)
  [ "$base" = "__init__" ] && continue
  venv/Scripts/python.exe -m nuitka --mode=module \
    --output-dir=nuitka_pyd \
    --nofollow-import-to=torch --nofollow-import-to=transformers \
    --nofollow-import-to=fastapi --nofollow-import-to=... \
    "$f"
done

# 2. PyInstaller 打包 engine/ 目录
venv/Scripts/python.exe -m PyInstaller api_server.spec --noconfirm

# 3. 复制 engine/ 到 Tauri 构建目录
mkdir -p _tauri_staging
cp -r dist/engine _tauri_staging/

# 4. Tauri 构建前端 app.exe
cd frontend
npm install
npx tauri build

# 5. Inno Setup 打包安装器
# 用 Inno Setup 6 打开 installer/setup.iss 编译
```

详细构建文档见项目 Wiki。

## 📡 API 端点

所有 API 在 `http://127.0.0.1:8712`：

| 方法 | 路径 | 功能 |
|------|------|------|
| GET | `/api/health` | 健康检查 (GPU 状态/模型就绪) |
| POST | `/api/asr` | 语音识别 → 字幕 JSON |
| POST | `/api/translate` | 批量翻译字幕 |
| POST | `/api/translate/single` | 单句翻译 |
| POST | `/api/optimize` | AI 润色 + 自动断句 |
| POST | `/api/export/srt` | 导出 SRT 字幕 |
| POST | `/api/export/ass` | 导出 ASS 样式字幕 |
| POST | `/api/export/video` | 压制硬字幕视频 |
| POST | `/api/upload` | 上传视频文件 |

## 📄 许可证

本项目采用双轨制：
- **源代码**: MIT License
- **预编译安装包**: 需输入激活码使用

## 🙏 致谢

- [Qwen](https://github.com/QwenLM/Qwen3) — ASR 与 Forced Aligner 模型
- [Silero VAD](https://github.com/snakers4/silero-vad) — 语音活动检测
- [Tauri](https://tauri.app/) — 跨平台桌面框架
- [FastAPI](https://fastapi.tiangolo.com/) — 高性能 Python Web 框架

---

**作者**: [金水1987](https://space.bilibili.com/) | B站搜索「金水1987」

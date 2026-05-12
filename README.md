# 金水字幕 Pro v2.0

> 专业级 AI 语音识别字幕工具 — GPU 加速 · 字级对齐 · 一键压制

基于 Qwen3-ASR 大模型的桌面端字幕制作工具，支持语音识别、字级时间戳对齐、多引擎翻译、双语字幕导出和硬字幕压制。

## 核心功能

- **AI 语音识别** — Qwen3-ASR-1.7B 大模型，GPU 加速推理，VAD 防漏音引擎
- **字级对齐** — Qwen3-ForcedAligner-0.6B 精确到字的时间戳对齐
- **多引擎翻译** — DeepSeek AI 语境翻译 / Google 免费翻译 / 百度翻译
- **术语强控** — 自定义术语表，AI 翻译强制替换指定词汇
- **智能断句** — 超字数自动回溯断句，按标点智能拆分
- **样式字幕** — ASS 高级字幕，独立控制原文/译文字体、颜色、大小、位置
- **视频压制** — GPU 硬件编码硬字幕，自动检测 NVENC/AMF/QSV
- **桌面应用** — Tauri + Vue 3 原生桌面，支持拖拽导入

## 系统要求

| 项目 | 最低配置 | 推荐配置 |
|------|---------|---------|
| 操作系统 | Windows 10+ | Windows 11 |
| 内存 | 8 GB | 16 GB+ |
| GPU 显存 | 4 GB (CPU 回退) | 8 GB+ (CUDA 12.1) |
| 磁盘空间 | 10 GB | 15 GB (含模型) |
| Python | 3.11 | 3.11 |

## 安装与运行

### 1. 克隆仓库

```bash
git clone https://github.com/jinshuixiaopuzi/jinshui-subtitle-pro.git
cd jinshui-subtitle-pro
```

### 2. 创建虚拟环境

```bash
python -m venv venv
venv\Scripts\activate
```

### 3. 安装 PyTorch

```bash
# GPU 版本 (CUDA 12.1)
pip install torch==2.5.1+cu121 torchaudio==2.5.1+cu121 --index-url https://download.pytorch.org/whl/cu121

# 或 CPU 版本 (无 GPU)
pip install torch==2.5.1 torchaudio==2.5.1 --index-url https://download.pytorch.org/whl/cpu
```

### 4. 安装依赖

```bash
pip install -r requirements.txt
```

### 5. 下载 AI 模型

```bash
mkdir models

# 从 HuggingFace 下载
huggingface-cli download Qwen/Qwen3-ASR-1.7B --local-dir models/Qwen3-ASR-1.7B
huggingface-cli download Qwen/Qwen3-ForcedAligner-0.6B --local-dir models/Qwen3-ForcedAligner-0.6B

# 或从 ModelScope 下载 (国内更快)
pip install modelscope
modelscope download --model Qwen/Qwen3-ASR-1.7B --local_dir models/Qwen3-ASR-1.7B
modelscope download --model Qwen/Qwen3-ForcedAligner-0.6B --local_dir models/Qwen3-ForcedAligner-0.6B
```

### 6. 安装 FFmpeg

下载 [FFmpeg](https://ffmpeg.org/download.html)，将 `ffmpeg.exe` 放到项目根目录。

### 7. 启动

```bash
# 启动后端 API 服务 (端口 8712)
python api_server.py

# 新终端 — 启动前端桌面应用
cd frontend
npm install
npm run tauri dev
```

## API 端点

所有接口在 `http://127.0.0.1:8712`：

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

## 技术栈

| 层级 | 技术 |
|------|------|
| 桌面框架 | Tauri v2 (Rust) |
| 前端 UI | Vue 3 + TypeScript + Vite |
| 后端 API | FastAPI + Uvicorn |
| AI 推理 | Transformers + PyTorch CUDA |
| ASR 模型 | Qwen3-ASR-1.7B |
| 对齐模型 | Qwen3-ForcedAligner-0.6B |
| 翻译 | DeepSeek API / Google / Baidu |
| 音视频 | ffmpeg-python + PyAV |

## 许可证

- **源代码**: MIT License
- **预编译安装包**: 需输入激活码使用

## 致谢

- [Qwen](https://github.com/QwenLM/Qwen3) — ASR 与 Forced Aligner 模型
- [Silero VAD](https://github.com/snakers4/silero-vad) — 语音活动检测
- [Tauri](https://tauri.app/) — 跨平台桌面框架
- [FastAPI](https://fastapi.tiangolo.com/) — 高性能 Python Web 框架

---

**作者**: 金水1987 | B站搜索「金水1987」

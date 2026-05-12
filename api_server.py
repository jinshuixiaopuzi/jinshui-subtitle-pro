# api_server.py
"""金水字幕 Pro v2.0 — FastAPI 后端引擎"""
import os
import sys
import json
import uvicorn
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional

# ===== Windows 控制台 UTF-8 编码（修复 emoji GBK 报错） =====
if sys.platform == 'win32':
    # Python 3.7+ 标准做法
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# ===== PyInstaller 路径兼容 =====
def _get_app_root() -> str:
    """获取应用根目录（开发/PyInstaller 通用）
    开发模式: api_server.py 所在目录
    PyInstaller: engine.exe 所在目录 (资源文件均在此)
    """
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def _get_ffmpeg_path() -> str:
    root = _get_app_root()
    # 优先查找同级目录，其次 _internal (PyInstaller onedir)
    for candidate in [
        os.path.join(root, 'ffmpeg.exe'),
        os.path.join(root, '_internal', 'ffmpeg.exe'),
    ]:
        if os.path.exists(candidate):
            return os.path.abspath(candidate)
    return os.path.abspath(os.path.join(root, 'ffmpeg.exe'))

def _get_models_dir() -> str:
    return os.path.abspath(os.path.join(_get_app_root(), 'models'))

# 确保能找到 core/ 模块
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

# 设置 ffmpeg 路径供 ffmpeg-python 使用
_ffmpeg_dir = os.path.dirname(_get_ffmpeg_path())
if _ffmpeg_dir not in os.environ.get('PATH', ''):
    os.environ['PATH'] = _ffmpeg_dir + os.pathsep + os.environ.get('PATH', '')

from core.subtitle_model import SubtitleManager
from core.audio_processor import AudioProcessor
from core.asr_engine import ASREngine  # _get_models_dir 使用本地 PyInstaller 兼容版本
from core.translator import TranslatorEngine
from core.exporter import ExporterEngine

app = FastAPI(title="金水字幕 Pro 引擎", version="2.0.0")

# CORS：允许 Tauri 前端跨域调用
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ================= 请求/响应模型 =================

class ASRRequest(BaseModel):
    video_path: str
    max_chars: int = 25

class ASRResponse(BaseModel):
    success: bool
    subtitles: list
    message: str = ""

class TranslateRequest(BaseModel):
    subtitles: list
    api_key: str = ""
    api_base: str = "https://api.deepseek.com"
    model: str = "deepseek-chat"
    target_lang: str = "英文"
    engine_type: str = "google"
    glossary: str = ""

class TranslateResponse(BaseModel):
    success: bool
    translated: list
    message: str = ""

class OptimizeRequest(BaseModel):
    subtitles: list
    api_key: str = ""
    api_base: str = "https://api.deepseek.com"
    model: str = "deepseek-chat"
    engine_type: str = "deepseek"
    glossary: str = ""
    max_chars: int = 25

class OptimizeResponse(BaseModel):
    success: bool
    optimized: list
    message: str = ""

class ExportRequest(BaseModel):
    subtitles: list
    mode: str
    output_path: str
    video_path: str = ""
    style_config: dict = {}

class SingleTranslateRequest(BaseModel):
    text: str
    api_key: str = ""
    api_base: str = "https://api.deepseek.com"
    model: str = "deepseek-chat"
    target_lang: str = "英文"
    engine_type: str = "deepseek"

class SingleTranslateResponse(BaseModel):
    success: bool
    translated_text: str = ""
    message: str = ""

class HealthResponse(BaseModel):
    status: str
    gpu_available: bool
    models_ready: bool
    models_dir: str

class FontsResponse(BaseModel):
    success: bool
    fonts: list

# ================= 引擎实例（懒加载） =================

_asr_engine = None
_exporter_engine = None

def get_asr_engine():
    global _asr_engine
    if _asr_engine is None:
        _asr_engine = ASREngine()
    return _asr_engine

def get_exporter_engine():
    global _exporter_engine
    if _exporter_engine is None:
        _exporter_engine = ExporterEngine()
    return _exporter_engine

# ================= API 端点 =================

@app.get("/api/health", response_model=HealthResponse)
def health_check():
    """健康检查 — 判断 GPU、模型状态"""
    import torch
    gpu_ok = torch.cuda.is_available()
    models_dir = _get_models_dir()
    asr_ok = os.path.exists(os.path.join(models_dir, "Qwen3-ASR-1.7B"))
    align_ok = os.path.exists(os.path.join(models_dir, "Qwen3-ForcedAligner-0.6B"))
    return HealthResponse(
        status="ok",
        gpu_available=gpu_ok,
        models_ready=asr_ok and align_ok,
        models_dir=models_dir,
    )

@app.get("/api/fonts")
def list_system_fonts():
    """返回系统安装的所有字体名称（Windows 通过 .NET 枚举）"""
    import subprocess
    try:
        ps_cmd = (
            'Add-Type -AssemblyName System.Drawing; '
            '[System.Drawing.FontFamily]::Families | '
            'ForEach-Object { $_.Name } | Sort-Object'
        )
        result = subprocess.run(
            ['powershell', '-NoProfile', '-Command', ps_cmd],
            capture_output=True, text=True, timeout=10
        )
        fonts = [line.strip() for line in result.stdout.split('\n') if line.strip()]
        if not fonts:
            raise ValueError("PowerShell 返回空字体列表")
        return {"success": True, "fonts": fonts}
    except Exception:
        # Fallback: 常见中英文字体
        return {"success": True, "fonts": [
            "Microsoft YaHei", "SimHei", "SimSun", "FangSong", "KaiTi", "YouYuan",
            "Arial", "Segoe UI", "Consolas", "Courier New", "Times New Roman",
            "Noto Sans SC", "Noto Serif SC", "PingFang SC", "STHeiti", "STKaiti",
        ]}

@app.post("/api/asr", response_model=ASRResponse)
def run_asr(req: ASRRequest):
    """接收视频路径 → 语音识别 → 返回字幕 JSON"""
    if not os.path.exists(req.video_path):
        raise HTTPException(400, f"视频文件不存在: {req.video_path}")

    wav_path = "temp/api_extracted.wav"
    os.makedirs("temp", exist_ok=True)

    try:
        AudioProcessor().extract_audio(req.video_path, wav_path)
        sub_manager = SubtitleManager()
        get_asr_engine().process_video_to_subtitles(wav_path, sub_manager, max_chars=req.max_chars)

        result = []
        for s in sub_manager.subtitles:
            result.append({
                "id": s.id,
                "start_time": round(s.start_time, 3),
                "end_time": round(s.end_time, 3),
                "original_text": s.original_text,
                "reference_text": s.reference_text,
                "translated_text": s.translated_text,
            })

        return ASRResponse(success=True, subtitles=result, message=f"共识别 {len(result)} 条字幕")

    except Exception as e:
        raise HTTPException(500, str(e))

    finally:
        if os.path.exists(wav_path):
            os.remove(wav_path)

@app.post("/api/translate", response_model=TranslateResponse)
def run_translate(req: TranslateRequest):
    """批量翻译字幕"""
    if not req.subtitles:
        raise HTTPException(400, "字幕数据为空")

    try:
        from core.subtitle_model import SubtitleItem
        sub_manager = SubtitleManager()
        for s in req.subtitles:
            item = SubtitleItem(
                id=s.get("id", ""),
                start_time=s.get("start_time", 0),
                end_time=s.get("end_time", 0),
                original_text=s.get("original_text", ""),
                reference_text=s.get("reference_text", s.get("original_text", "")),
                translated_text=s.get("translated_text", ""),
            )
            sub_manager.subtitles.append(item)

        engine = TranslatorEngine(
            api_key=req.api_key,
            base_url=req.api_base,
            model=req.model,
            engine_type=req.engine_type,
        )
        engine.batch_translate(sub_manager, glossary=req.glossary, target_lang=req.target_lang)

        result = []
        for s in sub_manager.subtitles:
            result.append({
                "id": s.id,
                "translated_text": s.translated_text,
            })

        return TranslateResponse(success=True, translated=result, message=f"翻译完成")

    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/api/optimize", response_model=OptimizeResponse)
def run_optimize(req: OptimizeRequest):
    """优化/润色原文（超字数自动回溯断句 + 拆分新字幕条）"""
    if not req.subtitles:
        raise HTTPException(400, "字幕数据为空")

    import re

    try:
        from core.subtitle_model import SubtitleItem
        sub_manager = SubtitleManager()
        for s in req.subtitles:
            item = SubtitleItem(
                id=s.get("id", ""),
                start_time=s.get("start_time", 0),
                end_time=s.get("end_time", 0),
                original_text=s.get("original_text", ""),
                reference_text=s.get("reference_text", s.get("original_text", "")),
                translated_text=s.get("translated_text", ""),
            )
            sub_manager.subtitles.append(item)

        engine = TranslatorEngine(
            api_key=req.api_key,
            base_url=req.api_base,
            model=req.model,
            engine_type=req.engine_type,
        )
        engine.batch_optimize(sub_manager, glossary=req.glossary)

        split_count = 0
        new_items = []  # 收集需要插入的新字幕条

        for i, s in enumerate(sub_manager.subtitles):
            if len(s.original_text) <= req.max_chars:
                continue

            # 超字数：找到 max_chars 范围内最后一个断句点
            text = s.original_text
            limit = req.max_chars
            within = text[:limit]

            # 断句点优先级：。！？> ；：> ，> 空格 > 英文标点
            break_points = [
                r'[。！？]',
                r'[；;：:]',
                r'[，,、]',
                r'\s',
                r'[\.!\?]',
            ]

            split_at = -1
            for bp in break_points:
                matches = list(re.finditer(bp, within))
                if matches:
                    split_at = matches[-1].end()
                    break

            if split_at <= 0:
                continue  # 找不到断句点，跳过

            # 拆分文本
            first_part = text[:split_at].strip()
            second_part = text[split_at:].lstrip('，,、;；:：!！?？.。\s')

            if not first_part or not second_part:
                continue

            # 按字符比例拆分时间
            total_chars = len(text)
            ratio = len(first_part) / total_chars
            duration = s.end_time - s.start_time
            split_time = s.start_time + duration * ratio

            # 更新当前字幕
            s.original_text = first_part
            s.reference_text = first_part
            s.end_time = round(split_time, 3)

            # 创建新字幕条（溢出部分）
            import uuid
            new_sub = SubtitleItem(
                id=str(uuid.uuid4()),
                start_time=round(split_time, 3),
                end_time=round(split_time + max(2.0, duration * (1 - ratio)), 3),
                original_text=second_part,
                reference_text=second_part,
                translated_text="",  # 新字幕需重新翻译
            )
            new_items.append((i + 1 + split_count, new_sub))
            split_count += 1

        # 按倒序插入新字幕（避免索引偏移）
        for insert_idx, new_sub in sorted(new_items, key=lambda x: -x[0]):
            sub_manager.subtitles.insert(insert_idx, new_sub)

        result = []
        for s in sub_manager.subtitles:
            result.append({
                "id": s.id,
                "start_time": s.start_time,
                "end_time": s.end_time,
                "original_text": s.original_text,
                "translated_text": s.translated_text,
            })

        msg = "润色完成"
        if split_count > 0:
            msg += f"，{split_count} 条超字数已自动断句拆分"

        return OptimizeResponse(success=True, optimized=result, message=msg)

    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/api/translate/single", response_model=SingleTranslateResponse)
def translate_single(req: SingleTranslateRequest):
    """单句翻译"""
    if not req.text:
        raise HTTPException(400, "文本为空")

    try:
        from core.translator import TranslatorEngine
        engine = TranslatorEngine(
            api_key=req.api_key,
            base_url=req.api_base,
            model=req.model,
            engine_type=req.engine_type,
        )

        # 直接调 API 翻译单句
        response = engine.client.chat.completions.create(
            model=req.model,
            messages=[{"role": "user", "content": f"请将以下文本翻译为{req.target_lang}，无需多余解释:\n{req.text}"}],
            temperature=0.3
        )
        translated = response.choices[0].message.content.strip()

        return SingleTranslateResponse(success=True, translated_text=translated)

    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/api/export/srt")
def export_srt(req: ExportRequest):
    """导出 SRT 字幕文件"""
    try:
        sub_manager = _build_sub_manager(req.subtitles)
        get_exporter_engine().export_srt(
            sub_manager, req.output_path,
            mode=req.style_config.get("mode", "bilingual"),
            swap_order=req.style_config.get("swap_order", False),
        )
        return {"success": True, "path": req.output_path}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/api/export/ass")
def export_ass(req: ExportRequest):
    """导出 ASS 样式字幕"""
    try:
        sub_manager = _build_sub_manager(req.subtitles)
        get_exporter_engine().export_ass(sub_manager, req.output_path, req.style_config)
        return {"success": True, "path": req.output_path}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/api/export/video")
def export_video(req: ExportRequest):
    """压制硬字幕视频"""
    if not req.video_path:
        raise HTTPException(400, "需要源视频路径")
    try:
        sub_manager = _build_sub_manager(req.subtitles)
        get_exporter_engine().burn_video(req.video_path, sub_manager, req.output_path, req.style_config)
        return {"success": True, "path": req.output_path}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/api/upload")
async def upload_video(file: UploadFile = File(...)):
    """浏览器模式：上传视频到服务端 temp 目录，返回本地路径"""
    os.makedirs("temp", exist_ok=True)
    ext = os.path.splitext(file.filename or "video.mp4")[1] or ".mp4"
    save_path = f"temp/upload_{int(os.times()[4] * 1000)}{ext}"
    try:
        content = await file.read()
        with open(save_path, "wb") as f:
            f.write(content)
        return {"success": True, "path": os.path.abspath(save_path), "message": f"文件上传成功: {file.filename}"}
    except Exception as e:
        raise HTTPException(500, f"文件上传失败: {str(e)}")

def _build_sub_manager(subtitles_data: list) -> SubtitleManager:
    """从请求数据重建 SubtitleManager"""
    from core.subtitle_model import SubtitleItem
    sm = SubtitleManager()
    for s in subtitles_data:
        item = SubtitleItem(
            id=s.get("id", ""),
            start_time=s.get("start_time", 0),
            end_time=s.get("end_time", 0),
            original_text=s.get("original_text", ""),
            reference_text=s.get("reference_text", s.get("original_text", "")),
            translated_text=s.get("translated_text", ""),
        )
        sm.subtitles.append(item)
    return sm

# ================= 启动入口 =================

if __name__ == "__main__":
    import torch
    gpu_ok = False
    try:
        gpu_ok = torch.cuda.is_available()
        if gpu_ok:
            print(f"[OK] GPU: {torch.cuda.get_device_name(0)} 已就绪")
        else:
            print("[INFO] 未检测到 GPU，将使用 CPU（速度较慢）")
    except Exception as e:
        print(f"[WARN] CUDA 初始化失败 ({e})，回退到 CPU 模式")

    print(f"模型目录: {_get_models_dir()}")
    print("API 服务启动: http://127.0.0.1:8712")
    print("文档: http://127.0.0.1:8712/docs")
    uvicorn.run(app, host="127.0.0.1", port=8712)

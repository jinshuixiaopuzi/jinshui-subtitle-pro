# core/exporter.py
import os
import sys
import subprocess
import ffmpeg
from core.subtitle_model import SubtitleManager

def _get_ffmpeg_path() -> str:
    """获取 ffmpeg.exe 路径（开发/PyInstaller 通用）"""
    if getattr(sys, 'frozen', False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.join(os.path.dirname(__file__), '..')
    return os.path.abspath(os.path.join(base, 'ffmpeg.exe'))

# GPU 编码器优先级（按速度/质量综合排序）
GPU_ENCODERS = [
    ("h264_nvenc",  "NVIDIA GPU (NVENC)"),
    ("h264_amf",    "AMD GPU (AMF)"),
    ("h264_qsv",    "Intel 核显 (QSV)"),
    ("h264_vulkan", "Vulkan GPU"),
    ("h264_d3d12va","Direct3D 12 GPU"),
    ("h264_vaapi",  "VAAPI GPU"),
]

def detect_best_encoder():
    """自动检测系统支持的最佳 GPU 编码器，失败则回退到 libx264"""
    try:
        result = subprocess.run(
            [_get_ffmpeg_path(), '-encoders'],
            capture_output=True, text=True, timeout=5
        )
        available = result.stdout + result.stderr
        for codec, name in GPU_ENCODERS:
            if codec in available:
                return codec
    except:
        pass
    return "libx264"  # 回退到 CPU

class ExporterEngine:
    def __init__(self, encoder="auto"):
        if encoder == "auto":
            self.encoder = detect_best_encoder()
        else:
            self.encoder = encoder
        if self.encoder and self.encoder != "libx264":
            print(f"[Exporter] 🚀 GPU 加速已启用: {self.encoder}")
        else:
            print(f"[Exporter] 💻 使用 CPU 编码: libx264")

    def format_srt_time(self, seconds: float) -> str:
        h, m = int(seconds // 3600), int((seconds % 3600) // 60)
        s, ms = int(seconds % 60), int((seconds - int(seconds)) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    def format_ass_time(self, seconds: float) -> str:
        h, m = int(seconds // 3600), int((seconds % 3600) // 60)
        s, cs = int(seconds % 60), int((seconds - int(seconds)) * 100)
        return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

    def hex_to_ass_color(self, hex_color: str) -> str:
        """把 #RRGGBB 颜色转为 ASS 的 &HAABBGGRR 格式"""
        hex_color = hex_color.replace("#", "")
        if len(hex_color) == 6:
            r, g, b = hex_color[0:2], hex_color[2:4], hex_color[4:6]
            return f"&H00{b}{g}{r}"  
        return "&H00FFFFFF" 

    def export_srt(self, sub_manager: SubtitleManager, output_path: str, mode="bilingual", swap_order=False):
        print(f"[Exporter] 正在生成 SRT 文件: {output_path}")
        with open(output_path, 'w', encoding='utf-8') as f:
            for i, sub in enumerate(sub_manager.subtitles):
                f.write(f"{i + 1}\n")
                f.write(f"{self.format_srt_time(sub.start_time)} --> {self.format_srt_time(sub.end_time)}\n")
                if mode == "bilingual":
                    if swap_order:
                        if sub.original_text: f.write(f"{sub.original_text}\n")
                        if sub.translated_text: f.write(f"{sub.translated_text}\n")
                    else:
                        if sub.translated_text: f.write(f"{sub.translated_text}\n")
                        f.write(f"{sub.original_text}\n")
                elif mode == "original": f.write(f"{sub.original_text}\n")
                elif mode == "translated": f.write(f"{sub.translated_text}\n")
                f.write("\n")

    def export_ass(self, sub_manager: SubtitleManager, output_path: str, style_config: dict):
        print(f"[Exporter] 正在生成 ASS 文件: {output_path}")

        # 1. 核心修复：中文字体名映射表 (FFmpeg 在 Windows 下必须用英文底层名才能挂载字体)
        font_map = {
            "微软雅黑": "Microsoft YaHei", "黑体": "SimHei", "宋体": "SimSun",
            "仿宋": "FangSong", "楷体": "KaiTi", "幼圆": "YouYuan", "隶书": "LiSu"
        }

        t_font = font_map.get(style_config.get("trans_font", "微软雅黑"), style_config.get("trans_font", "微软雅黑"))
        t_size = style_config.get("trans_size", 45)
        t_color = self.hex_to_ass_color(style_config.get("trans_color", "#FFFFFF"))
        t_out_color = self.hex_to_ass_color(style_config.get("trans_outline_color", "#000000"))
        t_out_size = style_config.get("trans_outline_size", 2)

        o_font = font_map.get(style_config.get("orig_font", "微软雅黑"), style_config.get("orig_font", "微软雅黑"))
        o_size = style_config.get("orig_size", 30)
        o_color = self.hex_to_ass_color(style_config.get("orig_color", "#CCCCCC"))
        o_out_color = self.hex_to_ass_color(style_config.get("orig_outline_color", "#000000"))
        o_out_size = style_config.get("orig_outline_size", 2)

        # 独立底边距（原文/译文各自距屏幕底边的距离）
        trans_bottom_margin = style_config.get("trans_bottom_margin", 60)
        orig_bottom_margin = style_config.get("orig_bottom_margin", 10)
        swap_order = style_config.get("swap_order", False)
        mode = style_config.get("mode", "bilingual")

        # swap=false: 译文用 trans_margin, 原文用 orig_margin
        # swap=true:  译文用 orig_margin, 原文用 trans_margin
        if swap_order:
            trans_mv = orig_bottom_margin
            orig_mv = trans_bottom_margin
        else:
            trans_mv = trans_bottom_margin
            orig_mv = orig_bottom_margin

        # ASS 样式：译文(TransStyle) 和 原文(OrigStyle) 各自独立 MarginV
        ass_content = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 1

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: TransStyle,{t_font},{t_size:.0f},{t_color},&H000000FF,{t_out_color},&H00000000,1,0,0,0,100,100,0,0,1,{t_out_size},0,2,10,10,{trans_mv:.0f},1
Style: OrigStyle,{o_font},{o_size:.0f},{o_color},&H000000FF,{o_out_color},&H00000000,1,0,0,0,100,100,0,0,1,{o_out_size},0,2,10,10,{orig_mv:.0f},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

        for sub in sub_manager.subtitles:
            start = self.format_ass_time(sub.start_time)
            end = self.format_ass_time(sub.end_time)

            if mode == "trans_only":
                if sub.translated_text:
                    ass_content += f"Dialogue: 0,{start},{end},TransStyle,,0,0,0,,{sub.translated_text}\n"
            elif mode == "orig_only":
                if sub.original_text:
                    ass_content += f"Dialogue: 0,{start},{end},OrigStyle,,0,0,0,,{sub.original_text}\n"
            else:  # bilingual
                if sub.translated_text:
                    ass_content += f"Dialogue: 0,{start},{end},TransStyle,,0,0,0,,{sub.translated_text}\n"
                if sub.original_text:
                    ass_content += f"Dialogue: 0,{start},{end},OrigStyle,,0,0,0,,{sub.original_text}\n"

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(ass_content)

    def burn_video(self, video_path: str, sub_manager: SubtitleManager, output_path: str, style_config: dict):
        print("[Exporter] 正在准备硬字幕烧录...")
        
        # 将临时文件保存在项目目录下，获取绝对路径
        temp_ass_path = os.path.abspath("temp_burn.ass").replace('\\', '/')
        self.export_ass(sub_manager, temp_ass_path, style_config)

        safe_video_path = os.path.abspath(video_path).replace('\\', '/')
        safe_output_path = os.path.abspath(output_path).replace('\\', '/')
        
        # 3. 核心修复：防爆陷阱！FFmpeg 处理盘符绝对路径时，必须对冒号转义，否则滤镜直接失效
        escaped_ass_path = temp_ass_path.replace(':', '\\:')

        print(f"[Exporter] 正在压制视频...")
        try:
            (
                ffmpeg
                .input(safe_video_path)
                .output(safe_output_path, vf=f"ass='{escaped_ass_path}'", vcodec=self.encoder, acodec="copy")
                .overwrite_output()
                .run(quiet=True)
            )
            print("[Exporter] 🎉 视频硬字幕压制成功！")
        except ffmpeg.Error as e:
            print(f"[Exporter] ❌ FFmpeg 压制报错: {e.stderr.decode('utf8')}")
            raise e
        finally:
            if os.path.exists(temp_ass_path):
                os.remove(temp_ass_path)
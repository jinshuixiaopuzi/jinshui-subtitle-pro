# main_cli.py
import sys
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from core.subtitle_model import SubtitleManager
from core.audio_processor import AudioProcessor
from core.asr_engine import ASREngine
# 新增导入翻译引擎
from core.translator import TranslatorEngine 

def main():
    # ==== 配置区 ====
    video_path = "test.mp4"
    wav_path = "temp/extracted.wav"
    os.makedirs("temp", exist_ok=True)
    
    # ⚠️ 在这里填入你的 DeepSeek API Key
    DEEPSEEK_API_KEY = "sk-your-api-key-here"
    # ================

    if not os.path.exists(video_path):
        print(f"请在当前目录放一个测试用的短视频: {video_path}")
        return

    # 1. 初始化
    sub_manager = SubtitleManager()
    audio_proc = AudioProcessor()
    asr_engine = ASREngine(model_size="large-v3")
    # 初始化翻译机
    translator = TranslatorEngine(api_key=DEEPSEEK_API_KEY) 

    # 2. 跑音频提取和打轴 (刚才跑通的)
    print("\n--- 阶段 1 & 2: 音频抽取与 ASR 推理 ---")
    audio_proc.extract_audio(video_path, wav_path)
    asr_engine.process_video_to_subtitles(wav_path, sub_manager)

    # 3. 跑大模型翻译！
    print("\n--- 阶段 3: DeepSeek 语境翻译 ---")
    # 测试术语表：假设你的视频里提到了 'ComfyUI' 和 'Apple'，我们强制它怎么翻
    custom_glossary = """
    - ComfyUI -> 节点式AI绘图神器
    - Apple -> 苹果公司 (不要翻译成水果)
    """
    translator.batch_translate(sub_manager, glossary=custom_glossary)

    # 4. 打印最终结果
    print("\n--- 阶段 4: 最终的双语字幕状态 ---")
    sub_manager.debug_print()

if __name__ == "__main__":
    main()
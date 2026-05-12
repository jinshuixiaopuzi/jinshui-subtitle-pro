# core/asr_engine.py
import os
import io
import torch
import torchaudio
import concurrent.futures
from qwen_asr import Qwen3ASRModel
from core.subtitle_model import SubtitleManager

def _get_models_dir() -> str:
    """自动定位项目 models/ 目录（开发/PyInstaller 通用）"""
    import sys
    if getattr(sys, 'frozen', False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.abspath(os.path.join(base, "models"))

class ASREngine:
    def __init__(self, model_size="1.7B", models_dir=None):
        if models_dir is None:
            models_dir = _get_models_dir()
        self.asr_model_dir = os.path.join(models_dir, "Qwen3-ASR-1.7B")
        self.aligner_model_dir = os.path.join(models_dir, "Qwen3-ForcedAligner-0.6B")
        
        print(f"\n[ASREngine] 正在加载 Qwen3-ASR 双擎架构...")
        try:
            self.model = Qwen3ASRModel.from_pretrained(
                self.asr_model_dir, 
                dtype=torch.float16, 
                device_map="cuda" if torch.cuda.is_available() else "cpu",
                forced_aligner=self.aligner_model_dir,
                forced_aligner_kwargs=dict(
                    dtype=torch.float16, 
                    device_map="cuda" if torch.cuda.is_available() else "cpu"
                )
            )
            print("[ASREngine] ✅ Qwen3 加载成功！显存已锁定。")
        except Exception as e:
            print(f"[ASREngine] ❌ Qwen3 加载失败: {e}")
            raise e

        # ================= 核心防漏墙：同步挂载 VAD 物理切片引擎 =================
        print(f"[ASREngine] 同步加载 Silero-VAD 物理切片引擎...")
        self.vad_model, utils = torch.hub.load('snakers4/silero-vad', 'silero_vad', trust_repo=True)
        self.get_speech_timestamps = utils[0]
        self.read_audio = utils[2]
        print("[ASREngine] ✅ VAD 引擎备战完毕！")

    def _save_chunk_to_bytes(self, wav_tensor, start_idx, end_idx):
        """将音频块保存到内存 BytesIO，绕过磁盘 I/O"""
        chunk_tensor = wav_tensor[start_idx:end_idx].unsqueeze(0)
        buffer = io.BytesIO()
        torchaudio.save(buffer, chunk_tensor, 16000, format='wav')
        buffer.seek(0)
        return buffer

    def _parse_results(self, results, chunk_start_sec, subtitle_manager, max_chars, filler_words):
        """解析模型返回的结果并添加到字幕管理器（从主循环提取为独立方法）"""
        last_end = -1.0
        
        for r in results:
            ts_data = getattr(r, 'time_stamps', None) or (r.get('time_stamps',[]) if isinstance(r, dict) else [])
            
            parsed_words =[]
            if ts_data:
                for item in ts_data:
                    sub_items = item if isinstance(item, (list, tuple)) else [item]
                    for w in sub_items:
                        txt = getattr(w, "text", w.get("text", "") if isinstance(w, dict) else "")
                        st = getattr(w, "start_time", w.get("start", 0.0) if isinstance(w, dict) else 0.0)
                        ed = getattr(w, "end_time", w.get("end", 0.0) if isinstance(w, dict) else 0.0)
                        if txt: 
                            parsed_words.append({"text": txt, "start": st + chunk_start_sec, "end": ed + chunk_start_sec})

            segment_text = getattr(r, 'text', '') or (r.get('text', '') if isinstance(r, dict) else '')
            
            if not parsed_words and segment_text:
                print(f"  ->[兜底还原] 发现无时间戳句子: {segment_text.strip()}")
                start = last_end if last_end != -1.0 else chunk_start_sec
                end = start + len(segment_text) * 0.25 
                subtitle_manager.add_from_asr(start=start, end=end, text=segment_text.strip())
                continue
            if not parsed_words:
                continue

            if not segment_text:
                segment_text = "".join([p["text"] for p in parsed_words])

            text_idx = 0
            for w in parsed_words:
                core_word = w["text"].strip()
                pos = segment_text.find(core_word, text_idx)
                if pos != -1:
                    text_idx = pos + len(core_word)
                    punct_and_space = ""
                    while text_idx < len(segment_text):
                        char = segment_text[text_idx]
                        if char in '，。？！,?!;；、:：' or char.isspace():
                            punct_and_space += char
                            text_idx += 1
                        else:
                            break
                    w["text"] = core_word + punct_and_space

            current_text = ""
            current_start = -1.0
            last_end = -1.0

            for j in range(len(parsed_words)):
                w = parsed_words[j]
                raw_text = w["text"]
                core_text = raw_text.strip('，。？！,?!;；、:： \t\n')
                is_filler = core_text in filler_words
                do_break = False

                if is_filler:
                    if current_text.strip(): do_break = True
                else:
                    if current_start == -1.0: current_start = w["start"]
                    current_text += raw_text
                    last_end = w["end"]
                    
                    clean_text = current_text.strip()
                    cur_len = len(clean_text)
                    next_gap = parsed_words[j+1]["start"] - w["end"] if j + 1 < len(parsed_words) else 999.0
                        
                    break_major_punct = clean_text and clean_text[-1] in '。？！?!;；'
                    break_minor_punct = clean_text and clean_text[-1] in '，,、:：'
                    
                    if break_major_punct: do_break = True
                    elif cur_len >= max_chars: do_break = True
                    elif break_minor_punct and cur_len >= (max_chars * 0.4): do_break = True
                    elif next_gap > 0.8: do_break = True
                    elif next_gap > 0.3 and cur_len >= (max_chars * 0.6): do_break = True
                        
                if do_break and current_text.strip():
                    final_text = current_text.strip().rstrip('，。；：、,.;:')
                    if final_text:
                        subtitle_manager.add_from_asr(start=current_start, end=last_end, text=final_text)
                    current_text = ""
                    current_start = -1.0

            if current_text.strip():
                final_text = current_text.strip().rstrip('，。；：、,.;:')
                if final_text:
                    subtitle_manager.add_from_asr(start=current_start, end=last_end, text=final_text)

    def process_video_to_subtitles(self, audio_path: str, subtitle_manager: SubtitleManager, max_chars: int = 25):
        print(f"\n[ASREngine] 启动 VAD 物理安全切片 (防吞音机制)...")
        
        wav_tensor = self.read_audio(audio_path)
        timestamps = self.get_speech_timestamps(
            wav_tensor, 
            self.vad_model, 
            sampling_rate=16000, 
            min_silence_duration_ms=400
        )
        
        # ================= 30秒黄金打包法 =================
        merged_chunks =[]
        current_start_idx = -1
        current_end_idx = -1
        
        for ts in timestamps:
            start_idx = ts['start']
            end_idx = ts['end']
            
            if current_start_idx == -1:
                current_start_idx = start_idx
                current_end_idx = end_idx
            else:
                if (end_idx - current_start_idx) / 16000.0 > 30.0:
                    merged_chunks.append({"start": current_start_idx, "end": current_end_idx})
                    current_start_idx = start_idx
                    current_end_idx = end_idx
                else:
                    current_end_idx = end_idx
                    
        if current_start_idx != -1:
            merged_chunks.append({"start": current_start_idx, "end": current_end_idx})
            
        print(f"[ASREngine] 物理隔离优化完毕！原碎切片被打包为 {len(merged_chunks)} 个(约30秒)的黄金区块。")
        # ================================================================
        
        # ★ 使用单个可复用的临时文件路径，避免大量磁盘 I/O
        chunk_dir = "temp"
        os.makedirs(chunk_dir, exist_ok=True)
        temp_wav = os.path.join(chunk_dir, "_current_chunk.wav")
        filler_words = {"呃", "啊", "嗯", "哦", "哎", "嘶", "嗯嗯", "那个", "就是"}

        total_chunks = len(merged_chunks)
        
        # ★ 流水线并发：用 ThreadPoolExecutor 实现准备下一块和 GPU 推理重叠
        # max_workers=2：一个线程准备数据，主线程做 GPU 推理
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            # 预准备第一个块
            next_future = executor.submit(self._save_chunk_to_bytes, wav_tensor, 
                                          merged_chunks[0]['start'], merged_chunks[0]['end'])
            
            for i in range(total_chunks):
                # 获取当前块的音频数据（可能已经在后台准备好了）
                audio_buffer = next_future.result()
                
                # 启动下一块的准备（与当前 GPU 推理并行）
                if i + 1 < total_chunks:
                    next_future = executor.submit(self._save_chunk_to_bytes, wav_tensor,
                                                  merged_chunks[i+1]['start'], merged_chunks[i+1]['end'])
                
                # ★ 将内存 buffer 写入可复用的临时文件（比每个块单独建文件快得多）
                with open(temp_wav, 'wb') as f:
                    f.write(audio_buffer.read())
                
                chunk_start_sec = merged_chunks[i]['start'] / 16000.0
                print(f"  -> 正在对齐黄金区块 {i+1}/{total_chunks} (起始时间: {chunk_start_sec:.1f}s)...")
                
                # GPU 推理（CUDA 调用会自动释放 GIL，不阻塞数据准备线程）
                results = self.model.transcribe(audio=temp_wav, return_time_stamps=True)
                
                # 解析结果（纯 CPU 操作，不占显存）
                self._parse_results(results, chunk_start_sec, subtitle_manager, max_chars, filler_words)

        # 清理临时文件
        if os.path.exists(temp_wav):
            os.remove(temp_wav)
            
        print("\n[ASREngine] 🎉 Qwen3 智能打轴全部完成！")

# core/audio_processor.py
import os
import torch
import ffmpeg

class AudioProcessor:
    def __init__(self):
        print("[AudioProcessor] 正在加载 Silero VAD 静音检测模型 (极速/低显存)...")
        # 直接从 torch hub 下载/加载轻量级的 VAD 模型
        self.vad_model, utils = torch.hub.load(
            repo_or_dir='snakers4/silero-vad',
            model='silero_vad',
            force_reload=False,
            trust_repo=True
        )
        (self.get_speech_timestamps, _, self.read_audio, _, _) = utils
        self.sample_rate = 16000

    def extract_audio(self, video_path: str, output_wav_path: str):
        """调用 FFmpeg 提取 16kHz 单声道音频"""
        print(f"[AudioProcessor] 正在从视频提取标准音频: {video_path}")
        try:
            # -vn: 忽略视频, -acodec pcm_s16le: 标准WAV, -ar 16000: 采样率, -ac 1: 单声道
            (
                ffmpeg
                .input(video_path)
                .output(output_wav_path, acodec='pcm_s16le', ac=1, ar=str(self.sample_rate))
                .overwrite_output()
                .run(quiet=True) # quiet=True 屏蔽一大坨终端日志
            )
            print("[AudioProcessor] 音频提取成功！")
        except ffmpeg.Error as e:
            print(f"[AudioProcessor] FFmpeg 报错: {e.stderr.decode('utf8')}")
            raise e

    def get_audio_chunks(self, wav_path: str, max_duration: float = 15.0) -> list:
        """
        核心防爆显存逻辑：将音频按静音切分为短句列表
        返回格式:[{'start_time': 1.2, 'end_time': 5.4, 'tensor': <音频数据>}, ...]
        """
        print("[AudioProcessor] 正在进行 VAD 音频切片分析...")
        wav_tensor = self.read_audio(wav_path)
        
        # 获取所有有人说话的片段（返回的是样本帧数索引）
        speech_timestamps = self.get_speech_timestamps(
            wav_tensor, self.vad_model, sampling_rate=self.sample_rate
        )
        
        chunks =[]
        for ts in speech_timestamps:
            start_sec = ts['start'] / self.sample_rate
            end_sec = ts['end'] / self.sample_rate
            
            # TODO: 如果某个单句依然超过 max_duration (比如有人一口气说了30秒)，
            # 这里还可以做更细的强行截断，但目前 VAD 的默认打断已经够用了。
            
            chunk_data = {
                "start_time": start_sec,
                "end_time": end_sec,
                "tensor": wav_tensor[ts['start']: ts['end']] # 切片取音频张量
            }
            chunks.append(chunk_data)
            
        print(f"[AudioProcessor] 切片完成！共切分出 {len(chunks)} 个短音频块。")
        return chunks
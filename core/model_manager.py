# core/model_manager.py
"""金水字幕 - 模型自动下载/检查系统"""
import os
import sys
import json
import urllib.request
import zipfile
import shutil
import hashlib
from pathlib import Path

# 模型配置：名称 → 下载信息
MODELS_CONFIG = {
    "Qwen3-ASR-1.7B": {
        "url": "https://modelscope.cn/models/Qwen/Qwen3-ASR-1.7B/resolve/main/model.safetensors",
        "size_gb": 3.5,
        "files": ["config.json", "model.safetensors", "tokenizer.json"],
    },
    "Qwen3-ForcedAligner-0.6B": {
        "url": "https://modelscope.cn/models/Qwen/Qwen3-ForcedAligner-0.6B/resolve/main/model.safetensors",
        "size_gb": 1.2,
        "files": ["config.json", "model.safetensors"],
    }
}

def get_models_dir() -> str:
    """获取模型目录（保证在程序所在磁盘）"""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    models_dir = os.path.join(base_dir, "models")
    os.makedirs(models_dir, exist_ok=True)
    return models_dir

def check_models_status() -> dict:
    """检查各模型是否存在，返回状态字典"""
    models_dir = get_models_dir()
    status = {}
    for name in MODELS_CONFIG:
        model_path = os.path.join(models_dir, name)
        exists = os.path.exists(model_path) and any(
            os.path.exists(os.path.join(model_path, f)) 
            for f in MODELS_CONFIG[name]["files"]
        )
        status[name] = {
            "exists": exists,
            "path": model_path,
            **MODELS_CONFIG[name]
        }
    return status

def all_models_ready() -> bool:
    """检查是否所有模型都已就绪"""
    status = check_models_status()
    return all(s["exists"] for s in status.values())

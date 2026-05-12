# core/license_manager.py
"""金水字幕 - 激活码验证系统"""
import os
import hashlib

LICENSE_FILE = "license.key"
VALID_CODE_HASH = hashlib.sha256("B站：金水1987".encode()).hexdigest()

def _hash_input(code: str) -> str:
    return hashlib.sha256(code.strip().encode()).hexdigest()

def check_license() -> bool:
    """检查是否已激活"""
    if os.path.exists(LICENSE_FILE):
        with open(LICENSE_FILE, 'r', encoding='utf-8') as f:
            stored = f.read().strip()
        return stored == VALID_CODE_HASH
    return False

def activate(code: str) -> bool:
    """验证激活码并保存"""
    if _hash_input(code) == VALID_CODE_HASH:
        with open(LICENSE_FILE, 'w', encoding='utf-8') as f:
            f.write(VALID_CODE_HASH)
        return True
    return False

def get_activation_code() -> str:
    """返回预期的激活码提示"""
    return "B站：金水1987"

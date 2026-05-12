# -*- mode: python ; coding: utf-8 -*-
"""
金水字幕 Pro — PyInstaller 打包配置
目标: 将 api_server.py 打包为 engine.exe (onedir 模式)
"""

import os
import sys
from PyInstaller.utils.hooks import collect_submodules, collect_data_files, collect_dynamic_libs
from PyInstaller.building.datastruct import TOC

project_root = os.path.dirname(os.path.abspath(SPEC))
# 注: SPEC 是 PyInstaller 内置变量，指向当前 .spec 文件的绝对路径

# =================== 收集 nagisa 数据文件 (字典/模型) ===================
nagisa_datas = collect_data_files('nagisa')

# =================== 收集 qwen_asr 子模块 ===================
# 注意: qwen_asr 的子目录使用命名空间包 (无 __init__.py)
# collect_submodules 无法遍历，需手动列出所有模块
qwen_asr_extra = [
    'qwen_asr.cli.demo', 'qwen_asr.cli.demo_streaming', 'qwen_asr.cli.serve',
    'qwen_asr.core.transformers_backend',
    'qwen_asr.core.transformers_backend.configuration_qwen3_asr',
    'qwen_asr.core.transformers_backend.modeling_qwen3_asr',
    'qwen_asr.core.transformers_backend.processing_qwen3_asr',
    'qwen_asr.core.vllm_backend', 'qwen_asr.core.vllm_backend.qwen3_asr',
    'qwen_asr.inference.qwen3_asr', 'qwen_asr.inference.qwen3_forced_aligner',
    'qwen_asr.inference.utils',
]

# =================== 数据文件 ===================
# 注意: models/ 不打包进 PyInstaller（CArchive 有 4GB 限制）
# 模型作为独立目录与 engine.exe 同级发布
datas = [
    (os.path.join(project_root, 'ffmpeg.exe'), '.'),        # FFmpeg 二进制
]
datas.extend(nagisa_datas)

# 收集 qwen_asr 数据文件 (字典等)
qwen_asr_datas = collect_data_files('qwen_asr')
datas.extend(qwen_asr_datas)

# =================== 隐藏导入 ===================
hiddenimports = []
hiddenimports.extend(qwen_asr_extra)
hiddenimports.extend([
    # ASR 引擎
    'qwen_asr', 'qwen_asr.core', 'qwen_asr.inference', 'qwen_asr.cli',
    # PyTorch
    'torch', 'torchaudio', 'torchvision',
    'torch.utils.tensorboard',
    # Transformers (qwen_asr 依赖)
    'transformers', 'transformers.models.qwen2',
    # 音频处理
    'soundfile', 'audioread', 'librosa',
    # Web 框架
    'uvicorn', 'uvicorn.loops', 'uvicorn.loops.auto',
    'uvicorn.protocols', 'uvicorn.protocols.http',
    'fastapi', 'starlette',
    'pydantic', 'pydantic.deprecated',
    # HTTP / API
    'openai', 'httpx', 'httpcore',
    'aiohttp', 'aiofiles',
    # 翻译引擎
    'deep_translator', 'translators',
    # 视频处理
    'ffmpeg', 'ffmpeg.run',
    # GUI (main_gui.py 依赖)
    'PySide6', 'PySide6.QtCore', 'PySide6.QtGui', 'PySide6.QtWidgets',
    'qfluentwidgets', 'qfluentwidgets.components',
    # 其他
    'tqdm', 'regex', 'yaml', 'json5',
    'PIL', 'PIL.Image',
    'scipy', 'numpy',
    'jinja2', 'anyio',
    # Silero VAD (torch.hub.load)
    'torch.hub',
    # PyTorch 深层导入依赖 (PyInstaller 可能遗漏)
    'unittest', 'unittest.mock',
    'torch.testing', 'torch._dispatch',
    'torch.fx', 'torch.fx.passes',
    'torch.export',
    # nagisa 子模块 (qwen_asr 依赖，使用了隐式相对导入)
    'nagisa', 'nagisa.tagger', 'nagisa.train',
    'nagisa.model', 'nagisa.prepro', 'nagisa.mecab_system_eval',
    'nagisa_utils',  # nagisa 的 C 扩展
    # DyNet (nagisa 依赖)
    'dynet', 'dynet_config', '_dynet',
])

# =================== 排除项 (减小体积) ===================
exclude_modules = [
    'tkinter', '_tkinter',
    'IPython', 'ipykernel', 'jupyter',
    'matplotlib', 'pylab',
    'pandas', 'pandas.tests',
    'notebook', 'nbformat',
    'sphinx', 'docutils',
    'pytest', 'nose',
    'setuptools', 'pip', 'wheel',
    'distutils',
    'sqlite3', 'sqlalchemy',
    'wx', 'gtk', 'curses',
    # 'test' 和 'tests' 不排除——PyTorch/torch.testing 需要它们
    'PyQt5', 'PyQt6',  # 只用 PySide6
]

# =================== PyInstaller Analysis ===================
a = Analysis(
    ['api_server.py'],
    pathex=[project_root],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=exclude_modules,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,  # 不加密 (超大文件加密会显著增加构建时间)
    noarchive=False,
)

# =================== Nuitka Hybrid: .pyd 替代 .pyc ===================
# 核心模块已用 Nuitka 编译为 .pyd (机器码)，PyInstaller 不再将其冻结为 .pyc
# 实现: 从 a.pure 中移除 core.* 模块，将 .pyd 文件添加到 binaries
core_modules = [name for name, _, _ in a.pure if name.startswith('core.')]
if core_modules:
    print(f"[Nuitka] 检测到 {len(core_modules)} 个 core.* 模块，将使用 .pyd 替代 .pyc:")
    for m in core_modules:
        print(f"  - {m} -> .pyd")

# 过滤 pure (移除 core.* 模块，避免 PyInstaller 冻结为 .pyc)
_filtered_pure = TOC([(n, p, t) for n, p, t in a.pure if not n.startswith('core.')])
a.pure = _filtered_pure  # 同步更新，确保一致性

# 收集 core/ 目录下的 .pyd 文件并添加到 binaries
import glob as _glob
core_pyd_files = _glob.glob(os.path.join(project_root, 'core', '*.pyd'))
_nuitka_pyd_binaries = []
for pyd_path in core_pyd_files:
    pyd_name = os.path.basename(pyd_path)
    mod_name = 'core.' + pyd_name.replace('.cp311-win_amd64.pyd', '').replace('.pyd', '')
    dest = os.path.join('core', pyd_name)
    _nuitka_pyd_binaries.append((dest, pyd_path, 'EXTENSION'))
    print(f"  [Nuitka] 添加二进制: {pyd_path} -> {dest}")

pyz = PYZ(_filtered_pure, a.zipped_data, cipher=None)

# 将所有二进制/数据文件从 CArchive 移到 _internal/ (避免 2.5GB+ CArchive 解压损坏)
# EXE 步骤只包含 pyz + scripts，大文件在 COLLECT 步骤加入 _internal/
_exe_binaries = a.binaries.copy()
_exe_datas = a.datas.copy()
# 将 Nuitka .pyd 文件合并到 _exe_binaries
_exe_binaries.extend(_nuitka_pyd_binaries)
a.binaries = TOC([])
a.datas = TOC([])

# =================== EXE ===================
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='engine',
    icon=os.path.join(project_root, 'jinshui.ico'),
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,           # 保留符号 (避免破坏 ctypes/C 扩展)
    upx=False,             # UPX 压缩大 DLL 可能导致反病毒误报
    console=True,          # 保留控制台输出 (方便调试)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

# =================== 收集输出目录 ===================
coll = COLLECT(
    exe,
    _exe_binaries,
    a.zipfiles,
    _exe_datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='engine',
)

# main_gui.py
"""金水字幕 Pro - 商业版启动入口 (qfluentwidgets 重构版)"""
import sys
import os

# 环境变量防坑
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from qfluentwidgets import setTheme, Theme

def main():
    # 创建应用
    app = QApplication(sys.argv)
    app.setApplicationName("金水字幕 Pro")
    app.setOrganizationName("金水1987")

    # 全局字体
    font = app.font()
    font.setPointSize(10)
    app.setFont(font)

    # ===== 强制深色模式 =====
    setTheme(Theme.DARK)

    # ===== 第一步：激活验证 =====
    from gui.activation_dialog import ActivationDialog
    activation = ActivationDialog()
    if activation.exec() != ActivationDialog.Accepted:
        sys.exit(0)

    # ===== 第二步：模型检查 =====
    from core.model_manager import all_models_ready
    if not all_models_ready():
        from gui.download_dialog import DownloadDialog
        download = DownloadDialog()
        if download.exec() != DownloadDialog.Accepted:
            sys.exit(0)

    # ===== 第三步：启动主界面 =====
    from gui.main_window import AutoCaptionWindow
    window = AutoCaptionWindow()
    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()

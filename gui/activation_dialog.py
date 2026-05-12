# gui/activation_dialog.py
"""金水字幕 - 激活对话框（暗紫色主题）"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QPushButton, QMessageBox, QWidget
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QFont, QPixmap, QPainter, QColor, QBrush, QLinearGradient

from core.license_manager import activate, check_license, get_activation_code

# 暗紫色主题样式
STYLE = """
QDialog {
    background-color: #1A1A2E;
}
QLabel {
    color: #E0E0E0;
    font-size: 14px;
}
QLineEdit {
    background-color: #16213E;
    color: #FFFFFF;
    border: 2px solid #6A0DAD;
    border-radius: 8px;
    padding: 12px 16px;
    font-size: 16px;
    min-height: 40px;
}
QLineEdit:focus {
    border-color: #8B5CF6;
    background-color: #1A1A3E;
}
QPushButton {
    background-color: #6A0DAD;
    color: white;
    border: none;
    border-radius: 8px;
    padding: 12px 32px;
    font-size: 16px;
    font-weight: bold;
    min-height: 40px;
}
QPushButton:hover {
    background-color: #8B5CF6;
}
QPushButton:pressed {
    background-color: #4A0D8D;
}
"""

class ActivationDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("金水字幕 - 激活")
        self.setFixedSize(480, 360)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setStyleSheet(STYLE)
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        
        # 主布局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(15)
        
        # 标题
        title = QLabel("金水字幕 Pro")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 28px; font-weight: bold; color: #8B5CF6;")
        layout.addWidget(title)
        
        subtitle = QLabel("请输入激活码以继续使用")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("font-size: 13px; color: #888;")
        layout.addWidget(subtitle)
        
        layout.addSpacing(10)
        
        # 激活码输入
        self.input_code = QLineEdit()
        self.input_code.setPlaceholderText("请输入激活码...")
        self.input_code.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.input_code)
        
        # 提示标签
        hint = QLabel(f'💡 激活码获取：B站搜索"金水1987"')
        hint.setAlignment(Qt.AlignCenter)
        hint.setStyleSheet("font-size: 12px; color: #9CA3AF;")
        layout.addWidget(hint)
        
        layout.addSpacing(5)
        
        # 激活按钮
        btn_activate = QPushButton("✨ 激 活")
        btn_activate.clicked.connect(self.try_activate)
        btn_activate.setCursor(Qt.PointingHandCursor)
        layout.addWidget(btn_activate)
        
        # 状态标签
        self.label_status = QLabel("")
        self.label_status.setAlignment(Qt.AlignCenter)
        self.label_status.setStyleSheet("font-size: 13px; color: #EF4444;")
        layout.addWidget(self.label_status)
        
        layout.addStretch()
        
        # 回车键触发激活
        self.input_code.returnPressed.connect(self.try_activate)
        
        # 如果已经激活（有 license.key），直接接受
        if check_license():
            self.accept()
    
    def paintEvent(self, event):
        """绘制渐变背景"""
        painter = QPainter(self)
        gradient = QLinearGradient(0, 0, self.width(), self.height())
        gradient.setColorAt(0, QColor("#1A1A2E"))
        gradient.setColorAt(1, QColor("#16213E"))
        painter.fillRect(self.rect(), QBrush(gradient))
    
    def try_activate(self):
        code = self.input_code.text().strip()
        if not code:
            self.label_status.setText("⚠️ 请输入激活码")
            return
        
        if activate(code):
            self.label_status.setStyleSheet("font-size: 14px; color: #22C55E; font-weight: bold;")
            self.label_status.setText("✅ 激活成功！欢迎使用金水字幕 Pro")
            self.input_code.setEnabled(False)
            # 延迟关闭
            from PySide6.QtCore import QTimer
            QTimer.singleShot(800, self.accept)
        else:
            self.label_status.setText("❌ 激活码错误，请确认后重试")
            self.input_code.clear()
            self.input_code.setFocus()

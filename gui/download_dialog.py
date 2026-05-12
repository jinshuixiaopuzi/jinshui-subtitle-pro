# gui/download_dialog.py
"""金水字幕 - 模型下载对话框"""
import os
import threading
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QProgressBar, QMessageBox
)
from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtGui import QPainter, QColor, QBrush, QLinearGradient

from core.model_manager import check_models_status, get_models_dir

STYLE = """
QDialog {
    background-color: #1A1A2E;
}
QLabel {
    color: #E0E0E0;
    font-size: 13px;
}
QProgressBar {
    background-color: #16213E;
    border: 1px solid #6A0DAD;
    border-radius: 6px;
    text-align: center;
    color: white;
    min-height: 24px;
}
QProgressBar::chunk {
    background-color: #6A0DAD;
    border-radius: 5px;
}
QPushButton {
    background-color: #6A0DAD;
    color: white;
    border: none;
    border-radius: 8px;
    padding: 10px 24px;
    font-size: 14px;
    font-weight: bold;
}
QPushButton:hover {
    background-color: #8B5CF6;
}
QPushButton:disabled {
    background-color: #333;
    color: #666;
}
"""

class DownloadWorker(QThread):
    progress = Signal(int, str)  # percent, status_text
    finished = Signal()
    error = Signal(str)
    
    def __init__(self, model_name, source_dir):
        super().__init__()
        self.model_name = model_name
        self.source_dir = source_dir
    
    def run(self):
        try:
            import shutil
            target_dir = os.path.join(get_models_dir(), self.model_name)
            os.makedirs(target_dir, exist_ok=True)
            
            # 复制模型文件
            source_path = os.path.join(self.source_dir, self.model_name)
            if not os.path.exists(source_path):
                self.error.emit(f"未找到模型目录：{source_path}\n请将模型放在：{source_path}")
                return
            
            all_files = []
            for root, dirs, files in os.walk(source_path):
                for f in files:
                    src = os.path.join(root, f)
                    rel = os.path.relpath(src, source_path)
                    all_files.append((src, rel))
            
            for i, (src, rel) in enumerate(all_files):
                dst = os.path.join(target_dir, rel)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(src, dst)
                pct = int((i + 1) / len(all_files) * 100)
                self.progress.emit(pct, f"正在复制 {self.model_name} - {rel}")
            
            self.progress.emit(100, f"✅ {self.model_name} 就绪")
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))

class DownloadDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("金水字幕 - 模型准备")
        self.setFixedSize(520, 380)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setStyleSheet(STYLE)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 25, 30, 25)
        layout.setSpacing(12)
        
        # 标题
        title = QLabel("📦 模型部署")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #8B5CF6;")
        layout.addWidget(title)
        
        desc = QLabel("首次使用需要部署 AI 模型文件")
        desc.setAlignment(Qt.AlignCenter)
        desc.setStyleSheet("font-size: 13px; color: #9CA3AF;")
        layout.addWidget(desc)
        
        layout.addSpacing(10)
        
        # 模型状态列表
        self.labels = {}
        status = check_models_status()
        for name, info in status.items():
            row = QHBoxLayout()
            lbl_name = QLabel(f"  {name}")
            lbl_name.setStyleSheet("font-size: 13px; color: #E0E0E0;")
            lbl_status = QLabel("⏳ 待部署" if not info["exists"] else "✅ 已就绪")
            lbl_status.setStyleSheet(
                "font-size: 13px; color: #F59E0B;" if not info["exists"]
                else "font-size: 13px; color: #22C55E;"
            )
            row.addWidget(lbl_name)
            row.addStretch()
            row.addWidget(lbl_status)
            self.labels[name] = {"status": lbl_status, "ready": info["exists"]}
            layout.addLayout(row)
        
        layout.addSpacing(5)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # 状态文本
        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("font-size: 12px; color: #9CA3AF;")
        layout.addWidget(self.status_label)
        
        layout.addSpacing(10)
        
        # 按钮区域
        btn_layout = QHBoxLayout()
        
        self.btn_auto = QPushButton("📥 自动部署（从计算机查找）")
        self.btn_auto.clicked.connect(self.auto_deploy)
        btn_layout.addWidget(self.btn_auto)
        
        self.btn_manual = QPushButton("📂 手动选择模型目录")
        self.btn_manual.clicked.connect(self.manual_select)
        btn_layout.addWidget(self.btn_manual)
        
        layout.addLayout(btn_layout)
        
        self.btn_continue = QPushButton("🚀 进入程序")
        self.btn_continue.setEnabled(all(v["ready"] for v in self.labels.values()))
        self.btn_continue.clicked.connect(self.accept)
        layout.addWidget(self.btn_continue)
        
        layout.addStretch()
        
        self.active_workers = 0
    
    def paintEvent(self, event):
        painter = QPainter(self)
        gradient = QLinearGradient(0, 0, self.width(), self.height())
        gradient.setColorAt(0, QColor("#1A1A2E"))
        gradient.setColorAt(1, QColor("#16213E"))
        painter.fillRect(self.rect(), QBrush(gradient))
        painter.setPen(QColor("#6A0DAD"))
        painter.drawLine(40, 58, self.width()-40, 58)
    
    def auto_deploy(self):
        """自动从常见位置查找模型"""
        from PySide6.QtWidgets import QFileDialog
        
        QMessageBox.information(self, "自动部署", 
            "请选择包含模型文件夹的父目录\n\n"
            "例如选择包含以下文件夹的目录：\n"
            "  - Qwen3-ASR-1.7B/\n"
            "  - Qwen3-ForcedAligner-0.6B/")
        
        dir_path = QFileDialog.getExistingDirectory(self, "选择模型所在目录")
        if not dir_path:
            return
        
        self.start_deploy_all(dir_path)
    
    def manual_select(self):
        """手动选择每个模型的目录"""
        from PySide6.QtWidgets import QFileDialog
        
        for name in self.labels:
            if self.labels[name]["ready"]:
                continue
            dir_path = QFileDialog.getExistingDirectory(self, f"请选择 {name} 模型文件夹")
            if dir_path:
                self.start_single_deploy(name, os.path.dirname(dir_path))
    
    def start_deploy_all(self, source_dir):
        """部署所有缺失的模型"""
        for name in self.labels:
            if not self.labels[name]["ready"]:
                self.start_single_deploy(name, source_dir)
    
    def start_single_deploy(self, name, source_dir):
        self.progress_bar.setVisible(True)
        self.btn_auto.setEnabled(False)
        self.btn_manual.setEnabled(False)
        
        worker = DownloadWorker(name, source_dir)
        worker.progress.connect(lambda p, s: self.update_progress(p, s))
        worker.finished.connect(lambda: self.on_model_done(name))
        worker.error.connect(self.on_error)
        worker.start()
        self.active_workers += 1
    
    def update_progress(self, pct, text):
        self.progress_bar.setValue(pct)
        self.status_label.setText(text)
    
    def on_model_done(self, name):
        self.labels[name]["status"].setText("✅ 已就绪")
        self.labels[name]["status"].setStyleSheet("font-size: 13px; color: #22C55E;")
        self.labels[name]["ready"] = True
        self.active_workers -= 1
        
        if self.active_workers <= 0:
            self.progress_bar.setVisible(False)
            self.status_label.setText("✅ 所有模型已就绪")
            self.btn_continue.setEnabled(True)
            self.btn_auto.setEnabled(True)
            self.btn_manual.setEnabled(True)
    
    def on_error(self, msg):
        QMessageBox.critical(self, "部署错误", msg)
        self.active_workers -= 1
        if self.active_workers <= 0:
            self.btn_auto.setEnabled(True)
            self.btn_manual.setEnabled(True)

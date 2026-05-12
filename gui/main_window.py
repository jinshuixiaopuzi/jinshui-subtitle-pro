# gui/main_window.py — qfluentwidgets 重构版（V 层仅改 UI，业务逻辑完全不动）
import os
import json
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QHeaderView,
    QLabel, QMessageBox, QFileDialog, QInputDialog, QDialog,
    QAbstractItemView, QSplitter, QFormLayout, QSizePolicy
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QPainter, QPainterPath, QPen, QColor, QPixmap, QFont, QFontMetrics, QIcon
from PySide6.QtCore import QSize

from qfluentwidgets import (
    PushButton, LineEdit, TextEdit, ComboBox, SpinBox,
    TableWidget, ListWidget, CardWidget, SettingCardGroup,
    TransparentToolButton, setTheme, Theme, FluentIcon,
    ProgressBar
)
from qfluentwidgets.components.material.acrylic_widget import AcrylicWidget

from core.subtitle_model import SubtitleManager

CONFIG_FILE = "settings.json"

# ================= 后台多线程任务区 —— 完全不动 =================
class ASRWorker(QThread):
    finished_signal = Signal()
    error_signal = Signal(str)

    def __init__(self, video_path, sub_manager, max_chars):
        super().__init__()
        self.video_path = video_path
        self.sub_manager = sub_manager
        self.max_chars = max_chars

    def run(self):
        try:
            from core.audio_processor import AudioProcessor
            from core.asr_engine import ASREngine
            wav_path = "temp/extracted.wav"
            os.makedirs("temp", exist_ok=True)
            AudioProcessor().extract_audio(self.video_path, wav_path)
            ASREngine(model_size="large-v3").process_video_to_subtitles(wav_path, self.sub_manager, max_chars=self.max_chars)
            self.finished_signal.emit()
        except Exception as e:
            self.error_signal.emit(str(e))

class TranslateWorker(QThread):
    finished_signal = Signal()
    error_signal = Signal(str)

    def __init__(self, api_key, base_url, model_name, glossary, engine_type, target_lang, sub_manager):
        super().__init__()
        self.api_key = api_key
        self.base_url = base_url
        self.model_name = model_name
        self.glossary = glossary
        self.engine_type = engine_type
        self.target_lang = target_lang
        self.sub_manager = sub_manager

    def run(self):
        try:
            from core.translator import TranslatorEngine
            engine = TranslatorEngine(self.api_key, self.base_url, self.model_name, self.engine_type)
            engine.batch_translate(self.sub_manager, glossary=self.glossary, target_lang=self.target_lang)
            self.finished_signal.emit()
        except Exception as e:
            self.error_signal.emit(str(e))

class OptimizeWorker(QThread):
    finished_signal = Signal()
    error_signal = Signal(str)

    def __init__(self, api_key, base_url, model_name, glossary, engine_type, sub_manager):
        super().__init__()
        self.api_key = api_key
        self.base_url = base_url
        self.model_name = model_name
        self.glossary = glossary
        self.engine_type = engine_type
        self.sub_manager = sub_manager

    def run(self):
        try:
            from core.translator import TranslatorEngine
            engine = TranslatorEngine(self.api_key, self.base_url, self.model_name, self.engine_type)
            engine.batch_optimize(self.sub_manager, glossary=self.glossary)
            self.finished_signal.emit()
        except Exception as e:
            self.error_signal.emit(str(e))

class ExportWorker(QThread):
    finished_signal = Signal(str)
    error_signal = Signal(str)

    def __init__(self, mode, video_path, sub_manager, out_path, style_cfg):
        super().__init__()
        self.mode = mode
        self.video_path = video_path
        self.sub_manager = sub_manager
        self.out_path = out_path
        self.style_cfg = style_cfg

    def run(self):
        try:
            from core.exporter import ExporterEngine
            engine = ExporterEngine()
            if self.mode == 'srt':
                engine.export_srt(self.sub_manager, self.out_path, mode="bilingual")
                self.finished_signal.emit("SRT 字幕导出成功！")
            elif self.mode == 'ass':
                engine.export_ass(self.sub_manager, self.out_path, self.style_cfg)
                self.finished_signal.emit("ASS 样式字幕导出成功！")
            elif self.mode == 'video':
                engine.burn_video(self.video_path, self.sub_manager, self.out_path, self.style_cfg)
                self.finished_signal.emit("视频硬字幕压制成功！")
        except Exception as e:
            self.error_signal.emit(str(e))


# ================= 真实像素级预览渲染器 —— 仅替换 PySide6 → PyQt5 =================
class SubtitlePreviewWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.bg_pixmap = None
        self.cfg = {}
        self.mode_idx = 0
        self.base_res_y = 1080.0

    def set_background(self, img_path):
        if img_path and os.path.exists(img_path):
            self.bg_pixmap = QPixmap(img_path)
            w, h = self.bg_pixmap.width(), self.bg_pixmap.height()
            ratio = w / h
            new_h = 300
            new_w = int(new_h * ratio)
            new_w = max(150, min(new_w, 600))
            self.setFixedSize(new_w, new_h)
        else:
            self.bg_pixmap = None
            self.setFixedSize(480, 270)
        self.update()

    def update_styles(self, config, mode_idx):
        self.cfg = config
        self.mode_idx = mode_idx
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)

        if self.bg_pixmap and not self.bg_pixmap.isNull():
            scaled_bg = self.bg_pixmap.scaled(self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            x = (scaled_bg.width() - self.width()) // 2
            y = (scaled_bg.height() - self.height()) // 2
            painter.drawPixmap(0, 0, scaled_bg, x, y, self.width(), self.height())
        else:
            painter.fillRect(self.rect(), QColor("#111111"))

        scale = self.height() / self.base_res_y

        def draw_text(text, prefix):
            cfg_size = self.cfg.get(f"{prefix}_size", 45)
            cfg_out = self.cfg.get(f"{prefix}_outline_size", 2)
            cfg_margin = self.cfg.get(f"{prefix}_margin", 60)
            real_size = max(1, int(cfg_size * scale))
            font = QFont(self.cfg.get(f"{prefix}_font", "微软雅黑"), real_size, QFont.Bold)
            font.setPixelSize(real_size)
            metrics = QFontMetrics(font)
            text_width = metrics.horizontalAdvance(text)
            x = (self.width() - text_width) / 2
            y = self.height() - int(cfg_margin * scale)
            path = QPainterPath()
            path.addText(x, y, font, text)
            real_out = int(cfg_out * scale)
            if real_out > 0:
                pen = QPen(QColor(self.cfg.get(f"{prefix}_outline_color", "#000000")), real_out * 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
                painter.setPen(pen)
                painter.drawPath(path)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(self.cfg.get(f"{prefix}_color", "#FFFFFF")))
            painter.drawPath(path)

        if self.mode_idx in [0, 2]:
            draw_text("你无敌的中文真实描边测试效果", "orig")
        if self.mode_idx in [0, 1]:
            draw_text("Your amazing English subtitles", "trans")


# ================= 样式设置弹窗 —— 仅替换控件 =================
class StyleConfigDialog(QDialog):
    def __init__(self, current_settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🎨 字幕样式与排版设置")
        self.resize(800, 600)
        self.settings = current_settings
        self.init_ui()

    def init_ui(self):
        main_layout = QHBoxLayout(self)
        left_layout = QVBoxLayout()
        right_layout = QVBoxLayout()

        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("展示模式:"))
        self.combo_mode = ComboBox()
        self.combo_mode.addItems(["双语展现", "仅译文", "仅原文"])
        mode_map = {"bilingual": 0, "trans_only": 1, "orig_only": 2}
        self.combo_mode.setCurrentIndex(mode_map.get(self.settings.get("mode", "bilingual"), 0))
        mode_layout.addWidget(self.combo_mode)
        left_layout.addLayout(mode_layout)

        from PySide6.QtGui import QFontDatabase
        sys_fonts = QFontDatabase.families()

        def create_style_group(title, prefix):
            group = CardWidget()
            form = QFormLayout()
            form.addRow(QLabel(f"<b>{title}</b>"))
            cb_font = ComboBox()
            cb_font.addItems(sys_fonts)
            cb_font.setCurrentText(self.settings.get(f"{prefix}_font", "微软雅黑"))
            sp_size = SpinBox()
            sp_size.setRange(10, 150)
            sp_size.setValue(self.settings.get(f"{prefix}_size", 45 if prefix == "trans" else 30))
            from PySide6.QtWidgets import QPushButton, QColorDialog as QCD
            btn_color = QPushButton(self.settings.get(f"{prefix}_color", "#FFFFFF" if prefix == "trans" else "#CCCCCC"))
            btn_color.setStyleSheet(f"background-color: {btn_color.text()}; color: {'#000' if btn_color.text() == '#FFFFFF' else '#FFF'};")
            btn_color.clicked.connect(lambda: self.pick_color(btn_color))
            btn_out_color = QPushButton(self.settings.get(f"{prefix}_outline_color", "#000000"))
            btn_out_color.setStyleSheet(f"background-color: {btn_out_color.text()}; color: {'#000' if btn_out_color.text() == '#FFFFFF' else '#FFF'};")
            btn_out_color.clicked.connect(lambda: self.pick_color(btn_out_color))
            sp_outline = SpinBox()
            sp_outline.setRange(0, 20)
            sp_outline.setValue(self.settings.get(f"{prefix}_outline_size", 2))
            sp_margin = SpinBox()
            sp_margin.setRange(0, 500)
            sp_margin.setValue(self.settings.get(f"{prefix}_margin", 60 if prefix == "trans" else 20))
            form.addRow("字体:", cb_font)
            form.addRow("字号:", sp_size)
            form.addRow("主色:", btn_color)
            form.addRow("描边色:", btn_out_color)
            form.addRow("描边粗细:", sp_outline)
            form.addRow("底距(Y轴):", sp_margin)
            group.setLayout(form)
            for widget in [cb_font, sp_size, sp_margin, sp_outline]:
                if hasattr(widget, "valueChanged"):
                    widget.valueChanged.connect(self.update_preview)
                else:
                    widget.currentTextChanged.connect(self.update_preview)
            return group, cb_font, sp_size, btn_color, btn_out_color, sp_outline, sp_margin

        self.grp_trans, self.t_font, self.t_size, self.t_color, self.t_out_color, self.t_out_size, self.t_margin = create_style_group("✨ 译文 (主)", "trans")
        self.grp_orig, self.o_font, self.o_size, self.o_color, self.o_out_color, self.o_out_size, self.o_margin = create_style_group("📝 原文 (副)", "orig")

        left_layout.addWidget(self.grp_trans)
        btn_swap = PushButton("↕️ 一键互换主副字幕位置")
        btn_swap.clicked.connect(self.action_swap_margin)
        left_layout.addWidget(btn_swap)
        left_layout.addWidget(self.grp_orig)

        btn_save = PushButton("💾 保存样式并应用")
        btn_save.clicked.connect(self.save_and_close)
        left_layout.addWidget(btn_save)

        right_layout.addWidget(QLabel("<b>画面预览 (模拟 16:9)</b>"))
        btn_pick_bg = PushButton("🖼️ 选择视频截图作为预览底图")
        btn_pick_bg.clicked.connect(self.action_pick_bg)
        right_layout.addWidget(btn_pick_bg)

        self.preview_frame = SubtitlePreviewWidget()
        self.preview_frame.setFixedSize(480, 270)
        self.preview_frame.set_background(self.settings.get("preview_bg", ""))
        right_layout.addWidget(self.preview_frame)
        right_layout.addStretch()

        main_layout.addLayout(left_layout)
        main_layout.addLayout(right_layout)
        self.combo_mode.currentIndexChanged.connect(self.update_preview)
        self.update_preview()

    def action_pick_bg(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "选择预览背景图", "", "图片 (*.png *.jpg *.jpeg)")
        if file_path:
            self.settings["preview_bg"] = file_path
            self.preview_frame.set_background(file_path)

    def action_swap_margin(self):
        temp = self.t_margin.value()
        self.t_margin.setValue(self.o_margin.value())
        self.o_margin.setValue(temp)

    def pick_color(self, btn):
        from PySide6.QtWidgets import QColorDialog
        color = QColorDialog.getColor()
        if color.isValid():
            hex_color = color.name().upper()
            btn.setText(hex_color)
            btn.setStyleSheet(f"background-color: {hex_color}; color: {'#000' if hex_color == '#FFFFFF' else '#FFF'};")
            self.update_preview()

    def update_preview(self):
        cfg = {
            "trans_font": self.t_font.currentText(), "trans_size": self.t_size.value(),
            "trans_color": self.t_color.text(), "trans_margin": self.t_margin.value(),
            "trans_outline_color": self.t_out_color.text(), "trans_outline_size": self.t_out_size.value(),
            "orig_font": self.o_font.currentText(), "orig_size": self.o_size.value(),
            "orig_color": self.o_color.text(), "orig_margin": self.o_margin.value(),
            "orig_outline_color": self.o_out_color.text(), "orig_outline_size": self.o_out_size.value(),
        }
        self.preview_frame.update_styles(cfg, self.combo_mode.currentIndex())

    def save_and_close(self):
        modes = ["bilingual", "trans_only", "orig_only"]
        self.settings.update({
            "mode": modes[self.combo_mode.currentIndex()],
            "trans_font": self.t_font.currentText(), "trans_size": self.t_size.value(),
            "trans_color": self.t_color.text(), "trans_margin": self.t_margin.value(),
            "trans_outline_color": self.t_out_color.text(), "trans_outline_size": self.t_out_size.value(),
            "orig_font": self.o_font.currentText(), "orig_size": self.o_size.value(),
            "orig_color": self.o_color.text(), "orig_margin": self.o_margin.value(),
            "orig_outline_color": self.o_out_color.text(), "orig_outline_size": self.o_out_size.value(),
        })
        self.accept()


# ================= 核心界面区 —— 年轻 Mica 风格 =================
class AutoCaptionWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("金水字幕 Pro")
        self.resize(1500, 800)

        # 启用暗色主题 + 紫色强调
        setTheme(Theme.DARK)

        self.projects = {}
        self.current_video_path = ""

        self.settings = {
            "api_key": "", "api_base": "https://api.deepseek.com", "model": "deepseek-chat", "glossary": "",
            "engine_type": "deepseek", "target_lang": "英文", "max_chars": 25,
            "mode": "bilingual",
            "trans_font": "Microsoft YaHei", "trans_size": 45, "trans_color": "#FFFFFF", "trans_margin": 60,
            "orig_font": "Microsoft YaHei", "orig_size": 30, "orig_color": "#CCCCCC", "orig_margin": 20,
        }
        self.load_settings()
        self.video_queue = []
        self.setAcceptDrops(True)
        self.init_ui()
        # 窗口整体样式 —— 暗色磨砂感 + 紫色强调
        self.setStyleSheet("""
            QMainWindow {
                background: rgba(20, 20, 28, 0.92);
            }
            QWidget#centralWidget {
                background: transparent;
            }
            QWidget#ribbonBar {
                background: rgba(30, 30, 40, 0.85);
                border-radius: 10px;
                border: 1px solid rgba(106, 13, 173, 0.25);
                padding: 2px;
            }
            CardWidget {
                background: rgba(38, 38, 50, 0.88);
                border: 1px solid rgba(255, 255, 255, 0.07);
                border-radius: 10px;
            }
            CardWidget:hover {
                border: 1px solid rgba(106, 13, 173, 0.4);
            }
            SettingCardGroup {
                background: transparent;
            }
        """)

    def load_settings(self):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                self.settings.update(json.load(f))

    def save_settings(self):
        self.settings["api_key"] = self.input_api_key.text().strip()
        self.settings["api_base"] = self.input_api_base.text().strip()
        self.settings["model"] = self.input_model.text().strip()
        self.settings["glossary"] = self.input_glossary.toPlainText()
        self.settings["engine_type"] = self.combo_engine.currentText()
        self.settings["target_lang"] = self.combo_lang.currentText()
        self.settings["max_chars"] = self.input_max_chars.value()
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.settings, f, ensure_ascii=False, indent=4)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        added_count = 0
        for url in urls:
            path = url.toLocalFile()
            if path.lower().endswith(('.mp4', '.mkv', '.mov', '.avi')):
                self.add_to_project_list(path)
                added_count += 1
        if added_count > 0:
            self.process_next_in_queue()

    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(12)

        # ===== 顶部 Ribbon 工具栏 =====
        ribbon = QWidget()
        ribbon.setObjectName("ribbonBar")
        ribbon_layout = QHBoxLayout(ribbon)
        ribbon_layout.setContentsMargins(2, 2, 2, 2)
        ribbon_layout.setSpacing(4)

        self.btn_import = PushButton(FluentIcon.ADD, "导入视频")
        self.btn_translate = PushButton(FluentIcon.LANGUAGE, "翻译")
        self.btn_optimize = PushButton(FluentIcon.EDIT, "润色原文")
        self.btn_style = PushButton(FluentIcon.FONT, "样式")
        self.btn_export = PushButton(FluentIcon.SAVE, "导出")

        ribbon_layout.addWidget(self.btn_import)
        ribbon_layout.addWidget(self.btn_translate)
        ribbon_layout.addWidget(self.btn_optimize)
        ribbon_layout.addWidget(self.btn_style)
        ribbon_layout.addWidget(self.btn_export)
        ribbon_layout.addStretch()

        # 右侧状态标签
        self.lbl_status = QLabel("就绪")
        self.lbl_status.setStyleSheet("color: #888888; font-size: 12px;")
        ribbon_layout.addWidget(self.lbl_status)

        main_layout.addWidget(ribbon)

        # ===== 三栏分割 =====
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)

        # ---------- 左侧：文件管理 ----------
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)

        left_layout.addWidget(QLabel("<b>📁 项目文件</b>"))

        self.list_videos = ListWidget()
        self.list_videos.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.list_videos.itemClicked.connect(self.on_video_selected)
        self.lbl_project_status = QLabel("拖拽视频文件到此处添加")
        self.lbl_project_status.setStyleSheet("color: #888888; font-size: 11px;")
        left_layout.addWidget(self.list_videos)
        left_layout.addWidget(self.lbl_project_status)
        splitter.addWidget(left_panel)

        # ---------- 中间：表格 ----------
        center_panel = QWidget()
        center_layout = QVBoxLayout(center_panel)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(4)

        # 标题行：字幕数据 + 合并行按钮
        center_title_layout = QHBoxLayout()
        center_title_layout.addWidget(QLabel("<b>📋 字幕数据</b>"))
        center_title_layout.addStretch()
        self.btn_merge_sel = PushButton(FluentIcon.MOVE, "合并行")
        center_title_layout.addWidget(self.btn_merge_sel)
        center_layout.addLayout(center_title_layout)

        self.table = TableWidget()
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(["开始", "结束", "原文", "译文", "重译", "插入", "删除"])
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.setWordWrap(True)
        self.table.verticalHeader().setDefaultSectionSize(50)
        self.table.verticalHeader().setMinimumSectionSize(30)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setAlternatingRowColors(True)
        # 隐藏双图标表头标签
        self.table.horizontalHeader().resizeSection(4, 40)
        self.table.horizontalHeader().resizeSection(5, 40)
        self.table.horizontalHeader().resizeSection(6, 40)
        center_layout.addWidget(self.table)
        splitter.addWidget(center_panel)

        # ---------- 右侧：属性面板 ----------
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)

        # 卡片 A：翻译引擎
        card_engine = CardWidget()
        engine_form = QFormLayout()
        engine_form.addRow(QLabel("<b>🤖 翻译引擎</b>"))
        self.combo_engine = ComboBox()
        self.combo_engine.addItems(["deepseek", "google", "baidu"])
        self.combo_engine.setCurrentText(self.settings.get("engine_type", "deepseek"))
        engine_form.addRow("选择引擎:", self.combo_engine)
        self.combo_lang = ComboBox()
        self.combo_lang.addItems(["英文", "日文", "韩文", "繁体中文", "法文", "俄文", "西班牙文"])
        self.combo_lang.setCurrentText(self.settings.get("target_lang", "英文"))
        engine_form.addRow("目标语言:", self.combo_lang)
        self.input_api_key = LineEdit()
        self.input_api_key.setText(self.settings.get("api_key", ""))
        self.input_api_key.setEchoMode(LineEdit.Password)
        self.input_api_base = LineEdit()
        self.input_api_base.setText(self.settings.get("api_base", "https://api.deepseek.com"))
        self.input_model = LineEdit()
        self.input_model.setText(self.settings.get("model", "deepseek-chat"))
        engine_form.addRow("API Key:", self.input_api_key)
        engine_form.addRow("Base URL:", self.input_api_base)
        engine_form.addRow("Model:", self.input_model)
        card_engine.setLayout(engine_form)
        right_layout.addWidget(card_engine)

        # 卡片 B：术语库
        card_glossary = CardWidget()
        glossary_layout = QVBoxLayout()
        glossary_layout.addWidget(QLabel("<b>📖 术语库与参考文稿</b>"))
        self.input_glossary = TextEdit()
        self.input_glossary.setText(self.settings.get("glossary", ""))
        glossary_layout.addWidget(self.input_glossary)
        btn_glossary_row = QHBoxLayout()
        self._btn_optimize_card = PushButton(FluentIcon.EDIT, "优化原文")
        self._btn_optimize_card.clicked.connect(self.action_batch_optimize)
        btn_save_cfg = PushButton(FluentIcon.SAVE, "暂存配置")
        btn_save_cfg.clicked.connect(self.action_save_settings)
        btn_glossary_row.addWidget(self._btn_optimize_card)
        btn_glossary_row.addWidget(btn_save_cfg)
        glossary_layout.addLayout(btn_glossary_row)
        # 单行字数限制（原先独立卡片，现移入术语库底部）
        chars_row = QHBoxLayout()
        chars_row.addWidget(QLabel("单行最大字数:"))
        self.input_max_chars = SpinBox()
        self.input_max_chars.setRange(10, 60)
        self.input_max_chars.setValue(self.settings.get("max_chars", 25))
        chars_row.addWidget(self.input_max_chars)
        glossary_layout.addLayout(chars_row)
        card_glossary.setLayout(glossary_layout)
        right_layout.addWidget(card_glossary)

        right_layout.addStretch()
        splitter.addWidget(right_panel)
        splitter.setSizes([200, 800, 350])

        # ===== 状态栏 =====
        from PySide6.QtWidgets import QStatusBar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # 底部进度条（默认隐藏）
        self.progress_bar = ProgressBar()
        self.progress_bar.setFixedHeight(4)
        self.progress_bar.setMinimumWidth(200)
        self.progress_bar.setVisible(False)
        self.status_bar.addPermanentWidget(self.progress_bar)

        # ===== 信号连接 =====
        self.btn_import.clicked.connect(self.action_import_video)
        self.btn_translate.clicked.connect(self.action_batch_translate)
        self.btn_style.clicked.connect(self.action_open_style_dialog)
        self.btn_export.clicked.connect(self.action_export)
        self.btn_merge_sel.clicked.connect(self.action_merge_selected)
        self.btn_optimize.clicked.connect(self.action_batch_optimize)
        self.table.cellChanged.connect(self.on_cell_changed)

        # 应用初始配置
        self.lbl_status.setText("就绪 - 可拖拽视频文件")

    # ---------- 项目列表核心逻辑 —— 完全不动 ----------
    def add_to_project_list(self, file_path):
        if file_path not in self.projects:
            self.projects[file_path] = SubtitleManager()
            from PySide6.QtWidgets import QListWidgetItem
            item = QListWidgetItem(os.path.basename(file_path))
            item.setData(Qt.UserRole, file_path)
            self.list_videos.addItem(item)
            self.video_queue.append(file_path)
            if not self.current_video_path:
                self.list_videos.setCurrentItem(item)
                self.on_video_selected(item)

    def on_video_selected(self, item):
        path = item.data(Qt.UserRole)
        self.current_video_path = path
        self.refresh_table()
        self.status_bar.showMessage(f"已切换至视频: {os.path.basename(path)}")

    def update_list_item_text(self, path, status_text):
        for i in range(self.list_videos.count()):
            item = self.list_videos.item(i)
            if item.data(Qt.UserRole) == path:
                base_name = os.path.basename(path)
                item.setText(f"{base_name} {status_text}")
                break

    # ---------- 功能方法 —— 完全不动 ----------
    def action_save_settings(self):
        self.save_settings()
        self.status_bar.showMessage("基础配置已保存")

    def action_open_style_dialog(self):
        dialog = StyleConfigDialog(self.settings, self)
        if dialog.exec() == QDialog.Accepted:
            self.settings = dialog.settings
            self.save_settings()

    def format_time(self, seconds: float) -> str:
        h, m = int(seconds // 3600), int((seconds % 3600) // 60)
        s, ms = int(seconds % 60), int((seconds - int(seconds)) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"

    def refresh_table(self, highlight_uid=None, scroll_to_uid=None):
        if not self.current_video_path:
            return
        manager = self.projects[self.current_video_path]

        old_scroll_pos = self.table.verticalScrollBar().value()
        old_current_row = self.table.currentRow()
        old_uid = None
        if old_current_row >= 0 and self.table.item(old_current_row, 0):
            old_uid = self.table.item(old_current_row, 0).data(Qt.UserRole)

        self.table.setUpdatesEnabled(False)
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        for i, sub in enumerate(manager.subtitles):
            self.table.insertRow(i)
            from PySide6.QtWidgets import QTableWidgetItem
            it_s = QTableWidgetItem(self.format_time(sub.start_time))
            it_s.setData(Qt.UserRole, sub.id)
            it_s.setFlags(it_s.flags() & ~Qt.ItemIsEditable)
            it_e = QTableWidgetItem(self.format_time(sub.end_time))
            it_e.setFlags(it_e.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(i, 0, it_s)
            self.table.setItem(i, 1, it_e)

            item_orig = QTableWidgetItem(sub.original_text)
            item_orig.setToolTip(sub.original_text)
            self.table.setItem(i, 2, item_orig)
            item_trans = QTableWidgetItem(sub.translated_text)
            item_trans.setToolTip(sub.translated_text)
            self.table.setItem(i, 3, item_trans)

            # 透明 Fluent 图标按钮
            btn_re = TransparentToolButton()
            btn_re.setIcon(FluentIcon.SYNC)
            btn_re.setIconSize(QSize(20, 20))
            btn_re.setFixedSize(28, 28)
            btn_re.setToolTip("重新翻译此句")
            btn_re.clicked.connect(lambda checked, uid=sub.id: self.action_single_translate(uid))
            self.table.setCellWidget(i, 4, btn_re)
            btn_ins = TransparentToolButton()
            btn_ins.setIcon(FluentIcon.ADD)
            btn_ins.setIconSize(QSize(20, 20))
            btn_ins.setFixedSize(28, 28)
            btn_ins.setToolTip("在下方插入新句")
            btn_ins.clicked.connect(lambda checked, uid=sub.id: self.action_insert_row(uid))
            self.table.setCellWidget(i, 5, btn_ins)
            btn_del = TransparentToolButton()
            btn_del.setIcon(FluentIcon.DELETE)
            btn_del.setIconSize(QSize(20, 20))
            btn_del.setFixedSize(28, 28)
            btn_del.setToolTip("删除此句")
            btn_del.clicked.connect(lambda checked, uid=sub.id: self.action_delete_row(uid))
            self.table.setCellWidget(i, 6, btn_del)

        if scroll_to_uid:
            self._scroll_to_uid(scroll_to_uid)
        else:
            self.table.verticalScrollBar().setValue(old_scroll_pos)

        if highlight_uid:
            self._highlight_uid(highlight_uid)
        elif old_uid:
            self._highlight_uid(old_uid)

        self.table.setUpdatesEnabled(True)
        self.table.blockSignals(False)

    def _scroll_to_uid(self, uid):
        for i in range(self.table.rowCount()):
            item = self.table.item(i, 0)
            if item and item.data(Qt.UserRole) == uid:
                self.table.scrollToItem(item, QAbstractItemView.PositionAtCenter)
                self.table.setCurrentCell(i, 2)
                break

    def _highlight_uid(self, uid, color=None):
        if color is None:
            color = QColor("#6A0DAD")
        for i in range(self.table.rowCount()):
            item = self.table.item(i, 0)
            if item and item.data(Qt.UserRole) == uid:
                for col in range(self.table.columnCount()):
                    cell = self.table.item(i, col)
                    if cell:
                        cell.setBackground(color)
                break

    # ---------- 队列打轴逻辑 —— 完全不动 ----------
    def action_import_video(self):
        file_paths, _ = QFileDialog.getOpenFileNames(self, "选择视频(可多选)", "", "视频 (*.mp4 *.mkv *.mov *.avi)")
        for p in file_paths:
            self.add_to_project_list(p)
        self.process_next_in_queue()

    def process_next_in_queue(self):
        if hasattr(self, 'asr_worker') and self.asr_worker.isRunning():
            return
        if not self.video_queue:
            self.status_bar.showMessage("✅ 队列中所有视频打轴完毕！")
            self.btn_import.setEnabled(True)
            return

        path = self.video_queue.pop(0)
        self.update_list_item_text(path, "[打轴中...]")
        self.btn_import.setEnabled(False)

        # 进度条显示打轴中
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(True)
        self.status_bar.showMessage(f"🎯 正在打轴: {os.path.basename(path)}")

        self.asr_worker = ASRWorker(path, self.projects[path], self.settings.get("max_chars", 25))
        self.asr_worker.finished_signal.connect(lambda: self.on_asr_finished(path))
        self.asr_worker.error_signal.connect(self.on_worker_error)
        self.asr_worker.start()

    def on_asr_finished(self, path):
        # 隐藏打轴进度条
        self.progress_bar.setVisible(False)
        self.progress_bar.setRange(0, 100)
        self.update_list_item_text(path, "[✅ 完成]")
        if self.current_video_path == path:
            self.refresh_table()
        self.process_next_in_queue()

    # ---------- 翻译、润色与导出 —— 完全不动 ----------
    def action_batch_translate(self):
        if not self.current_video_path:
            return
        self.save_settings()
        target_lang, engine_type = self.combo_lang.currentText(), self.combo_engine.currentText()
        if not self.settings.get("api_key") and engine_type == "deepseek":
            QMessageBox.warning(self, "警告", "使用云端 API 必须填写 API Key！")
            return
        self.btn_translate.setEnabled(False)
        self.status_bar.showMessage(f"正在翻译当前视频为 {target_lang}...")
        self.lbl_status.setText(f"🌐 翻译中...")
        self.trans_worker = TranslateWorker(
            self.settings.get("api_key", ""), self.settings.get("api_base", ""), self.settings.get("model", ""),
            self.settings.get("glossary", ""), engine_type, target_lang, self.projects[self.current_video_path]
        )
        self.trans_worker.finished_signal.connect(
            lambda: (self.btn_translate.setEnabled(True), self.refresh_table(), self.status_bar.showMessage("✅ 翻译完成！"), self.lbl_status.setText("翻译完成 ✅")))
        self.trans_worker.error_signal.connect(self.on_worker_error)
        self.trans_worker.start()

    def action_batch_optimize(self):
        if not self.current_video_path:
            return
        self.save_settings()
        engine_type = self.combo_engine.currentText()
        self.btn_optimize.setEnabled(False)
        self._btn_optimize_card.setEnabled(False)
        self.status_bar.showMessage("正在调用大模型进行润色...")
        self.lbl_status.setText("✨ 润色中...")
        self.opt_worker = OptimizeWorker(
            self.settings.get("api_key", ""), self.settings.get("api_base", ""), self.settings.get("model", ""),
            self.settings.get("glossary", ""), engine_type, self.projects[self.current_video_path]
        )
        self.opt_worker.finished_signal.connect(
            lambda: (self.btn_optimize.setEnabled(True), self._btn_optimize_card.setEnabled(True),
                     self.refresh_table(), self.status_bar.showMessage("✅ 润色完成！"), self.lbl_status.setText("润色完成 ✅")))
        self.opt_worker.error_signal.connect(self.on_worker_error)
        self.opt_worker.start()

    def action_export(self):
        if not self.current_video_path or not self.projects[self.current_video_path].subtitles:
            return
        items = ["1. 纯文本 SRT 字幕", "2. 高级样式 ASS 字幕", "3. 压制硬字幕视频"]
        choice, ok = QInputDialog.getItem(self, "导出当前视频", "选择：", items, 0, False)
        if ok and choice:
            if choice.startswith("1"):
                p, _ = QFileDialog.getSaveFileName(self, "保存", "sub.srt", "SRT (*.srt)")
                if p:
                    self.start_export('srt', p)
            elif choice.startswith("2"):
                p, _ = QFileDialog.getSaveFileName(self, "保存", "sub.ass", "ASS (*.ass)")
                if p:
                    self.start_export('ass', p)
            else:
                name = os.path.splitext(self.current_video_path)[0] + "_subbed.mp4"
                p, _ = QFileDialog.getSaveFileName(self, "保存", name, "MP4 (*.mp4)")
                if p:
                    self.start_export('video', p)

    def start_export(self, mode, out_path):
        self.btn_export.setEnabled(False)
        if mode == 'video':
            from core.exporter import detect_best_encoder
            enc = detect_best_encoder()
            if enc and enc != "libx264":
                self.status_bar.showMessage(f"🚀 GPU 加速压制中（编码器: {enc}）...")
            else:
                self.status_bar.showMessage("💻 CPU 压制中（编码器: libx264）...")
        self.exp_worker = ExportWorker(mode, self.current_video_path, self.projects[self.current_video_path], out_path, self.settings)
        self.exp_worker.finished_signal.connect(self.on_export_success)
        self.exp_worker.error_signal.connect(self.on_worker_error)
        self.exp_worker.start()

    def on_export_success(self, msg):
        self.btn_export.setEnabled(True)
        QMessageBox.information(self, "成功", msg)
        self.status_bar.showMessage(msg)
        self.lbl_status.setText("导出完成 ✅")

    def on_worker_error(self, err_msg):
        self.btn_import.setEnabled(True)
        self.btn_translate.setEnabled(True)
        self.btn_export.setEnabled(True)
        if hasattr(self, 'btn_optimize'):
            self.btn_optimize.setEnabled(True)
        if hasattr(self, '_btn_optimize_card'):
            self._btn_optimize_card.setEnabled(True)
        QMessageBox.critical(self, "报错", err_msg)
        self.status_bar.showMessage("❌ 后台出错")
        self.lbl_status.setText("❌ 出错")

    # ---------- 表格交互逻辑 —— 完全不动 ----------
    def _update_table_row(self, row, sub):
        self.table.item(row, 0).setText(self.format_time(sub.start_time))
        self.table.item(row, 1).setText(self.format_time(sub.end_time))
        self.table.item(row, 2).setText(sub.original_text)
        self.table.item(row, 2).setToolTip(sub.original_text)
        self.table.item(row, 3).setText(sub.translated_text)
        self.table.item(row, 3).setToolTip(sub.translated_text)

    def on_cell_changed(self, row, col):
        if col not in [2, 3] or not self.current_video_path:
            return
        id_ = self.table.item(row, 0).data(Qt.UserRole)
        txt = self.table.item(row, col).text()
        manager = self.projects[self.current_video_path]
        if col == 2:
            manager.update_original(id_, txt)
        elif col == 3:
            manager.update_translation(id_, txt)
        self._highlight_uid(id_)

    def _find_table_row_by_uid(self, uid):
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and item.data(Qt.UserRole) == uid:
                return row
        return -1

    def action_delete_row(self, uid):
        from PySide6.QtWidgets import QTableWidgetItem
        manager = self.projects[self.current_video_path]
        target_row = self._find_table_row_by_uid(uid)
        if target_row < 0:
            return
        manager.delete_item(uid)
        self.table.blockSignals(True)
        self.table.removeRow(target_row)
        new_row = min(target_row, self.table.rowCount() - 1)
        if new_row >= 0:
            new_uid = self.table.item(new_row, 0).data(Qt.UserRole)
            self.table.setCurrentCell(new_row, 2)
            self._highlight_uid(new_uid)
        self.table.blockSignals(False)
        self.status_bar.showMessage("✅ 已删除")

    def action_insert_row(self, uid):
        from PySide6.QtWidgets import QTableWidgetItem
        manager = self.projects[self.current_video_path]
        target_data_idx = -1
        for i, sub in enumerate(manager.subtitles):
            if sub.id == uid:
                target_data_idx = i
                break
        if target_data_idx < 0:
            return
        target_table_row = self._find_table_row_by_uid(uid)
        if target_table_row < 0:
            return

        manager.insert_item_after(uid)
        insert_pos = target_table_row + 1
        new_sub = manager.subtitles[target_data_idx + 1]

        self.table.blockSignals(True)
        self.table.insertRow(insert_pos)

        it_s = QTableWidgetItem(self.format_time(new_sub.start_time))
        it_s.setData(Qt.UserRole, new_sub.id)
        it_s.setFlags(it_s.flags() & ~Qt.ItemIsEditable)
        it_e = QTableWidgetItem(self.format_time(new_sub.end_time))
        it_e.setFlags(it_e.flags() & ~Qt.ItemIsEditable)
        self.table.setItem(insert_pos, 0, it_s)
        self.table.setItem(insert_pos, 1, it_e)

        item_orig = QTableWidgetItem(new_sub.original_text)
        item_orig.setToolTip(new_sub.original_text)
        self.table.setItem(insert_pos, 2, item_orig)
        item_trans = QTableWidgetItem(new_sub.translated_text)
        item_trans.setToolTip(new_sub.translated_text)
        self.table.setItem(insert_pos, 3, item_trans)

        btn_re = TransparentToolButton()
        btn_re.setIcon(FluentIcon.SYNC)
        btn_re.setIconSize(QSize(20, 20))
        btn_re.setFixedSize(28, 28)
        btn_re.setToolTip("重新翻译此句")
        btn_re.clicked.connect(lambda checked, uid2=new_sub.id: self.action_single_translate(uid2))
        self.table.setCellWidget(insert_pos, 4, btn_re)
        btn_ins = TransparentToolButton()
        btn_ins.setIcon(FluentIcon.ADD)
        btn_ins.setIconSize(QSize(20, 20))
        btn_ins.setFixedSize(28, 28)
        btn_ins.setToolTip("在下方插入新句")
        btn_ins.clicked.connect(lambda checked, uid2=new_sub.id: self.action_insert_row(uid2))
        self.table.setCellWidget(insert_pos, 5, btn_ins)
        btn_del = TransparentToolButton()
        btn_del.setIcon(FluentIcon.DELETE)
        btn_del.setIconSize(QSize(20, 20))
        btn_del.setFixedSize(28, 28)
        btn_del.setToolTip("删除此句")
        btn_del.clicked.connect(lambda checked, uid2=new_sub.id: self.action_delete_row(uid2))
        self.table.setCellWidget(insert_pos, 6, btn_del)

        self.table.setCurrentCell(insert_pos, 2)
        self._highlight_uid(new_sub.id)
        self.table.scrollToItem(it_s, QAbstractItemView.PositionAtCenter)
        self.table.blockSignals(False)
        self.status_bar.showMessage("✅ 已插入新行，可编辑原文/译文")

    def action_merge_selected(self):
        rows = sorted(set([it.row() for it in self.table.selectedItems()]))
        if len(rows) < 2 or not self.current_video_path:
            return

        first_uid = self.table.item(rows[0], 0).data(Qt.UserRole)
        id_list = [self.table.item(r, 0).data(Qt.UserRole) for r in rows]
        manager = self.projects[self.current_video_path]
        manager.merge_selected(id_list)

        first_sub = next((s for s in manager.subtitles if s.id == first_uid), None)
        if not first_sub:
            self.refresh_table()
            return

        self.table.blockSignals(True)
        self._update_table_row(rows[0], first_sub)
        for r in reversed(rows[1:]):
            self.table.removeRow(r)

        self.table.setCurrentCell(rows[0], 2)
        self._highlight_uid(first_uid)
        self.table.blockSignals(False)
        self.status_bar.showMessage("✅ 合并完成")

    def action_single_translate(self, uid):
        if not self.current_video_path:
            return
        self.save_settings()
        manager = self.projects[self.current_video_path]
        orig = next((s.reference_text for s in manager.subtitles if s.id == uid), "")
        if not orig:
            orig = next((s.original_text for s in manager.subtitles if s.id == uid), "")
        target_lang = self.combo_lang.currentText()

        try:
            from core.translator import TranslatorEngine
            eng = TranslatorEngine(self.settings.get("api_key", ""), self.settings.get("api_base", ""),
                                   self.settings.get("model", ""), self.settings.get("engine_type", "deepseek"))
            res = eng.client.chat.completions.create(
                model=self.settings["model"],
                messages=[{"role": "user", "content": f"请将以下文本翻译为{target_lang}，无需多余解释:\n{orig}"}],
                temperature=0.3
            )
            new_text = res.choices[0].message.content.strip()
            manager.update_translation(uid, new_text)

            row = self._find_table_row_by_uid(uid)
            if row >= 0:
                self.table.item(row, 3).setText(new_text)
                self.table.item(row, 3).setToolTip(new_text)
                self._highlight_uid(uid)
            self.status_bar.showMessage("✅ 单句重译完成！")
        except Exception as e:
            QMessageBox.critical(self, "报错", str(e))

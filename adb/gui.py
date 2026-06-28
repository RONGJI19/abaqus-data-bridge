"""ADB 桌面 GUI — 基于 PySide6.

提供图形化的 Abaqus 结果提取界面。
安装: pip install abaqus-data-bridge[gui]
运行: adb-gui  或  python -m adb.gui
"""

from __future__ import annotations

import os
import sys
import logging
import threading
from datetime import datetime
from pathlib import Path

from dataclasses import dataclass, field
from adb import __version__
from adb.models.extraction_config import ExtractionConfig
from adb.core.engine import ExtractionEngine
from adb.utils.logging import CrashProofLogger, create_debug_logger


# --- Logging setup ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("adb.gui")


# ============================================================
# 可用变量列表
# ============================================================
VARIABLE_GROUPS = {
    "节点位移 (U)": ("nodal", ["U"]),
    "支反力 (RF)": ("nodal", ["RF"]),
    "单元应力 (S)": ("element", ["S"]),
    "单元应变 (E)": ("element", ["E"]),
    "接触法向力 (CNORMF)": ("contact", ["CNORMF"]),
    "接触压力 (CPRESS)": ("contact", ["CPRESS"]),
    "接触张开 (COPEN)": ("contact", ["COPEN"]),
    "接触滑移 (CSLIP)": ("contact", ["CSLIP"]),
    "弹簧内力 (S11)": ("spring", ["S11"]),
    "弹簧位移 (E11)": ("spring", ["E11"]),
    "截面力 (SF)": ("section", ["SF"]),
    "截面弯矩 (SM)": ("section", ["SM"]),
}

ENCODING_OPTIONS = ["utf-8-sig (Excel推荐)", "utf-8", "gbk (中文Windows)"]
ENCODING_MAP = {
    "utf-8-sig (Excel推荐)": "utf-8-sig",
    "utf-8": "utf-8",
    "gbk (中文Windows)": "gbk",
}


# ============================================================
# 拖放输入框工厂
# ============================================================
def _create_drop_lineedit(qt_module):
    """创建支持文件拖放的 QLineEdit 子类."""
    class _DropLineEdit(qt_module.QLineEdit):
        def __init__(self, extensions=None, parent=None):
            super().__init__(parent)
            self._extensions = extensions or []
            self.setAcceptDrops(True)

        def dragEnterEvent(self, event):
            if event.mimeData().hasUrls():
                for url in event.mimeData().urls():
                    path = url.toLocalFile()
                    if any(path.lower().endswith(ext) for ext in self._extensions):
                        event.acceptProposedAction()
                        return
            event.ignore()

        def dropEvent(self, event):
            for url in event.mimeData().urls():
                path = url.toLocalFile()
                if any(path.lower().endswith(ext) for ext in self._extensions):
                    self.setText(path)
                    break
    return _DropLineEdit


# ============================================================
# 预分析结果数据模型
# ============================================================
@dataclass
class PreAnalysisData:
    """预分析结果."""
    node_count: int = 0
    element_count: int = 0
    nsets: dict = field(default_factory=dict)    # name -> member_count
    elsets: dict = field(default_factory=dict)   # name -> member_count
    steps: dict = field(default_factory=dict)    # step_name -> list of inc_nums
    step_types: dict = field(default_factory=dict)  # step_name -> step_type
    analysis_type: str = ""
    completion_status: str = ""
    job_name: str = ""
    element_connectivity: dict = field(default_factory=dict)  # elem_id -> {type, nodes, coords}


class ExtractionThread(threading.Thread):
    """后台提取线程，防止 GUI 冻结."""

    def __init__(self, config: ExtractionConfig, on_progress=None, on_done=None,
                 debug_log: Optional[CrashProofLogger] = None):
        super().__init__(daemon=True)
        self.config = config
        self.stats: dict | None = None
        self.error: str | None = None
        self._cancel = False
        self._on_progress = on_progress  # callback(step_name, percent)
        self._on_done = on_done          # callback(stats, error)
        self._debug_log = debug_log

    def cancel(self):
        self._cancel = True
        if self._debug_log:
            self._debug_log.log("Cancel requested by user", "WARN")

    def _report(self, step: str, pct: int):
        if self._on_progress:
            self._on_progress(step, pct)

    def run(self):
        dl = self._debug_log

        try:
            if dl:
                dl.start(f"INP: {self.config.inp_file}\n"
                         f"DAT: {self.config.dat_file}\n"
                         f"Output: {self.config.output_dir}")

            if self._cancel:
                if dl:
                    dl.log("Cancelled before extraction started", "WARN")
                    dl.close()
                return

            # Phase 1: Parse INP
            if dl:
                dl.log_phase_enter("Parse INP")
            self._report("解析 INP...", 10)
            from adb.parsers.inp_parser import parse_inp
            model = parse_inp(self.config.inp_file, debug_log=dl)
            if dl:
                dl.log_phase_exit("Parse INP",
                                  f"{model.get_node_count()} nodes, "
                                  f"{model.get_element_count()} elements")

            if self._cancel:
                if dl:
                    dl.log("Cancelled after INP parse", "WARN")
                    dl.close()
                return

            # Phase 2: Parse DAT
            if dl:
                dl.log_phase_enter("Parse DAT")
            self._report("解析 DAT...", 30)
            from adb.parsers.dat_parser import parse_dat
            results = parse_dat(self.config.dat_file, debug_log=dl)
            if dl:
                dl.log_phase_exit("Parse DAT",
                                  f"{len(results.steps)} steps, "
                                  f"status={results.completion_status}")

            if self._cancel:
                if dl:
                    dl.log("Cancelled after DAT parse", "WARN")
                    dl.close()
                return

            # Phase 3: Match
            if dl:
                dl.log_phase_enter("Match Results")
            self._report("匹配数据...", 50)
            from adb.core.matcher import match_results
            matched = match_results(model, results, self.config, debug_log=dl)
            if dl:
                dl.log_phase_exit("Match Results",
                                  f"{len(matched)} groups")

            if self._cancel:
                if dl:
                    dl.log("Cancelled after match", "WARN")
                    dl.close()
                return

            # Phase 4: Export CSV
            if dl:
                dl.log_phase_enter("Export CSV")
            self._report("导出 CSV...", 70)
            from adb.exporters.csv_exporter import CsvExporter
            exporter = CsvExporter(self.config.output)
            total = len(matched)
            count = [0]

            def per_file_cb():
                count[0] += 1
                pct = 70 + int(25 * count[0] / total) if total > 0 else 95
                self._report(f"导出 CSV ({count[0]}/{total})...", pct)

            export_count = exporter.export_all(
                matched,
                self.config.output_dir,
                job_name=self.config.job_name or results.job_name,
                step_increment_info=self._build_info(results),
                progress_callback=per_file_cb,
                debug_log=dl,
            )
            if dl:
                dl.log_phase_exit("Export CSV",
                                  f"{export_count} files")

            if self._cancel:
                if dl:
                    dl.log("Cancelled after CSV export", "WARN")
                    dl.close()
                return

            self._report("完成", 100)

            # 构建统计
            stats = {
                "job_name": self.config.job_name or results.job_name,
                "analysis_status": results.completion_status,
                "node_count": model.get_node_count(),
                "element_count": model.get_element_count(),
                "nset_count": model.get_nset_count(),
                "elset_count": model.get_elset_count(),
                "step_count": len(results.steps),
                "result_groups": len(matched),
                "total_rows": sum(len(r) for r in matched.values()),
                "exported_files": export_count,
            }
            self.stats = stats

            if dl:
                dl.log(f"EXTRACTION COMPLETE: {export_count} files, "
                       f"{stats['total_rows']} rows", "INFO")
                dl.close()

            if self._on_done:
                self._on_done(stats, None)

        except Exception as e:
            logger.exception("Extraction failed")
            if dl:
                dl.exception(e)
                dl.close()
            self.error = str(e)
            if self._on_done:
                self._on_done(None, str(e))

    @staticmethod
    def _build_info(results) -> dict:
        info = {}
        for step_name, step in results.steps.items():
            for inc_num in step.increments:
                inc = step.increments[inc_num]
                key = f"{step_name}_incr{inc_num}"
                info[key] = (
                    f"Step: {step_name}, Increment: {inc_num}, "
                    f"Step Time: {inc.step_time:.6E}"
                )
        return info


class PreAnalysisThread(threading.Thread):
    """后台预分析线程，解析 INP/DAT 但不导出."""

    def __init__(self, inp_path: str, dat_path: str, on_done=None):
        super().__init__(daemon=True)
        self.inp_path = inp_path
        self.dat_path = dat_path
        self.data: PreAnalysisData | None = None
        self.error: str | None = None
        self._on_done = on_done

    def run(self):
        try:
            from adb.parsers.inp_parser import parse_inp
            from adb.parsers.dat_parser import parse_dat

            # 解析 INP
            inp_model = parse_inp(self.inp_path)
            nsets = {name: len(ids) for name, ids in inp_model.nsets.items()}
            elsets = {name: len(ids) for name, ids in inp_model.elsets.items()}

            # 收集简单单元连接信息 (connectivity length == 2)
            elem_conn = {}
            for elem_id, elem in inp_model.elements.items():
                node_ids = elem.connectivity
                if len(node_ids) == 2:
                    n1, n2 = node_ids
                    node1 = inp_model.nodes.get(n1)
                    node2 = inp_model.nodes.get(n2)
                    coord1 = (node1.x, node1.y, node1.z) if node1 else (0.0, 0.0, 0.0)
                    coord2 = (node2.x, node2.y, node2.z) if node2 else (0.0, 0.0, 0.0)
                    elem_conn[elem_id] = {
                        "type": elem.type,
                        "nodes": [n1, n2],
                        "coords": [coord1, coord2],
                    }

            # 解析 DAT
            dat_results = parse_dat(self.dat_path)
            steps = {}
            step_types = {}
            for sname, step in dat_results.steps.items():
                steps[sname] = sorted(step.increments.keys())
                step_types[sname] = step.step_type

            self.data = PreAnalysisData(
                node_count=inp_model.get_node_count(),
                element_count=inp_model.get_element_count(),
                nsets=nsets,
                elsets=elsets,
                steps=steps,
                step_types=step_types,
                analysis_type=dat_results.analysis_type or "",
                completion_status=dat_results.completion_status or "",
                job_name=dat_results.job_name or inp_model.job_name,
                element_connectivity=elem_conn,
            )
        except Exception as e:
            logger.exception("Pre-analysis failed")
            self.error = str(e)
        finally:
            if self._on_done:
                self._on_done(self.data, self.error)


def _try_import_pyside6():
    """检测 PySide6 可用性."""
    try:
        from PySide6 import QtWidgets, QtCore, QtGui
        return QtWidgets, QtCore, QtGui
    except ImportError:
        return None, None, None


def run_gui():
    """启动 GUI 主循环."""
    QtWidgets, QtCore, QtGui = _try_import_pyside6()
    if QtWidgets is None:
        print("PySide6 未安装。请运行: pip install pyside6")
        print("或者使用命令行版本: adb extract -i ... -d ...")
        sys.exit(1)

    app = QtWidgets.QApplication(sys.argv)
    app.setStyle("Fusion")

    window = MainWindow(QtWidgets, QtCore, QtGui)
    window.show()

    sys.exit(app.exec())


class MainWindow:
    """主窗口."""

    def __init__(self, QtWidgets, QtCore, QtGui):
        self.Qt = QtWidgets
        self.QtCore = QtCore
        self.QtGui = QtGui
        self._build_ui()
        self._thread: ExtractionThread | None = None
        self._pre_thread: PreAnalysisThread | None = None
        self._nset_checkboxes: dict = {}
        self._elset_checkboxes: dict = {}

    def show(self):
        """显示窗口."""
        self.window.show()

    def _build_ui(self):
        Q = self.Qt
        w = Q.QWidget()
        self.window = w
        w.setWindowTitle(f"Abaqus Data Bridge v{__version__}")
        w.resize(960, 700)

        # --- 主布局 ---
        main_layout = Q.QVBoxLayout(w)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(8)

        # 创建可拖放的输入框类
        DropLineEdit = _create_drop_lineedit(Q)

        # === 标题 ===
        title = Q.QLabel(f"<h2>🔗 Abaqus Data Bridge v{__version__}</h2>")
        title.setAlignment(self.QtCore.Qt.AlignCenter)
        main_layout.addWidget(title)

        # === 文件选择区 ===
        file_group = Q.QGroupBox("📁 文件设置 (支持拖放 .inp / .dat)")
        file_layout = Q.QFormLayout(file_group)

        self.inp_edit = DropLineEdit(['.inp'])
        self.inp_edit.setPlaceholderText("拖放或选择 .inp 文件...")
        inp_btn = Q.QPushButton("浏览...")
        inp_btn.clicked.connect(lambda: self._browse_file("INP (*.inp)", self.inp_edit))
        inp_row = Q.QHBoxLayout()
        inp_row.addWidget(self.inp_edit)
        inp_row.addWidget(inp_btn)

        self.dat_edit = DropLineEdit(['.dat'])
        self.dat_edit.setPlaceholderText("拖放或选择 .dat 文件...")
        dat_btn = Q.QPushButton("浏览...")
        dat_btn.clicked.connect(lambda: self._browse_file("DAT (*.dat)", self.dat_edit))
        dat_row = Q.QHBoxLayout()
        dat_row.addWidget(self.dat_edit)
        dat_row.addWidget(dat_btn)

        # 输出目录 — INP 改变时自动设为 INP 所在目录
        self._out_manually_set = False
        self._auto_setting_out = False
        self.out_edit = Q.QLineEdit()
        self.out_edit.setText("./output")
        self.inp_edit.textChanged.connect(self._on_inp_changed)
        self.out_edit.textChanged.connect(self._on_out_changed)
        out_btn = Q.QPushButton("浏览...")
        out_btn.clicked.connect(lambda: self._browse_dir(self.out_edit))
        out_row = Q.QHBoxLayout()
        out_row.addWidget(self.out_edit)
        out_row.addWidget(out_btn)

        file_layout.addRow("INP 文件:", inp_row)
        file_layout.addRow("DAT 文件:", dat_row)
        file_layout.addRow("输出目录:", out_row)
        main_layout.addWidget(file_group)

        # === 变量选择区 ===
        var_group = Q.QGroupBox("📊 提取变量 (不选=全部)")
        var_layout = Q.QGridLayout(var_group)
        var_layout.setSpacing(4)

        self.var_checkboxes = {}
        for i, (label, (cat, vars_list)) in enumerate(VARIABLE_GROUPS.items()):
            cb = Q.QCheckBox(label)
            cb.setChecked(False)
            self.var_checkboxes[label] = (cb, cat, vars_list)
            row = i // 4
            col = i % 4
            var_layout.addWidget(cb, row, col)

        main_layout.addWidget(var_group)

        # === 筛选区 ===
        filt_group = Q.QGroupBox("🔍 筛选条件")
        filt_layout = Q.QFormLayout(filt_group)

        self.nsets_edit = Q.QLineEdit()
        self.nsets_edit.setPlaceholderText("如: TOP,BOTTOM (逗号分隔，留空=全部)")
        filt_layout.addRow("节点集:", self.nsets_edit)

        self.elsets_edit = Q.QLineEdit()
        self.elsets_edit.setPlaceholderText("如: SPRING_SET (逗号分隔，留空=全部)")
        filt_layout.addRow("单元集:", self.elsets_edit)

        incr_layout = Q.QHBoxLayout()
        self.incr_combo = Q.QComboBox()
        self.incr_combo.addItems(["last (最后一帧)", "all (全部)", "自定义... (如 1,3,5)"])
        incr_layout.addWidget(self.incr_combo)
        self.incr_custom = Q.QLineEdit()
        self.incr_custom.setPlaceholderText("1,3,5")
        self.incr_custom.setMaximumWidth(120)
        self.incr_custom.setEnabled(False)
        self.incr_combo.currentIndexChanged.connect(
            lambda i: self.incr_custom.setEnabled(i == 2)
        )
        incr_layout.addWidget(self.incr_custom)
        incr_layout.addStretch()
        filt_layout.addRow("Increment:", incr_layout)

        main_layout.addWidget(filt_group)

        # === 预分析结果区 (初始隐藏) ===
        self.pre_group = Q.QGroupBox("📋 预分析结果")
        self.pre_group.setVisible(False)
        pre_layout = Q.QVBoxLayout(self.pre_group)

        # 摘要行
        self.pre_summary_label = Q.QLabel("")
        self.pre_summary_label.setWordWrap(True)
        pre_layout.addWidget(self.pre_summary_label)

        # 滚动区域
        pre_scroll = Q.QScrollArea()
        pre_scroll.setWidgetResizable(True)
        pre_scroll_widget = Q.QWidget()
        self.pre_scroll_layout = Q.QVBoxLayout(pre_scroll_widget)
        pre_scroll.setWidget(pre_scroll_widget)
        pre_layout.addWidget(pre_scroll)

        # Select/Deselect + Apply 按钮
        pre_btn_row = Q.QHBoxLayout()
        self.pre_select_all_btn = Q.QPushButton("全选")
        self.pre_select_all_btn.clicked.connect(lambda: self._toggle_all_sets(True))
        self.pre_deselect_all_btn = Q.QPushButton("全不选")
        self.pre_deselect_all_btn.clicked.connect(lambda: self._toggle_all_sets(False))
        self.pre_apply_btn = Q.QPushButton("✅ 应用选中集合到筛选")
        self.pre_apply_btn.setStyleSheet(
            "QPushButton { background-color: #2196F3; color: white; font-weight: bold; "
            "border-radius: 4px; padding: 6px; }"
            "QPushButton:hover { background-color: #1976D2; }"
        )
        self.pre_apply_btn.clicked.connect(self._apply_sets_to_filters)
        pre_btn_row.addWidget(self.pre_select_all_btn)
        pre_btn_row.addWidget(self.pre_deselect_all_btn)
        pre_btn_row.addStretch()
        pre_btn_row.addWidget(self.pre_apply_btn)
        pre_layout.addLayout(pre_btn_row)

        main_layout.addWidget(self.pre_group)

        # === 输出选项区 ===
        out_group = Q.QGroupBox("⚙️ 输出选项")
        out_layout = Q.QFormLayout(out_group)

        self.enc_combo = Q.QComboBox()
        self.enc_combo.addItems(ENCODING_OPTIONS)
        out_layout.addRow("编码:", self.enc_combo)

        self.meta_cb = Q.QCheckBox("包含元数据头部")
        self.meta_cb.setChecked(True)
        self.coord_cb = Q.QCheckBox("附带节点坐标列")
        self.coord_cb.setChecked(True)
        opt_h_layout = Q.QHBoxLayout()
        opt_h_layout.addWidget(self.meta_cb)
        opt_h_layout.addWidget(self.coord_cb)
        opt_h_layout.addStretch()
        out_layout.addRow("", opt_h_layout)

        main_layout.addWidget(out_group)

        # === 控制按钮 ===
        btn_layout = Q.QHBoxLayout()

        self.pre_btn = Q.QPushButton("🔍 预分析")
        self.pre_btn.setMinimumHeight(40)
        self.pre_btn.setStyleSheet(
            "QPushButton { background-color: #2196F3; color: white; "
            "font-size: 13px; font-weight: bold; border-radius: 4px; }"
            "QPushButton:hover { background-color: #1976D2; }"
            "QPushButton:disabled { background-color: #999; }"
        )
        self.pre_btn.clicked.connect(self._start_pre_analysis)

        self.run_btn = Q.QPushButton("▶  开始提取")
        self.run_btn.setMinimumHeight(40)
        self.run_btn.setStyleSheet(
            "QPushButton { background-color: #4CAF50; color: white; "
            "font-size: 14px; font-weight: bold; border-radius: 4px; }"
            "QPushButton:hover { background-color: #45a049; }"
            "QPushButton:disabled { background-color: #999; }"
        )
        self.run_btn.clicked.connect(self._start_extraction)

        self.cancel_btn = Q.QPushButton("取消")
        self.cancel_btn.setMinimumHeight(40)
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self._cancel_extraction)

        btn_layout.addWidget(self.pre_btn)
        btn_layout.addWidget(self.run_btn)
        btn_layout.addWidget(self.cancel_btn)
        main_layout.addLayout(btn_layout)

        # === 进度 + 日志区 ===
        log_group = Q.QGroupBox("📋 日志")
        log_layout = Q.QVBoxLayout(log_group)

        self.progress = Q.QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(True)
        log_layout.addWidget(self.progress)

        self.status_label = Q.QLabel("就绪 — 选择 INP 和 DAT 文件后点击「开始提取」")
        log_layout.addWidget(self.status_label)

        self.log_text = Q.QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(180)
        self.log_text.setFont(self.QtGui.QFont("Consolas", 9))
        log_layout.addWidget(self.log_text)

        main_layout.addWidget(log_group)

        w.setLayout(main_layout)

    # ---- 文件选择 ----
    def _browse_file(self, filter_str: str, target: object):
        path, _ = self.Qt.QFileDialog.getOpenFileName(
            self.window, "选择文件", "", filter_str
        )
        if path:
            target.setText(path)

    def _browse_dir(self, target: object):
        path = self.Qt.QFileDialog.getExistingDirectory(
            self.window, "选择输出目录"
        )
        if path:
            target.setText(path)

    # ---- 提取逻辑 ----
    def _build_config(self) -> ExtractionConfig | None:
        """从 GUI 控件构建 ExtractionConfig."""
        config = ExtractionConfig()
        config.inp_file = self.inp_edit.text().strip()
        config.dat_file = self.dat_edit.text().strip()
        config.output_dir = self.out_edit.text().strip() or "./output"

        if not config.inp_file:
            self._log("❌ 请选择 INP 文件", error=True)
            return None
        if not config.dat_file:
            self._log("❌ 请选择 DAT 文件", error=True)
            return None
        if not os.path.exists(config.inp_file):
            self._log(f"❌ INP 文件不存在: {config.inp_file}", error=True)
            return None
        if not os.path.exists(config.dat_file):
            self._log(f"❌ DAT 文件不存在: {config.dat_file}", error=True)
            return None

        config.job_name = Path(config.dat_file).stem

        # 变量
        for label, (cb, cat, vars_list) in self.var_checkboxes.items():
            if cb.isChecked():
                getattr(config.variables, cat).extend(vars_list)

        # 筛选
        nsets_text = self.nsets_edit.text().strip()
        if nsets_text:
            config.filters.node_sets = [
                s.strip() for s in nsets_text.split(",") if s.strip()
            ]
        elsets_text = self.elsets_edit.text().strip()
        if elsets_text:
            config.filters.element_sets = [
                s.strip() for s in elsets_text.split(",") if s.strip()
            ]

        incr_idx = self.incr_combo.currentIndex()
        if incr_idx == 0:
            config.filters.increments = "last"
        elif incr_idx == 1:
            config.filters.increments = "all"
        elif incr_idx == 2:
            custom = self.incr_custom.text().strip()
            try:
                config.filters.increments = [
                    int(x.strip()) for x in custom.split(",") if x.strip()
                ]
            except ValueError:
                config.filters.increments = "last"

        # 输出选项
        config.output.encoding = ENCODING_MAP.get(
            self.enc_combo.currentText(), "utf-8-sig"
        )
        config.output.include_metadata = self.meta_cb.isChecked()
        config.output.include_node_coords = self.coord_cb.isChecked()

        return config

    def _start_extraction(self):
        config = self._build_config()
        if config is None:
            return

        # 创建调试日志 (EXE 模式下自动启用)
        debug_log = create_debug_logger(
            output_dir=config.output_dir,
            job_name=config.job_name,
        )

        self.run_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.progress.setValue(0)
        self.progress.setFormat("准备...")
        self.status_label.setText("正在提取...")
        self._log(f"▶ 开始提取: {config.job_name}")
        self._log(f"  INP: {config.inp_file}")
        self._log(f"  DAT: {config.dat_file}")
        self._log(f"  输出: {config.output_dir}")
        if debug_log:
            self._log(f"  调试日志: {debug_log.log_path}")

        # 线程间通信: 线程只写入这些变量，主线程定时器读取
        self._progress_step = "解析 INP..."
        self._progress_pct = 0
        self._done_stats = None
        self._done_error = None

        def on_progress(step, pct):
            self._progress_step = step
            self._progress_pct = pct

        def on_done(stats, error):
            self._done_stats = stats
            self._done_error = error

        self._thread = ExtractionThread(config, on_progress, on_done,
                                        debug_log=debug_log)
        self._thread.start()

        # 单一定时器: 轮询进度 & 完成状态
        self._poll_timer = self.QtCore.QTimer()
        self._poll_timer.timeout.connect(self._poll_status)
        self._poll_timer.start(50)  # 50ms 轮询

    def _poll_status(self):
        """主线程轮询: 更新进度，检测完成."""
        # 更新进度条
        if self._progress_pct != self.progress.value():
            self.progress.setValue(self._progress_pct)
            self.progress.setFormat(f"{self._progress_step} %p%")
            self.status_label.setText(self._progress_step)

        # 检测完成
        if self._done_stats is not None or self._done_error is not None:
            self._poll_timer.stop()

            if self._done_error:
                self.progress.setValue(0)
                self.progress.setFormat("失败")
                self.status_label.setText("提取失败")
                self._log(f"❌ 错误: {self._done_error}", error=True)
            elif self._done_stats:
                s = self._done_stats
                self.progress.setValue(100)
                self.progress.setFormat("完成")
                self.status_label.setText(
                    f"✅ 完成 — {s['exported_files']} 文件, {s['total_rows']} 行"
                )
                self._log(f"✅ 提取成功!")
                self._log(f"  节点: {s['node_count']}, 单元: {s['element_count']}")
                self._log(f"  NSET: {s['nset_count']}, ELSET: {s['elset_count']}")
                self._log(f"  输出: {s['exported_files']} 文件, {s['total_rows']} 行")
                self._log(f"  目录: {self.out_edit.text()}")
            else:
                self.progress.setValue(0)
                self.progress.setFormat("无结果")
                self.status_label.setText("无结果")
                self._log("⚠ 提取完成但没有结果", error=True)

            self._reset_ui()

    def _cancel_extraction(self):
        if self._thread and self._thread.is_alive():
            self._thread.cancel()
            self._log("⚠ 已取消", error=True)
            self.progress.setFormat("已取消")
        if hasattr(self, '_poll_timer') and self._poll_timer:
            self._poll_timer.stop()
        self._reset_ui()

    # ---- 自动输出目录 ----
    def _on_inp_changed(self, text: str):
        """INP 文件改变时自动设置输出目录."""
        if self._auto_setting_out:
            return
        if text and os.path.isfile(text) and not self._out_manually_set:
            parent = os.path.dirname(text)
            if parent and parent != self.out_edit.text():
                self._auto_setting_out = True
                self.out_edit.setText(parent)
                self._auto_setting_out = False

    def _on_out_changed(self, text: str):
        """用户手动修改输出目录时标记，防止被覆盖."""
        if self._auto_setting_out:
            return
        if not self._out_manually_set and text and text != "./output":
            self._out_manually_set = True

    # ---- 预分析 ----
    def _start_pre_analysis(self):
        """启动后台预分析."""
        inp_path = self.inp_edit.text().strip()
        dat_path = self.dat_edit.text().strip()

        if not inp_path:
            self._log("请先选择 INP 文件", error=True)
            return
        if not dat_path:
            self._log("请先选择 DAT 文件", error=True)
            return
        if not os.path.exists(inp_path):
            self._log(f"INP 文件不存在: {inp_path}", error=True)
            return
        if not os.path.exists(dat_path):
            self._log(f"DAT 文件不存在: {dat_path}", error=True)
            return

        self.pre_btn.setEnabled(False)
        self.pre_group.setVisible(False)
        self.progress.setRange(0, 0)
        self.progress.setFormat("Pre-analyzing...")
        self.status_label.setText("Parsing INP + DAT...")
        self._log(f"🔍 预分析: {os.path.basename(inp_path)} + {os.path.basename(dat_path)}")

        self._pre_done_data = None
        self._pre_done_error = None

        def on_done(data, error):
            self._pre_done_data = data
            self._pre_done_error = error

        self._pre_thread = PreAnalysisThread(inp_path, dat_path, on_done)
        self._pre_thread.start()

        self._pre_poll_timer = self.QtCore.QTimer()
        self._pre_poll_timer.timeout.connect(self._poll_pre_analysis)
        self._pre_poll_timer.start(50)

    def _poll_pre_analysis(self):
        """轮询预分析完成状态."""
        if self._pre_done_data is not None or self._pre_done_error is not None:
            self._pre_poll_timer.stop()
            self.pre_btn.setEnabled(True)
            self.progress.setRange(0, 100)
            self.progress.setValue(0)
            self.progress.setFormat("")
            self.status_label.setText("Pre-analysis complete")

            if self._pre_done_error:
                self._log(f"预分析失败: {self._pre_done_error}", error=True)
                return

            self._populate_pre_analysis_ui(self._pre_done_data)

    def _populate_pre_analysis_ui(self, data: PreAnalysisData):
        """用预分析结果填充 UI."""
        Q = self.Qt

        # 清空旧内容
        self._clear_layout(self.pre_scroll_layout)
        self._nset_checkboxes.clear()
        self._elset_checkboxes.clear()

        # 摘要
        summary_parts = [
            f"Job: {data.job_name}",
            f"Nodes: {data.node_count}",
            f"Elements: {data.element_count}",
            f"Node Sets: {len(data.nsets)}",
            f"Element Sets: {len(data.elsets)}",
            f"Steps: {len(data.steps)}",
        ]
        if data.analysis_type:
            summary_parts.append(f"Type: {data.analysis_type}")
        if data.completion_status:
            summary_parts.append(f"Status: {data.completion_status}")
        self.pre_summary_label.setText("  ".join(summary_parts))

        # 步骤信息
        if data.steps:
            step_group = Q.QGroupBox("📊 Steps & Increments")
            step_layout = Q.QVBoxLayout(step_group)
            for sname, incs in data.steps.items():
                stype = data.step_types.get(sname, "")
                inc_str = ", ".join(str(i) for i in incs)
                step_layout.addWidget(Q.QLabel(f"  {sname} ({stype}): Increments [{inc_str}]"))
            self.pre_scroll_layout.addWidget(step_group)

        # 节点集
        if data.nsets:
            nset_group = Q.QGroupBox(f"🔵 Node Sets ({len(data.nsets)})")
            nset_layout = Q.QGridLayout(nset_group)
            nset_layout.setSpacing(2)
            sorted_nsets = sorted(data.nsets.items(), key=lambda x: x[0].lower())
            for i, (name, count) in enumerate(sorted_nsets):
                cb = Q.QCheckBox(f"{name}  ({count})")
                cb.setChecked(True)
                self._nset_checkboxes[name] = cb
                nset_layout.addWidget(cb, i // 5, i % 5)
            self.pre_scroll_layout.addWidget(nset_group)

        # 单元集
        if data.elsets:
            elset_group = Q.QGroupBox(f"🟢 Element Sets ({len(data.elsets)})")
            elset_layout = Q.QGridLayout(elset_group)
            elset_layout.setSpacing(2)
            sorted_elsets = sorted(data.elsets.items(), key=lambda x: x[0].lower())
            for i, (name, count) in enumerate(sorted_elsets):
                cb = Q.QCheckBox(f"{name}  ({count})")
                cb.setChecked(True)
                self._elset_checkboxes[name] = cb
                elset_layout.addWidget(cb, i // 5, i % 5)
            self.pre_scroll_layout.addWidget(elset_group)

        # 简单单元连接性
        if data.element_connectivity:
            conn_group = Q.QGroupBox(
                f"🔗 Simple Element Connectivity (Spring/Truss/Beam) "
                f"({len(data.element_connectivity)} elements)"
            )
            conn_layout = Q.QGridLayout(conn_group)
            conn_layout.setSpacing(3)

            # 表头
            conn_layout.addWidget(Q.QLabel("<b>Elem ID</b>"), 0, 0)
            conn_layout.addWidget(Q.QLabel("<b>Type</b>"), 0, 1)
            conn_layout.addWidget(Q.QLabel("<b>Node A (x, y, z)</b>"), 0, 2)
            conn_layout.addWidget(Q.QLabel("<b>Node B (x, y, z)</b>"), 0, 3)

            sorted_conn = sorted(data.element_connectivity.items())[:100]
            for row, (elem_id, info) in enumerate(sorted_conn, start=1):
                etype = info["type"]
                n1, n2 = info["nodes"]
                c1, c2 = info["coords"]
                c1_str = f"({c1[0]:.3f}, {c1[1]:.3f}, {c1[2]:.3f})"
                c2_str = f"({c2[0]:.3f}, {c2[1]:.3f}, {c2[2]:.3f})"

                conn_layout.addWidget(Q.QLabel(str(elem_id)), row, 0)
                conn_layout.addWidget(Q.QLabel(etype), row, 1)
                conn_layout.addWidget(Q.QLabel(f"{n1} {c1_str}"), row, 2)
                conn_layout.addWidget(Q.QLabel(f"{n2} {c2_str}"), row, 3)

            if len(data.element_connectivity) > 100:
                conn_layout.addWidget(
                    Q.QLabel(f"... and {len(data.element_connectivity) - 100} more"),
                    len(sorted_conn) + 1, 0, 1, 4,
                )

            self.pre_scroll_layout.addWidget(conn_group)

        self.pre_scroll_layout.addStretch()

        self.pre_group.setVisible(True)
        self._log(f"预分析完成: {data.node_count} nodes, {data.element_count} elements, "
                  f"{len(data.nsets)} nsets, {len(data.elsets)} elsets, {len(data.steps)} steps")

    @staticmethod
    def _clear_layout(layout):
        """递归清空布局中的所有 widget."""
        if layout is None:
            return
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
            elif item.layout() is not None:
                MainWindow._clear_layout(item.layout())

    def _toggle_all_sets(self, checked: bool):
        """全选/全不选所有集合."""
        for cb in self._nset_checkboxes.values():
            cb.setChecked(checked)
        for cb in self._elset_checkboxes.values():
            cb.setChecked(checked)

    def _apply_sets_to_filters(self):
        """将选中的集合名称写入筛选输入框."""
        checked_nsets = [name for name, cb in self._nset_checkboxes.items() if cb.isChecked()]
        checked_elsets = [name for name, cb in self._elset_checkboxes.items() if cb.isChecked()]

        self.nsets_edit.setText(", ".join(checked_nsets))
        self.elsets_edit.setText(", ".join(checked_elsets))
        self._log(f"已应用: {len(checked_nsets)} NSETs, {len(checked_elsets)} ELSETs 到筛选条件")

    def _reset_ui(self):
        self.run_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)

    def _log(self, msg: str, error: bool = False):
        timestamp = datetime.now().strftime("%H:%M:%S")
        prefix = "❌" if error else "  "
        self.log_text.append(f"[{timestamp}] {prefix} {msg}")
        # 自动滚动到底部
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())


# ============================================================
# 入口
# ============================================================

def main():
    """adb-gui 命令入口."""
    run_gui()


if __name__ == "__main__":
    main()

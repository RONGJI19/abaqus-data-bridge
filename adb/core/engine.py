"""主提取引擎 — 编排整个提取流程."""

import os
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional

from ..models.inp_model import InpModel
from ..models.dat_model import DatResults
from ..models.extraction_config import ExtractionConfig
from ..parsers.inp_parser import parse_inp
from ..parsers.dat_parser import parse_dat
from ..exporters.csv_exporter import CsvExporter
from ..utils.progress import create_progress
from ..utils.logging import CrashProofLogger
from .matcher import match_results
from .statistics import ExtractionSummary

logger = logging.getLogger(__name__)


class ExtractionEngine:
    """主提取引擎.

    编排 INP 解析 → DAT 解析 → 数据匹配 → CSV 导出 的完整流程.
    """

    def __init__(self, config: ExtractionConfig,
                 debug_log: Optional[CrashProofLogger] = None):
        """初始化引擎.

        Args:
            config: 提取配置
            debug_log: 可选的崩溃安全诊断日志记录器
        """
        self.config = config
        self._debug_log = debug_log
        self.model: Optional[InpModel] = None
        self.results: Optional[DatResults] = None
        self.matched: Dict[str, List[Dict[str, Any]]] = {}
        self.summary = ExtractionSummary()

    def run(self) -> Dict[str, Any]:
        """执行完整的提取流程.

        Returns:
            包含提取统计信息的字典
        """
        dl = self._debug_log  # 本地别名

        # --- 启动调试日志 ---
        if dl:
            config_summary = self._build_config_summary()
            dl.start(config_summary)

        try:
            # Step 1: 解析 INP
            if dl:
                dl.log_phase_enter("Parse INP")
            logger.info(f"Parsing INP file: {self.config.inp_file}")
            with create_progress(desc="Parsing INP", total=1, unit="file",
                                 enabled=self.config.advanced.log_level != "DEBUG") as pbar:
                self.model = parse_inp(self.config.inp_file,
                                       debug_log=dl)
                pbar.update(1)
            if dl:
                dl.log_phase_exit("Parse INP",
                                  f"{self.model.get_node_count()} nodes, "
                                  f"{self.model.get_element_count()} elements, "
                                  f"{self.model.get_nset_count()} nsets, "
                                  f"{self.model.get_elset_count()} elsets")

            # Step 2: 解析 DAT
            if dl:
                dl.log_phase_enter("Parse DAT")
            logger.info(f"Parsing DAT file: {self.config.dat_file}")
            with create_progress(desc="Parsing DAT", total=1, unit="file",
                                 enabled=self.config.advanced.log_level != "DEBUG") as pbar:
                self.results = parse_dat(self.config.dat_file,
                                         debug_log=dl)
                pbar.update(1)
                dat_size = os.path.getsize(self.config.dat_file)
                logger.info(f"DAT file size: {dat_size / 1024:.0f} KB")
            if dl:
                dl.log_phase_exit("Parse DAT",
                                  f"{len(self.results.steps)} steps, "
                                  f"status={self.results.completion_status}")

            # Step 3: 检查分析完整性
            if dl:
                dl.log_phase_enter("Check Completion")
            if (self.config.advanced.detect_incomplete and
                    not self.results.is_completed()):
                self.summary.warnings.append(
                    f"Analysis may be incomplete: {self.results.completion_status}"
                )
                logger.warning(
                    f"Analysis may be incomplete! Status: "
                    f"{self.results.completion_status}"
                )
                if dl:
                    dl.log(f"Analysis incomplete: {self.results.completion_status}",
                           "WARN")
            if dl:
                dl.log_phase_exit("Check Completion")

            # Step 4: 匹配数据
            if dl:
                dl.log_phase_enter("Match Results")
            logger.info("Matching results to model sets...")
            self.matched = match_results(self.model, self.results,
                                         self.config, debug_log=dl)
            logger.info(f"Matched {len(self.matched)} result groups")
            if dl:
                dl.log_phase_exit("Match Results",
                                  f"{len(self.matched)} groups")

            # Step 5: 导出 CSV
            if dl:
                dl.log_phase_enter("Export CSV")
            logger.info(f"Exporting to: {self.config.output_dir}")
            exporter = CsvExporter(self.config.output)
            with create_progress(desc="Exporting CSV", total=len(self.matched),
                                 unit="file",
                                 enabled=self.config.advanced.log_level != "DEBUG") as pbar:
                export_count = exporter.export_all(
                    self.matched,
                    self.config.output_dir,
                    job_name=self.config.job_name or self.results.job_name,
                    step_increment_info=self._build_step_info(),
                    progress_callback=lambda: pbar.update(1),
                    debug_log=dl,
                )
            logger.info(f"Exported {export_count} CSV files")
            if dl:
                dl.log_phase_exit("Export CSV",
                                  f"{export_count} files")

            # Step 6: 收集统计
            for group_name, records in self.matched.items():
                self.summary.add_group(group_name, records)

            # Step 7: 返回统计摘要
            stats = self.get_stats()
            stats["exported_files"] = export_count

            if dl:
                dl.log(f"EXTRACTION COMPLETE: {export_count} files, "
                       f"{stats['total_rows']} rows", "INFO")
                dl.close()

            return stats

        except Exception as e:
            if dl:
                dl.exception(e)
                dl.close()
            raise

    def _build_step_info(self) -> Dict[str, str]:
        """构建 step/increment 信息用于元数据."""
        info = {}
        if self.results:
            for step_name, step in self.results.steps.items():
                for inc_num in step.increments:
                    inc = step.increments[inc_num]
                    key = f"{step_name}_incr{inc_num}"
                    info[key] = (
                        f"Step: {step_name}, Increment: {inc_num}, "
                        f"Step Time: {inc.step_time:.6E}"
                    )
        return info

    def _build_config_summary(self) -> str:
        """构建配置摘要用于调试日志头."""
        lines = []
        lines.append(f"INP: {self.config.inp_file}")
        lines.append(f"DAT: {self.config.dat_file}")
        lines.append(f"Output: {self.config.output_dir}")
        # 文件大小
        try:
            inp_size = os.path.getsize(self.config.inp_file)
            lines.append(f"INP size: {inp_size / 1024:.0f} KB")
        except OSError:
            pass
        try:
            dat_size = os.path.getsize(self.config.dat_file)
            lines.append(f"DAT size: {dat_size / 1024:.0f} KB")
        except OSError:
            pass
        # 筛选条件
        filt = self.config.filters
        if filt.node_sets:
            lines.append(f"NSETs: {', '.join(filt.node_sets)}")
        if filt.element_sets:
            lines.append(f"ELSETs: {', '.join(filt.element_sets)}")
        if filt.steps:
            lines.append(f"Steps: {', '.join(filt.steps)}")
        if filt.increments:
            lines.append(f"Increments: {filt.increments}")
        if filt.bbox:
            lines.append(f"BBox: {filt.bbox}")
        return "\n".join(lines)

    def get_stats(self) -> Dict[str, Any]:
        """获取提取统计信息."""
        stats = {
            "job_name": self.config.job_name or "",
            "inp_file": self.config.inp_file,
            "dat_file": self.config.dat_file,
            "analysis_status": "",
            "node_count": 0,
            "element_count": 0,
            "nset_count": 0,
            "elset_count": 0,
            "step_count": 0,
            "result_groups": 0,
            "total_rows": 0,
        }

        if self.model:
            stats.update({
                "node_count": self.model.get_node_count(),
                "element_count": self.model.get_element_count(),
                "nset_count": self.model.get_nset_count(),
                "elset_count": self.model.get_elset_count(),
            })

        if self.results:
            stats.update({
                "analysis_status": self.results.completion_status,
                "step_count": len(self.results.steps),
            })

        stats["result_groups"] = len(self.matched)
        stats["total_rows"] = sum(
            len(records) for records in self.matched.values()
        )

        return stats

    def print_summary(self):
        """打印模型和结果摘要."""
        if self.model:
            print("\n--- INP Model ---")
            print(self.model.summary())
        if self.results:
            print("\n--- DAT Results ---")
            print(self.results.summary())
        print(f"\n--- Matched Groups: {len(self.matched)} ---")
        for key, records in self.matched.items():
            print(f"  {key}: {len(records)} rows")

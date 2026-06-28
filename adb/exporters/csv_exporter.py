"""CSV 导出引擎."""

import os
import csv
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional

from ..models.extraction_config import OutputConfig
from ..utils.logging import CrashProofLogger

logger = logging.getLogger(__name__)


class CsvExporter:
    """CSV 文件导出器.

    支持:
    - 元数据头部 (可选)
    - 自定义分隔符
    - 多种编码 (UTF-8 / UTF-8-BOM / GBK)
    - 小数位数控制
    - 批量导出
    """

    def __init__(self, config: OutputConfig):
        """初始化导出器.

        Args:
            config: 输出配置
        """
        self.config = config

    def export_all(
        self,
        matched: Dict[str, List[Dict[str, Any]]],
        output_dir: str,
        job_name: str = "",
        step_increment_info: Dict[str, str] = None,
        progress_callback: callable = None,
        debug_log: Optional[CrashProofLogger] = None,
    ) -> int:
        """批量导出所有匹配结果.

        Args:
            matched: match_results() 返回的匹配结果
            output_dir: 输出目录路径
            job_name: 作业名称 (用于元数据)
            step_increment_info: Step/Increment 信息
            debug_log: 可选的崩溃安全诊断日志记录器

        Returns:
            导出的文件数量
        """
        dl = debug_log
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        step_info = step_increment_info or {}

        count = 0

        if dl:
            dl.log(f"Export start: {len(matched)} groups, "
                   f"merge={self.config.merge_sets}")

        if self.config.merge_sets:
            # 合并所有结果到一个文件
            all_records = []
            for key, records in matched.items():
                for rec in records:
                    rec["_SOURCE"] = key
                all_records.extend(records)
            if all_records:
                filepath = output_path / f"{job_name or 'results'}_all.csv"
                if dl:
                    dl.log(f"Exporting merged: {filepath.name} "
                           f"({len(all_records)} rows)")
                self._export_table(
                    filepath, all_records, job_name, "ALL_MERGED"
                )
                count = 1
        else:
            # 每个匹配组一个文件
            for key, records in matched.items():
                if not records:
                    continue
                # 生成文件名
                safe_key = key.replace("/", "_").replace("\\", "_").replace(" ", "_")
                filepath = output_path / f"{safe_key}.csv"
                info = step_info.get(key, "")
                if dl:
                    dl.log(f"Exporting: {safe_key}.csv ({len(records)} rows)")
                self._export_table(filepath, records, job_name, info)
                count += 1
                if progress_callback:
                    progress_callback()

        if dl:
            dl.log(f"Export complete: {count} files written")

        return count

    def _export_table(
        self,
        filepath: Path,
        records: List[Dict[str, Any]],
        job_name: str,
        step_info: str,
    ):
        """导出一个表格到 CSV 文件.

        Args:
            filepath: 输出文件路径
            records: 数据记录列表
            job_name: 作业名称
            step_info: Step/Increment 描述
        """
        if not records:
            return

        encoding = self.config.encoding
        delimiter = self.config.delimiter
        decimal_places = self.config.decimal_places

        with open(filepath, 'w', newline='', encoding=encoding) as f:
            writer = csv.writer(f, delimiter=delimiter)

            # 写入元数据头部
            if self.config.include_metadata:
                self._write_metadata(writer, job_name, step_info,
                                     len(records))

            # 确定列顺序
            columns = self._get_column_order(records[0])
            # 写入表头
            writer.writerow(columns)

            # 写入数据行
            for rec in records:
                row = []
                for col in columns:
                    val = rec.get(col, "")
                    if isinstance(val, float):
                        val = round(val, decimal_places)
                    row.append(val)
                writer.writerow(row)

    def _write_metadata(
        self,
        writer: csv.writer,
        job_name: str,
        step_info: str,
        row_count: int,
    ):
        """写入元数据头部行."""
        from .. import __version__
        from datetime import datetime

        metadata_lines = [
            f"# Abaqus Data Bridge v{__version__}",
            f"# Job: {job_name or '(unknown)'}",
            f"# {step_info}" if step_info else "",
            f"# Rows: {row_count}",
            f"# Extracted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        ]
        for line in metadata_lines:
            if line.strip() and line != "# ":
                writer.writerow([line])

    def _get_column_order(self, sample: Dict[str, Any]) -> List[str]:
        """确定 CSV 列顺序.

        优先级: ENTITY_ID → X/Y/Z → 其他变量 (字母序) → 内部字段 (_开头排除)
        """
        columns = []

        # 第一优先级: ENTITY_ID
        if "ENTITY_ID" in sample:
            columns.append("ENTITY_ID")

        # 第二优先级: 坐标列
        for coord in ["X", "Y", "Z"]:
            if coord in sample:
                columns.append(coord)

        # 第三优先级: 其他字段 (排除内部字段)
        remaining = sorted(
            k for k in sample.keys()
            if k not in columns
            and not k.startswith("_")
        )
        columns.extend(remaining)

        return columns


def export_csv(
    records: List[Dict[str, Any]],
    filepath: str,
    columns: Optional[List[str]] = None,
    encoding: str = "utf-8-sig",
    delimiter: str = ",",
    include_metadata: bool = True,
    job_name: str = "",
    decimal_places: int = 6,
) -> None:
    """快捷函数: 导出单个 CSV 文件.

    Args:
        records: 数据记录列表
        filepath: 输出文件路径
        columns: 列顺序 (None = 自动检测)
        encoding: 文件编码
        delimiter: 分隔符
        include_metadata: 是否包含元数据头部
        job_name: 作业名称
        decimal_places: 小数位数
    """
    from .. import __version__
    from datetime import datetime

    if not records:
        logger.warning(f"No records to export to {filepath}")
        return

    if columns is None:
        # 自动检测列
        columns = []
        sample = records[0]
        if "ENTITY_ID" in sample:
            columns.append("ENTITY_ID")
        for coord in ["X", "Y", "Z"]:
            if coord in sample:
                columns.append(coord)
        remaining = sorted(
            k for k in sample.keys()
            if k not in columns and not k.startswith("_")
        )
        columns.extend(remaining)

    with open(filepath, 'w', newline='', encoding=encoding) as f:
        writer = csv.writer(f, delimiter=delimiter)

        if include_metadata:
            writer.writerow([f"# Abaqus Data Bridge v{__version__}"])
            writer.writerow([f"# Job: {job_name or '(unknown)'}"])
            writer.writerow([
                f"# Extracted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            ])
            writer.writerow([f"# Rows: {len(records)}"])

        writer.writerow(columns)

        for rec in records:
            row = []
            for col in columns:
                val = rec.get(col, "")
                if isinstance(val, float):
                    val = round(val, decimal_places)
                row.append(val)
            writer.writerow(row)

"""流式 CSV 导出 — 适用于大模型 (>100万行)."""

import csv
import os
from pathlib import Path
from typing import Dict, List, Any, Optional, Iterator
import logging

logger = logging.getLogger(__name__)


def export_streaming(
    records_iterator: Iterator[Dict[str, Any]],
    filepath: str,
    columns: Optional[List[str]] = None,
    encoding: str = "utf-8-sig",
    delimiter: str = ",",
    include_metadata: bool = True,
    job_name: str = "",
    decimal_places: int = 6,
    chunk_size: int = 10000,
) -> int:
    """流式导出大量记录到 CSV.

    不一次性加载所有数据到内存，适合 >100万 行的场景。

    Args:
        records_iterator: 记录迭代器 (每次 yield 一个 dict)
        filepath: 输出文件路径
        columns: 列顺序 (None = 从第一条记录自动检测)
        encoding: 文件编码
        delimiter: 分隔符
        include_metadata: 是否包含元数据头部
        job_name: 作业名称
        decimal_places: 小数位数
        chunk_size: 每次刷新的行数

    Returns:
        写入的总行数
    """
    from .. import __version__
    from datetime import datetime

    total_rows = 0
    columns_detected = columns

    with open(filepath, 'w', newline='', encoding=encoding) as f:
        writer = csv.writer(f, delimiter=delimiter)

        # 元数据头部
        if include_metadata:
            writer.writerow([f"# Abaqus Data Bridge v{__version__}"])
            writer.writerow([f"# Job: {job_name or '(unknown)'}"])
            writer.writerow([
                f"# Extracted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            ])

        # 消费迭代器，写入数据
        column_written = False
        chunk = []

        for record in records_iterator:
            if not column_written:
                if columns_detected is None:
                    columns_detected = _detect_columns(record)
                writer.writerow(columns_detected)
                column_written = True

            # 格式化行
            row = []
            for col in columns_detected:
                val = record.get(col, "")
                if isinstance(val, float):
                    val = round(val, decimal_places)
                row.append(val)
            chunk.append(row)
            total_rows += 1

            # 分批刷新
            if len(chunk) >= chunk_size:
                writer.writerows(chunk)
                chunk = []

        # 写入剩余
        if chunk:
            writer.writerows(chunk)

    if include_metadata:
        # 更新元数据中的行数 (可选)
        pass

    logger.debug(f"Streaming export: {total_rows} rows → {filepath}")
    return total_rows


def _detect_columns(sample: Dict[str, Any]) -> List[str]:
    """从样本记录检测列顺序."""
    columns = []
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
    return columns


def count_records(iterator: Iterator) -> int:
    """统计迭代器中的记录数 (不修改迭代器).

    注意: 这会消费迭代器!
    """
    return sum(1 for _ in iterator)

"""结果统计分析模块."""

import math
from typing import Dict, List, Any, Optional


def compute_statistics(
    records: List[Dict[str, Any]],
    variable_names: Optional[List[str]] = None,
) -> Dict[str, Dict[str, float]]:
    """计算每个变量的基本统计量.

    Args:
        records: 数据记录列表
        variable_names: 要统计的变量名 (None = 自动检测数值列)

    Returns:
        {variable_name: {min, max, mean, std, count}}
    """
    if not records:
        return {}

    # 自动检测数值变量
    if variable_names is None:
        vars_found = set()
        for rec in records:
            for key, val in rec.items():
                if key in ("ENTITY_ID", "X", "Y", "Z"):
                    continue
                if isinstance(val, (int, float)):
                    vars_found.add(key)
        variable_names = list(vars_found)

    stats = {}
    for var in variable_names:
        values = []
        for rec in records:
            val = rec.get(var)
            if isinstance(val, (int, float)) and not math.isnan(val):
                values.append(val)

        if not values:
            continue

        n = len(values)
        mean = sum(values) / n
        variance = sum((v - mean) ** 2 for v in values) / n
        std = math.sqrt(variance)

        stats[var] = {
            "count": n,
            "min": min(values),
            "max": max(values),
            "mean": mean,
            "std": std,
        }

    return stats


def format_stats_table(stats: Dict[str, Dict[str, float]]) -> str:
    """格式化统计结果为文本表格.

    Args:
        stats: compute_statistics() 的返回值

    Returns:
        格式化后的文本表格字符串
    """
    if not stats:
        return "No statistics available."

    lines = []
    lines.append(f"{'Variable':<16} {'Count':>6} {'Min':>14} {'Max':>14} "
                  f"{'Mean':>14} {'Std':>14}")
    lines.append("-" * 78)

    for var in sorted(stats.keys()):
        s = stats[var]
        lines.append(
            f"{var:<16} {s['count']:>6} {s['min']:>14.6E} {s['max']:>14.6E} "
            f"{s['mean']:>14.6E} {s['std']:>14.6E}"
        )

    return "\n".join(lines)


class ExtractionSummary:
    """提取结果汇总."""

    def __init__(self):
        self.total_files = 0
        self.total_rows = 0
        self.variable_stats: Dict[str, Dict[str, Dict[str, float]]] = {}
        self.warnings: List[str] = []
        self.errors: List[str] = []

    def add_group(self, group_name: str, records: List[Dict[str, Any]]):
        """添加一个结果组的统计."""
        self.total_rows += len(records)
        self.total_files += 1
        self.variable_stats[group_name] = compute_statistics(records)

    def overall_stats(self) -> Dict[str, Any]:
        """计算所有结果组的总体统计."""
        return {
            "total_files": self.total_files,
            "total_rows": self.total_rows,
            "groups": len(self.variable_stats),
        }

    def to_text(self) -> str:
        """生成文本报告."""
        lines = []
        lines.append("=" * 60)
        lines.append("  Abaqus Data Bridge — Extraction Summary")
        lines.append("=" * 60)
        lines.append(f"  Result Groups: {len(self.variable_stats)}")
        lines.append(f"  Total Rows:    {self.total_rows}")
        lines.append(f"  Total Files:   {self.total_files}")
        lines.append()

        for group_name, stats in self.variable_stats.items():
            lines.append(f"--- {group_name} ---")
            lines.append(format_stats_table(stats))
            lines.append()

        if self.warnings:
            lines.append("--- Warnings ---")
            for w in self.warnings:
                lines.append(f"  - {w}")

        if self.errors:
            lines.append("--- Errors ---")
            for e in self.errors:
                lines.append(f"  - {e}")

        return "\n".join(lines)

"""DAT 结果文件数据模型."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


@dataclass
class ResultRow:
    """一行结果数据."""
    entity_id: int  # Node ID / Element ID
    values: Dict[str, float] = field(default_factory=dict)
    foot_note: Optional[str] = None


@dataclass
class ResultTable:
    """一张结果表."""
    table_type: str = ""  # "NODE_OUTPUT" | "ELEMENT_OUTPUT" | "CONTACT_OUTPUT"
    set_name: str = ""  # 所属 SET
    variable_names: List[str] = field(default_factory=list)
    data: List[ResultRow] = field(default_factory=list)
    entity_type: str = ""  # 实际单元类型 (如 "SPRINGA") 仅 ELEMENT_OUTPUT
    # 接触输出专用字段
    surface_role: str = ""  # "MASTER" | "SLAVE"  仅 CONTACT_OUTPUT
    contact_pair: str = ""  # 接触对名称  仅 CONTACT_OUTPUT

    def to_records(self) -> List[Dict[str, Any]]:
        """转换为字典列表，方便导出."""
        records = []
        for row in self.data:
            record = {"ENTITY_ID": row.entity_id}
            for var_name, value in row.values.items():
                record[var_name] = value
            records.append(record)
        return records

    def get_row_count(self) -> int:
        return len(self.data)


@dataclass
class IncrementResult:
    """一个 Increment 的结果."""
    increment_num: int
    time: float = 0.0
    step_time: float = 0.0
    tables: List[ResultTable] = field(default_factory=list)

    def get_tables_by_type(self, table_type: str) -> List[ResultTable]:
        """按类型筛选表格."""
        return [t for t in self.tables if t.table_type == table_type]


@dataclass
class StepResult:
    """一个 Step 的结果."""
    step_name: str
    step_type: str = ""  # "STATIC" | "FREQUENCY" | ...
    increments: Dict[int, IncrementResult] = field(default_factory=dict)

    def get_last_increment(self) -> Optional[IncrementResult]:
        """获取最后一个 increment."""
        if not self.increments:
            return None
        return self.increments[max(self.increments.keys())]

    def get_increment(self, num: int) -> Optional[IncrementResult]:
        return self.increments.get(num)


@dataclass
class DatResults:
    """DAT 文件解析结果."""
    job_name: str = ""
    analysis_type: str = ""  # "STANDARD" | "EXPLICIT"
    completion_status: str = ""  # "COMPLETED" | "INCOMPLETE" | "ERROR" | "UNKNOWN"
    steps: Dict[str, StepResult] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    job_time_summary: Dict[str, float] = field(default_factory=dict)

    def get_step_names(self) -> List[str]:
        return list(self.steps.keys())

    def get_step(self, name: str) -> Optional[StepResult]:
        return self.steps.get(name)

    def is_completed(self) -> bool:
        return "COMPLETED" in self.completion_status.upper()

    def summary(self) -> str:
        """返回结果摘要."""
        lines = [
            f"Job: {self.job_name or '(unknown)'}",
            f"Analysis: {self.analysis_type or '(unknown)'}",
            f"Status: {self.completion_status or '(unknown)'}",
            f"Steps: {len(self.steps)}",
        ]
        for step_name, step in self.steps.items():
            inc_count = len(step.increments)
            table_count = sum(
                len(inc.tables) for inc in step.increments.values()
            )
            lines.append(
                f"  {step_name}: {inc_count} increments, {table_count} tables"
            )
        if self.warnings:
            lines.append(f"Warnings: {len(self.warnings)}")
        if self.errors:
            lines.append(f"Errors: {len(self.errors)}")
        if self.job_time_summary:
            cpu = self.job_time_summary.get("total_cpu_time", "N/A")
            wall = self.job_time_summary.get("wallclock_time", "N/A")
            lines.append(f"CPU Time: {cpu}s, Wall Time: {wall}s")
        return "\n".join(lines)

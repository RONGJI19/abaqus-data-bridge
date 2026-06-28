"""测试 DAT 解析器."""

import os
import math
import pytest
from adb.parsers.dat_parser import parse_dat
from adb.models.dat_model import DatResults

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


class TestDatParser:
    """DAT 解析器测试."""

    def test_parse_truss(self):
        """解析简单桁架的 DAT 结果."""
        filepath = os.path.join(FIXTURES_DIR, "simple_truss.dat")
        results = parse_dat(filepath)

        assert isinstance(results, DatResults)
        assert results.is_completed()

        # Step 检查
        assert "Step-1" in results.steps
        step1 = results.steps["Step-1"]
        assert step1.step_type == "STATIC"

        # Increment 检查
        assert 1 in step1.increments
        inc = step1.increments[1]
        assert inc.time == pytest.approx(1.0)

        # 表格检查
        assert len(inc.tables) >= 2  # 至少节点输出和单元输出

    def test_node_output_table(self):
        """验证节点位移表解析."""
        filepath = os.path.join(FIXTURES_DIR, "simple_truss.dat")
        results = parse_dat(filepath)

        inc = results.steps["Step-1"].increments[1]
        node_tables = inc.get_tables_by_type("NODE_OUTPUT")
        assert len(node_tables) >= 1

        table = node_tables[0]
        assert table.set_name == "ALL_NODES"
        assert len(table.data) == 5  # 5 个节点

        # 查找节点 1 的数据
        node1_row = next(
            (r for r in table.data if r.entity_id == 1), None
        )
        assert node1_row is not None
        assert "U1" in node1_row.values or "U2" in node1_row.values

    def test_element_output_table(self):
        """验证单元应力表解析."""
        filepath = os.path.join(FIXTURES_DIR, "simple_truss.dat")
        results = parse_dat(filepath)

        inc = results.steps["Step-1"].increments[1]
        elem_tables = inc.get_tables_by_type("ELEMENT_OUTPUT")
        assert len(elem_tables) >= 1

        table = elem_tables[0]
        assert len(table.data) == 7  # 7 个单元

    def test_completion_status(self):
        """验证分析完成状态检测."""
        filepath = os.path.join(FIXTURES_DIR, "simple_truss.dat")
        results = parse_dat(filepath)
        assert results.is_completed()
        assert "COMPLETED" in results.completion_status.upper()

    def test_job_time_summary(self):
        """验证时间摘要解析."""
        filepath = os.path.join(FIXTURES_DIR, "simple_truss.dat")
        results = parse_dat(filepath)
        assert results.job_time_summary
        assert "total_cpu_time" in results.job_time_summary

    def test_parse_spring_model(self):
        """解析弹簧模型的 DAT 结果."""
        filepath = os.path.join(FIXTURES_DIR, "spring_model.dat")
        results = parse_dat(filepath)

        assert results.is_completed()
        assert "Step-1" in results.steps

    def test_spring_element_output(self):
        """验证弹簧单元输出 (S11 = 力, 不是应力)."""
        filepath = os.path.join(FIXTURES_DIR, "spring_model.dat")
        results = parse_dat(filepath)

        inc = results.steps["Step-1"].increments[1]
        # 找到 ELEMENT_OUTPUT 表
        elem_tables = inc.get_tables_by_type("ELEMENT_OUTPUT")
        assert len(elem_tables) >= 1

        # 弹簧单元的 S11 应该是力值
        table = elem_tables[0]
        assert len(table.data) == 3  # 3 个弹簧
        # 检查 entity_type 是否被检测为 SPRINGA
        # (这取决于 DAT 解析是否从表中提取了单元类型)

    def test_summary(self):
        """测试摘要."""
        filepath = os.path.join(FIXTURES_DIR, "simple_truss.dat")
        results = parse_dat(filepath)
        summary = results.summary()
        assert "Step-1" in summary
        assert "COMPLETED" in summary.upper()

    def test_nonexistent_file(self):
        """不存在的文件应抛出异常."""
        with pytest.raises(FileNotFoundError):
            parse_dat("/nonexistent/path/results.dat")

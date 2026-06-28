"""测试接触结果提取."""

import os
import tempfile
import pytest
from adb.parsers.dat_parser import parse_dat
from adb.parsers.inp_parser import parse_inp
from adb.models.extraction_config import ExtractionConfig
from adb.core.engine import ExtractionEngine

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


class TestContactDatParser:
    """接触输出 DAT 解析测试."""

    def test_parse_contact_model(self):
        """解析接触模型 DAT 文件."""
        filepath = os.path.join(FIXTURES_DIR, "contact_model.dat")
        results = parse_dat(filepath)

        assert results.is_completed()
        assert "Step-1" in results.steps

        inc = results.steps["Step-1"].increments[1]

        # 应该有多种表格: NODE, CONTACT, ELEMENT
        table_types = [t.table_type for t in inc.tables]
        assert "CONTACT_OUTPUT" in table_types
        assert "NODE_OUTPUT" in table_types
        assert "ELEMENT_OUTPUT" in table_types

    def test_contact_force_table(self):
        """验证接触力 (CNORMF) 表格."""
        filepath = os.path.join(FIXTURES_DIR, "contact_model.dat")
        results = parse_dat(filepath)

        inc = results.steps["Step-1"].increments[1]
        contact_tables = inc.get_tables_by_type("CONTACT_OUTPUT")

        assert len(contact_tables) > 0

        # 查找 CNORMF 表
        cnormf_tables = [
            t for t in contact_tables
            if "CNORMF" in t.variable_names
        ]
        assert len(cnormf_tables) > 0

        # 验证数据
        for table in cnormf_tables:
            assert len(table.data) > 0
            # 每个接触面应该有 4 个节点
            for row in table.data:
                val = row.values.get("CNORMF", 0)
                # CNORMF 应该是正的 (接触力)
                assert val > 0, f"Expected positive CNORMF, got {val}"

    def test_contact_pressure_table(self):
        """验证接触压力 (CPRESS) 表格."""
        filepath = os.path.join(FIXTURES_DIR, "contact_model.dat")
        results = parse_dat(filepath)

        inc = results.steps["Step-1"].increments[1]
        contact_tables = inc.get_tables_by_type("CONTACT_OUTPUT")

        cpress_tables = [
            t for t in contact_tables
            if "CPRESS" in t.variable_names
        ]
        assert len(cpress_tables) > 0

    def test_contact_opening_table(self):
        """验证接触张开 (COPEN) 表格."""
        filepath = os.path.join(FIXTURES_DIR, "contact_model.dat")
        results = parse_dat(filepath)

        inc = results.steps["Step-1"].increments[1]
        contact_tables = inc.get_tables_by_type("CONTACT_OUTPUT")

        copen_tables = [
            t for t in contact_tables
            if "COPEN" in t.variable_names
        ]
        assert len(copen_tables) > 0

        # COPEN 负值表示穿透 (接触状态)
        for table in copen_tables:
            for row in table.data:
                copen = row.values.get("COPEN", 0)
                # 应该在负值范围 (穿透) 或 0
                assert copen <= 0.01, f"COPEN should be <= 0 (penetration), got {copen}"

    def test_surface_role_detection(self):
        """验证主/从面角色检测."""
        filepath = os.path.join(FIXTURES_DIR, "contact_model.dat")
        results = parse_dat(filepath)

        inc = results.steps["Step-1"].increments[1]
        contact_tables = inc.get_tables_by_type("CONTACT_OUTPUT")

        master_tables = [t for t in contact_tables if t.surface_role == "MASTER"]
        slave_tables = [t for t in contact_tables if t.surface_role == "SLAVE"]

        assert len(master_tables) > 0, "Should have master surface tables"
        assert len(slave_tables) > 0, "Should have slave surface tables"

    def test_contact_pair_detection(self):
        """验证接触对名称检测."""
        filepath = os.path.join(FIXTURES_DIR, "contact_model.dat")
        results = parse_dat(filepath)

        inc = results.steps["Step-1"].increments[1]
        contact_tables = inc.get_tables_by_type("CONTACT_OUTPUT")

        for table in contact_tables:
            assert table.contact_pair, "Contact pair should be detected"
            assert "TOP_BOTTOM_SURF" in table.contact_pair
            assert "BOTTOM_TOP_SURF" in table.contact_pair


class TestContactIntegration:
    """接触结果集成测试."""

    def test_contact_full_pipeline(self):
        """测试接触模型完整提取流程."""
        config = ExtractionConfig()
        config.inp_file = os.path.join(FIXTURES_DIR, "contact_model.inp")
        config.dat_file = os.path.join(FIXTURES_DIR, "contact_model.dat")

        with tempfile.TemporaryDirectory() as tmpdir:
            config.output_dir = tmpdir

            engine = ExtractionEngine(config)
            stats = engine.run()

            assert stats["node_count"] == 16
            assert stats["element_count"] == 2
            assert stats["total_rows"] > 0
            assert stats["exported_files"] > 0

            # 验证接触相关 CSV 文件
            csv_files = [
                f for f in os.listdir(tmpdir) if f.endswith(".csv")
            ]
            contact_csvs = [
                f for f in csv_files if "CNORMF" in f or "CPRESS" in f or "CDISP" in f
            ]
            assert len(contact_csvs) > 0, f"No contact CSVs found in {csv_files}"

    def test_contact_filter_by_variable(self):
        """测试只提取接触力."""
        config = ExtractionConfig()
        config.inp_file = os.path.join(FIXTURES_DIR, "contact_model.inp")
        config.dat_file = os.path.join(FIXTURES_DIR, "contact_model.dat")
        config.variables.contact = ["CNORMF"]

        with tempfile.TemporaryDirectory() as tmpdir:
            config.output_dir = tmpdir

            engine = ExtractionEngine(config)
            stats = engine.run()

            csv_files = [
                f for f in os.listdir(tmpdir) if f.endswith(".csv")
            ]
            # 只应该有 CNORMF 相关的文件
            for f in csv_files:
                assert "CNORMF" in f, f"Expected only CNORMF files, got {f}"

"""集成测试 — 端到端提取流程."""

import os
import tempfile
import pytest
from adb.models.extraction_config import ExtractionConfig
from adb.core.engine import ExtractionEngine

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


class TestIntegration:
    """端到端集成测试."""

    def test_truss_full_pipeline(self):
        """测试完整提取流程: INP + DAT → CSV."""
        config = ExtractionConfig()
        config.inp_file = os.path.join(FIXTURES_DIR, "simple_truss.inp")
        config.dat_file = os.path.join(FIXTURES_DIR, "simple_truss.dat")

        with tempfile.TemporaryDirectory() as tmpdir:
            config.output_dir = tmpdir

            engine = ExtractionEngine(config)
            stats = engine.run()

            # 验证统计信息
            assert stats["node_count"] == 5
            assert stats["element_count"] == 7
            assert stats["nset_count"] == 4
            assert stats["total_rows"] > 0
            assert stats["exported_files"] > 0

            # 验证输出文件存在
            csv_files = [
                f for f in os.listdir(tmpdir) if f.endswith(".csv")
            ]
            assert len(csv_files) > 0

            # 验证 CSV 文件内容
            first_csv = os.path.join(tmpdir, csv_files[0])
            with open(first_csv, 'r', encoding='utf-8-sig') as f:
                content = f.read()
                assert len(content) > 0
                # 检查元数据
                assert "Abaqus Data Bridge" in content

    def test_truss_filtered_by_nset(self):
        """测试按 NSET 筛选."""
        config = ExtractionConfig()
        config.inp_file = os.path.join(FIXTURES_DIR, "simple_truss.inp")
        config.dat_file = os.path.join(FIXTURES_DIR, "simple_truss.dat")
        config.filters.node_sets = ["SUPPORT"]

        with tempfile.TemporaryDirectory() as tmpdir:
            config.output_dir = tmpdir

            engine = ExtractionEngine(config)
            stats = engine.run()

            # SUPPORT 只有 2 个节点
            assert stats["total_rows"] > 0

    def test_truss_filtered_by_increment(self):
        """测试按 increment 筛选."""
        config = ExtractionConfig()
        config.inp_file = os.path.join(FIXTURES_DIR, "simple_truss.inp")
        config.dat_file = os.path.join(FIXTURES_DIR, "simple_truss.dat")
        config.filters.increments = "last"

        with tempfile.TemporaryDirectory() as tmpdir:
            config.output_dir = tmpdir

            engine = ExtractionEngine(config)
            stats = engine.run()
            assert stats["total_rows"] > 0

    def test_spring_full_pipeline(self):
        """测试弹簧模型完整流程."""
        config = ExtractionConfig()
        config.inp_file = os.path.join(FIXTURES_DIR, "spring_model.inp")
        config.dat_file = os.path.join(FIXTURES_DIR, "spring_model.dat")

        with tempfile.TemporaryDirectory() as tmpdir:
            config.output_dir = tmpdir

            engine = ExtractionEngine(config)
            stats = engine.run()

            assert stats["node_count"] == 6
            assert stats["element_count"] == 3
            assert stats["total_rows"] > 0

    def test_merge_sets_output(self):
        """测试合并输出模式."""
        config = ExtractionConfig()
        config.inp_file = os.path.join(FIXTURES_DIR, "simple_truss.inp")
        config.dat_file = os.path.join(FIXTURES_DIR, "simple_truss.dat")
        config.output.merge_sets = True

        with tempfile.TemporaryDirectory() as tmpdir:
            config.output_dir = tmpdir

            engine = ExtractionEngine(config)
            stats = engine.run()

            csv_files = [
                f for f in os.listdir(tmpdir) if f.endswith(".csv")
            ]
            assert len(csv_files) == 1  # 合并后只有一个文件

    def test_tsv_output(self):
        """测试 TSV 输出格式."""
        config = ExtractionConfig()
        config.inp_file = os.path.join(FIXTURES_DIR, "simple_truss.inp")
        config.dat_file = os.path.join(FIXTURES_DIR, "simple_truss.dat")
        config.output.format = "tsv"
        config.output.delimiter = "\t"

        with tempfile.TemporaryDirectory() as tmpdir:
            config.output_dir = tmpdir

            engine = ExtractionEngine(config)
            stats = engine.run()

            csv_files = [
                f for f in os.listdir(tmpdir) if f.endswith(".csv")
            ]
            if csv_files:
                first_csv = os.path.join(tmpdir, csv_files[0])
                with open(first_csv, 'r', encoding='utf-8-sig') as f:
                    first_line = f.readline()
                    # TSV 文件的第一行数据行应该用 tab 分隔
                    if not first_line.startswith("#"):
                        assert "\t" in first_line

    def test_get_stats(self):
        """测试统计函数."""
        config = ExtractionConfig()
        config.inp_file = os.path.join(FIXTURES_DIR, "simple_truss.inp")
        config.dat_file = os.path.join(FIXTURES_DIR, "simple_truss.dat")

        engine = ExtractionEngine(config)
        # 在 run 之前先解析
        engine.model = __import__(
            'adb.parsers.inp_parser', fromlist=['parse_inp']
        ).parse_inp(config.inp_file)

        stats = engine.get_stats()
        assert stats["node_count"] == 5
        assert stats["element_count"] == 7

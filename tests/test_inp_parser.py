"""测试 INP 解析器."""

import os
import pytest
from adb.parsers.inp_parser import parse_inp
from adb.models.inp_model import InpModel

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


class TestInpParser:
    """INP 解析器测试."""

    def test_parse_truss(self):
        """解析简单桁架模型."""
        filepath = os.path.join(FIXTURES_DIR, "simple_truss.inp")
        model = parse_inp(filepath)

        assert isinstance(model, InpModel)
        assert model.get_node_count() == 5
        assert model.get_element_count() == 7

        # 验证节点坐标
        assert 1 in model.nodes
        assert model.nodes[1].x == 0.0
        assert model.nodes[1].y == 0.0
        assert model.nodes[1].z == 0.0

        assert 3 in model.nodes
        assert model.nodes[3].x == 50.0
        assert model.nodes[3].y == pytest.approx(86.6025)

        # 验证单元
        assert 1 in model.elements
        assert model.elements[1].type == "T2D2"
        assert model.elements[1].connectivity == [1, 2]

        # 验证 NSET
        assert "SUPPORT" in model.nsets
        assert model.nsets["SUPPORT"] == [1, 4]
        assert "TOP_NODES" in model.nsets
        assert model.nsets["TOP_NODES"] == [3, 5]
        assert "MIDDLE" in model.nsets
        assert model.nsets["MIDDLE"] == [2]
        assert "ALL_NODES" in model.nsets

        # 验证 ELSET
        assert "BOTTOM_CHORD" in model.elsets
        assert model.elsets["BOTTOM_CHORD"] == [1, 4]
        assert "TOP_CHORD" in model.elsets
        assert model.elsets["TOP_CHORD"] == [6, 7]
        assert "DIAGONALS" in model.elsets
        assert model.elsets["DIAGONALS"] == [2, 3, 5]

    def test_get_nodes_by_set(self):
        """测试按 Set 获取节点."""
        filepath = os.path.join(FIXTURES_DIR, "simple_truss.inp")
        model = parse_inp(filepath)

        support_nodes = model.get_nodes_by_set("SUPPORT")
        assert support_nodes == [1, 4]

        # 不存在的 Set
        assert model.get_nodes_by_set("NONEXISTENT") == []

    def test_get_elements_by_set(self):
        """测试按 Set 获取单元."""
        filepath = os.path.join(FIXTURES_DIR, "simple_truss.inp")
        model = parse_inp(filepath)

        bottom = model.get_elements_by_set("BOTTOM_CHORD")
        assert bottom == [1, 4]

    def test_get_node_coords(self):
        """测试批量获取坐标."""
        filepath = os.path.join(FIXTURES_DIR, "simple_truss.inp")
        model = parse_inp(filepath)

        coords = model.get_node_coords([1, 3])
        assert len(coords) == 2
        assert coords[0] == (1, 0.0, 0.0, 0.0)
        assert coords[1][0] == 3
        assert coords[1][1] == 50.0

    def test_summary(self):
        """测试摘要."""
        filepath = os.path.join(FIXTURES_DIR, "simple_truss.inp")
        model = parse_inp(filepath)
        summary = model.summary()
        assert "Nodes: 5" in summary
        assert "Elements: 7" in summary

    def test_parse_spring_model(self):
        """解析弹簧模型."""
        filepath = os.path.join(FIXTURES_DIR, "spring_model.inp")
        model = parse_inp(filepath)

        assert model.get_node_count() == 6
        assert model.get_element_count() == 3

        # 验证弹簧单元
        assert 101 in model.elements
        assert model.elements[101].type == "SPRINGA"
        assert model.elements[101].connectivity == [1, 2]

        # 验证 Set
        assert "FIXED" in model.nsets
        assert "LOADED" in model.nsets
        assert "SPRING_SET" in model.elsets
        assert "ALL_SPRINGS" in model.elsets

    def test_nonexistent_file(self):
        """不存在的文件应抛出异常."""
        with pytest.raises(FileNotFoundError):
            parse_inp("/nonexistent/path/model.inp")

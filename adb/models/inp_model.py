"""INP 文件解析数据模型."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


@dataclass
class Node:
    """Abaqus 节点."""
    id: int
    x: float
    y: float
    z: float
    coordinate_system: str = "global"


@dataclass
class Element:
    """Abaqus 单元."""
    id: int
    type: str  # "C3D8R", "S4R", "SPRINGA", etc.
    connectivity: List[int]  # node IDs in order


@dataclass
class Material:
    """材料属性 (简化版)."""
    name: str
    properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Section:
    """截面属性 (简化版)."""
    name: str
    category: str = ""  # "SOLID", "SHELL", "BEAM", etc.
    material: str = ""


@dataclass
class InpModel:
    """INP 文件解析结果."""
    nodes: Dict[int, Node] = field(default_factory=dict)
    elements: Dict[int, Element] = field(default_factory=dict)
    nsets: Dict[str, List[int]] = field(default_factory=dict)
    elsets: Dict[str, List[int]] = field(default_factory=dict)
    materials: Dict[str, Material] = field(default_factory=dict)
    sections: Dict[str, Section] = field(default_factory=dict)
    job_name: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_node_count(self) -> int:
        return len(self.nodes)

    def get_element_count(self) -> int:
        return len(self.elements)

    def get_nset_count(self) -> int:
        return len(self.nsets)

    def get_elset_count(self) -> int:
        return len(self.elsets)

    def get_nodes_by_set(self, nset_name: str) -> List[int]:
        """获取指定 NSET 的节点 ID 列表."""
        return self.nsets.get(nset_name, [])

    def get_elements_by_set(self, elset_name: str) -> List[int]:
        """获取指定 ELSET 的单元 ID 列表."""
        return self.elsets.get(elset_name, [])

    def get_node_coords(self, node_ids: List[int]) -> List[tuple]:
        """批量获取节点坐标. 返回 [(id, x, y, z), ...]."""
        result = []
        for nid in node_ids:
            node = self.nodes.get(nid)
            if node:
                result.append((nid, node.x, node.y, node.z))
        return result

    def summary(self) -> str:
        """返回模型摘要."""
        lines = [
            f"Job: {self.job_name or '(unknown)'}",
            f"Nodes: {self.get_node_count()}",
            f"Elements: {self.get_element_count()}",
            f"Node Sets: {self.get_nset_count()}",
            f"Element Sets: {self.get_elset_count()}",
            f"Materials: {len(self.materials)}",
            f"Sections: {len(self.sections)}",
        ]
        return "\n".join(lines)

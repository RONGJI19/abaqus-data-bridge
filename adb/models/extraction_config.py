"""提取配置数据模型."""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


@dataclass
class FilterConfig:
    """筛选条件配置."""
    node_sets: List[str] = field(default_factory=list)
    element_sets: List[str] = field(default_factory=list)
    steps: List[str] = field(default_factory=list)
    increments: Optional[Any] = None  # "last" | "all" | [1, 3, 5]
    bbox: Optional[List[float]] = None  # [xmin, ymin, zmin, xmax, ymax, zmax]
    set_pattern: Optional[str] = None  # 正则模式
    element_types: List[str] = field(default_factory=list)


@dataclass
class OutputConfig:
    """输出设置配置."""
    format: str = "csv"  # csv | tsv
    encoding: str = "utf-8-sig"
    delimiter: str = ","
    include_metadata: bool = True
    merge_sets: bool = False  # True = 所有 Set 合并到一个文件
    decimal_places: int = 6
    include_node_coords: bool = True


@dataclass
class VariableConfig:
    """提取变量配置."""
    nodal: List[str] = field(default_factory=list)  # ["U", "RF"]
    element: List[str] = field(default_factory=list)  # ["S", "E"]
    contact: List[str] = field(default_factory=list)  # ["CNORMF", "CPRESS", "COPEN"]
    spring: List[str] = field(default_factory=list)  # ["S11", "E11"]
    section: List[str] = field(default_factory=list)  # ["SF"]


@dataclass
class AdvancedConfig:
    """高级选项."""
    coordinate_system: str = "global"
    memory_limit_mb: int = 2048
    detect_incomplete: bool = True
    parallel: bool = False
    log_level: str = "INFO"


@dataclass
class ExtractionConfig:
    """完整的提取配置."""
    # Job 信息
    job_name: str = ""
    inp_file: str = ""
    dat_file: str = ""
    output_dir: str = "./output"

    # 子配置
    variables: VariableConfig = field(default_factory=VariableConfig)
    filters: FilterConfig = field(default_factory=FilterConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    advanced: AdvancedConfig = field(default_factory=AdvancedConfig)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExtractionConfig":
        """从字典创建配置 (支持 YAML 解析后的 dict)."""
        job = data.get("job", {})
        extraction = data.get("extraction", {})
        var_data = extraction.get("variables", {})
        filt_data = extraction.get("filters", {})
        out_data = extraction.get("output", {})
        adv_data = extraction.get("advanced", {})

        return cls(
            job_name=job.get("name", ""),
            inp_file=job.get("inp_file", ""),
            dat_file=job.get("dat_file", ""),
            output_dir=job.get("output_dir", "./output"),
            variables=VariableConfig(
                nodal=var_data.get("nodal", []),
                element=var_data.get("element", []),
                contact=var_data.get("contact", []),
                spring=var_data.get("spring", []),
                section=var_data.get("section", []),
            ),
            filters=FilterConfig(
                node_sets=filt_data.get("node_sets", []),
                element_sets=filt_data.get("element_sets", []),
                steps=filt_data.get("steps", []),
                increments=filt_data.get("increments"),
                bbox=filt_data.get("bbox"),
                set_pattern=filt_data.get("set_pattern"),
                element_types=filt_data.get("element_types", []),
            ),
            output=OutputConfig(
                format=out_data.get("format", "csv"),
                encoding=out_data.get("encoding", "utf-8-sig"),
                delimiter=out_data.get("delimiter", ","),
                include_metadata=out_data.get("include_metadata", True),
                merge_sets=out_data.get("merge_sets", False),
                decimal_places=out_data.get("decimal_places", 6),
                include_node_coords=out_data.get("include_node_coords", True),
            ),
            advanced=AdvancedConfig(
                coordinate_system=adv_data.get("coordinate_system", "global"),
                memory_limit_mb=adv_data.get("memory_limit_mb", 2048),
                detect_incomplete=adv_data.get("detect_incomplete", True),
                parallel=adv_data.get("parallel", False),
                log_level=adv_data.get("log_level", "INFO"),
            ),
        )

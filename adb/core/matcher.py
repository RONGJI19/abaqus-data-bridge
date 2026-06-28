"""数据匹配器 — 将 DAT 结果与 INP 模型交叉匹配."""

from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path

from ..models.inp_model import InpModel
from ..models.dat_model import DatResults, ResultTable, StepResult, IncrementResult
from ..models.extraction_config import ExtractionConfig, FilterConfig
from ..utils.logging import CrashProofLogger


def _resolve_increments(
    step: StepResult,
    inc_filter: Optional[Any]
) -> List[IncrementResult]:
    """解析 increment 筛选条件.

    Args:
        step: Step 结果
        inc_filter: "last" | "all" | [1, 3, 5] | None

    Returns:
        筛选后的 IncrementResult 列表
    """
    if not step.increments:
        return []

    inc_nums = sorted(step.increments.keys())

    if inc_filter is None or inc_filter == "last":
        return [step.increments[inc_nums[-1]]]
    elif inc_filter == "all":
        return [step.increments[i] for i in inc_nums]
    elif isinstance(inc_filter, list):
        return [step.increments[i] for i in inc_filter if i in step.increments]
    else:
        # 默认返回最后一个
        return [step.increments[inc_nums[-1]]]


def _filter_nodes_by_bbox(
    model: InpModel,
    node_ids: List[int],
    bbox: List[float]
) -> List[int]:
    """用包围盒筛选节点.

    Args:
        model: INP 模型
        node_ids: 待筛选的节点 ID 列表
        bbox: [xmin, ymin, zmin, xmax, ymax, zmax]

    Returns:
        在包围盒内的节点 ID 列表
    """
    if not bbox or len(bbox) != 6:
        return node_ids

    xmin, ymin, zmin, xmax, ymax, zmax = bbox
    result = []
    for nid in node_ids:
        node = model.nodes.get(nid)
        if node and (xmin <= node.x <= xmax and
                     ymin <= node.y <= ymax and
                     zmin <= node.z <= zmax):
            result.append(nid)
    return result


def _get_table_entity_ids(table: ResultTable) -> List[int]:
    """获取表格中所有实体 ID."""
    return [row.entity_id for row in table.data]


def _match_table_to_set(
    table: ResultTable,
    model: InpModel,
    target_ids: Optional[List[int]] = None,
) -> ResultTable:
    """将结果表匹配到指定的 ID 集合.

    Args:
        table: 结果表
        model: INP 模型 (用于查找坐标)
        target_ids: 目标实体 ID 列表，None 表示不过滤

    Returns:
        筛选后的结果表 (新对象)
    """
    if target_ids is None:
        return table

    target_set = set(target_ids)
    filtered_data = [row for row in table.data if row.entity_id in target_set]

    import copy
    new_table = copy.copy(table)
    new_table.data = filtered_data
    return new_table


def _is_table_matching_variable(table: ResultTable, variables: List[str]) -> bool:
    """检查表格是否包含指定的变量."""
    if not variables:
        return True
    table_vars = set(v.upper() for v in table.variable_names)
    req_vars = set(v.upper() for v in variables)
    return bool(table_vars & req_vars)


MatchResult = Dict[str, List[Dict[str, Any]]]
"""匹配结果: {table_label: [records]}"""


def match_results(
    model: InpModel,
    results: DatResults,
    config: ExtractionConfig,
    debug_log: Optional[CrashProofLogger] = None,
) -> MatchResult:
    """匹配 INP 模型和 DAT 结果，生成结构化输出.

    Args:
        model: 解析后的 INP 模型
        results: 解析后的 DAT 结果
        config: 提取配置
        debug_log: 可选的崩溃安全诊断日志记录器

    Returns:
        匹配结果字典: key 为 "{step}_{incr}_{set}_{vartype}", value 为记录列表
    """
    matched: MatchResult = {}
    filt = config.filters
    dl = debug_log

    # 确定要处理的 steps
    target_steps = filt.steps if filt.steps else list(results.steps.keys())

    if dl:
        dl.log(f"Match: {len(target_steps)} steps to process")

    for step_name in target_steps:
        step = results.steps.get(step_name)
        if not step:
            continue

        increments = _resolve_increments(step, filt.increments)

        if dl:
            dl.log(f"  Step {step_name}: {len(increments)} increments, "
                   f"{sum(len(inc.tables) for inc in increments)} tables")

        for inc in increments:
            for table in inc.tables:
                # --- 确定目标实体 ID ---
                target_ids = None

                if table.table_type == "NODE_OUTPUT":
                    # 优先按 node_sets 筛选
                    if filt.node_sets:
                        target_ids = []
                        for ns_name in filt.node_sets:
                            target_ids.extend(model.get_nodes_by_set(ns_name))
                    elif filt.set_pattern:
                        import re
                        pattern = re.compile(filt.set_pattern, re.IGNORECASE)
                        for ns_name, ids in model.nsets.items():
                            if pattern.search(ns_name):
                                target_ids.extend(ids)
                    # 按 bbox 再筛一次
                    if target_ids and filt.bbox:
                        target_ids = _filter_nodes_by_bbox(
                            model, target_ids, filt.bbox
                        )

                elif table.table_type == "ELEMENT_OUTPUT":
                    if filt.element_sets:
                        target_ids = []
                        for es_name in filt.element_sets:
                            target_ids.extend(
                                model.get_elements_by_set(es_name)
                            )
                    elif filt.set_pattern:
                        import re
                        pattern = re.compile(filt.set_pattern, re.IGNORECASE)
                        for es_name, ids in model.elsets.items():
                            if pattern.search(es_name):
                                target_ids.extend(ids)

                elif table.table_type == "CONTACT_OUTPUT":
                    # 接触输出也是基于节点的
                    if filt.node_sets:
                        target_ids = []
                        for ns_name in filt.node_sets:
                            target_ids.extend(model.get_nodes_by_set(ns_name))

                # --- 按变量类型筛选 ---
                table_var_type = _classify_table_variables(table, config)
                if not table_var_type:
                    continue

                # --- 应用筛选 ---
                filtered_table = _match_table_to_set(table, model, target_ids)

                if not filtered_table.data:
                    continue

                # --- 转换为记录列表 ---
                records = filtered_table.to_records()

                # 附上节点坐标 (如果配置要求且是节点输出或接触输出)
                if (config.output.include_node_coords and
                        table.table_type in ("NODE_OUTPUT", "CONTACT_OUTPUT")):
                    for rec in records:
                        nid = rec.get("ENTITY_ID")
                        if nid and nid in model.nodes:
                            node = model.nodes[nid]
                            rec["X"] = node.x
                            rec["Y"] = node.y
                            rec["Z"] = node.z

                # --- 生成 key ---
                set_label = table.set_name or "ALL"
                if table.table_type == "CONTACT_OUTPUT":
                    pair = table.contact_pair or "CONTACT"
                    role = table.surface_role or "UNKNOWN"
                    key = f"{step_name}_incr{inc.increment_num}_{pair}_{role}_{table_var_type}"
                else:
                    key = f"{step_name}_incr{inc.increment_num}_{set_label}_{table_var_type}"

                if key in matched:
                    matched[key].extend(records)
                else:
                    matched[key] = records

    if dl:
        total_rows = sum(len(r) for r in matched.values())
        dl.log(f"Match complete: {len(matched)} groups, {total_rows} total rows")

    return matched


def _classify_table_variables(
    table: ResultTable,
    config: ExtractionConfig,
) -> Optional[str]:
    """根据变量名判断表格类型，返回变量类型标签.

    返回值如: "U", "RF", "S", "E", "CNORMF", "CPRESS", "COPEN", "S11", "SF"
    如果表格不匹配任何请求的变量类型，返回 None.
    """
    table_vars = set(v.upper() for v in table.variable_names)
    cfg = config.variables

    # 判断用户是否配置了任何变量筛选
    has_any_filter = bool(
        cfg.nodal or cfg.element or cfg.contact or cfg.spring or cfg.section
    )
    # 如果没有配置任何筛选，允许所有类型通过
    allow_all = not has_any_filter

    # 节点变量
    displacement_vars = {"U1", "U2", "U3", "UR1", "UR2", "UR3", "U_MAGNITUDE"}
    rf_vars = {"RF1", "RF2", "RF3", "RF_MAGNITUDE", "RF"}

    # 单元变量 — 应力
    stress_vars = {"S11", "S22", "S33", "S12", "S13", "S23", "MISES",
                   "MAXPRINCIPAL", "MIDPRINCIPAL", "MINPRINCIPAL"}
    strain_vars = {"E11", "E22", "E33", "E12", "E13", "E23"}

    # 接触变量
    contact_force_vars = {"CNORMF", "CSHEARF1", "CSHEARF2"}
    contact_stress_vars = {"CPRESS", "CSHEAR1", "CSHEAR2"}
    contact_disp_vars = {"COPEN", "CSLIP1", "CSLIP2", "CSLIPEQ", "CSLIP"}

    # 弹簧变量 (S11 in spring context = force)
    spring_vars = {"S11", "E11"}

    # 截面变量
    section_vars = {"SF1", "SF2", "SF3", "SM1", "SM2", "SM3"}

    # CONTACT_OUTPUT 类型优先按接触变量分类
    if table.table_type == "CONTACT_OUTPUT":
        if table_vars & contact_force_vars:
            if allow_all or _has_any_match(cfg.contact, ["CNORMF"]):
                return "CNORMF"
        if table_vars & contact_stress_vars:
            if allow_all or _has_any_match(cfg.contact, ["CPRESS"]):
                return "CPRESS"
        if table_vars & contact_disp_vars:
            if allow_all or _has_any_match(cfg.contact, ["COPEN", "CSLIP"]):
                return "CDISP"
        return _guess_table_type(table) if allow_all else None

    if table_vars & displacement_vars:
        if allow_all or _has_any_match(cfg.nodal, ["U"]):
            return "U"

    if table_vars & rf_vars:
        if allow_all or _has_any_match(cfg.nodal, ["RF"]):
            return "RF"

    # 弹簧单元优先检查 (独立于 element 配置)
    # 当 entity_type 包含 SPRING 时，S11/E11 表示内力/位移而非应力/应变
    if table_vars & stress_vars:
        if (table.entity_type and
                "SPRING" in table.entity_type.upper()):
            if allow_all or _has_any_match(cfg.spring, ["S11"]):
                return "SPRING_S11"
        if allow_all or _has_any_match(cfg.element, ["S"]):
            return "S"

    if table_vars & strain_vars:
        if (table.entity_type and
                "SPRING" in table.entity_type.upper()):
            if allow_all or _has_any_match(cfg.spring, ["E11"]):
                return "SPRING_E11"
        if allow_all or _has_any_match(cfg.element, ["E"]):
            return "E"

    if table_vars & contact_force_vars:
        if allow_all or _has_any_match(cfg.contact, ["CNORMF"]):
            return "CNORMF"

    if table_vars & contact_stress_vars:
        if allow_all or _has_any_match(cfg.contact, ["CPRESS"]):
            return "CPRESS"

    if table_vars & contact_disp_vars:
        if allow_all or _has_any_match(cfg.contact, ["COPEN", "CSLIP"]):
            return "CDISP"

    if table_vars & section_vars:
        if allow_all or _has_any_match(cfg.section, ["SF", "SM"]):
            return "SF"

    # 如果未配置任何过滤变量，默认返回最可能的类型
    if allow_all:
        return _guess_table_type(table)
    return None


def _has_any_match(config_list: List[str], target_list: List[str]) -> bool:
    """检查配置列表和目标列表是否有交集."""
    config_upper = set(c.upper() for c in config_list)
    target_upper = set(t.upper() for t in target_list)
    return bool(config_upper & target_upper)


def _guess_table_type(table: ResultTable) -> str:
    """当没有配置过滤时，根据表格内容猜测类型."""
    table_vars = set(v.upper() for v in table.variable_names)

    if table_vars & {"U1", "U2", "U3"}:
        return "U"
    elif table_vars & {"RF1", "RF2", "RF3"}:
        return "RF"
    elif table_vars & {"S11", "S22", "S33"}:
        if table.entity_type and "SPRING" in table.entity_type.upper():
            return "SPRING_S11"
        return "S"
    elif table_vars & {"E11", "E22", "E33"}:
        if table.entity_type and "SPRING" in table.entity_type.upper():
            return "SPRING_E11"
        return "E"
    elif table_vars & {"CNORMF"}:
        return "CNORMF"
    elif table_vars & {"CPRESS"}:
        return "CPRESS"
    elif table_vars & {"COPEN"}:
        return "CDISP"
    elif table_vars & {"CSHEARF1", "CSHEARF2"}:
        return "CSHEARF"
    elif table_vars & {"CSLIP1", "CSLIP2"}:
        return "CSLIP"
    elif table_vars & {"SF1", "SF2", "SF3"}:
        return "SF"
    elif table_vars & {"SM1", "SM2", "SM3"}:
        return "SM"
    return "UNKNOWN"

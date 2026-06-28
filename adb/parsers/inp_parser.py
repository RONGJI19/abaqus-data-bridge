"""INP 文件解析器.

解析 Abaqus .inp 文件为 InpModel 数据模型。
使用状态机方法，逐行流式读取，适合大文件。

支持的 Abaqus 关键字:
    *NODE   — 含 NSET 参数及 GENERATE 语法
    *ELEMENT — 含 TYPE 及 ELSET 参数
    *NSET   — 含 NSET 参数及 GENERATE 语法
    *ELSET  — 含 ELSET 参数及 GENERATE 语法
    *HEADING — 提取作业名
    *INCLUDE — 记录警告（不追踪引用文件）

特性:
    - 续行处理（行尾逗号表示下一行为续行，含关键字行）
    - 注释行跳过（** 开头）
    - 流式读取（不自旋整个文件到内存）
    - 健壮的错误处理（跳过格式错误的行，继续解析）
"""

from __future__ import annotations

import logging
import os
from typing import Dict, List, Optional, Tuple

from adb.models.inp_model import Element, InpModel, Node
from adb.utils.fortran import try_parse_int
from adb.utils.logging import CrashProofLogger

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 内部常量
# ---------------------------------------------------------------------------

# 已知关键字 → 对应的数据处理函数（在模块底部绑定）
_DISPATCH: Dict[str, "callable"] = {}


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def _detect_encoding(filepath: str) -> str:
    """检测文件编码。优先使用 chardet，回退到常见编码尝试。

    使用 adb.utils.encoding 模块的统一编码检测函数，
    支持 UTF-8, GBK, cp1252, latin-1 等多种编码。
    """
    from adb.utils.encoding import detect_encoding
    return detect_encoding(filepath)


def _parse_keyword_line(text: str) -> Tuple[str, Dict[str, str]]:
    """解析关键字行（可能已拼接续行），返回 (keyword_name, {param: value})。

    示例:
        '*NODE, NSET=MY_SET'         → ('NODE', {'NSET': 'MY_SET'})
        '*ELEMENT, TYPE=C3D8R, ELSET=S1' → ('ELEMENT', {'TYPE': 'C3D8R', 'ELSET': 'S1'})
        '*NSET, NSET=S1, GENERATE'   → ('NSET', {'NSET': 'S1', 'GENERATE': True})
    """
    content = text.strip()
    if content.startswith("*"):
        content = content[1:]

    parts = [p.strip() for p in content.split(",")]
    keyword = parts[0].upper()
    params: Dict[str, str] = {}

    for part in parts[1:]:
        if not part:
            continue
        if "=" in part:
            key, val = part.split("=", 1)
            params[key.strip().upper()] = val.strip()
        else:
            # 无值标志参数 (GENERATE, UNSORTED 等)
            params[part.strip().upper()] = True

    return keyword, params


def _split_data_values(line: str) -> List[str]:
    """按逗号分割数据行，去除空白，滤掉空串。"""
    return [v.strip() for v in line.split(",") if v.strip() != ""]


def _join_continuations(lines: List[str]) -> List[str]:
    """将续行拼接为完整逻辑行。

    Abaqus 中行尾逗号表示下一行为续行。
    续行间直接拼接（去除换行），然后按逗号分隔时自然得到完整值列表。

    Examples:
        ['1, 2, 3,', '4, 5, 6']  →  ['1, 2, 3,4, 5, 6']
    """
    if not lines:
        return []

    result: List[str] = []
    current = ""

    for line in lines:
        stripped = line.strip()
        if current:
            current += stripped
        else:
            current = stripped

        if current.endswith(","):
            continue  # 等待续行
        else:
            result.append(current)
            current = ""

    if current:
        # 未闭合的续行 —— 去掉末尾逗号
        result.append(current.rstrip(","))

    return result


# ---------------------------------------------------------------------------
# *NODE 数据处理
# ---------------------------------------------------------------------------

def _process_node_simple(
    model: InpModel,
    nset_name: str,
    logical_lines: List[str],
) -> None:
    """处理 *NODE 简单格式：每行 ``node_id, x, y, z``"""
    nset_ids: List[int] = []

    for line in logical_lines:
        parts = _split_data_values(line)
        if len(parts) < 4:
            logger.warning("跳过格式错误的 NODE 行（需要 4 个值）: %s", line)
            continue

        node_id = try_parse_int(parts[0])
        if node_id is None:
            logger.warning("跳过无效节点 ID: '%s'", parts[0])
            continue

        try:
            x = float(parts[1])
            y = float(parts[2])
            z = float(parts[3])
        except (ValueError, IndexError):
            logger.warning("跳过无效节点坐标: %s", line)
            continue

        model.nodes[node_id] = Node(id=node_id, x=x, y=y, z=z)
        nset_ids.append(node_id)

    if nset_name and nset_ids:
        existing = model.nsets.get(nset_name)
        if existing is not None:
            existing.extend(nset_ids)
        else:
            model.nsets[nset_name] = nset_ids


def _process_node_generate(
    model: InpModel,
    nset_name: str,
    logical_lines: List[str],
) -> None:
    """处理 *NODE, GENERATE 格式。

    期望 2-3 个逻辑行::

        first_id, x1, y1, z1
        last_id,  x2, y2, z2
        increment              (可选，默认 1)

    线性插值生成 first_id .. last_id 范围内的节点。
    """
    if len(logical_lines) < 2:
        logger.warning(
            "*NODE GENERATE 需要至少 2 行数据，实际 %d 行", len(logical_lines)
        )
        return

    # ---- 第一行：起点 ----
    parts1 = _split_data_values(logical_lines[0])
    if len(parts1) < 4:
        logger.warning("*NODE GENERATE 第一行格式错误: %s", logical_lines[0])
        return
    first_id = try_parse_int(parts1[0])
    if first_id is None:
        return
    try:
        x1, y1, z1 = float(parts1[1]), float(parts1[2]), float(parts1[3])
    except ValueError:
        logger.warning("*NODE GENERATE 第一行坐标无效: %s", logical_lines[0])
        return

    # ---- 第二行：终点 ----
    parts2 = _split_data_values(logical_lines[1])
    if len(parts2) < 4:
        logger.warning("*NODE GENERATE 第二行格式错误: %s", logical_lines[1])
        return
    last_id = try_parse_int(parts2[0])
    if last_id is None:
        return
    try:
        x2, y2, z2 = float(parts2[1]), float(parts2[2]), float(parts2[3])
    except ValueError:
        logger.warning("*NODE GENERATE 第二行坐标无效: %s", logical_lines[1])
        return

    # ---- 第三行：增量 (可选) ----
    increment = 1
    if len(logical_lines) >= 3:
        inc_val = try_parse_int(logical_lines[2].strip())
        if inc_val is not None and inc_val > 0:
            increment = inc_val

    if last_id < first_id or increment <= 0:
        logger.warning(
            "*NODE GENERATE: 无效范围 (first=%d, last=%d, step=%d)",
            first_id, last_id, increment,
        )
        return

    n_steps = (last_id - first_id) // increment
    nset_ids: List[int] = []

    for i in range(n_steps + 1):
        nid = first_id + i * increment
        t = i / n_steps if n_steps > 0 else 0.0
        x = x1 + (x2 - x1) * t
        y = y1 + (y2 - y1) * t
        z = z1 + (z2 - z1) * t
        model.nodes[nid] = Node(id=nid, x=x, y=y, z=z)
        nset_ids.append(nid)

    if nset_name and nset_ids:
        existing = model.nsets.get(nset_name)
        if existing is not None:
            existing.extend(nset_ids)
        else:
            model.nsets[nset_name] = nset_ids


def _process_node_data(
    model: InpModel,
    params: Dict[str, str],
    data_lines: List[str],
) -> None:
    """处理 *NODE 段数据（调度简单 / GENERATE 两种模式）。"""
    nset_name: str = params.get("NSET", "")
    is_generate = "GENERATE" in params

    logical_lines = _join_continuations(data_lines)

    if is_generate:
        _process_node_generate(model, nset_name, logical_lines)
    else:
        _process_node_simple(model, nset_name, logical_lines)


# ---------------------------------------------------------------------------
# *ELEMENT 数据处理
# ---------------------------------------------------------------------------

def _process_element_data(
    model: InpModel,
    params: Dict[str, str],
    data_lines: List[str],
) -> None:
    """处理 *ELEMENT 段数据。

    每行格式: ``elem_id, n1, n2, n3, ...``
    第一个值为单元 ID，其余为节点连接列表。
    """
    el_type: str = params.get("TYPE", "UNKNOWN")
    elset_name: str = params.get("ELSET", "")

    logical_lines = _join_continuations(data_lines)
    elset_ids: List[int] = []

    for line in logical_lines:
        parts = _split_data_values(line)
        if len(parts) < 2:
            logger.warning("跳过格式错误的 ELEMENT 行: %s", line)
            continue

        elem_id = try_parse_int(parts[0])
        if elem_id is None:
            logger.warning("跳过无效单元 ID: '%s'", parts[0])
            continue

        connectivity: List[int] = []
        for token in parts[1:]:
            nid = try_parse_int(token)
            if nid is not None:
                connectivity.append(nid)

        if not connectivity:
            logger.warning("跳过无有效节点的单元 %s", parts[0])
            continue

        model.elements[elem_id] = Element(
            id=elem_id, type=el_type, connectivity=connectivity
        )
        elset_ids.append(elem_id)

    if elset_name and elset_ids:
        existing = model.elsets.get(elset_name)
        if existing is not None:
            existing.extend(elset_ids)
        else:
            model.elsets[elset_name] = elset_ids


# ---------------------------------------------------------------------------
# *NSET / *ELSET 数据处理
# ---------------------------------------------------------------------------

def _process_set_data(
    model: InpModel,
    params: Dict[str, str],
    data_lines: List[str],
    *,
    set_type: str,  # "NSET" | "ELSET"
) -> None:
    """处理 *NSET 或 *ELSET 段数据。

    支持两种格式:

    * 简单格式（续行支持）::

        1, 2, 3, 4,
        5, 6, 7

    * GENERATE 格式::

        start_id, end_id, step       (step 默认 1)
    """
    param_key = set_type  # "NSET" → params["NSET"], "ELSET" → params["ELSET"]
    set_name: str = params.get(param_key, "")
    if not set_name:
        logger.warning("*%s 缺少 %s 参数", set_type, param_key)
        return

    is_generate = "GENERATE" in params
    logical_lines = _join_continuations(data_lines)

    ids: List[int] = []

    if is_generate:
        for line in logical_lines[:1]:  # GENERATE 只用第一逻辑行
            parts = _split_data_values(line)
            if len(parts) >= 2:
                start = try_parse_int(parts[0])
                end = try_parse_int(parts[1])
                step = try_parse_int(parts[2]) if len(parts) >= 3 else 1
                if start is not None and end is not None:
                    if step is None or step <= 0:
                        step = 1
                    ids.extend(range(start, end + 1, step))
            else:
                logger.warning("*%s GENERATE 格式错误: %s", set_type, line)
    else:
        for line in logical_lines:
            for token in _split_data_values(line):
                nid = try_parse_int(token)
                if nid is not None:
                    ids.append(nid)

    if not ids:
        return

    target: Dict[str, List[int]]
    if set_type == "NSET":
        target = model.nsets
    else:
        target = model.elsets

    existing = target.get(set_name)
    if existing is not None:
        existing.extend(ids)
    else:
        target[set_name] = ids


# ---------------------------------------------------------------------------
# *HEADING 数据处理
# ---------------------------------------------------------------------------

def _process_heading_data(
    model: InpModel,
    _params: Dict[str, str],
    data_lines: List[str],
) -> None:
    """从 *HEADING 段提取作业名（取第一行非空文本）。"""
    for line in data_lines:
        stripped = line.strip()
        if stripped:
            model.job_name = stripped
            return


# ---------------------------------------------------------------------------
# *INCLUDE 处理
# ---------------------------------------------------------------------------

def _process_include(
    _model: InpModel,
    params: Dict[str, str],
    _data_lines: List[str],
) -> None:
    """*INCLUDE — 记录警告，不追踪引用文件。"""
    included = params.get("INPUT", "(未指定)")
    logger.warning("*INCLUDE 不被追踪: %s", included)


# ---------------------------------------------------------------------------
# 调度表
# ---------------------------------------------------------------------------

_DISPATCH = {
    "NODE": _process_node_data,
    "ELEMENT": _process_element_data,
    "NSET": lambda model, params, lines: _process_set_data(
        model, params, lines, set_type="NSET"
    ),
    "ELSET": lambda model, params, lines: _process_set_data(
        model, params, lines, set_type="ELSET"
    ),
    "HEADING": _process_heading_data,
    "INCLUDE": _process_include,
}


# ---------------------------------------------------------------------------
# 公共 API
# ---------------------------------------------------------------------------

def parse_inp(filepath: str, encoding: Optional[str] = None,
              debug_log: Optional[CrashProofLogger] = None) -> InpModel:
    """解析 Abaqus .inp 文件为 InpModel 数据模型。

    使用状态机方法，逐行流式读取，适合大文件。

    Args:
        filepath: .inp 文件路径。
        encoding: 文件编码。``None`` 则自动检测 (utf-8 → cp1252 → latin-1)。
        debug_log: 可选的崩溃安全诊断日志记录器。

    Returns:
        InpModel: 包含节点、单元、集合等解析结果。

    Raises:
        FileNotFoundError: 文件不存在。
        OSError: 读取错误。
    """
    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"INP 文件不存在: {filepath}")

    dl = debug_log  # 本地别名

    # ---- 编码检测 ----
    if encoding is None:
        encoding = _detect_encoding(filepath)
        logger.info("检测到编码: %s", encoding)
        if dl:
            dl.log(f"Encoding detected: {encoding}")

    # ---- 文件大小 ----
    if dl:
        try:
            fsize = os.path.getsize(filepath)
            dl.log(f"INP file size: {fsize / 1024:.0f} KB")
        except OSError:
            pass

    model = InpModel()
    # 默认作业名 = 文件名（不含扩展名）
    model.job_name = os.path.splitext(os.path.basename(filepath))[0]

    # ---- 状态机变量 ----
    state: Optional[str] = None         # 当前关键字 (None = 未知/跳过)
    params: Dict[str, str] = {}         # 当前关键字的参数
    data_lines: List[str] = []          # 当前段的数据行缓冲
    keyword_continuation: Optional[str] = None  # 关键字续行累积文本
    warning_count: int = 0

    # ---- 刷新前一个关键字 ----
    def _flush() -> None:
        nonlocal state, params, data_lines, warning_count
        if state is None:
            return

        handler = _DISPATCH.get(state)
        if handler is not None:
            try:
                handler(model, params, data_lines)
            except Exception:
                logger.exception("处理 *%s 时发生异常，跳过该段", state)
                warning_count += 1
        # 其他未知关键字静默跳过

        state = None
        params = {}
        data_lines = []

    # ---- 主解析循环 ----
    try:
        with open(filepath, "r", encoding=encoding) as fh:
            for raw_line in fh:
                line = raw_line.strip()

                # 空行
                if not line:
                    continue

                # 注释行
                if line.startswith("**"):
                    continue

                # ── 关键字续行累积 ──
                if keyword_continuation is not None:
                    keyword_continuation += line
                    if not line.endswith(","):
                        # 续行结束，处理完整关键字
                        _flush()
                        kw, p = _parse_keyword_line(keyword_continuation)
                        state = kw if kw in _DISPATCH else None
                        params = p
                        data_lines = []
                        keyword_continuation = None
                    continue

                # ── 新关键字行 ──
                if line.startswith("*"):
                    if line.endswith(","):
                        # 关键字行以逗号结尾 → 下一行为续行
                        keyword_continuation = line
                        continue

                    _flush()
                    kw, p = _parse_keyword_line(line)
                    state = kw if kw in _DISPATCH else None
                    params = p
                    data_lines = []
                    continue

                # ── 数据行 ──
                if state is not None:
                    data_lines.append(raw_line.rstrip("\n\r"))

        # 如果文件在关键字续行中结束，尝试处理
        if keyword_continuation is not None:
            _flush()
            kw, p = _parse_keyword_line(keyword_continuation.rstrip(","))
            state = kw if kw in _DISPATCH else None
            params = p
            data_lines = []
            _flush()

        # 处理文件末尾的最后一段
        _flush()

    except UnicodeDecodeError:
        if encoding != "latin-1":
            if dl:
                dl.log(f"UnicodeDecodeError with {encoding}, "
                       f"retrying with latin-1", "WARN")
            logger.info(
                "使用 %s 解码失败，回退到 latin-1 重试", encoding
            )
            return parse_inp(filepath, encoding="latin-1", debug_log=dl)
        raise

    if warning_count:
        logger.info("解析完成，共 %d 个警告", warning_count)
        if dl:
            dl.log(f"INP parse complete: {warning_count} warnings", "WARN")

    if dl:
        dl.log(f"INP parsed: {model.get_node_count()} nodes, "
               f"{model.get_element_count()} elements, "
               f"{model.get_nset_count()} nsets, "
               f"{model.get_elset_count()} elsets")

    return model

"""DAT 结果文件解析器.

解析 Abaqus .dat 打印输出文件为 DatResults 数据模型。
使用状态机逐行解析，支持大文件流式读取。

支持的解析:
    - 分析类型 (STANDARD / EXPLICIT)
    - 完成状态
    - Job 时间摘要
    - Step / Increment 边界
    - NODE OUTPUT 表格 (位移、支反力等)
    - ELEMENT OUTPUT 表格 (应力、应变等)
    - SET 名称提取
"""

from __future__ import annotations

import logging
import os
import re
from typing import Dict, List, Optional, Tuple

from adb.models.dat_model import (
    DatResults, StepResult, IncrementResult,
    ResultTable, ResultRow,
)
from adb.utils.fortran import parse_fortran_float, try_parse_int
from adb.utils.logging import CrashProofLogger
from .version_patterns import compile_output_patterns, normalize_variable_name

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 正则模式
# ---------------------------------------------------------------------------

# Step 开始: "S T E P   1    S T A T I C   A N A L Y S I S"
RE_STEP = re.compile(
    r'S\s+T\s+E\s+P\s+(\d+)\s+(.+)', re.IGNORECASE
)

# Increment: "INCREMENT     1  SUMMARY"
RE_INCREMENT = re.compile(
    r'INCREMENT\s+(\d+)\s+SUMMARY', re.IGNORECASE
)

# 时间值: "TIME       1.0000E+00" / "STEP TIME  1.0000E+00"
RE_TIME = re.compile(r'TIME\s+(.+)', re.IGNORECASE)
RE_STEP_TIME = re.compile(r'STEP\s+TIME\s+(.+)', re.IGNORECASE)

# 表格头部标记
RE_NODE_OUTPUT = re.compile(r'N\s+O\s+D\s+E\s+O\s+U\s+T\s+P\s+U\s+T', re.IGNORECASE)
RE_ELEMENT_OUTPUT = re.compile(
    r'E\s+L\s+E\s+M\s+E\s+N\s+T\s+O\s+U\s+T\s+P\s+U\s+T', re.IGNORECASE
)
RE_CONTACT_OUTPUT = re.compile(
    r'C\s+O\s+N\s+T\s+A\s+C\s+T\s+O\s+U\s+T\s+P\s+U\s+T', re.IGNORECASE
)

# Contact surface description:
# "THE FOLLOWING TABLE IS PRINTED FOR THE MASTER SURFACE XXX OF CONTACT PAIR YYY-ZZZ"
# "THE FOLLOWING TABLE IS PRINTED FOR THE SLAVE SURFACE XXX OF CONTACT PAIR YYY-ZZZ"
RE_CONTACT_SURFACE = re.compile(
    r'THE\s+FOLLOWING\s+TABLE\s+IS\s+PRINTED\s+FOR\s+THE\s+'
    r'(MASTER|SLAVE)\s+SURFACE\s+(\S+)\s+OF\s+CONTACT\s+PAIR\s+(\S+)',
    re.IGNORECASE
)

# SET 名称: "THE FOLLOWING TABLE IS PRINTED FOR ... BELONGING TO NODE SET XXX"
# 或 "THE FOLLOWING TABLE IS PRINTED FOR ELEMENTS BELONGING TO ELEMENT SET XXX"
RE_SET_NAME = re.compile(
    r'(?:NODE|ELEMENT)\s+SET\s+(\S+)', re.IGNORECASE
)

# 数据行检测: 以数字开头 (节点/单元 ID)
RE_DATA_LINE = re.compile(r'^\s*\d+')

# 表头检测: 包含 NODE FOOT-NOTE, ELEMENT FOOT-NOTE 等
RE_HEADER_START = re.compile(
    r'(NODE|ELEMENT)\s+FOOT', re.IGNORECASE
)

# 分析完成
RE_COMPLETED = re.compile(r'THE\s+ANALYSIS\s+HAS\s+BEEN\s+COMPLETED', re.IGNORECASE)
RE_ANALYSIS_COMPLETE = re.compile(r'ANALYSIS\s+COMPLETE', re.IGNORECASE)

# 分析类型
RE_STANDARD = re.compile(r'S\s+T\s+A\s+N\s+D\s+A\s+R\s+D', re.IGNORECASE)
RE_EXPLICIT = re.compile(r'E\s+X\s+P\s+L\s+I\s+C\s+I\s+T', re.IGNORECASE)

# Job 时间摘要
RE_JOB_TIME = re.compile(r'JOB\s+TIME\s+SUMMARY', re.IGNORECASE)
RE_USER_TIME = re.compile(r'USER\s+TIME\s+\(SEC\)\s*=\s*(.+)', re.IGNORECASE)
RE_SYSTEM_TIME = re.compile(r'SYSTEM\s+TIME\s+\(SEC\)\s*=\s*(.+)', re.IGNORECASE)
RE_CPU_TIME = re.compile(r'TOTAL\s+CPU\s+TIME\s+\(SEC\)\s*=\s*(.+)', re.IGNORECASE)
RE_WALLCLOCK = re.compile(r'WALLCLOCK\s+TIME\s+\(SEC\)\s*=\s*(.+)', re.IGNORECASE)

# 子表边界
RE_TABLE_FOR_SET = re.compile(
    r'THE\s+FOLLOWING\s+TABLE\s+IS\s+PRINTED\s+FOR\s+'
    r'(NODES|ELEMENTS)\s+BELONGING\s+TO\s+'
    r'(NODE|ELEMENT)\s+SET\s+(\S+)',
    re.IGNORECASE
)

# 表头中变量名: U1, U2, S11, S22, RF1, etc.
RE_VARIABLE_NAME = re.compile(r'\b([A-Z][A-Z0-9]*)\b')


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


def _normalize_step_type(raw: str) -> str:
    """将带空格的步骤类型标准化.

    "S T A T I C   A N A L Y S I S" → "STATIC"
    "F R E Q U E N C Y" → "FREQUENCY"
    """
    # 去除所有空格
    no_spaces = re.sub(r'\s+', '', raw).upper()
    # 尝试匹配已知类型
    if 'STATIC' in no_spaces:
        return 'STATIC'
    elif 'FREQUENCY' in no_spaces:
        return 'FREQUENCY'
    elif 'BUCKLE' in no_spaces:
        return 'BUCKLE'
    elif 'MODAL' in no_spaces and 'DYNAMIC' in no_spaces:
        return 'MODAL_DYNAMIC'
    elif 'DYNAMIC' in no_spaces and 'EXPLICIT' in no_spaces:
        return 'DYNAMIC_EXPLICIT'
    elif 'DYNAMIC' in no_spaces:
        return 'DYNAMIC'
    elif 'HEAT' in no_spaces and 'TRANSFER' in no_spaces:
        return 'HEAT_TRANSFER'
    elif 'COUPLED' in no_spaces:
        return 'COUPLED'
    else:
        # 简洁形式 (如果已经无空格)
        return no_spaces


def _parse_variables_from_header(header_lines: List[str]) -> List[str]:
    """从表格头部行提取变量名列表.

    表头格式示例:
        NODE FOOT-   U1           U2           UR3          RF1          RF2
             NOTE

    策略: 从第一行提取大写字母开头的变量名，排除已知的非变量词
    (NODE, ELEMENT, FOOT, NOTE, SPRINGA, etc.)
    """
    known_non_vars = {
        'NODE', 'ELEMENT', 'FOOT', 'NOTE', 'SPRINGA', 'SPRING1', 'SPRING2',
        'SPRING', 'DASHPOT', 'GAP', 'ITS', 'BEAM', 'SHELL', 'MEMBRANE',
        'CONTINUUM', 'TRUSS', 'DASHPOTA', 'GAPUNI',
        # SET 描述行中可能出现的常见词
        'THE', 'FOLLOWING', 'TABLE', 'IS', 'PRINTED', 'FOR',
        'NODES', 'ELEMENTS', 'BELONGING', 'TO', 'SET',
        'NODE', 'ELEMENT',
    }

    # 收集所有候选变量名
    candidate_vars: List[str] = []
    for line in header_lines:
        # 跳过明显的描述行: 包含 SET 描述短语的行
        line_descriptions = {'PRINTED', 'BELONGING', 'FOLLOWING', 'TABLE'}
        tokens = line.split()
        # 如果这行包含多个描述词，跳过
        desc_word_count = sum(1 for t in tokens if t.upper() in line_descriptions)
        if desc_word_count >= 2:
            continue
        # 如果行长度超过 60 字符且不包含典型的变量间距模式，可能是描述行
        if len(line) > 60 and '  ' not in line:
            continue

        for token in tokens:
            token_upper = token.upper()
            # 跳过已知非变量词
            if token_upper in known_non_vars:
                continue
            # 变量名特征: 字母开头，至少2个字符，可能包含数字
            # 典型的 Abaqus 变量: U1, S11, RF2, CPRESS, CNORMF, etc.
            if (len(token) >= 2 and
                    token[0].isalpha() and
                    re.match(r'^[A-Za-z][A-Za-z0-9_]*$', token)):
                # 排除纯小数
                try:
                    float(token)
                    continue
                except ValueError:
                    pass
                if token_upper not in candidate_vars:
                    candidate_vars.append(token_upper)

    # 后过滤: 移除长得不像 Abaqus 变量名的 token
    # (太长的单词，可能是描述词)
    variables = [
        v for v in candidate_vars
        if len(v) <= 12  # Abaqus 变量名 <= 12 字符
    ]

    return variables


def _parse_entity_type_from_header(header_lines: List[str]) -> str:
    """从表头检测实体类型 (如 SPRINGA, C3D8R)."""
    # 已知的 Abaqus 变量名 — 这些不是单元类型
    known_variable_patterns = {
        # 位移
        'U1', 'U2', 'U3', 'UR1', 'UR2', 'UR3',
        # 力
        'RF1', 'RF2', 'RF3', 'RF',
        # 应力/应变
        'S11', 'S22', 'S33', 'S12', 'S13', 'S23',
        'E11', 'E22', 'E33', 'E12', 'E13', 'E23',
        'MISES', 'MAXPRINCIPAL', 'MIDPRINCIPAL', 'MINPRINCIPAL',
        'TRESC', 'PRESSURE', 'PEEQ', 'SDEG',
        # 接触
        'CNORMF', 'CSHEARF1', 'CSHEARF2',
        'CPRESS', 'CSHEAR1', 'CSHEAR2',
        'COPEN', 'CSLIP1', 'CSLIP2', 'CSLIPEQ',
        # 截面
        'SF1', 'SF2', 'SF3', 'SM1', 'SM2', 'SM3',
        # 能量等
        'ALLKE', 'ALLIE', 'ALLSE', 'ALLPD', 'ALLCD', 'ALLAE',
        'ETOTAL', 'WKEXT',
    }

    for line in header_lines:
        tokens = line.split()
        for token in tokens:
            token_upper = token.upper()
            if token_upper in known_variable_patterns:
                continue
            # 纯字母类型
            if token_upper in ('SPRINGA', 'SPRING1', 'SPRING2',
                               'DASHPOTA', 'GAPUNI'):
                return token_upper
            # 单元类型: 字母 + 数字混合，且 >= 3 字符 (如 C3D8R, S4R, B31)
            # 实体类型特征是字母和数字交替出现 (C3D8R)，而变量名是
            # 字母前缀 + 数字后缀 (S11, U1) 或纯字母 (CNORMF)
            if (len(token) >= 3 and
                    any(c.isdigit() for c in token) and
                    any(c.isalpha() for c in token)):
                # 检测模式: 数字出现在字母之间 (如 C3D8R) 说明是单元类型
                # 纯字母前缀+数字后缀 (如 S11) 是变量名
                has_digit_between_letters = False
                chars = list(token)
                for i in range(1, len(chars) - 1):
                    if chars[i].isdigit():
                        # 检查前后是否有字母
                        prev_is_alpha = any(
                            chars[j].isalpha()
                            for j in range(max(0, i - 1), i)
                        )
                        next_is_alpha = any(
                            chars[j].isalpha()
                            for j in range(i + 1, min(len(chars), i + 2))
                        )
                        if prev_is_alpha and next_is_alpha:
                            has_digit_between_letters = True
                            break
                if has_digit_between_letters:
                    return token_upper
    return ""


# 多版本模式 (模块加载时编译一次)
_VERSION_PATTERNS = compile_output_patterns()


def _classify_table(header_text: str) -> str:
    """根据头部文本分类表格类型 (支持多版本 Abaqus)."""
    for pattern in _VERSION_PATTERNS["NODE_OUTPUT"]:
        if pattern.search(header_text):
            return "NODE_OUTPUT"
    for pattern in _VERSION_PATTERNS["ELEMENT_OUTPUT"]:
        if pattern.search(header_text):
            return "ELEMENT_OUTPUT"
    for pattern in _VERSION_PATTERNS["CONTACT_OUTPUT"]:
        if pattern.search(header_text):
            return "CONTACT_OUTPUT"
    return "UNKNOWN"


# ---------------------------------------------------------------------------
# 状态机状态
# ---------------------------------------------------------------------------

# 状态枚举
S_SCANNING = "SCANNING"          # 寻找 Step/Increment/Table
S_IN_TABLE_HEADER = "TABLE_HEADER"  # 正在收集表头
S_IN_TABLE_DATA = "TABLE_DATA"     # 正在收集数据行
S_IN_JOB_TIME = "JOB_TIME"        # 正在收集 Job Time Summary


# ---------------------------------------------------------------------------
# 公共 API
# ---------------------------------------------------------------------------

def parse_dat(filepath: str, encoding: Optional[str] = None,
              debug_log: Optional[CrashProofLogger] = None) -> DatResults:
    """解析 Abaqus .dat 结果文件.

    Args:
        filepath: .dat 文件路径
        encoding: 文件编码，None 则自动检测
        debug_log: 可选的崩溃安全诊断日志记录器

    Returns:
        DatResults: 包含所有解析结果

    Raises:
        FileNotFoundError: 文件不存在
    """
    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"DAT 文件不存在: {filepath}")

    dl = debug_log  # 本地别名

    if encoding is None:
        encoding = _detect_encoding(filepath)
        logger.info("检测到编码: %s", encoding)
        if dl:
            dl.log(f"Encoding detected: {encoding}")

    # ---- 文件大小 ----
    if dl:
        try:
            fsize = os.path.getsize(filepath)
            dl.log(f"DAT file size: {fsize / 1024:.0f} KB")
        except OSError:
            pass

    results = DatResults()
    results.job_name = os.path.splitext(os.path.basename(filepath))[0]

    # --- 状态机 ---
    state = S_SCANNING
    current_step: Optional[StepResult] = None
    current_inc: Optional[IncrementResult] = None
    current_table_header_lines: List[str] = []
    current_table_type: str = ""
    current_table_set_name: str = ""
    current_table_data: List[ResultRow] = []
    current_entity_type: str = ""
    current_surface_role: str = ""  # "MASTER" | "SLAVE"  仅 CONTACT_OUTPUT
    current_contact_pair: str = ""  # 接触对名称  仅 CONTACT_OUTPUT

    # 缓冲区 — 在遇到表格头部前可能看到的描述行
    header_buffer: List[str] = []

    def _commit_table():
        """将当前累积的表格保存到当前 increment."""
        nonlocal current_inc, current_table_header_lines, current_table_data
        nonlocal current_table_type, current_table_set_name, current_entity_type
        nonlocal current_surface_role, current_contact_pair

        if not current_table_data or not current_inc:
            current_table_header_lines = []
            current_table_data = []
            return

        # 解析表头获取变量名
        variables = _parse_variables_from_header(current_table_header_lines)
        entity_type = _parse_entity_type_from_header(current_table_header_lines)
        if not entity_type:
            entity_type = current_entity_type

        table = ResultTable(
            table_type=current_table_type or "UNKNOWN",
            set_name=current_table_set_name,
            variable_names=variables,
            data=current_table_data,
            entity_type=entity_type,
            surface_role=current_surface_role,
            contact_pair=current_contact_pair,
        )
        # 将 V0, V1, ... 占位符键映射为真实变量名
        _remap_variable_names(table)
        current_inc.tables.append(table)

        logger.debug(
            "Committed table: type=%s, set=%s, vars=%s, rows=%d, entity=%s,"
            " role=%s, pair=%s",
            table.table_type, table.set_name,
            table.variable_names[:6], len(table.data), table.entity_type,
            table.surface_role, table.contact_pair,
        )

        # 重置
        current_table_header_lines = []
        current_table_data = []
        current_table_set_name = ""
        current_surface_role = ""
        current_contact_pair = ""

    try:
        with open(filepath, "r", encoding=encoding) as fh:
            for raw_line in fh:
                line = raw_line.strip()
                # 保留原始行用于表头收集 (可能有前导空格)
                raw_stripped = raw_line.rstrip("\n\r")

                # --- 全局检测: 分析类型 ---
                if not results.analysis_type:
                    if RE_STANDARD.search(line):
                        results.analysis_type = "STANDARD"
                    elif RE_EXPLICIT.search(line):
                        results.analysis_type = "EXPLICIT"

                # --- 全局检测: 完成状态 ---
                if not results.completion_status:
                    completion_matched = False
                    for pattern in _VERSION_PATTERNS["COMPLETION"]:
                        if pattern.search(line):
                            results.completion_status = "COMPLETED"
                            completion_matched = True
                            break
                    # 兼容旧版 (保留原有逻辑)
                    if not completion_matched:
                        if RE_COMPLETED.search(line):
                            results.completion_status = "COMPLETED"
                        elif RE_ANALYSIS_COMPLETE.search(line):
                            if not results.completion_status:
                                results.completion_status = "COMPLETED"

                # --- 全局检测: JOB TIME SUMMARY ---
                if RE_JOB_TIME.search(line):
                    state = S_IN_JOB_TIME
                    continue

                if state == S_IN_JOB_TIME:
                    # 收集时间信息
                    m = RE_USER_TIME.search(line)
                    if m:
                        results.job_time_summary["user_time"] = _parse_float_safe(m.group(1))
                    m = RE_SYSTEM_TIME.search(line)
                    if m:
                        results.job_time_summary["system_time"] = _parse_float_safe(m.group(1))
                    m = RE_CPU_TIME.search(line)
                    if m:
                        results.job_time_summary["total_cpu_time"] = _parse_float_safe(m.group(1))
                    m = RE_WALLCLOCK.search(line)
                    if m:
                        results.job_time_summary["wallclock_time"] = _parse_float_safe(m.group(1))
                    # 空行或遇到非时间行 → 回到 SCANNING
                    if not line.strip() or (
                            not RE_USER_TIME.search(line) and
                            not RE_SYSTEM_TIME.search(line) and
                            not RE_CPU_TIME.search(line) and
                            not RE_WALLCLOCK.search(line) and
                            "JOB TIME" not in line.upper()):
                        state = S_SCANNING
                    continue

                # --- Step 检测 ---
                m = RE_STEP.search(line)
                if m:
                    _commit_table()
                    step_name = f"Step-{m.group(1)}"
                    raw_type = m.group(2).strip()
                    step_type = _normalize_step_type(raw_type)
                    current_step = StepResult(step_name=step_name, step_type=step_type)
                    results.steps[step_name] = current_step
                    current_inc = None
                    state = S_SCANNING
                    continue

                # --- Increment 检测 ---
                m = RE_INCREMENT.search(line)
                if m:
                    _commit_table()
                    inc_num = int(m.group(1))
                    if current_step is not None:
                        current_inc = IncrementResult(increment_num=inc_num)
                        current_step.increments[inc_num] = current_inc
                    state = S_SCANNING
                    continue

                # --- 时间值 ---
                if current_inc is not None and current_inc.time == 0.0:
                    m = RE_TIME.search(line)
                    if m:
                        current_inc.time = _parse_float_safe(m.group(1))
                        continue

                if current_inc is not None and current_inc.step_time == 0.0:
                    m = RE_STEP_TIME.search(line)
                    if m:
                        current_inc.step_time = _parse_float_safe(m.group(1))
                        continue

                # --- 表格头部检测 ---
                is_output_header = (
                    RE_NODE_OUTPUT.search(line) or
                    RE_ELEMENT_OUTPUT.search(line) or
                    RE_CONTACT_OUTPUT.search(line)
                )
                if is_output_header:
                    _commit_table()
                    current_table_type = _classify_table(line)
                    # 用紧凑版本来匹配 SET 名称
                    compact = re.sub(r'\s+', ' ', line)
                    set_m = RE_SET_NAME.search(compact)
                    if set_m:
                        current_table_set_name = set_m.group(1)
                    else:
                        # 重新搜索原始行
                        set_m2 = RE_SET_NAME.search(line)
                        if set_m2:
                            current_table_set_name = set_m2.group(1)

                    current_table_header_lines = []
                    header_buffer = []
                    current_surface_role = ""
                    current_contact_pair = ""
                    state = S_IN_TABLE_HEADER
                    continue

                # --- 子表边界检测 (SET 打印范围) ---
                # "THE FOLLOWING TABLE IS PRINTED FOR NODES/ELEMENTS
                #  BELONGING TO NODE/ELEMENT SET XXX"
                table_set_m = RE_TABLE_FOR_SET.search(line)
                if table_set_m:
                    _commit_table()
                    current_table_set_name = table_set_m.group(3)
                    # 保留已有的表格类型，否则从匹配推断
                    if not current_table_type:
                        if table_set_m.group(1).upper() == "NODES":
                            current_table_type = "NODE_OUTPUT"
                        elif table_set_m.group(1).upper() == "ELEMENTS":
                            current_table_type = "ELEMENT_OUTPUT"
                    current_table_header_lines = []
                    header_buffer = []
                    state = S_IN_TABLE_HEADER
                    continue

                # --- Contact surface 行检测 (CONTACT OUTPUT 子表边界) ---
                # 在 SCANNING 状态中，CONTACT OUTPUT 的各子表之间有空行，
                # 空行会提交表格并回到 SCANNING。下一个 contact surface 行
                # 需要在此处被识别，以启动新的子表解析。
                contact_sf_m = RE_CONTACT_SURFACE.search(line)
                if contact_sf_m:
                    _commit_table()
                    current_table_type = "CONTACT_OUTPUT"
                    current_surface_role = contact_sf_m.group(1).upper()
                    current_table_set_name = contact_sf_m.group(2)
                    current_contact_pair = contact_sf_m.group(3)
                    current_table_header_lines = []
                    header_buffer = []
                    state = S_IN_TABLE_HEADER
                    logger.debug(
                        "Contact surface: role=%s surface=%s pair=%s",
                        current_surface_role, current_table_set_name,
                        current_contact_pair,
                    )
                    continue

                # --- 表格头部累积 ---
                if state == S_IN_TABLE_HEADER:

                    # 跳过空白行
                    if not line.strip():
                        continue

                    header_buffer.append(raw_stripped)

                    # 检查是否到了数据行 (以数字开头)
                    if RE_DATA_LINE.match(line):
                        # 处理头部缓冲区: 最后一行是数据行，前面的是表头
                        if len(header_buffer) >= 2:
                            current_table_header_lines = [
                                h.strip() for h in header_buffer[:-1]
                            ]
                        elif header_buffer:
                            # 只有一行头部? 检查是否包含变量名
                            current_table_header_lines = [header_buffer[0].strip()]

                        # 解析 SET 名称 (从头部行中)
                        for hline in header_buffer[:-1]:
                            set_m = RE_SET_NAME.search(hline)
                            if set_m:
                                current_table_set_name = set_m.group(1)

                        state = S_IN_TABLE_DATA

                        # 处理第一个数据行
                        row = _parse_data_line(line)
                        if row is not None:
                            current_table_data.append(row)
                        continue

                    # 还在表头中: 检测 SET 名称
                    set_m = RE_SET_NAME.search(line)
                    if set_m and not current_table_set_name:
                        current_table_set_name = set_m.group(1)

                    # 检测 Contact surface 行 (CONTACT OUTPUT 子表边界)
                    # 如果在表头累积过程中遇到新的 contact surface 行，
                    # 说明前一个子表没有数据行，直接开始新的子表。
                    contact_sf_m2 = RE_CONTACT_SURFACE.search(line)
                    if contact_sf_m2:
                        current_surface_role = contact_sf_m2.group(1).upper()
                        current_table_set_name = contact_sf_m2.group(2)
                        current_contact_pair = contact_sf_m2.group(3)
                        # 重置头部缓冲区，从这一行重新开始
                        header_buffer = [raw_stripped]
                        current_table_header_lines = []
                        logger.debug(
                            "Contact surface (in header): role=%s surface=%s pair=%s",
                            current_surface_role, current_table_set_name,
                            current_contact_pair,
                        )
                        continue

                    # 如果缓冲区过长 (超过5行)，可能不是标准表头，进入数据模式
                    if len(header_buffer) > 5:
                        # 检查最近的几行是否有变量名
                        all_header_text = " ".join(h.strip() for h in header_buffer)
                        vars_found = _parse_variables_from_header([all_header_text])
                        if vars_found:
                            current_table_header_lines = [all_header_text]
                            # 如果最后一行以数字开头，就纳入数据
                            last_line = header_buffer[-1].strip()
                            if RE_DATA_LINE.match(last_line):
                                state = S_IN_TABLE_DATA
                                row = _parse_data_line(last_line)
                                if row is not None:
                                    current_table_data.append(row)
                            else:
                                state = S_IN_TABLE_DATA
                        else:
                            # 可能不是我们关注的表格，跳过
                            state = S_SCANNING
                            header_buffer = []
                    continue

                # --- 表格数据累积 ---
                if state == S_IN_TABLE_DATA:
                    # 检测表格是否结束
                    if _is_table_end(line):
                        current_table_header_lines = [
                            h.strip() for h in header_buffer[:-1]
                        ] if header_buffer else []
                        _commit_table()
                        state = S_SCANNING
                        header_buffer = []
                        continue

                    # 检测是否进入了新的输出段
                    if is_output_header:
                        _commit_table()
                        state = S_SCANNING
                        header_buffer = []
                        continue

                    # 检测 Step 或 Increment 变化
                    if RE_STEP.search(line) or RE_INCREMENT.search(line):
                        _commit_table()
                        state = S_SCANNING
                        header_buffer = []
                        # 重新处理这一行
                        # (简单起见，跳过这行，pattern 会在外层重新应用)
                        continue

                    # 检测 Contact surface 行 (CONTACT OUTPUT 子表边界)
                    # 当子表之间没有空行分隔时，新 contact surface 行
                    # 直接跟在上一子表的数据行之后。
                    contact_sf_m3 = RE_CONTACT_SURFACE.search(line)
                    if contact_sf_m3:
                        _commit_table()
                        current_table_type = "CONTACT_OUTPUT"
                        current_surface_role = contact_sf_m3.group(1).upper()
                        current_table_set_name = contact_sf_m3.group(2)
                        current_contact_pair = contact_sf_m3.group(3)
                        current_table_header_lines = []
                        header_buffer = [raw_stripped]
                        state = S_IN_TABLE_HEADER
                        logger.debug(
                            "Contact surface (in data): role=%s surface=%s pair=%s",
                            current_surface_role, current_table_set_name,
                            current_contact_pair,
                        )
                        continue

                    # 空白行可能表示表格结束
                    if not line.strip():
                        if current_table_data:
                            _commit_table()
                            state = S_SCANNING
                            header_buffer = []
                        continue

                    # 子表边界检测 (SET 打印范围)
                    # "THE FOLLOWING TABLE IS PRINTED FOR NODES/ELEMENTS
                    #  BELONGING TO NODE/ELEMENT SET XXX"
                    table_set_m = RE_TABLE_FOR_SET.search(line)
                    if table_set_m:
                        _commit_table()
                        current_table_set_name = table_set_m.group(3)
                        current_table_header_lines = []
                        header_buffer = [raw_stripped]
                        state = S_IN_TABLE_HEADER
                        continue

                    # 解析数据行
                    row = _parse_data_line(line)
                    if row is not None:
                        current_table_data.append(row)
                    else:
                        # 不是数据行，可能表格结束
                        if current_table_data:
                            _commit_table()
                            state = S_SCANNING
                            header_buffer = []
                    continue

    except UnicodeDecodeError:
        if encoding != "latin-1":
            if dl:
                dl.log(f"UnicodeDecodeError with {encoding}, "
                       f"retrying with latin-1", "WARN")
            logger.info("使用 %s 解码失败，回退到 latin-1 重试", encoding)
            return parse_dat(filepath, encoding="latin-1", debug_log=dl)
        raise

    # 处理文件末尾残留
    if state == S_IN_TABLE_DATA and current_table_data:
        _commit_table()

    # 如果未显式检测到完成标记
    if not results.completion_status:
        results.completion_status = "UNKNOWN"

    logger.info(
        "DAT 解析完成: %d steps, status=%s",
        len(results.steps), results.completion_status,
    )

    if dl:
        # 统计总表数
        total_tables = 0
        for s in results.steps.values():
            for inc in s.increments.values():
                total_tables += len(inc.tables)
        dl.log(f"DAT parsed: {len(results.steps)} steps, "
               f"{total_tables} tables, "
               f"status={results.completion_status}, "
               f"type={results.analysis_type}")

    return results


def _is_table_end(line: str) -> bool:
    """检测表格是否结束."""
    line_upper = line.upper().replace(" ", "")
    # 表格结束后常见的标记
    end_markers = [
        "MAXIMUM", "MINIMUM",  # 表格统计 (某些版本)
        "THEANALYSISHASBEENCOMPLETED",
        "ANALYSISCOMPLETE",
        "JOBTIMESUMMARY",
    ]
    for marker in end_markers:
        if marker.replace(" ", "") in line_upper:
            return True
    # 页分隔符
    if line.strip().startswith("\f") or line.strip() == "\x0c":
        return True
    return False


def _parse_data_line(line: str) -> Optional[ResultRow]:
    """解析一行数据.

    格式: entity_id  val1  val2  val3 ...

    Returns:
        ResultRow 或 None (如果行不以数字开头)
    """
    if not RE_DATA_LINE.match(line):
        return None

    tokens = line.split()
    if not tokens:
        return None

    entity_id = try_parse_int(tokens[0])
    if entity_id is None:
        return None

    values: Dict[str, float] = {}
    # 后面的 token 依次对应变量 (在 commit_table 时与表头配对)
    for i, token in enumerate(tokens[1:]):
        val = parse_fortran_float(token)
        # 用占位符号 V0, V1, ... (稍后 commit 时替换为真实变量名)
        values[f"V{i}"] = val

    return ResultRow(
        entity_id=entity_id,
        values=values,
    )


def _parse_float_safe(s: str) -> float:
    """安全解析浮点数."""
    try:
        return float(s.strip())
    except (ValueError, AttributeError):
        return 0.0


# ---------------------------------------------------------------------------
# 后处理: 将 V0, V1, ... 占位符映射为真实变量名
# ---------------------------------------------------------------------------

def _remap_variable_names(table: ResultTable) -> ResultTable:
    """将数据行中的 V0, V1, ... 键替换为真实变量名.

    此函数在 commit_table 时由 parse_dat 自动调用。
    """
    if not table.variable_names:
        return table

    var_count = len(table.variable_names)
    for row in table.data:
        new_values = {}
        for i, var_name in enumerate(table.variable_names):
            old_key = f"V{i}"
            if old_key in row.values:
                new_values[var_name] = row.values[old_key]
            else:
                # 保留其他非占位符键
                pass
        # 保留非占位符键
        for key, val in row.values.items():
            if not key.startswith("V") or not key[1:].isdigit():
                new_values[key] = val
        row.values = new_values

    return table

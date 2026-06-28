"""多版本 Abaqus DAT 格式兼容模式库.

不同 Abaqus 版本的 DAT 输出格式有细微差异，
此模块集中管理各版本的表头检测模式。
"""

import re
from typing import Dict, List, Tuple

# 版本特定的表头变体
# 格式: {version_range: (pattern_name, regex_string)}

NODE_OUTPUT_PATTERNS: List[str] = [
    # 标准格式 (Abaqus 6.x ~ 2025)
    r'N\s+O\s+D\s+E\s+O\s+U\s+T\s+P\s+U\s+T',
    # 紧凑格式 (某些 Abaqus/Explicit 输出)
    r'NODE\s+OUTPUT',
]

ELEMENT_OUTPUT_PATTERNS: List[str] = [
    r'E\s+L\s+E\s+M\s+E\s+N\s+T\s+O\s+U\s+T\s+P\s+U\s+T',
    r'ELEMENT\s+OUTPUT',
]

CONTACT_OUTPUT_PATTERNS: List[str] = [
    r'C\s+O\s+N\s+T\s+A\s+C\s+T\s+O\s+U\s+T\s+P\s+U\s+T',
    r'CONTACT\s+OUTPUT',
]

# 完成标记 — 各版本可能用小写或混合大小写
COMPLETION_PATTERNS: List[str] = [
    r'THE\s+ANALYSIS\s+HAS\s+BEEN\s+COMPLETED',
    r'ANALYSIS\s+COMPLETE',
    r'JOB\s+COMPLETED',
]

# 版本号检测
RE_VERSION = re.compile(
    r'(?:VERSION|VER)\s*(\d+[\.\d]*)\s*(?:RELEASE|DATE)?',
    re.IGNORECASE,
)

# 已知的变量名别名 (同义不同名)
VARIABLE_ALIASES: Dict[str, str] = {
    # 旧名 → 标准名
    "SIG11": "S11",
    "SIG22": "S22",
    "SIG33": "S33",
    "SIG12": "S12",
    "SIG13": "S13",
    "SIG23": "S23",
    "EP11": "E11",
    "EP22": "E22",
    "EP33": "E33",
    "EP12": "E12",
    "EP13": "E13",
    "EP23": "E23",
    "U1": "U1",  # 标准
    "U2": "U2",
    "U3": "U3",
    "MAGNITUDE": "U_MAGNITUDE",
    "MAG": "U_MAGNITUDE",
}


def normalize_variable_name(name: str) -> str:
    """将变量名标准化为现代 Abaqus 命名.

    Args:
        name: 原始变量名

    Returns:
        标准化后的变量名
    """
    upper = name.upper().strip()
    return VARIABLE_ALIASES.get(upper, upper)


def detect_abaqus_version(dat_content_sample: str) -> Tuple[str, str]:
    """从 DAT 文件内容中检测 Abaqus 版本.

    Args:
        dat_content_sample: DAT 文件前几行

    Returns:
        (version_string, solver_type)  如 ("6.24-1", "STANDARD")
    """
    version = "unknown"
    solver = "unknown"

    m = RE_VERSION.search(dat_content_sample)
    if m:
        version = m.group(1)

    if re.search(r'S\s+T\s+A\s+N\s+D\s+A\s+R\s+D', dat_content_sample, re.IGNORECASE):
        solver = "STANDARD"
    elif re.search(r'E\s+X\s+P\s+L\s+I\s+C\s+I\s+T', dat_content_sample, re.IGNORECASE):
        solver = "EXPLICIT"

    return version, solver


def compile_output_patterns() -> Dict[str, List[re.Pattern]]:
    """编译所有输出模式为 regex 对象.

    Returns:
        {"NODE_OUTPUT": [re1, re2], "ELEMENT_OUTPUT": [...], ...}
    """
    return {
        "NODE_OUTPUT": [re.compile(p, re.IGNORECASE) for p in NODE_OUTPUT_PATTERNS],
        "ELEMENT_OUTPUT": [re.compile(p, re.IGNORECASE) for p in ELEMENT_OUTPUT_PATTERNS],
        "CONTACT_OUTPUT": [re.compile(p, re.IGNORECASE) for p in CONTACT_OUTPUT_PATTERNS],
        "COMPLETION": [re.compile(p, re.IGNORECASE) for p in COMPLETION_PATTERNS],
    }

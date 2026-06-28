"""Fortran 格式浮点数解析器.

处理 Abaqus .dat 文件中使用的 Fortran 科学记数法格式。
"""

import re
import math
from typing import Union


# 匹配 Fortran 浮点数的正则模式
# 支持: 1.234E+02, 1.234D+02, -.1234E-02, 1.234+02, 1.234-02, 1.234E+003
_FORTRAN_RE = re.compile(
    r'^'
    r'\s*'
    r'([-+]?)'           # 符号
    r'(\d*\.?\d*)'        # 整数/小数部分
    r'(?:[EeDd]([+-]?\d+))?'  # E/D 指数 (可选)
    r'\s*$'
)


# 处理 Fortran 中省略 E 的情况: 1.234+02 → 1.234E+02
# 也处理整数格式: 1234+02 → 1234E+02
_FORTRAN_NO_E_RE = re.compile(
    r'^'
    r'\s*'
    r'([-+]?)'
    r'(\d+(?:\.\d*)?)'      # 整数或小数
    r'([+-]\d{2,3})'        # +02, -003 等 → 指数
    r'\s*$'
)


def parse_fortran_float(s: str) -> float:
    """解析 Fortran 格式的浮点数.

    支持格式:
    - 0.1234E+02  (标准 Fortran)
    - 0.1234D+02  (双精度标记)
    - 1234.5678    (普通小数)
    - -.1234E-02   (前导负号省略零)
    - 0.1234+02    (省略 E)
    - 1.234E+003   (3位指数)
    - **********   (溢出/未定义 → NaN)

    Args:
        s: 字符串形式的数值

    Returns:
        float: 解析后的浮点数，解析失败返回 NaN

    Examples:
        >>> parse_fortran_float("1.234E+02")
        123.4
        >>> parse_fortran_float("-.1234E-02")
        -0.001234
        >>> parse_fortran_float("1.234+02")
        123.4
    """
    s = s.strip()
    if not s:
        return float('nan')

    # 检测溢出标记 (Abaqus 用 * 表示数值溢出)
    if '*' in s:
        return float('nan')

    # 将双精度 D 标记替换为 E
    s_upper = s.replace('D', 'E').replace('d', 'E')

    # 尝试标准 float 解析
    try:
        return float(s_upper)
    except ValueError:
        pass

    # 尝试处理省略 E 的情况: "1.234+02" → "1.234E+02"
    #    或 "1.234-02" → "1.234E-02"
    match = _FORTRAN_NO_E_RE.match(s)
    if match:
        base = match.group(1) + match.group(2)
        exponent = match.group(3)
        # 确保指数有 E 前缀
        return float(base + 'E' + exponent)

    return float('nan')


def parse_fortran_floats(line: str, expected_count: int = None) -> list:
    """从一行文本中解析多个 Fortran 浮点数.

    Abaqus 的 DAT 输出中，一行可能有多个数值，通过空白分隔。

    Args:
        line: 包含多个数值的一行文本
        expected_count: 期望的数值个数 (可选，用于验证)

    Returns:
        list: 解析后的浮点数列表
    """
    values = []
    for token in line.split():
        val = parse_fortran_float(token)
        if not math.isnan(val):
            values.append(val)

    if expected_count is not None and len(values) != expected_count:
        # 如果数量不匹配，可能是某些值解析失败
        # 返回实际解析出的值
        pass

    return values


def try_parse_int(s: str) -> Union[int, None]:
    """尝试将字符串解析为整数.

    Args:
        s: 字符串

    Returns:
        int or None: 解析成功返回整数，否则返回 None
    """
    try:
        return int(s.strip())
    except (ValueError, AttributeError):
        return None

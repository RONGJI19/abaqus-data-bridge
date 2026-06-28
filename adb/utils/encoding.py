"""文件编码检测与处理工具."""

import os
from typing import Optional


def detect_encoding(filepath: str, sample_size: int = 4096) -> str:
    """检测文本文件的编码.

    优先使用 chardet，不可用时回退到常见编码检测。

    Args:
        filepath: 文件路径
        sample_size: 采样大小 (字节)

    Returns:
        str: 检测到的编码名称
    """
    try:
        import chardet
        with open(filepath, 'rb') as f:
            raw_data = f.read(sample_size)
        result = chardet.detect(raw_data)
        encoding = result.get('encoding', 'utf-8')
        confidence = result.get('confidence', 0)
        if encoding and confidence > 0.7:
            # 规范化编码名称
            encoding = encoding.lower()
            if encoding in ('gb2312', 'gb18030', 'gbk'):
                return 'gbk'
            if encoding in ('iso-8859-1', 'latin-1'):
                return 'latin-1'
            return encoding
    except ImportError:
        pass

    # 回退: 简单检测 UTF-8 BOM
    try:
        with open(filepath, 'rb') as f:
            bom = f.read(3)
        if bom == b'\xef\xbb\xbf':
            return 'utf-8-sig'
    except IOError:
        pass

    # 默认使用 UTF-8
    return 'utf-8'


def read_file_safe(filepath: str, encoding: Optional[str] = None) -> str:
    """安全读取文件内容，自动处理编码.

    Args:
        filepath: 文件路径
        encoding: 指定编码，为 None 时自动检测

    Returns:
        str: 文件内容
    """
    if encoding is None:
        encoding = detect_encoding(filepath)

    # 尝试多种编码
    encodings_to_try = [encoding, 'utf-8', 'utf-8-sig', 'gbk', 'latin-1']

    for enc in encodings_to_try:
        try:
            with open(filepath, 'r', encoding=enc) as f:
                return f.read()
        except (UnicodeDecodeError, LookupError):
            continue

    # 最后尝试: 忽略错误
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        return f.read()


def read_lines_safe(filepath: str, encoding: Optional[str] = None) -> list:
    """安全按行读取文件.

    Args:
        filepath: 文件路径
        encoding: 指定编码，为 None 时自动检测

    Returns:
        list: 行列表 (去除换行符)
    """
    content = read_file_safe(filepath, encoding)
    return content.splitlines()

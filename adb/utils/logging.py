"""崩溃安全的诊断文件日志.

提供 CrashProofLogger，将带时间戳的诊断条目写入文件，
使用行缓冲 I/O，确保 EXE 崩溃或强制退出时日志不丢失。

自动启用条件:
    - PyInstaller 打包的 EXE (sys.frozen = True)
    - 环境变量 ADB_DEBUG_LOG=1
    - CLI --debug 标志

用法:
    from adb.utils.logging import create_debug_logger

    logger = create_debug_logger(output_dir="./output", job_name="my_job")
    if logger:
        logger.log_phase_enter("Parse INP")
        ...
        logger.log_phase_exit("Parse INP", "5 nodes, 7 elements")
        logger.close()
"""

from __future__ import annotations

import os
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Optional

__all__ = [
    "CrashProofLogger",
    "should_enable_debug_log",
    "resolve_debug_log_path",
    "create_debug_logger",
]

# ---------------------------------------------------------------------------
# 启用判断
# ---------------------------------------------------------------------------


def should_enable_debug_log() -> bool:
    """判断是否应启用崩溃安全调试日志.

    满足以下任一条件即启用:
        1. 运行在 PyInstaller 打包的 EXE 中 (sys.frozen)
        2. 环境变量 ADB_DEBUG_LOG 设为 1/true/yes/on
    """
    # PyInstaller 打包检测
    if getattr(sys, "frozen", False):
        return True
    # 备选 frozen 检测
    if hasattr(sys, "_MEIPASS"):
        return True
    # 环境变量 opt-in
    env_val = os.environ.get("ADB_DEBUG_LOG", "").strip().lower()
    if env_val in ("1", "true", "yes", "on"):
        return True
    return False


# ---------------------------------------------------------------------------
# 日志文件路径
# ---------------------------------------------------------------------------


def resolve_debug_log_path(output_dir: Optional[str] = None) -> Path:
    """确定调试日志文件的写入路径.

    优先级:
        1. output_dir（如果提供且可写）
        2. EXE 所在目录（如果是 frozen）
        3. 当前工作目录

    Returns:
        Path: 日志文件完整路径，文件名含时间戳
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"adb_debug_{timestamp}.log"

    # 1. output_dir
    if output_dir:
        out_path = Path(output_dir)
        try:
            out_path.mkdir(parents=True, exist_ok=True)
            return out_path / filename
        except OSError:
            pass

    # 2. EXE 所在目录
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).parent
        return exe_dir / filename

    # 3. 当前工作目录
    return Path.cwd() / filename


# ---------------------------------------------------------------------------
# CrashProofLogger
# ---------------------------------------------------------------------------


class CrashProofLogger:
    """崩溃安全的文件日志记录器.

    特性:
        - 行缓冲 I/O (buffering=1)，每次写入后显式 flush
        - 所有方法内部 try/except 包裹，日志失败不影响主流程
        - 支持阶段标记 (PHASE START/END) 和耗时统计
    """

    def __init__(
        self,
        log_path: Path,
        job_name: str = "",
        verbose: bool = False,
    ):
        """初始化日志记录器.

        Args:
            log_path: 日志文件路径
            job_name: 作业名称 (用于文件头)
            verbose: True 时记录更多细节（匹配详情、每文件详情等）
        """
        self._job_name = job_name
        self._verbose = verbose
        self._enabled = False
        self._file = None
        self._start_time = time.monotonic()
        self._phase_start = 0.0

        try:
            # buffering=1 = 行缓冲，每行写入后自动刷到 OS
            self._file = open(log_path, "w", encoding="utf-8", buffering=1)
            self._enabled = True
        except OSError:
            # 权限不足 / 路径不存在 — 静默禁用，不影响提取
            self._enabled = False
            return

        self._log_path = log_path

    # ---- 属性 ----

    @property
    def is_enabled(self) -> bool:
        """日志是否已启用."""
        return self._enabled

    @property
    def log_path(self) -> Path:
        """日志文件路径."""
        return self._log_path

    # ---- 生命周期 ----

    def start(self, config_summary: str = "") -> None:
        """写入日志文件头."""
        if not self._enabled:
            return
        self._safe_write("=" * 80)
        self._safe_write(f"ADB Debug Log — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self._safe_write("=" * 80)
        self._safe_write(f"Job: {self._job_name or '(unknown)'}")
        if config_summary:
            for line in config_summary.strip().split("\n"):
                self._safe_write(line)
        self._safe_write(f"EXE mode: {getattr(sys, 'frozen', False)}  |  "
                         f"PID: {os.getpid()}")
        self._safe_write("=" * 80)
        self._flush()

    def close(self) -> None:
        """关闭日志文件."""
        if not self._enabled or self._file is None:
            return
        try:
            elapsed = (time.monotonic() - self._start_time) * 1000
            self._safe_write("=" * 80)
            self._safe_write(f"LOG END — Total: {elapsed:.0f}ms")
            self._safe_write("=" * 80)
            self._file.close()
        except Exception:
            pass
        finally:
            self._enabled = False
            self._file = None

    # ---- 日志方法 ----

    def log(self, message: str, level: str = "INFO") -> None:
        """写入一条带时间戳的日志条目.

        Args:
            message: 日志消息
            level: 级别标签 (INFO / WARN / ERROR / DEBUG)
        """
        if not self._enabled:
            return
        elapsed = (time.monotonic() - self._start_time) * 1000
        now = datetime.now().strftime("%H:%M:%S") + f".{datetime.now().microsecond // 1000:03d}"
        line = f"[{now}] [+{elapsed:5.0f}ms] [{level:5s}] {message}"
        self._safe_write(line)
        self._flush()

    def log_phase_enter(self, phase_name: str) -> None:
        """记录阶段开始."""
        if not self._enabled:
            return
        self._phase_start = time.monotonic()
        self.log(f"=== PHASE START: {phase_name} ===", "INFO")

    def log_phase_exit(self, phase_name: str, extra: str = "") -> None:
        """记录阶段结束，附带耗时和额外信息.

        Args:
            phase_name: 阶段名称
            extra: 额外信息 (如 "5 nodes, 7 elements")
        """
        if not self._enabled:
            return
        delta_ms = (time.monotonic() - self._phase_start) * 1000
        msg = f"=== PHASE END: {phase_name} ({delta_ms:.0f}ms) ==="
        if extra:
            msg += f"  [{extra}]"
        self.log(msg, "INFO")

    def exception(self, exc: Exception) -> None:
        """记录异常及完整 traceback.

        Args:
            exc: 异常对象
        """
        if not self._enabled:
            return
        tb_str = traceback.format_exception(type(exc), exc, exc.__traceback__)
        self.log(f"EXCEPTION: {exc}", "ERROR")
        for line in "".join(tb_str).strip().split("\n"):
            self.log(f"  {line}", "ERROR")
        self._flush()

    # ---- 内部 ----

    def _safe_write(self, line: str) -> None:
        """安全写入一行，内部异常静默."""
        try:
            self._file.write(line + "\n")
        except Exception:
            pass

    def _flush(self) -> None:
        """安全 flush，内部异常静默."""
        try:
            self._file.flush()
        except Exception:
            pass

    def __del__(self):
        """析构时尝试关闭文件."""
        try:
            if self._file is not None:
                self._file.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# 工厂函数
# ---------------------------------------------------------------------------


def create_debug_logger(
    output_dir: Optional[str] = None,
    job_name: str = "",
    verbose: bool = False,
) -> Optional[CrashProofLogger]:
    """创建 CrashProofLogger 的工厂函数.

    仅在 should_enable_debug_log() 返回 True 时创建，
    否则返回 None。

    Args:
        output_dir: 输出目录 (用于日志路径)
        job_name: 作业名称
        verbose: 是否启用详细日志

    Returns:
        CrashProofLogger 或 None
    """
    if not should_enable_debug_log():
        return None

    log_path = resolve_debug_log_path(output_dir)
    return CrashProofLogger(log_path, job_name=job_name, verbose=verbose)

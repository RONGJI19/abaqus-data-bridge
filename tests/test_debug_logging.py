"""测试崩溃安全诊断日志."""

import os
import sys
import tempfile
from pathlib import Path

import pytest

from adb.utils.logging import (
    CrashProofLogger,
    should_enable_debug_log,
    resolve_debug_log_path,
    create_debug_logger,
)


class TestShouldEnableDebugLog:
    """should_enable_debug_log() 测试."""

    def test_not_enabled_by_default(self, monkeypatch):
        """默认不应启用."""
        monkeypatch.setattr(sys, "frozen", False, raising=False)
        monkeypatch.delenv("ADB_DEBUG_LOG", raising=False)
        # 确保 _MEIPASS 不存在
        monkeypatch.delattr(sys, "_MEIPASS", raising=False)
        assert should_enable_debug_log() is False

    def test_enabled_when_frozen(self, monkeypatch):
        """frozen=True 时应启用."""
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        assert should_enable_debug_log() is True
        monkeypatch.setattr(sys, "frozen", False, raising=False)

    def test_enabled_when_meipass(self, monkeypatch):
        """_MEIPASS 存在时应启用."""
        monkeypatch.setattr(sys, "frozen", False, raising=False)
        monkeypatch.setattr(sys, "_MEIPASS", "/fake/path", raising=False)
        assert should_enable_debug_log() is True
        monkeypatch.delattr(sys, "_MEIPASS", raising=False)

    def test_enabled_by_env_var(self, monkeypatch):
        """环境变量 ADB_DEBUG_LOG=1 时应启用."""
        monkeypatch.setattr(sys, "frozen", False, raising=False)
        monkeypatch.delenv("ADB_DEBUG_LOG", raising=False)

        for val in ("1", "true", "yes", "on", "TRUE", "YES"):
            monkeypatch.setenv("ADB_DEBUG_LOG", val)
            assert should_enable_debug_log() is True, f"Failed for {val}"

        monkeypatch.delenv("ADB_DEBUG_LOG", raising=False)


class TestResolveDebugLogPath:
    """resolve_debug_log_path() 测试."""

    def test_with_output_dir(self, tmp_path):
        """有 output_dir 时使用它."""
        out = str(tmp_path / "my_output")
        path = resolve_debug_log_path(output_dir=out)
        assert path.parent == Path(out)
        assert path.name.startswith("adb_debug_")
        assert path.name.endswith(".log")

    def test_without_output_dir(self, monkeypatch, tmp_path):
        """无 output_dir 且非 frozen 时使用 CWD."""
        monkeypatch.setattr(sys, "frozen", False, raising=False)
        monkeypatch.chdir(tmp_path)
        path = resolve_debug_log_path()
        # 路径应该在 tmp_path 下
        assert path.parent == tmp_path
        assert path.name.startswith("adb_debug_")

    def test_frozen_uses_exe_dir(self, monkeypatch, tmp_path):
        """frozen 模式下使用 EXE 所在目录."""
        exe_dir = tmp_path / "exe_dir"
        exe_dir.mkdir()
        fake_exe = str(exe_dir / "adb.exe")
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "executable", fake_exe, raising=False)
        path = resolve_debug_log_path()
        assert path.parent == exe_dir


class TestCrashProofLogger:
    """CrashProofLogger 测试."""

    def test_create_and_write(self, tmp_path):
        """基本写入测试."""
        log_path = tmp_path / "test.log"
        logger = CrashProofLogger(log_path, job_name="test_job")
        assert logger.is_enabled

        logger.start("INP: test.inp\nDAT: test.dat")
        logger.log("Test message", "INFO")
        logger.log_phase_enter("Parse INP")
        logger.log_phase_exit("Parse INP", "5 nodes")
        logger.close()

        # 验证文件存在且非空
        assert log_path.exists()
        content = log_path.read_text(encoding="utf-8")
        assert "ADB Debug Log" in content
        assert "test_job" in content
        assert "Test message" in content
        assert "PHASE START: Parse INP" in content
        assert "PHASE END: Parse INP" in content
        assert "5 nodes" in content
        assert "LOG END" in content

    def test_exception_logging(self, tmp_path):
        """异常记录测试."""
        log_path = tmp_path / "test_exc.log"
        logger = CrashProofLogger(log_path, job_name="test")
        logger.start("")

        try:
            raise ValueError("Something went wrong")
        except ValueError as e:
            logger.exception(e)

        logger.close()

        content = log_path.read_text(encoding="utf-8")
        assert "EXCEPTION: Something went wrong" in content
        assert "ValueError" in content

    def test_not_enabled_when_path_invalid(self):
        """无效路径时静默禁用."""
        # 使用一个不可能可写的路径
        logger = CrashProofLogger(Path("Z:/nonexistent/path/test.log"))
        assert not logger.is_enabled
        # 这些调用不应抛出异常
        logger.start("")
        logger.log("should not raise", "INFO")
        logger.log_phase_enter("test")
        logger.log_phase_exit("test")
        logger.close()

    def test_crash_survival(self, tmp_path):
        """崩溃安全: 不调用 close() 也会保留已写入内容."""
        log_path = tmp_path / "crash_test.log"
        logger = CrashProofLogger(log_path, job_name="crash_test")
        logger.start("INP: test.inp")
        logger.log("Halfway through", "INFO")
        # 模拟崩溃: 不调用 close()，直接删除 logger
        del logger

        # 内容应该已写入
        assert log_path.exists()
        content = log_path.read_text(encoding="utf-8")
        assert "Halfway through" in content
        # 没有 LOG END 是正常的

    def test_verbose_detail(self, tmp_path):
        """verbose 模式记录更多细节."""
        log_path = tmp_path / "verbose.log"
        logger = CrashProofLogger(log_path, job_name="test", verbose=True)
        logger.start("")
        logger.log("This is a detail", "DEBUG")
        logger.close()

        content = log_path.read_text(encoding="utf-8")
        assert "This is a detail" in content
        assert "DEBUG" in content

    def test_flush_after_write(self, tmp_path):
        """每次写入后确保 flush."""
        log_path = tmp_path / "flush_test.log"
        logger = CrashProofLogger(log_path, job_name="test")
        logger.start("")

        # 写入一条，立即检查大小
        logger.log("First message", "INFO")
        # 文件应该有内容（不依赖 close）
        assert log_path.stat().st_size > 0
        first_size = log_path.stat().st_size

        # 再写一条，应该增长
        logger.log("Second message", "INFO")
        assert log_path.stat().st_size > first_size

        logger.close()

    def test_elapsed_time_format(self, tmp_path):
        """验证耗时格式."""
        log_path = tmp_path / "elapsed.log"
        logger = CrashProofLogger(log_path, job_name="test")
        logger.start("")
        logger.log_phase_enter("Phase A")
        logger.log_phase_exit("Phase A", "done")
        logger.close()

        content = log_path.read_text(encoding="utf-8")
        # 检查 [+XXXXms] 格式
        assert "[+" in content
        assert "ms]" in content


class TestCreateDebugLogger:
    """create_debug_logger() 工厂函数测试."""

    def test_returns_none_when_disabled(self, monkeypatch):
        """未启用时返回 None."""
        monkeypatch.setattr(sys, "frozen", False, raising=False)
        monkeypatch.delenv("ADB_DEBUG_LOG", raising=False)
        monkeypatch.delattr(sys, "_MEIPASS", raising=False)
        logger = create_debug_logger()
        assert logger is None

    def test_returns_logger_when_enabled(self, monkeypatch, tmp_path):
        """启用时返回 CrashProofLogger."""
        monkeypatch.setenv("ADB_DEBUG_LOG", "1")
        logger = create_debug_logger(output_dir=str(tmp_path), job_name="test")
        assert logger is not None
        assert logger.is_enabled
        logger.close()
        monkeypatch.delenv("ADB_DEBUG_LOG", raising=False)


class TestDebugLogIntegration:
    """集成测试: 通过完整提取流程验证日志."""

    def test_full_pipeline_with_log(self, tmp_path):
        """全流程生成日志文件."""
        import os as _os
        from adb.models.extraction_config import ExtractionConfig
        from adb.core.engine import ExtractionEngine

        fixtures = Path(__file__).parent / "fixtures"
        config = ExtractionConfig()
        config.inp_file = str(fixtures / "simple_truss.inp")
        config.dat_file = str(fixtures / "simple_truss.dat")
        config.output_dir = str(tmp_path / "output")

        log_path = tmp_path / "adb_test.log"
        logger = CrashProofLogger(log_path, job_name="integration_test")
        logger.start(f"INP: {config.inp_file}\nDAT: {config.dat_file}")

        engine = ExtractionEngine(config, debug_log=logger)
        stats = engine.run()

        # 验证提取成功
        assert stats["total_rows"] > 0
        assert stats["exported_files"] > 0

        # 验证日志文件
        assert log_path.exists()
        content = log_path.read_text(encoding="utf-8")

        # 检查关键阶段标记
        assert "PHASE START: Parse INP" in content
        assert "PHASE END: Parse INP" in content
        assert "PHASE START: Parse DAT" in content
        assert "PHASE END: Parse DAT" in content
        assert "PHASE START: Match Results" in content
        assert "PHASE END: Match Results" in content
        assert "PHASE START: Export CSV" in content
        assert "PHASE END: Export CSV" in content
        assert "EXTRACTION COMPLETE" in content

        # 检查内容包含实际数据
        assert "5 nodes" in content.lower() or "5" in content
        assert "LOG END" in content

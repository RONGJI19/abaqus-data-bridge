"""测试工具函数."""

import math
import pytest
from adb.utils.fortran import parse_fortran_float, parse_fortran_floats, try_parse_int


class TestFortranFloat:
    """Fortran 浮点数解析测试."""

    def test_standard_positive(self):
        assert parse_fortran_float("1.234E+02") == pytest.approx(123.4)

    def test_standard_negative(self):
        assert parse_fortran_float("-1.234E+02") == pytest.approx(-123.4)

    def test_double_precision(self):
        assert parse_fortran_float("0.1234D+02") == pytest.approx(12.34)
        assert parse_fortran_float("0.1234D+01") == pytest.approx(1.234)

    def test_plain_decimal(self):
        assert parse_fortran_float("1234.5678") == pytest.approx(1234.5678)

    def test_negative_without_leading_zero(self):
        """处理 -.1234E-02 这种省略前导零的格式."""
        result = parse_fortran_float("-.1234E-02")
        assert result == pytest.approx(-0.001234)

    def test_omit_e_positive_exp(self):
        """省略 E: 0.1234+02 → 0.1234E+02."""
        result = parse_fortran_float("0.1234+02")
        assert result == pytest.approx(12.34)

    def test_omit_e_negative_exp(self):
        """省略 E: 1.234-02 → 1.234E-02."""
        result = parse_fortran_float("1.234-02")
        assert result == pytest.approx(0.01234)

    def test_three_digit_exponent(self):
        """3位指数: 1.234E+003."""
        assert parse_fortran_float("1.234E+003") == pytest.approx(1234.0)

    def test_overflow_stars(self):
        """溢出标记 ********** → NaN."""
        result = parse_fortran_float("**********")
        assert math.isnan(result)

    def test_negative_exp_lowercase(self):
        assert parse_fortran_float("5.0e-02") == pytest.approx(0.05)

    def test_empty_string(self):
        assert math.isnan(parse_fortran_float(""))

    def test_whitespace(self):
        assert parse_fortran_float("  1.5E+01  ") == pytest.approx(15.0)


class TestParseFortranFloats:
    """一行多个 Fortran 数值解析测试."""

    def test_multiple_values(self):
        result = parse_fortran_floats("1.0E+00  2.0E+00  3.0E+00")
        assert len(result) == 3
        assert result == [1.0, 2.0, 3.0]

    def test_skip_nan(self):
        """溢出值应被跳过."""
        result = parse_fortran_floats("1.0  *******  3.0")
        assert len(result) == 2


class TestTryParseInt:
    """整数解析测试."""

    def test_valid(self):
        assert try_parse_int("123") == 123

    def test_negative(self):
        assert try_parse_int("-5") == -5

    def test_float_string(self):
        assert try_parse_int("1.5") is None

    def test_empty(self):
        assert try_parse_int("") is None

from __future__ import annotations

import pytest

from gfi_scout.utils.validators import (
    MAX_RESULTS_HARD_CAP,
    ValidationError,
    clamp_max_results,
    validate_language,
)


class TestValidateLanguage:
    def test_lowercases_and_strips(self) -> None:
        assert validate_language("  Python  ") == "python"

    def test_accepts_special_chars(self) -> None:
        assert validate_language("c++") == "c++"
        assert validate_language("c#") == "c#"
        assert validate_language("objective-c") == "objective-c"

    def test_rejects_empty(self) -> None:
        with pytest.raises(ValidationError):
            validate_language("   ")

    def test_rejects_invalid_chars(self) -> None:
        with pytest.raises(ValidationError):
            validate_language("py thon")
        with pytest.raises(ValidationError):
            validate_language("py;thon")

    def test_rejects_too_long(self) -> None:
        with pytest.raises(ValidationError):
            validate_language("a" * 200)


class TestClampMaxResults:
    def test_returns_value_in_range(self) -> None:
        assert clamp_max_results(10) == 10

    def test_clamps_below_min(self) -> None:
        assert clamp_max_results(0) == 1
        assert clamp_max_results(-5) == 1

    def test_clamps_above_max(self) -> None:
        assert clamp_max_results(1000) == MAX_RESULTS_HARD_CAP

    def test_rejects_bool(self) -> None:
        with pytest.raises(ValidationError):
            clamp_max_results(True)  # type: ignore[arg-type]

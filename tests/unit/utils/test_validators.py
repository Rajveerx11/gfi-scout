from __future__ import annotations

import pytest

from gfi_scout.utils.validators import (
    MAX_RESULTS_HARD_CAP,
    ValidationError,
    clamp_max_results,
    parse_issue_url,
    validate_language,
    validate_repo_full_name,
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


class TestValidateRepoFullName:
    def test_accepts_simple(self) -> None:
        assert validate_repo_full_name("fastapi/fastapi") == "fastapi/fastapi"

    def test_accepts_url(self) -> None:
        assert validate_repo_full_name("https://github.com/fastapi/fastapi") == "fastapi/fastapi"

    def test_strips_extra_path(self) -> None:
        assert (
            validate_repo_full_name("https://github.com/fastapi/fastapi/issues/1")
            == "fastapi/fastapi"
        )

    def test_rejects_garbage(self) -> None:
        with pytest.raises(ValidationError):
            validate_repo_full_name("not-a-repo")

    def test_rejects_non_github(self) -> None:
        with pytest.raises(ValidationError):
            validate_repo_full_name("https://gitlab.com/foo/bar")


class TestParseIssueUrl:
    def test_basic(self) -> None:
        repo, num = parse_issue_url("https://github.com/fastapi/fastapi/issues/42")
        assert repo == "fastapi/fastapi"
        assert num == 42

    def test_trailing_anchor(self) -> None:
        repo, num = parse_issue_url("https://github.com/a/b/issues/7#issuecomment-1")
        assert repo == "a/b"
        assert num == 7

    def test_rejects_pr_url(self) -> None:
        with pytest.raises(ValidationError):
            parse_issue_url("https://github.com/a/b/pull/7")

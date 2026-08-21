"""Tests for post-install GDAL diagnostics."""

from __future__ import annotations

import importlib
import json

import pytest

import isobands
from isobands import __main__ as cli
from isobands import _diagnostics as diagnostics


class _FakeGdal:
    def __init__(self, *, native: str = "3.13.2") -> None:
        self.native = native

    def VersionInfo(self, name: str) -> str:  # noqa: N802
        assert name == "RELEASE_NAME"
        return self.native


def _successful_smoke() -> diagnostics.CheckResult:
    return diagnostics.CheckResult(
        "contour_smoke",
        True,
        {"result": "generated"},
        "A tiny in-memory contour was generated successfully.",
        "No action needed.",
    )


def test_check_reports_missing_bindings_without_raising(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing GDAL returns a useful, serializable failed report."""
    monkeypatch.setattr(
        diagnostics,
        "load_gdal_modules",
        lambda: (_ for _ in ()).throw(ImportError("no module named osgeo")),
    )

    report = isobands.check()

    assert not report.ok
    assert [result.name for result in report.checks] == [
        "python_bindings",
        "gdal_versions",
        "supported_gdal_version",
        "contour_smoke",
    ]
    assert report.checks[0].observed == {"error": "ImportError"}
    assert "gdal310/gdal311/gdal312/gdal313" in report.checks[0].guidance
    assert json.loads(json.dumps(report.to_dict())) == report.to_dict()


def test_package_import_does_not_run_gdal_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Importing isobands does not initialize GDAL."""
    monkeypatch.setattr(
        diagnostics,
        "load_gdal_modules",
        lambda: (_ for _ in ()).throw(AssertionError("GDAL check ran on import")),
    )

    importlib.reload(isobands)


def test_check_reports_native_loader_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    """Broken native libraries are reported like missing Python bindings."""
    monkeypatch.setattr(
        diagnostics,
        "load_gdal_modules",
        lambda: (_ for _ in ()).throw(OSError("native library mismatch")),
    )

    report = isobands.check()

    assert not report.ok
    assert report.checks[0].observed == {"error": "OSError"}


def test_check_reports_version_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    """Binding/native mismatches prevent the contour smoke test."""
    monkeypatch.setattr(
        diagnostics,
        "load_gdal_modules",
        lambda: (_FakeGdal(native="3.13.2"), object()),
    )
    monkeypatch.setattr(diagnostics, "_installed_binding_version", lambda: "3.12.2")
    monkeypatch.setattr(
        diagnostics,
        "_smoke_check",
        lambda: (_ for _ in ()).throw(AssertionError("smoke should not run")),
    )

    report = isobands.check()

    assert not report.ok
    assert not report.checks[1].ok
    assert report.checks[-1].message.startswith("Not run:")


def test_check_reports_untested_version(monkeypatch: pytest.MonkeyPatch) -> None:
    """A matching but untested GDAL release receives focused guidance."""
    monkeypatch.setattr(
        diagnostics,
        "load_gdal_modules",
        lambda: (_FakeGdal(native="3.14.0"), object()),
    )
    monkeypatch.setattr(diagnostics, "_installed_binding_version", lambda: "3.14.0")

    report = isobands.check()

    assert not report.ok
    assert not report.checks[2].ok
    assert report.checks[2].observed["native"] == "3.14.0"


def test_check_runs_contour_smoke_for_supported_gdal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A supported installation runs the final contour check."""
    monkeypatch.setattr(
        diagnostics,
        "load_gdal_modules",
        lambda: (_FakeGdal(), object()),
    )
    monkeypatch.setattr(diagnostics, "_installed_binding_version", lambda: "3.13.2")
    monkeypatch.setattr(diagnostics, "_smoke_check", _successful_smoke)

    report = isobands.check()

    assert report.ok
    assert all(result.ok for result in report.checks)


def test_cli_human_output_and_exit_code(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Human output explains failures and returns a nonzero exit code."""
    failed = diagnostics.CheckResult(
        "python_bindings",
        False,
        {"error": "ImportError"},
        "GDAL Python bindings could not be imported.",
        diagnostics.GDAL_INSTALL_GUIDANCE,
    )
    report = diagnostics.CheckReport(False, (failed,))
    monkeypatch.setattr(cli, "check", lambda: report)

    assert cli.main(["check"]) == 1
    output = capsys.readouterr().out
    assert "[failed] python_bindings" in output
    assert "Guidance:" in output


def test_cli_json_output_and_exit_code(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """JSON output is machine-readable and successful when GDAL is usable."""
    report = diagnostics.CheckReport(True, (_successful_smoke(),))
    monkeypatch.setattr(cli, "check", lambda: report)

    assert cli.main(["check", "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == report.to_dict()


@pytest.mark.integration
def test_real_gdal_diagnostics_smoke() -> None:
    """The installed test GDAL passes the public diagnostics."""
    pytest.importorskip("osgeo.gdal")

    report = isobands.check()

    assert report.ok, report.to_dict()

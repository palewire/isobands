"""Runtime checks for the GDAL installation used by isobands."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from importlib import import_module
from importlib.metadata import version
from typing import Any, Literal

_SUPPORTED_GDAL_VERSIONS = (
    (3, 10, 2),
    (3, 11, 5),
    (3, 12, 2),
    (3, 13, 2),
)
_DIAGNOSTIC_FAILURES = (
    AttributeError,
    ImportError,
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
)
_CHECK_NAMES = (
    "python_bindings",
    "gdal_versions",
    "supported_gdal_version",
    "contour_smoke",
)

GDAL_INSTALL_GUIDANCE = (
    "Install matching GDAL and Python bindings from conda-forge, or install the "
    "native GDAL library first and then use the matching "
    "gdal310/gdal311/gdal312/gdal313 extra."
)

CheckName = Literal[
    "python_bindings",
    "gdal_versions",
    "supported_gdal_version",
    "contour_smoke",
]


@dataclass(frozen=True, slots=True)
class CheckResult:
    """One result returned by :func:`check`."""

    name: CheckName
    ok: bool
    observed: dict[str, str]
    message: str
    guidance: str


@dataclass(frozen=True, slots=True)
class CheckReport:
    """Structured GDAL diagnostic report returned by :func:`check`."""

    ok: bool
    checks: tuple[CheckResult, ...]

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable representation."""
        return {"ok": self.ok, "checks": [asdict(result) for result in self.checks]}


def load_gdal_modules() -> tuple[Any, Any]:
    """Import GDAL bindings only when runtime work is requested."""
    return import_module("osgeo.gdal"), import_module("osgeo.ogr")


def _installed_binding_version() -> str:
    """Return the independently installed GDAL Python distribution version."""
    return version("GDAL")


def _result(
    name: CheckName,
    ok: bool,
    observed: dict[str, str],
    message: str,
    guidance: str,
) -> CheckResult:
    return CheckResult(name, ok, observed, message, guidance)


def _not_run(name: CheckName, reason: str) -> CheckResult:
    return _result(
        name,
        False,
        {},
        f"Not run: {reason}",
        "Fix the earlier failed checks, then run the check again.",
    )


def _version_parts(value: str) -> tuple[int, int, int] | None:
    match = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?", value)
    if match is None:
        return None
    return (int(match.group(1)), int(match.group(2)), int(match.group(3) or 0))


def _reported_version(value: object) -> str:
    parts = _version_parts(str(value))
    return ".".join(map(str, parts)) if parts is not None else "unknown"


def _version_check(gdal: Any, binding_version: str) -> CheckResult:  # noqa: ANN401
    binding = _reported_version(binding_version)
    native = _reported_version(gdal.VersionInfo("RELEASE_NAME") or "unknown")
    binding_parts = _version_parts(binding)
    native_parts = _version_parts(native)
    compatible = (
        binding_parts is not None
        and native_parts is not None
        and binding_parts[:2] == native_parts[:2]
    )
    return _result(
        "gdal_versions",
        compatible,
        {"binding": binding, "native": native},
        (
            "Python bindings and native GDAL are compatible."
            if compatible
            else "Python bindings and native GDAL must have the same major and minor version."
        ),
        "No action needed." if compatible else GDAL_INSTALL_GUIDANCE,
    )


def _supported_version_check(gdal: Any) -> CheckResult:  # noqa: ANN401
    native = _reported_version(gdal.VersionInfo("RELEASE_NAME") or "unknown")
    version = _version_parts(native)
    supported = version in _SUPPORTED_GDAL_VERSIONS
    tested = ", ".join(".".join(map(str, item)) for item in _SUPPORTED_GDAL_VERSIONS)
    return _result(
        "supported_gdal_version",
        supported,
        {"native": native, "tested": tested},
        (
            "Installed GDAL matches a tested version."
            if supported
            else "Installed GDAL does not match a tested version."
        ),
        (
            "No action needed."
            if supported
            else f"Install one of the tested GDAL versions: {tested}."
        ),
    )


def _smoke_check() -> CheckResult:
    """Generate a tiny contour through the public API."""
    try:
        import xarray as xr

        from isobands.core import from_raster

        data = xr.DataArray(
            [[0.0, 1.0], [1.0, 2.0]],
            dims=("y", "x"),
            coords={"x": [0.0, 1.0], "y": [1.0, 0.0]},
        )
        result = from_raster(data, levels=[1.0], crs="EPSG:4326")
        if list(result.columns) != ["min_value", "max_value", "geometry"]:
            raise ValueError("unexpected contour result")
    except _DIAGNOSTIC_FAILURES as exc:
        return _result(
            "contour_smoke",
            False,
            {"error": type(exc).__name__},
            "The in-memory contour smoke test failed.",
            "Reinstall a complete, matching GDAL build, then run the check again.",
        )
    return _result(
        "contour_smoke",
        True,
        {"result": "generated"},
        "A tiny in-memory contour was generated successfully.",
        "No action needed.",
    )


def check() -> CheckReport:
    """Check whether the active environment can generate isobands.

    Ordinary installation failures are returned in the report rather than raised.
    """
    try:
        gdal, _ogr = load_gdal_modules()
    except _DIAGNOSTIC_FAILURES as exc:
        bindings = _result(
            "python_bindings",
            False,
            {"error": type(exc).__name__},
            "GDAL Python bindings could not be imported.",
            GDAL_INSTALL_GUIDANCE,
        )
        return CheckReport(
            False,
            (
                bindings,
                *(
                    _not_run(name, "GDAL Python bindings are unavailable")
                    for name in _CHECK_NAMES[1:]
                ),
            ),
        )

    bindings = _result(
        "python_bindings",
        True,
        {"gdal": "imported", "ogr": "imported"},
        "GDAL and OGR Python bindings imported successfully.",
        "No action needed.",
    )
    try:
        versions = _version_check(gdal, _installed_binding_version())
    except _DIAGNOSTIC_FAILURES as exc:
        versions = _result(
            "gdal_versions",
            False,
            {"error": type(exc).__name__},
            "Could not read GDAL binding and native versions.",
            GDAL_INSTALL_GUIDANCE,
        )
    try:
        supported = _supported_version_check(gdal)
    except _DIAGNOSTIC_FAILURES as exc:
        supported = _result(
            "supported_gdal_version",
            False,
            {"error": type(exc).__name__},
            "Could not determine whether the GDAL version is tested.",
            GDAL_INSTALL_GUIDANCE,
        )
    smoke = (
        _smoke_check()
        if versions.ok and supported.ok
        else _not_run("contour_smoke", "a required GDAL version check failed")
    )
    checks = (bindings, versions, supported, smoke)
    return CheckReport(all(result.ok for result in checks), checks)

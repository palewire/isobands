"""Coordinate discovery and validation for regular raster grids."""

from __future__ import annotations

from collections.abc import Hashable
from typing import Any

import numpy as np
import xarray as xr

# A coordinate is considered regularly spaced when every interval is within
# this relative (and absolute) tolerance of the first interval.  The
# absolute term matters for coordinates close to zero.
SPACING_RTOL = 1e-9
SPACING_ATOL = 1e-12

_X_STANDARD_NAMES = frozenset(
    {"longitude", "grid_longitude", "projection_x_coordinate", "x"}
)
_Y_STANDARD_NAMES = frozenset(
    {"latitude", "grid_latitude", "projection_y_coordinate", "y"}
)
_X_NAMES = frozenset({"x", "lon", "longitude"})
_Y_NAMES = frozenset({"y", "lat", "latitude"})


def materialize_array(value: Any) -> np.ndarray:  # noqa: ANN401
    """Return a NumPy array without mutating an xarray or Dask object."""

    if hasattr(value, "compute"):
        value = value.compute()
    return np.asarray(value)


def _metadata_role(coord: xr.DataArray) -> str | None:
    """Return the role declared by CF metadata, if any."""

    attrs = coord.attrs
    axis = attrs.get("axis")
    standard_name = attrs.get("standard_name")
    axis_text = str(axis).strip().upper() if axis is not None else ""
    standard_text = (
        str(standard_name).strip().lower() if standard_name is not None else ""
    )
    axis_role = axis_text if axis_text in {"X", "Y"} else None
    standard_role = (
        "x"
        if standard_text in _X_STANDARD_NAMES
        else "y"
        if standard_text in _Y_STANDARD_NAMES
        else None
    )
    if (
        axis_role is not None
        and standard_role is not None
        and axis_role.lower() != standard_role
    ):
        raise ValueError(
            f"Coordinate {coord.name!r} has conflicting axis and standard_name metadata"
        )
    return axis_role.lower() if axis_role is not None else standard_role


def _name_role(name: Hashable) -> str | None:
    text = str(name).strip().lower()
    if text in _X_NAMES:
        return "x"
    if text in _Y_NAMES:
        return "y"
    return None


def identify_spatial_dimensions(data: xr.DataArray) -> tuple[Hashable, Hashable]:
    """Find the x and y coordinate names, preferring CF metadata.

    CF ``axis`` and ``standard_name`` declarations are considered before
    conventional names (``x``, ``y``, ``lon``, ``lat``, and their long forms).
    A coordinate can be selected even when it is malformed so validation can
    report the useful dimensional/curvilinear error.
    """

    metadata: dict[str, list[Hashable]] = {"x": [], "y": []}
    conventional: dict[str, list[Hashable]] = {"x": [], "y": []}
    for name, coord in data.coords.items():
        role = _metadata_role(coord)
        if role is not None:
            metadata[role].append(name)
        else:
            role = _name_role(name)
            if role is not None:
                conventional[role].append(name)

    selected: dict[str, list[Hashable]] = {
        role: metadata[role] or conventional[role] for role in ("x", "y")
    }
    missing = [role for role in ("x", "y") if not selected[role]]
    if missing:
        missing_text = " and ".join(missing)
        raise ValueError(
            f"Could not identify {missing_text} spatial coordinate; "
            "add CF axis/standard_name metadata or pass a DataArray with "
            "x/y (or longitude/latitude) coordinates"
        )
    ambiguous = [role for role in ("x", "y") if len(selected[role]) != 1]
    if ambiguous:
        details = ", ".join(f"{role}={selected[role]!r}" for role in ambiguous)
        raise ValueError(f"Ambiguous spatial coordinates ({details})")
    x_name, y_name = selected["x"][0], selected["y"][0]
    x_coord, y_coord = data.coords[x_name], data.coords[y_name]
    x_dim = x_coord.dims[0] if x_coord.ndim == 1 else x_name
    y_dim = y_coord.dims[0] if y_coord.ndim == 1 else y_name
    if x_dim == y_dim:
        raise ValueError(
            f"Spatial coordinates {x_name!r} and {y_name!r} use the same "
            f"dimension {x_dim!r}"
        )
    return x_name, y_name


def validate_coordinate(
    coord: xr.DataArray,
    *,
    axis: str,
) -> tuple[np.ndarray, float]:
    """Validate a one-dimensional finite, monotonic, regular coordinate."""

    if coord.ndim != 1:
        raise ValueError(
            f"{axis} coordinate {coord.name!r} must be one-dimensional; "
            "curvilinear coordinates are not supported"
        )
    if not coord.dims:
        raise ValueError(f"{axis} coordinate {coord.name!r} has no dimension")
    values = materialize_array(coord.data)
    if values.ndim != 1:
        raise ValueError(f"{axis} coordinate {coord.name!r} must be one-dimensional")
    if not np.issubdtype(values.dtype, np.number) or np.issubdtype(
        values.dtype, np.complexfloating
    ):
        raise TypeError(f"{axis} coordinate {coord.name!r} must contain numeric values")
    with np.errstate(all="ignore"):
        values = values.astype(np.float64, copy=False)
    if values.size < 2:
        raise ValueError(
            f"{axis} coordinate {coord.name!r} must contain at least two points"
        )
    if not np.all(np.isfinite(values)):
        raise ValueError(f"{axis} coordinate {coord.name!r} contains nonfinite values")
    with np.errstate(all="ignore"):
        differences = np.diff(values)
    if not np.all(np.isfinite(differences)):
        raise ValueError(
            f"{axis} coordinate spacing is not finite; coordinate differences "
            "overflow the supported numeric range"
        )
    step = float(differences[0])
    if step == 0 or (not np.all(differences > 0) and not np.all(differences < 0)):
        raise ValueError(
            f"{axis} coordinate {coord.name!r} must be strictly monotonic "
            "with no duplicate points"
        )
    if not np.allclose(
        differences,
        step,
        rtol=SPACING_RTOL,
        atol=SPACING_ATOL,
    ):
        raise ValueError(
            f"{axis} coordinate {coord.name!r} is irregularly spaced; "
            f"intervals must agree within rtol={SPACING_RTOL:g} and "
            f"atol={SPACING_ATOL:g}"
        )
    return values, step


def geotransform_from_coordinates(
    x_values: np.ndarray,
    y_values: np.ndarray,
) -> tuple[float, float, float, float, float, float]:
    """Compute a GDAL geotransform from pixel-center coordinates."""

    with np.errstate(all="ignore"):
        x_centers = np.asarray(x_values, dtype=np.float64)
        y_centers = np.asarray(y_values, dtype=np.float64)
    if (
        x_centers.ndim != 1
        or y_centers.ndim != 1
        or x_centers.size < 2
        or y_centers.size < 2
        or not np.all(np.isfinite(x_centers))
        or not np.all(np.isfinite(y_centers))
    ):
        raise ValueError("Raster coordinates must be finite one-dimensional arrays")
    with np.errstate(all="ignore"):
        x_step = np.subtract(x_centers[1], x_centers[0])
        y_step = np.subtract(y_centers[1], y_centers[0])
        transform = np.asarray(
            [
                np.subtract(x_centers[0], x_step / 2),
                x_step,
                0.0,
                np.subtract(y_centers[0], y_step / 2),
                0.0,
                y_step,
            ],
            dtype=np.float64,
        )
    if not np.all(np.isfinite(transform)):
        raise ValueError(
            "GDAL geotransform is not finite; coordinate spacing or "
            "pixel-center origin overflowed"
        )
    return (
        float(transform[0]),
        float(transform[1]),
        float(transform[2]),
        float(transform[3]),
        float(transform[4]),
        float(transform[5]),
    )

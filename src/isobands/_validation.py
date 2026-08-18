"""Validation and materialization of raster inputs."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import numpy as np
import pyproj
import xarray as xr

from isobands._coordinates import (
    geotransform_from_coordinates,
    identify_spatial_dimensions,
    materialize_array,
    validate_coordinate,
)


@dataclass(frozen=True, slots=True)
class RasterSpec:
    """A validated, GDAL-oriented representation of an xarray raster."""

    values: np.ndarray
    valid_values: np.ndarray
    geotransform: tuple[float, float, float, float, float, float]
    crs: pyproj.CRS
    nodata: float | int | None
    min_value: float
    max_value: float


def _resolve_crs(data: xr.DataArray, explicit: Any | None) -> pyproj.CRS:  # noqa: ANN401
    if explicit is not None:
        return _parse_crs(explicit, "explicit crs")

    # Do not import rioxarray here.  If its accessor has already been
    # registered, it is the most authoritative source for a DataArray.
    try:
        rio = data.rio
    except (AttributeError, RuntimeError, ValueError):
        rio = None
    if rio is not None:
        try:
            rio_crs = rio.crs
        except (AttributeError, ValueError):
            rio_crs = None
        if rio_crs is not None:
            return _parse_crs(rio_crs, "rioxarray metadata")

    candidates: list[tuple[str, Any]] = []
    attrs = dict(data.attrs)
    encoding = dict(data.encoding)
    grid_mapping_name = attrs.get("grid_mapping", encoding.get("grid_mapping"))
    if grid_mapping_name is not None:
        try:
            mapping = data.coords[str(grid_mapping_name)]
        except (KeyError, TypeError):
            mapping = None
        if mapping is not None:
            mapping_attrs = dict(mapping.attrs)
            if "grid_mapping_name" in mapping_attrs:
                candidates.append(("CF grid-mapping metadata", mapping_attrs))
            _append_crs_attributes(candidates, mapping_attrs, "grid-mapping metadata")

    _append_crs_attributes(candidates, attrs, "DataArray metadata")
    _append_crs_attributes(candidates, encoding, "DataArray encoding")
    for name, coord in data.coords.items():
        _append_crs_attributes(candidates, dict(coord.attrs), f"coordinate {name!r}")

    parsed: list[tuple[str, pyproj.CRS]] = []
    errors: list[str] = []
    for label, value in candidates:
        try:
            parsed.append((label, _parse_crs(value, label)))
        except (TypeError, ValueError) as error:
            errors.append(f"{label}: {error}")
    if not parsed:
        detail = f" Metadata errors: {'; '.join(errors)}." if errors else ""
        raise ValueError(
            "A CRS could not be resolved from the raster. Pass crs= "
            "explicitly (for example crs='EPSG:4326')." + detail
        )
    first = parsed[0][1]
    if any(not first.equals(candidate) for _, candidate in parsed[1:]):
        labels = ", ".join(label for label, _ in parsed)
        raise ValueError(f"Ambiguous CRS metadata ({labels}); pass crs= explicitly")
    return first


def _append_crs_attributes(
    candidates: list[tuple[str, Any]],
    attrs: Mapping[str, Any],
    label: str,
) -> None:
    for key in ("spatial_ref", "crs_wkt", "crs"):
        if key in attrs and attrs[key] is not None:
            candidates.append((f"{label} {key}", attrs[key]))


def _parse_crs(value: Any, label: str) -> pyproj.CRS:  # noqa: ANN401
    try:
        if isinstance(value, Mapping) and "grid_mapping_name" in value:
            parsed = pyproj.CRS.from_cf(dict(value))
        else:
            parsed = pyproj.CRS.from_user_input(value)
    except (TypeError, ValueError, pyproj.exceptions.ProjError) as error:
        raise ValueError(f"{label} is not a valid CRS: {error}") from error
    if not isinstance(parsed, pyproj.CRS):
        raise TypeError(f"{label} did not produce a pyproj.CRS")
    return parsed


def _metadata_nodata(data: xr.DataArray) -> float | int | None:
    for source_name, source in (
        ("encoding", data.encoding),
        ("attributes", data.attrs),
    ):
        for key in ("_FillValue", "missing_value"):
            if key in source and source[key] is not None:
                value = _coerce_nodata(source[key], f"{source_name} {key}")
                if value is not None:
                    return value
    return None


def _coerce_nodata(value: Any, label: str) -> float | int | None:  # noqa: ANN401
    array = np.asarray(value)
    if array.size != 1:
        raise ValueError(f"{label} must be a scalar numeric value")
    scalar = array.reshape(-1)[0]
    if isinstance(scalar, (bool, np.bool_)) or not np.issubdtype(
        np.asarray(scalar).dtype, np.number
    ):
        raise TypeError(f"{label} must be a scalar numeric value")
    if np.issubdtype(np.asarray(scalar).dtype, np.integer):
        return int(scalar)
    try:
        result = float(scalar)
    except (TypeError, ValueError, OverflowError) as error:
        raise TypeError(f"{label} must be a scalar numeric value") from error
    # NaN fill values are a common convention; nonfinite cells are handled
    # below with a finite GDAL sentinel instead.
    return result if np.isfinite(result) else None


def _sentinel(values: np.ndarray) -> float:
    """Select a finite value outside the valid range of a float dtype."""

    info = np.finfo(values.dtype)
    finite = values[np.isfinite(values)]
    unique = np.unique(finite)
    if unique[0] > info.min:
        candidate = np.nextafter(
            np.asarray(unique[0], dtype=values.dtype),
            np.asarray(info.min, dtype=values.dtype),
        )
    elif unique[-1] < info.max:
        candidate = np.nextafter(
            np.asarray(unique[-1], dtype=values.dtype),
            np.asarray(info.max, dtype=values.dtype),
        )
    else:
        next_values = np.nextafter(
            unique[:-1],
            np.asarray(info.max, dtype=values.dtype),
        )
        gaps = next_values < unique[1:]
        if not np.any(gaps):
            raise ValueError(
                "Could not find a finite nodata sentinel for the raster dtype"
            )
        candidate = next_values[np.flatnonzero(gaps)[0]]
    candidate_float = float(candidate)
    if not np.isfinite(candidate_float):
        raise ValueError("Could not find a finite nodata sentinel for the raster dtype")
    return candidate_float


def _materialize_values(
    data: xr.DataArray,
    nodata: float | int | None,
) -> tuple[np.ndarray, float | int | None, np.ndarray]:
    raw = materialize_array(data.data)
    if raw.ndim != 2:
        raise ValueError("Raster data must be two-dimensional after squeezing")
    if (
        not np.issubdtype(raw.dtype, np.number)
        or np.issubdtype(raw.dtype, np.complexfloating)
        or np.issubdtype(raw.dtype, np.bool_)
    ):
        raise TypeError("Raster data must contain numeric real values")
    if np.issubdtype(raw.dtype, np.integer):
        valid_integers = np.ones(raw.shape, dtype=bool)
        if nodata is not None:
            valid_integers &= raw != nodata
        _validate_integer_precision(raw[valid_integers])
    values = np.array(raw, copy=True)
    floating = np.issubdtype(values.dtype, np.floating)
    if nodata is not None and np.issubdtype(values.dtype, np.integer):
        integer_info = np.iinfo(values.dtype)
        representable = (
            isinstance(nodata, int) or float(nodata).is_integer()
        ) and integer_info.min <= nodata <= integer_info.max
        if not representable:
            values = _cast_integer_values(values, nodata)
    finite_mask = np.isfinite(values) if floating else np.ones(values.shape, dtype=bool)
    if nodata is not None and floating:
        limits = np.finfo(values.dtype)
        if float(limits.min) <= nodata <= float(limits.max):
            converted = np.asarray(nodata, dtype=values.dtype).item()
            if np.isfinite(converted):
                nodata = float(converted)
            else:
                values = values.astype(np.float64)
                finite_mask = np.isfinite(values)
        else:
            values = values.astype(np.float64)
            finite_mask = np.isfinite(values)
    valid_mask = finite_mask.copy()
    if nodata is not None:
        valid_mask &= values != nodata
    if not np.any(valid_mask):
        raise ValueError(
            "Raster contains no valid finite cells (all values are nodata)"
        )

    if floating and not np.all(finite_mask):
        replacement = nodata if nodata is not None else _sentinel(values)
        values[~finite_mask] = replacement
        if nodata is None:
            nodata = replacement
    valid_values = values[valid_mask]
    return values, nodata, valid_values


def _validate_integer_precision(values: np.ndarray) -> None:
    """Reject integer samples that Float64 cannot represent consecutively."""

    exact_limit = 2**53
    if np.any(values < -exact_limit) or np.any(values > exact_limit):
        raise ValueError(
            "Integer values exceed GDAL Float64 exact precision; "
            "rescale or cast intentionally."
        )


def _cast_integer_values(values: np.ndarray, nodata: float | int) -> np.ndarray:
    """Widen integer values before applying an out-of-range nodata value."""

    minimum = min(int(np.min(values)), int(nodata))
    maximum = max(int(np.max(values)), int(nodata))
    for dtype in (np.int8, np.int16, np.int32, np.int64):
        limits = np.iinfo(dtype)
        if limits.min <= minimum and maximum <= limits.max:
            return values.astype(dtype)

    cast = values.astype(np.float64)
    if np.array_equal(cast.astype(values.dtype), values):
        return cast
    raise ValueError(
        "Integer raster values and nodata cannot be represented losslessly "
        "in a GDAL-compatible numeric array"
    )


def prepare_raster(
    data: xr.DataArray,
    *,
    crs: Any | None,  # noqa: ANN401
    nodata: float | None,
) -> RasterSpec:
    """Validate and materialize a regular rectilinear two-dimensional raster.

    Singleton dimensions are squeezed in a derived DataArray, leaving the
    caller's object unchanged.  Coordinates must be regular to
    ``rtol=1e-9`` and ``atol=1e-12``; geotransform origins refer to pixel
    corners while coordinate values refer to pixel centers. Integer samples
    must be within Float64's exact consecutive-integer range for GDAL.
    """

    if not isinstance(data, xr.DataArray):
        raise TypeError("data must be an xarray.DataArray")
    if crs is not None:
        explicit_crs = _parse_crs(crs, "explicit crs")
    else:
        explicit_crs = None
    if nodata is not None:
        explicit_nodata = _coerce_nodata(nodata, "explicit nodata")
        if explicit_nodata is None:
            raise ValueError("explicit nodata must be finite for GDAL")
    else:
        explicit_nodata = _metadata_nodata(data)

    singleton_dims = [dim for dim, size in data.sizes.items() if size == 1]
    raster = data.squeeze(dim=singleton_dims, drop=True)
    if raster.ndim != 2:
        raise ValueError(
            "Raster data must have exactly two nonsingleton dimensions; "
            "singleton dimensions may be squeezed"
        )
    x_name, y_name = identify_spatial_dimensions(raster)
    x_coord, y_coord = raster.coords[x_name], raster.coords[y_name]
    x_values, _ = validate_coordinate(x_coord, axis="x")
    y_values, _ = validate_coordinate(y_coord, axis="y")
    x_dim, y_dim = x_coord.dims[0], y_coord.dims[0]
    if x_dim not in raster.dims or y_dim not in raster.dims:
        raise ValueError("Spatial coordinates must be aligned to raster dimensions")
    if raster.sizes[x_dim] != x_values.size or raster.sizes[y_dim] != y_values.size:
        raise ValueError("Spatial coordinate lengths must match their dimensions")
    ordered = raster.transpose(y_dim, x_dim)
    values, resolved_nodata, valid_values = _materialize_values(
        ordered,
        explicit_nodata,
    )
    resolved_crs = explicit_crs or _resolve_crs(data, None)
    return RasterSpec(
        values=values,
        valid_values=valid_values,
        geotransform=geotransform_from_coordinates(x_values, y_values),
        crs=resolved_crs,
        nodata=resolved_nodata,
        min_value=float(np.min(valid_values)),
        max_value=float(np.max(valid_values)),
    )

"""Private GDAL bridge for creating filled contour polygons in memory."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from itertools import pairwise
from math import isfinite
from typing import TYPE_CHECKING, Any

import numpy as np
from shapely import from_wkb
from shapely.errors import GEOSException
from shapely.geometry import MultiPolygon, Polygon
from shapely.geometry.base import BaseGeometry

if TYPE_CHECKING:
    from isobands._validation import RasterSpec


@dataclass(frozen=True, slots=True)
class _ContourInput:
    """Numerically conditioned values and their original contour labels."""

    values: np.ndarray
    nodata: float | None
    normalized_bounds: tuple[float, ...]
    original_bounds: tuple[float, ...]
    upper_bound: float
    component_band_index: int | None = None


@dataclass(frozen=True, slots=True)
class _RingRoleParts:
    """Rebuilt shells and deferred candidates from one invalid GDAL feature."""

    retained: tuple[Polygon, ...]
    promoted: tuple[Polygon, ...]


@dataclass(frozen=True, slots=True)
class _FeatureParts:
    """Retained GDAL geometries and deferred component/ring candidates."""

    retained: tuple[tuple[float, float, BaseGeometry], ...]
    candidates: tuple[tuple[float, float, Polygon], ...]


GeoTransform = tuple[float, float, float, float, float, float]


def generate_polygons(
    raster: RasterSpec,
    *,
    thresholds: Sequence[float],
) -> list[tuple[float, float, BaseGeometry]]:
    """Generate filled contour polygons without creating files on disk.

    ``thresholds`` contains only the interior boundaries. Finite fixed levels
    let the public result clip outer bands to the valid raster extrema.
    """

    gdal, ogr = _import_gdal()
    contour_input = _condition_contour_input(raster, thresholds)
    with gdal.ExceptionMgr(useExceptions=True):
        try:
            if contour_input.nodata is None:
                return _append_promotions(
                    _generate_component(
                        gdal,
                        ogr,
                        raster,
                        contour_input,
                        raster.geotransform,
                    )
                )
            retained: list[tuple[float, float, BaseGeometry]] = []
            candidates: list[tuple[float, float, Polygon]] = []
            for component_input, geotransform in _iter_component_windows(
                contour_input,
                raster.geotransform,
            ):
                parts = _generate_component(
                    gdal,
                    ogr,
                    raster,
                    component_input,
                    geotransform,
                )
                retained.extend(parts.retained)
                candidates.extend(parts.candidates)
            return _append_promotions(_FeatureParts(tuple(retained), tuple(candidates)))
        except RuntimeError as error:
            raise RuntimeError(
                f"GDAL failed while generating filled contour polygons: {error}"
            ) from error


def _generate_component(
    gdal: Any,  # noqa: ANN401
    ogr: Any,  # noqa: ANN401
    raster: RasterSpec,
    contour_input: _ContourInput,
    geotransform: GeoTransform,
) -> _FeatureParts:
    """Run GDAL contouring for one four-connected valid raster component."""

    raster_dataset: Any | None = None
    vector_dataset: Any | None = None
    band: Any | None = None
    layer: Any | None = None
    try:
        component_input = _perturb_constant_component(contour_input)
        raster_dataset, band = _create_raster_dataset(
            gdal,
            raster,
            component_input,
            geotransform,
        )
        vector_dataset, layer = _create_vector_layer(gdal, ogr)
        result = gdal.ContourGenerateEx(band, layer, _contour_options(component_input))
        if result != gdal.CE_None:
            raise RuntimeError(
                "GDAL could not generate filled contour polygons "
                f"(error code {result})."
            )
        return _read_features(layer, component_input)
    finally:
        del layer, band, vector_dataset, raster_dataset


def _import_gdal() -> tuple[Any, Any]:
    """Import GDAL lazily so package import does not initialize its bindings."""

    try:
        from osgeo import gdal, ogr
    except ImportError as error:
        raise RuntimeError(
            "GDAL Python bindings are required to generate isobands. "
            "Install the matching gdal310/gdal312 extra or conda-forge bindings."
        ) from error
    return gdal, ogr


def _create_raster_dataset(
    gdal: Any,  # noqa: ANN401
    raster: RasterSpec,
    contour_input: _ContourInput,
    geotransform: GeoTransform,
) -> tuple[Any, Any]:
    """Materialize a RasterSpec in GDAL's in-memory raster driver."""

    height, width = contour_input.values.shape
    driver = gdal.GetDriverByName("MEM")
    if driver is None:
        raise RuntimeError("GDAL's in-memory MEM driver is unavailable.")
    dataset = driver.Create("", width, height, 1, gdal.GDT_Float64)
    if dataset is None:
        raise RuntimeError("GDAL could not create an in-memory raster dataset.")
    _check_gdal_result(
        dataset.SetGeoTransform(geotransform), gdal, "set the raster geotransform"
    )
    _check_gdal_result(
        dataset.SetProjection(raster.crs.to_wkt()),
        gdal,
        "set the raster projection",
    )
    band = dataset.GetRasterBand(1)
    if band is None:
        raise RuntimeError("GDAL could not create an in-memory raster band.")
    _check_gdal_result(
        band.WriteArray(contour_input.values),
        gdal,
        "write raster values",
    )
    if contour_input.nodata is not None:
        _check_gdal_result(
            band.SetNoDataValue(contour_input.nodata),
            gdal,
            "set raster nodata",
        )
    return dataset, band


def _check_gdal_result(result: int | None, gdal: Any, operation: str) -> None:  # noqa: ANN401
    """Raise an actionable error when a GDAL configuration call fails."""

    if result not in (None, gdal.CE_None):
        raise RuntimeError(f"GDAL could not {operation} (error code {result}).")


def _condition_contour_input(
    raster: RasterSpec,
    thresholds: Sequence[float],
) -> _ContourInput:
    """Scale finite samples into GDAL's stable ``[-1, 1]`` contour range."""

    original_bounds = (raster.min_value, *thresholds, raster.max_value)
    magnitude = max(abs(value) for value in original_bounds)
    scale = magnitude if magnitude != 0.0 else 1.0
    raw_values = np.asarray(raster.values, dtype=np.float64)
    valid = (
        np.ones(raw_values.shape, dtype=bool)
        if raster.nodata is None
        else raster.values != raster.nodata
    )
    values = np.empty_like(raw_values)
    values[valid] = raw_values[valid] / scale
    normalized_bounds = tuple(value / scale for value in original_bounds)
    if raster.min_value != raster.max_value and (
        not all(isfinite(value) for value in normalized_bounds)
        or any(left >= right for left, right in pairwise(normalized_bounds))
    ):
        _raise_dynamic_range_error()
    if not np.all(np.isfinite(values[valid])):
        _raise_dynamic_range_error()
    nodata = None
    if not np.all(valid):
        nodata = 2.0
        values[~valid] = nodata

    upper_bound = (
        normalized_bounds[-1] + 1e-2
        if raster.min_value == raster.max_value
        else normalized_bounds[-1] + 1e-5
    )
    if not isfinite(upper_bound):
        _raise_dynamic_range_error()
    return _ContourInput(
        values=values,
        nodata=nodata,
        normalized_bounds=normalized_bounds,
        original_bounds=original_bounds,
        upper_bound=upper_bound,
    )


def _raise_dynamic_range_error() -> None:
    """Explain when affine GDAL conditioning cannot preserve thresholds."""

    raise ValueError(
        "The data and levels span a dynamic range too large to contour safely; "
        "rescale data or choose representable levels."
    )


def _iter_component_windows(
    contour_input: _ContourInput,
    geotransform: GeoTransform,
) -> Iterator[tuple[_ContourInput, GeoTransform]]:
    """Yield cropped four-connected valid components without retaining masks."""

    assert contour_input.nodata is not None
    values = contour_input.values
    visited = np.zeros(values.shape, dtype=bool)
    height, width = values.shape
    for row, column in np.ndindex(values.shape):
        if values[row, column] == contour_input.nodata or visited[row, column]:
            continue
        pending = [(row, column)]
        cells: list[tuple[int, int]] = []
        visited[row, column] = True
        while pending:
            current_row, current_column = pending.pop()
            cells.append((current_row, current_column))
            for row_offset, column_offset in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                next_row = current_row + row_offset
                next_column = current_column + column_offset
                if (
                    0 <= next_row < height
                    and 0 <= next_column < width
                    and values[next_row, next_column] != contour_input.nodata
                    and not visited[next_row, next_column]
                ):
                    visited[next_row, next_column] = True
                    pending.append((next_row, next_column))
        row_start = min(row for row, _ in cells)
        row_stop = max(row for row, _ in cells) + 1
        column_start = min(column for _, column in cells)
        column_stop = max(column for _, column in cells) + 1
        component_values = np.full(
            (row_stop - row_start, column_stop - column_start),
            contour_input.nodata,
        )
        for current_row, current_column in cells:
            component_values[current_row - row_start, current_column - column_start] = (
                contour_input.values[current_row, current_column]
            )
        yield (
            _ContourInput(
                values=component_values,
                nodata=contour_input.nodata,
                normalized_bounds=contour_input.normalized_bounds,
                original_bounds=contour_input.original_bounds,
                upper_bound=contour_input.upper_bound,
            ),
            _shift_geotransform(geotransform, row_start, column_start),
        )


def _shift_geotransform(
    geotransform: GeoTransform,
    row_offset: int,
    column_offset: int,
) -> GeoTransform:
    """Move a geotransform origin to a cropped raster window's top-left cell."""

    origin_x, pixel_width, row_rotation, origin_y, column_rotation, pixel_height = (
        geotransform
    )
    return (
        origin_x + column_offset * pixel_width + row_offset * row_rotation,
        pixel_width,
        row_rotation,
        origin_y + column_offset * column_rotation + row_offset * pixel_height,
        column_rotation,
        pixel_height,
    )


def _perturb_constant_component(contour_input: _ContourInput) -> _ContourInput:
    """Give every constant component a variation inside its global band."""

    valid = contour_input.values != contour_input.nodata
    component_values = contour_input.values[valid]
    value = float(component_values[0])
    if not np.all(component_values == value):
        return contour_input
    band_index = _component_band_index(value, contour_input)
    upper = _component_band_upper(band_index, contour_input)
    perturbation = value + (upper - value) / 2
    if not isfinite(perturbation) or not value < perturbation < upper:
        perturbation = float(np.nextafter(value, upper))
    if not isfinite(perturbation) or not value < perturbation < upper:
        raise ValueError(
            "A constant nodata-separated component cannot be perturbed within "
            "its contour band; rescale data or choose representable levels."
        )
    values = contour_input.values.copy()
    valid_indices = np.argwhere(valid)
    values[tuple(valid_indices[0])] = perturbation
    return _ContourInput(
        values=values,
        nodata=contour_input.nodata,
        normalized_bounds=contour_input.normalized_bounds,
        original_bounds=contour_input.original_bounds,
        upper_bound=contour_input.upper_bound,
        component_band_index=band_index,
    )


def _component_band_index(value: float, contour_input: _ContourInput) -> int:
    """Return the lower-inclusive global band index for a component value."""

    bounds = contour_input.normalized_bounds
    index = int(np.searchsorted(bounds, value, side="right")) - 1
    if index < 0:
        raise ValueError("A component value falls below the conditioned contour range.")
    if index >= len(bounds) - 1:
        return len(bounds) - 2
    return index


def _component_band_upper(index: int, contour_input: _ContourInput) -> float:
    """Return the exclusive conditioned upper bound for a component's band."""

    bounds = contour_input.normalized_bounds
    upper = contour_input.upper_bound if index == len(bounds) - 2 else bounds[index + 1]
    value = bounds[index]
    if not value < upper:
        raise ValueError(
            "A constant nodata-separated component has no representable contour "
            "band; rescale data or choose representable levels."
        )
    return upper


def _create_vector_layer(
    gdal: Any,  # noqa: ANN401
    ogr: Any,  # noqa: ANN401
) -> tuple[Any, Any]:
    """Create an in-memory output layer with numeric contour-bound fields."""
    mem_driver = gdal.GetDriverByName("MEM")
    if mem_driver is not None and mem_driver.GetMetadataItem("DCAP_VECTOR") == "YES":
        dataset = mem_driver.Create("", 0, 0, 0, gdal.GDT_Unknown)
    else:
        memory_driver = ogr.GetDriverByName("Memory")
        if memory_driver is None:
            raise RuntimeError("GDAL's in-memory Memory vector driver is unavailable.")
        dataset = memory_driver.CreateDataSource("")
    if dataset is None:
        raise RuntimeError("GDAL could not create an in-memory vector dataset.")
    layer = dataset.CreateLayer("isobands", geom_type=ogr.wkbMultiPolygon)
    if layer is None:
        raise RuntimeError("GDAL could not create an in-memory contour layer.")
    for name in ("min_value", "max_value"):
        field = ogr.FieldDefn(name, ogr.OFTReal)
        if layer.CreateField(field) != ogr.OGRERR_NONE:
            raise RuntimeError(f"GDAL could not create the {name!r} contour field.")
    return dataset, layer


def _contour_options(contour_input: _ContourInput) -> list[str]:
    """Build ContourGenerateEx options for finite fixed-level polygons."""

    fixed_levels = ",".join(
        (
            *(format(level, ".17g") for level in contour_input.normalized_bounds[:-1]),
            format(contour_input.upper_bound, ".17g"),
        )
    )
    options = [
        "POLYGONIZE=YES",
        f"FIXED_LEVELS={fixed_levels}",
        "ELEV_FIELD_MIN=0",
        "ELEV_FIELD_MAX=1",
    ]
    if contour_input.nodata is not None:
        options.append(f"NODATA={contour_input.nodata:.17g}")
    return options


def _read_features(
    layer: Any,  # noqa: ANN401
    contour_input: _ContourInput,
) -> _FeatureParts:
    """Convert OGR feature geometries directly from WKB to Shapely.

    GDAL 3.12 can assign a disconnected exterior ring as a polygon interior
    when nodata splits a contour. The narrow normalization below only promotes
    such outside rings (which GDAL may leave touching at a vertex); it neither
    changes coordinates nor repairs overlapping or malformed topology.
    """

    retained: list[tuple[float, float, BaseGeometry]] = []
    candidates: list[tuple[float, float, Polygon]] = []
    valid = (
        np.ones(contour_input.values.shape, dtype=bool)
        if contour_input.nodata is None
        else contour_input.values != contour_input.nodata
    )
    component_minimum = contour_input.original_bounds[
        _component_band_index(float(np.min(contour_input.values[valid])), contour_input)
    ]
    layer.ResetReading()
    for feature in layer:
        ogr_geometry = feature.GetGeometryRef()
        if ogr_geometry is None:
            raise RuntimeError("GDAL produced a contour feature without geometry.")
        geometry = from_wkb(bytes(ogr_geometry.ExportToWkb()))
        minimum = _original_bound(
            float(feature.GetFieldAsDouble(0)),
            contour_input,
        )
        upper = _original_bound(
            float(feature.GetFieldAsDouble(1)),
            contour_input,
        )
        if contour_input.component_band_index is not None:
            index = contour_input.component_band_index
            minimum = contour_input.original_bounds[index]
            upper = contour_input.original_bounds[index + 1]
        elif minimum < component_minimum:
            # GDAL emits empty lower bands when a nodata-separated component
            # starts exactly on a fixed threshold. Clip that extrapolated label
            # to the component's lower-inclusive band and discard empty bands.
            minimum = component_minimum
        if contour_input.component_band_index is None and minimum >= upper:
            continue
        if geometry.is_empty or geometry.area == 0.0:
            continue
        if geometry.is_valid:
            retained.append((minimum, upper, geometry))
            continue
        parts = _normalize_gdal_ring_roles(geometry)
        retained.extend((minimum, upper, shell) for shell in parts.retained)
        candidates.extend((minimum, upper, ring) for ring in parts.promoted)

    return _FeatureParts(tuple(retained), tuple(candidates))


def _append_promotions(
    parts: _FeatureParts,
) -> list[tuple[float, float, BaseGeometry]]:
    """Append only outside rings not already represented by retained geometry."""

    promotions: list[tuple[float, float, Polygon]] = []
    for minimum, upper, candidate in parts.candidates:
        candidate = _retain_nested_covered_candidates(candidate, parts)
        if any(
            _contains_full_candidate(geometry, candidate)
            for _, _, geometry in parts.retained
        ):
            continue
        if any(
            _contains_full_candidate(geometry, candidate)
            for _, _, geometry in promotions
        ):
            continue
        promotions.append((minimum, upper, candidate))
    return [*parts.retained, *promotions]


def _retain_nested_covered_candidates(
    candidate: Polygon,
    parts: _FeatureParts,
) -> Polygon:
    """Keep a nested duplicate candidate as an exact interior ring."""

    nested_rings = [
        tuple(other.exterior.coords)
        for _, _, other in parts.candidates
        if other is not candidate
        and candidate.covers(other)
        and any(
            _contains_full_candidate(geometry, other)
            for _, _, geometry in parts.retained
        )
    ]
    if not nested_rings:
        return candidate
    try:
        rebuilt = Polygon(
            candidate.exterior.coords,
            [*(tuple(ring.coords) for ring in candidate.interiors), *nested_rings],
        )
    except (GEOSException, ValueError) as error:
        raise RuntimeError("GDAL generated malformed nested contour rings.") from error
    if rebuilt.is_empty or not rebuilt.is_valid:
        raise RuntimeError("GDAL generated an invalid nested contour ring.")
    return rebuilt


def _normalize_gdal_ring_roles(geometry: BaseGeometry) -> _RingRoleParts:
    """Promote only GDAL interior rings that are demonstrably outside a shell."""

    if isinstance(geometry, Polygon):
        return _normalize_polygon_ring_roles(geometry)
    if not isinstance(geometry, MultiPolygon):
        raise RuntimeError("GDAL generated an invalid non-polygon contour geometry.")

    retained: list[Polygon] = []
    candidates: list[Polygon] = []
    for polygon in geometry.geoms:
        if polygon.is_valid:
            # A valid component inside an invalid MultiPolygon can be GDAL's
            # duplicate representation of an outside ring. Defer it alongside
            # promoted rings until all retained geometries are available.
            candidates.append(polygon)
            continue
        parts = _normalize_polygon_ring_roles(polygon)
        retained.extend(parts.retained)
        candidates.extend(parts.promoted)
    if any(part.is_empty or not part.is_valid for part in retained):
        raise RuntimeError("GDAL generated an invalid filled-contour geometry.")
    return _RingRoleParts(tuple(retained), tuple(candidates))


def _normalize_polygon_ring_roles(polygon: Polygon) -> _RingRoleParts:
    """Rebuild one polygon, retaining holes and promoting outside ring exteriors."""

    try:
        shell = Polygon(polygon.exterior.coords)
        if shell.is_empty or shell.area == 0.0:
            # A zero-area ring cannot contain raster domain area. GDAL can emit
            # these artifacts next to a valid positive-area component.
            return _RingRoleParts((), ())
        if shell.is_empty or not shell.is_valid:
            if not polygon.interiors:
                return _RingRoleParts(_rebuild_self_touching_exterior(polygon), ())
            raise RuntimeError("GDAL generated an invalid contour exterior ring.")
        retained_holes: list[tuple[tuple[float, float], ...]] = []
        promoted: list[Polygon] = []
        for ring in polygon.interiors:
            ring_coordinates = tuple(ring.coords)
            ring_area = Polygon(ring_coordinates)
            if ring_area.is_empty or ring_area.area == 0.0:
                continue
            if not ring_area.is_valid:
                raise RuntimeError("GDAL generated an invalid contour interior ring.")
            if shell.covers(ring_area):
                retained_holes.append(ring_coordinates)
            # GDAL's false hole can share a single shell vertex without its
            # area overlapping the shell, so ``touches`` is still promotable.
            elif shell.disjoint(ring_area) or shell.touches(ring_area):
                promoted.append(ring_area)
            else:
                raise RuntimeError(
                    "GDAL generated an overlapping contour interior ring."
                )
        rebuilt = Polygon(polygon.exterior.coords, retained_holes)
    except (GEOSException, ValueError) as error:
        raise RuntimeError("GDAL generated malformed contour rings.") from error
    if rebuilt.is_empty or rebuilt.area == 0.0:
        return _RingRoleParts((), ())
    if not rebuilt.is_valid:
        raise RuntimeError("GDAL generated an invalid filled-contour geometry.")
    return _RingRoleParts((rebuilt,), tuple(promoted))


def _split_self_touching_exterior(
    coordinates: Sequence[tuple[float, float]],
) -> tuple[Polygon, ...]:
    """Split exact repeated-vertex exterior loops without repairing topology."""

    rings = [tuple(coordinates)]
    simple_rings: list[tuple[tuple[float, float], ...]] = []
    while rings:
        ring = rings.pop()
        seen: dict[tuple[float, float], int] = {}
        for end, coordinate in enumerate(ring[:-1]):
            start = seen.get(coordinate)
            if start is None:
                seen[coordinate] = end
                continue
            if end - start < 2:
                continue
            rings.extend(
                (
                    ring[start : end + 1],
                    (*ring[: start + 1], *ring[end + 1 :]),
                )
            )
            break
        else:
            simple_rings.append(ring)

    polygons: list[Polygon] = []
    for ring in simple_rings:
        candidate = Polygon(ring)
        if candidate.is_empty or candidate.area == 0.0:
            continue
        if not candidate.is_valid:
            raise RuntimeError("GDAL generated an invalid contour exterior ring.")
        polygons.append(candidate)
    return tuple(polygons)


def _rebuild_self_touching_exterior(polygon: Polygon) -> tuple[Polygon, ...]:
    """Classify exact repeated-vertex loops as shells or positive-area holes."""

    parts = _split_self_touching_exterior(polygon.exterior.coords)
    for index, left in enumerate(parts):
        for right in parts[index + 1 :]:
            if (
                left.intersection(right).area > 0.0
                and not left.covers(right)
                and not right.covers(left)
            ):
                raise RuntimeError("GDAL generated overlapping contour exteriors.")
    outer_parts = [
        part
        for part in parts
        if not any(other is not part and other.covers(part) for other in parts)
    ]
    holes: dict[int, list[tuple[tuple[float, float], ...]]] = {
        index: [] for index in range(len(outer_parts))
    }
    for part in parts:
        all_containers = [
            outer for outer in parts if outer is not part and outer.covers(part)
        ]
        if len(all_containers) > 1:
            raise RuntimeError("GDAL generated ambiguously nested contour exteriors.")
        containers = [
            (index, outer)
            for index, outer in enumerate(outer_parts)
            if outer is not part and outer.covers(part)
        ]
        if not containers:
            continue
        if len(containers) != 1:
            raise RuntimeError("GDAL generated ambiguously nested contour exteriors.")
        holes[containers[0][0]].append(tuple(part.exterior.coords))

    rebuilt: list[Polygon] = []
    for index, outer in enumerate(outer_parts):
        candidate = Polygon(outer.exterior.coords, holes[index])
        if candidate.is_empty or candidate.area == 0.0:
            continue
        if not candidate.is_valid:
            raise RuntimeError(
                "GDAL generated an invalid self-touching contour exterior."
            )
        rebuilt.append(candidate)
    if not rebuilt and parts:
        raise RuntimeError("GDAL generated an invalid self-touching contour exterior.")
    return tuple(rebuilt)


def _contains_full_candidate(geometry: BaseGeometry, candidate: Polygon) -> bool:
    """Return whether one retained GDAL polygon already covers a candidate."""

    if isinstance(geometry, Polygon):
        return geometry.covers(candidate)
    if isinstance(geometry, MultiPolygon):
        return any(part.covers(candidate) for part in geometry.geoms)
    return False


def _original_bound(value: float, contour_input: _ContourInput) -> float:
    """Snap a conditioned GDAL field value to its exact original label."""

    index = min(
        range(len(contour_input.normalized_bounds)),
        key=lambda candidate: abs(value - contour_input.normalized_bounds[candidate]),
    )
    return contour_input.original_bounds[index]

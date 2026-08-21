"""Create filled-contour polygons from xarray data."""

from isobands._diagnostics import CheckReport, CheckResult, check
from isobands.core import from_raster

__all__ = ["CheckReport", "CheckResult", "check", "from_raster"]

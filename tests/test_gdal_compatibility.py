"""GDAL-version compatibility tests."""

from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from isobands._gdal import _create_vector_layer, _import_gdal


def test_missing_gdal_bindings_lists_all_supported_extras() -> None:
    """Missing-binding guidance names every exact GDAL extra."""

    with (
        patch(
            "isobands._gdal.load_gdal_modules",
            side_effect=ImportError,
        ),
        pytest.raises(
            RuntimeError,
            match="gdal310/gdal311/gdal312/gdal313",
        ),
    ):
        _import_gdal()


def test_broken_native_gdal_binding_has_installation_guidance() -> None:
    """Native loader failures get the same actionable error as missing bindings."""

    with (
        patch(
            "isobands._gdal.load_gdal_modules",
            side_effect=OSError,
        ),
        pytest.raises(RuntimeError, match="matching GDAL and Python bindings"),
    ):
        _import_gdal()


def test_vector_layer_falls_back_to_ogr_memory_driver() -> None:
    """The vector backend works before GDAL's unified MEM driver."""
    layer = Mock()
    layer.CreateField.return_value = 0
    dataset = Mock()
    dataset.CreateLayer.return_value = layer
    driver = Mock()
    driver.CreateDataSource.return_value = dataset
    ogr = SimpleNamespace(
        GetDriverByName=Mock(return_value=driver),
        OGRERR_NONE=0,
        OFTReal=2,
        wkbMultiPolygon=6,
        FieldDefn=Mock(),
    )

    gdal = SimpleNamespace(
        GetDriverByName=Mock(
            return_value=SimpleNamespace(GetMetadataItem=lambda _: None)
        )
    )

    actual_dataset, actual_layer = _create_vector_layer(gdal, ogr)

    assert (actual_dataset, actual_layer) == (dataset, layer)
    gdal.GetDriverByName.assert_called_once_with("MEM")
    ogr.GetDriverByName.assert_called_once_with("Memory")
    driver.CreateDataSource.assert_called_once_with("")


def test_vector_layer_uses_vector_capable_mem_driver() -> None:
    """Newer GDAL releases use their unified in-memory driver."""
    layer = Mock()
    layer.CreateField.return_value = 0
    dataset = Mock()
    dataset.CreateLayer.return_value = layer
    mem_driver = Mock()
    mem_driver.GetMetadataItem.return_value = "YES"
    mem_driver.Create.return_value = dataset
    gdal = SimpleNamespace(
        GetDriverByName=Mock(return_value=mem_driver),
        GDT_Unknown=0,
    )
    ogr = SimpleNamespace(
        GetDriverByName=Mock(),
        OGRERR_NONE=0,
        OFTReal=2,
        wkbMultiPolygon=6,
        FieldDefn=Mock(),
    )

    actual_dataset, actual_layer = _create_vector_layer(gdal, ogr)

    assert (actual_dataset, actual_layer) == (dataset, layer)
    mem_driver.Create.assert_called_once_with("", 0, 0, 0, 0)
    ogr.GetDriverByName.assert_not_called()

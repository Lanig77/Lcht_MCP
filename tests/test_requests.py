from pathlib import Path

import pytest

from lichtfeld_mcp.core.requests import (
    BoxSelectionRequest,
    ColorSelectionRequest,
    ExportRequest,
    HeightRange,
    OptimizationRequest,
    RGBColor,
)
from lichtfeld_mcp.errors import InvalidParameterError


def test_height_range_normalizes_reversed_bounds():
    height_range = HeightRange(z_min=4.0, z_max=1.0)

    assert height_range.z_min == 1.0
    assert height_range.z_max == 4.0


def test_rgb_color_rejects_invalid_values():
    with pytest.raises(InvalidParameterError, match="r must be between 0 and 255"):
        RGBColor(r=300, g=0, b=0)


def test_color_selection_request_rejects_invalid_tolerance():
    with pytest.raises(InvalidParameterError, match="tolerance must be between 0 and 255"):
        ColorSelectionRequest.from_rgb(10, 20, 30, tolerance=999)


def test_box_selection_request_normalizes_bounds():
    request = BoxSelectionRequest.from_bounds(5, 4, 3, -1, -2, -3, mode=" add ")

    assert request.mode == "add"
    assert request.box.min.x == -1
    assert request.box.min.y == -2
    assert request.box.min.z == -3
    assert request.box.max.x == 5
    assert request.box.max.y == 4
    assert request.box.max.z == 3


def test_optimization_request_rejects_invalid_max_splats():
    with pytest.raises(InvalidParameterError, match="max_splats must be greater than 0"):
        OptimizationRequest(target="web", max_splats=0)


def test_export_request_normalizes_values():
    request = ExportRequest(output_path="  out/demo.spz  ", fmt=".SPZ", target=" Unity ")

    assert Path(request.output_path) == Path("out/demo.spz")
    assert request.fmt == "spz"
    assert request.target == "unity"

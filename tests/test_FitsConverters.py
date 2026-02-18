import pytest
import numpy as np
from le_beta_vis.frontend.fitsconverters import (
    FastPixmapConverter,
    OpenCVBasedConverter,
    NoOpConverter,
    Colormap,
    ScalingFunction,
)


@pytest.fixture
def test_data():
    return np.random.rand(100, 100).astype(np.float32) * 100.0


def test_fast_converter_returns_buffer(test_data):
    converter = FastPixmapConverter()
    buffer = converter.convert(test_data, Colormap.VIRIDIS, (0, 100))
    assert isinstance(buffer, np.ndarray)
    assert buffer.dtype == np.uint8
    assert buffer.shape == (100, 100)


def test_opencv_converter_returns_rgb_buffer(test_data):
    converter = OpenCVBasedConverter()
    buffer = converter.convert(test_data, Colormap.VIRIDIS, (0, 100))
    assert isinstance(buffer, np.ndarray)
    assert buffer.dtype == np.uint8
    # RGB buffer has 3 channels
    assert buffer.shape == (100, 100, 3)


def test_noop_converter_returns_empty(test_data):
    converter = NoOpConverter()
    buffer = converter.convert(test_data, Colormap.VIRIDIS, (0, 100))
    assert isinstance(buffer, np.ndarray)
    assert buffer.size == 0


def test_scaling_logic(test_data):
    converter = OpenCVBasedConverter()
    # Test LOG scaling
    buffer_log = converter.convert(
        test_data, Colormap.VIRIDIS, (0, 100), scaling=ScalingFunction.LOG
    )
    # Test SQRT scaling
    buffer_sqrt = converter.convert(
        test_data, Colormap.VIRIDIS, (0, 100), scaling=ScalingFunction.SQRT
    )

    assert buffer_log.shape == (100, 100, 3)
    assert buffer_sqrt.shape == (100, 100, 3)

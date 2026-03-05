import os
import tempfile
import numpy as np
import pytest
from pathlib import Path
from astropy.io import fits

from le_beta_vis.common.CCDCaptureModel import CCDCaptureModel
from le_beta_vis.common.BoundingBox import BoundingBox


def _make_model(shape=(4, 5)):
    """Helper to return a CCDCaptureModel filled with sequential values."""
    data = np.arange(shape[0] * shape[1]).reshape(shape)
    return CCDCaptureModel(data)


class TestClusterFromBoundingBox:

    def test_clusterFromBoundingBox_valid_region(self):
        model = _make_model((6, 8))
        # choose an interior 2x3 block starting at (1,1)
        bbox = BoundingBox(top=1, left=1, bottom=3, right=4)
        cropped = model.clusterFromBoundingBox(bbox)
        # should have shape (2,3)
        assert cropped.shape == (2, 3)
        # verify values correspond to original array slice
        expected = model.rawData()[1:3, 1:4]
        np.testing.assert_array_equal(cropped, expected)

    def test_clusterFromBoundingBox_out_of_bounds(self):
        model = _make_model((5, 5))
        # bounding box extends beyond right/bottom
        bbox = BoundingBox(top=2, left=2, bottom=10, right=10)
        cropped = model.clusterFromBoundingBox(bbox)
        # should be clamped to shape (3,3)
        assert cropped.shape == (3, 3)
        expected = model.rawData()[2:5, 2:5]
        np.testing.assert_array_equal(cropped, expected)

    def test_clusterFromBoundingBox_unbounded(self):
        model = _make_model((3, 4))
        bbox = BoundingBox.unbounded()
        cropped = model.clusterFromBoundingBox(bbox)
        assert cropped.shape == model.rawData().shape
        np.testing.assert_array_equal(cropped, model.rawData())

    def test_clusterFromBoundingBox_invalid_box(self):
        model = _make_model((3, 3))
        # top greater than bottom
        bbox = BoundingBox(top=3, left=0, bottom=1, right=2)
        with pytest.raises(ValueError):
            model.clusterFromBoundingBox(bbox)
        # left greater than right
        bbox2 = BoundingBox(top=0, left=3, bottom=2, right=1)
        with pytest.raises(ValueError):
            model.clusterFromBoundingBox(bbox2)


class TestExtractClusterFromFile:

    def _make_temp_fits(self, shapes):
        """Create a temporary FITS file containing HDUs with given shapes."""
        hdus = []
        for shape in shapes:
            data = np.arange(np.product(shape)).reshape(shape)
            hdu = fits.PrimaryHDU(data)
            hdus.append(hdu)
        hdul = fits.HDUList(hdus)
        tmp = tempfile.NamedTemporaryFile(suffix=".fits", delete=False)
        tmpname = tmp.name
        tmp.close()
        hdul.writeto(tmpname, overwrite=True)
        return tmpname

    def test_extractClusterFromFile(self, tmp_path):
        shapes = [(4, 4), (2, 3)]
        fname = self._make_temp_fits(shapes)
        bbox = BoundingBox(top=1, left=1, bottom=3, right=3)
        arr = CCDCaptureModel.extractClusterFromFile(Path(fname), 0, bbox)
        # manually open file and check slice
        with fits.open(fname) as hdul:
            expected = hdul[0].data[1:3, 1:3]
        np.testing.assert_array_equal(arr, expected)
        os.remove(fname)

    def test_extractClusterFromFile_invalid_hdu_id(self, tmp_path):
        shapes = [(2, 2)]
        fname = self._make_temp_fits(shapes)
        bbox = BoundingBox(top=0, left=0, bottom=1, right=1)
        with pytest.raises(IndexError):
            CCDCaptureModel.extractClusterFromFile(Path(fname), 5, bbox)
        os.remove(fname)

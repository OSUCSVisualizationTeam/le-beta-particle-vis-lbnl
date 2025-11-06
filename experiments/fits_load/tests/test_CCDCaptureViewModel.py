import unittest
import numpy as np
from ccdioutils.CCDCaptureModel import CCDCaptureModel
from ccdioutils.CCDCaptureViewModel import CCDCaptureViewModel
from ccdioutils.BoundingBox import BoundingBox
from ccdioutils.VizFilter import UniformFilter


class TestCCDCaptureViewModelTest(unittest.TestCase):
    def _mockMatrix(self, min: float, max: float) -> np.matrix:
        assert min < max
        mock = np.eye(max)
        mock[0][0] = -255
        mock[max - 1][max - 1] = 255
        return mock

    def setUp(self):
        self.mockNpMatrix = self._mockMatrix(-255, 255)
        self.ccdCaptureModel = CCDCaptureModel(ccdData=self.mockNpMatrix)
        self.ccdCaptureViewModel = CCDCaptureViewModel(self.ccdCaptureModel)
        self.mockFilter = UniformFilter.Add(1)

    def test_initViewModelWithDefaultValues_givenCcdCaptureModel_initializesCorrectly(
        self,
    ):
        self.assertEqual(self.ccdCaptureViewModel.getCurrentColormap(), "Greys_r")
        self.assertEqual(self.ccdCaptureViewModel.getVisualizationRange(), (-255, 255))

    def test_crop_givenBoundingBox_updatesCropBox(self):
        newCropBox = BoundingBox(1, 2, 3, 4)
        self.ccdCaptureViewModel.crop(newCropBox)
        self.assertEqual(
            self.ccdCaptureViewModel._CCDCaptureViewModel__cropBox, newCropBox
        )

    def test_reset_givenModifiedState_restoresDefaultState(self):
        self.ccdCaptureViewModel.setCurrentColormap("viridis")
        self.ccdCaptureViewModel.setVisualizationRange((10.0, 20.0))
        self.ccdCaptureViewModel.applyFilter(self.mockFilter)
        self.ccdCaptureViewModel.reset()
        self.assertEqual(self.ccdCaptureViewModel.getCurrentColormap(), "Greys_r")
        self.assertEqual(self.ccdCaptureViewModel.getVisualizationRange(), (-255, 255))

    def test_applyFilter_givenUniformVizFilter_appliesFilterToCcdVizCapture(self):
        self.ccdCaptureViewModel.applyFilter(self.mockFilter)
        self.assertEqual(self.ccdCaptureViewModel.valueAt(0, 0), -254)

    def test_extractClusters_always_returnsEmptyList(self):
        result = self.ccdCaptureViewModel.extractClusters()
        self.assertEqual(result, [])

    def test_setCurrentColormap_givenColormapName_setsCurrentColormap(self):
        newColormap = "plasma"
        self.ccdCaptureViewModel.setCurrentColormap(newColormap)
        self.assertEqual(self.ccdCaptureViewModel.getCurrentColormap(), newColormap)

    def test_getCurrentColormap_afterSettingColormap_returnsCorrectColormap(self):
        expectedColormap = "viridis"
        self.ccdCaptureViewModel.setCurrentColormap(expectedColormap)
        actualColormap = self.ccdCaptureViewModel.getCurrentColormap()
        self.assertEqual(actualColormap, expectedColormap)

    def test_valueAt_givenCoordinates_returnsCorrectValue(self):
        row, col = 0, 0
        expectedValue = -255
        value = self.ccdCaptureViewModel.valueAt(row, col)
        self.assertEqual(value, expectedValue)

    def test_valueAt_givenCoordinatesAndConversionFunc_returnsConvertedValue(self):
        self.ccdCaptureViewModel = CCDCaptureViewModel(
            self.ccdCaptureModel, conversionFunc=lambda x: x * 2
        )
        expectedConvertedValue = -510
        value = self.ccdCaptureViewModel.valueAt(0, 0)
        self.assertEqual(value, expectedConvertedValue)

    def test_captureInfo_returnsCcdVizCaptureInfo(self):
        info = self.ccdCaptureViewModel.captureInfo()
        self.assertEqual(
            info,
            self.ccdCaptureModel.info(),
            f"\n{info.__dict__}\n !=\n{self.ccdCaptureModel.info().__dict__}",
        )

    def test_setVisualizationRange_givenRange_setsVisualizationRange(self):
        newRange = (100, 200)
        self.ccdCaptureViewModel.setVisualizationRange(newRange)
        self.assertEqual(self.ccdCaptureViewModel.getVisualizationRange(), newRange)

    def test_getVisualizationRange_afterSettingRange_returnsCorrectRange(self):
        expectedRange = (50, 150)
        self.ccdCaptureViewModel.setVisualizationRange(expectedRange)
        actualRange = self.ccdCaptureViewModel.getVisualizationRange()
        self.assertEqual(actualRange, expectedRange)

    def test_restrictVisualizationToRange_appliesSubstituteOutOfRangeFilter(self):
        rawData = np.ones((4, 4), dtype=int)
        rawData[0][1] = 2
        rawData[0][2] = 3
        expected = np.zeros((4, 4), dtype=int)
        expected[0][1] = 2
        expected[0][2] = 3
        model = CCDCaptureModel(rawData)
        viewModel = CCDCaptureViewModel(model)

        viewModel.setVisualizationRange((2, 3))
        viewModel.restrictVisualizationToRange()

        result = viewModel._CCDCaptureViewModel__ccdVizCapture.rawData()
        self.assertTrue(
            np.array_equal(result, expected),
            f"\n{result}\n{expected}",
        )

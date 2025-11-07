import unittest
import numpy as np
from PySide6 import QtGui
from PySide6.QtWidgets import QApplication
from ccdioutils.Fits2QPixmapConverter import (
    FastPixmapConverter,
    MatplotlibBasedConverter,
    RawPixmapConverter,
)


class TestFits2QPixmapConverter(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication([])

    @classmethod
    def tearDownClass(cls):
        cls.app.quit()

    def setUp(self):
        self.testMatrix = np.array([[10, 20], [30, 40]], dtype=np.float32)
        self.largeTestMatrix = np.random.rand(100, 100) * 255

    def test_FastPixmapConverter_convert_returnsQPixmap(self):
        converter = FastPixmapConverter()
        pixmap = converter.convert(self.testMatrix)
        self.assertIsInstance(pixmap, QtGui.QPixmap)
        self.assertFalse(pixmap.isNull())
        self.assertEqual(pixmap.width(), self.testMatrix.shape[1])
        self.assertEqual(pixmap.height(), self.testMatrix.shape[0])

    def test_FastPixmapConverter_isFast_returnsTrue(self):
        converter = FastPixmapConverter()
        self.assertTrue(converter.isFast())

    def test_RawPixmapConverter_convert_returnsQPixmap(self):
        converter = RawPixmapConverter()
        pixmap = converter.convert(self.testMatrix)
        self.assertIsInstance(pixmap, QtGui.QPixmap)
        self.assertFalse(pixmap.isNull())
        self.assertEqual(pixmap.width(), self.testMatrix.shape[1])
        self.assertEqual(pixmap.height(), self.testMatrix.shape[0])

    def test_MatplotlibBasedConverter_convert_returnsQPixmap(self):
        converter = MatplotlibBasedConverter(colormap="Greys_r")
        pixmap = converter.convert(self.testMatrix)
        self.assertIsInstance(pixmap, QtGui.QPixmap)
        self.assertFalse(pixmap.isNull())
        self.assertTrue(pixmap.width() > 0)
        self.assertTrue(pixmap.height() > 0)

    def test_MatplotlibBasedConverter_isFast_returnsFalse(self):
        converter = MatplotlibBasedConverter(colormap="Greys_r")
        self.assertFalse(converter.isFast())

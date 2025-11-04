from astropy.io import fits
from astropy.time import Time, TimeDelta
from copy import deepcopy
from pathlib import Path
from typing import List, Optional
from .VizFilter import UniformVizFilter
import numpy as np


class CCDCaptureModel:
    """
    CCD Data Capture

    Encapsulates data obtained from a CCD capture
    """

    class Info:
        """CCD Capture relevant info"""

        def __init__(
            self,
            cols: int = 0,
            rows: int = 0,
            min: float = 0,
            max: float = 0,
            start: Optional[Time] = None,
            end: Optional[Time] = None,
            date: Optional[Time] = None,
        ):
            self.cols = cols
            self.rows = rows
            self.min = min
            self.max = max
            self.__captureStart = start
            self.__captureEnd = end
            self.__captureDate = date

        @staticmethod
        def fromHDU(hdu: fits.hdu):
            """Instantiate CCDCaptureModel.Info metadata from an HDU"""
            rows, cols = np.shape(hdu.data)
            return CCDCaptureModel.Info(
                cols=cols,
                rows=rows,
                min=hdu.data.min(),
                max=hdu.data.max(),
                start=Time(hdu.header["DATESTART"]),
                end=Time(hdu.header["DATEEND"]),
                date=Time(hdu.header["DATE"]),
            )

        def captureStart(self) -> Optional[Time]:
            """Date when this data capture exposure started"""
            return self.__captureStart

        def captureEnd(self) -> Optional[Time]:
            """Date when this data capture exposure ended"""
            return self.__captureEnd

        def captureDate(self) -> Time:
            """Date when the data was captured"""
            return self.__captureDate

        def exposureDuration(self) -> Optional[TimeDelta]:
            """Exposure duration"""
            if self.__captureStart is None or self.__captureEnd is None:
                return None
            return self.__captureEnd - self.__captureStart

        def __str__(self):
            duration = self.exposureDuration()
            duration.format = "quantity_str"
            return (
                f"{self.rows}x{self.cols}, "
                f"min={self.min}, max={self.max}, "
                f"start={self.captureStart()}, end={self.captureEnd()}, "
                f"date={self.captureDate()}, exposureDuration={duration},"
            )

    def __init__(
        self, ccdData: np.matrix, info: Optional["CCDCaptureModel.Info"] = None
    ):
        self.__data = ccdData
        rows, cols = np.shape(ccdData)
        if info is None:
            self.__info = CCDCaptureModel.Info(
                cols=cols, rows=rows, min=self.__data.min(), max=self.__data.max()
            )
        else:
            self.__info = info

    @staticmethod
    def __fromHDU(hdu: fits.hdu):
        dump = CCDCaptureModel(hdu.data)
        dump.__info = CCDCaptureModel.Info.fromHDU(hdu)
        return dump

    @staticmethod
    def load(fitsFile: Path) -> List["CCDCaptureModel"]:
        """
        Load CCD dumps from a given FITS file

        Parses data containing HDUs and stores them in a list of CCDDump items
        """
        result: List[CCDCaptureModel] = list()
        with fits.open(fitsFile) as hduList:
            for hdu in hduList:
                result.append(CCDCaptureModel.__fromHDU(hdu))
        return result

    def rawData(self) -> np.matrix:
        """Get raw data from this capture"""
        return self.__data

    def __str__(self):
        return self.__info.__str__()

    def info(self) -> "Info":
        """Fetch capture information"""
        return self.__info

    def applyFilter(self, filter: UniformVizFilter):
        result = filter.filter(self.__data)
        self.__data = result.copy()

    def copy(self) -> "CCDCaptureModel":
        """Reliably copy this CCDCaptureModel instance"""
        newModel = CCDCaptureModel(self.__data.copy())
        newModel.__info = deepcopy(self.__info)
        return newModel

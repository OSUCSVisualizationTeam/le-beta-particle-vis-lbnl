from astropy.io import fits
from astropy.time import Time, TimeDelta
from pathlib import Path
from typing import List, Optional
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

    def __init__(self, ccdData: np.matrix):
        self.__data = ccdData
        rows, cols = np.shape(ccdData)
        self.__info = CCDCaptureModel.Info(
            cols=cols, rows=rows, min=ccdData.min(), max=ccdData.max()
        )

    def __setInfo(
        self,
        cols: int = 0,
        rows: int = 0,
        min: float = 0,
        max: float = 0,
        start: Optional[Time] = None,
        end: Optional[Time] = None,
        date: Optional[Time] = None,
    ):
        self.__info = CCDCaptureModel.Info(cols, rows, min, max, start, end, date)

    @staticmethod
    def __fromHDU(hdu: fits.hdu):
        dump = CCDCaptureModel(hdu.data)
        rows, cols = np.shape(hdu.data)
        dump.__setInfo(
            cols=cols,
            rows=rows,
            min=hdu.data.min(),
            max=hdu.data.max(),
            start=Time(hdu.header["DATESTART"]),
            end=Time(hdu.header["DATEEND"]),
            date=Time(hdu.header["DATE"]),
        )
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

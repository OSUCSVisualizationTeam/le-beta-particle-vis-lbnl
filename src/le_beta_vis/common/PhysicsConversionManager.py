from abc import ABC, abstractmethod
import numpy as np
from typing import Union, overload
from .ConfigurationService import ConfigurationService

class PhysicsConversionManager(ABC):
    """
    Interface for managing physical unit conversions.
    """

    @property
    @abstractmethod
    def kev_conversion_factor(self) -> float:
        """Returns the current ADU-to-keV conversion factor."""
        pass

    @property
    @abstractmethod
    def pedestal_width(self) -> int:
        """Returns the configured pedestal width (background noise level) in ADU."""
        pass

    @abstractmethod
    def calculate_threshold(self, sigma: float) -> float:
        """
        Calculates the signal detection threshold based on sigma and pedestal width.
        
        Args:
            sigma: The multiplier for the standard deviation (sigma).
            
        Returns:
            The threshold value in ADU.
        """
        pass

    @overload
    def adu_to_kev(self, value: float) -> float: ...

    @overload
    def adu_to_kev(self, value: np.ndarray) -> np.ndarray: ...

    @abstractmethod
    def adu_to_kev(self, value: Union[float, np.ndarray]) -> Union[float, np.ndarray]:
        """
        Converts raw ADU (Analog-to-Digital Units) to Energy in keV.

        Args:
            value: A single float or a NumPy array of ADU values.

        Returns:
            The converted value(s) in keV.
        """
        pass


class PhysicsConversionManagerImpl(PhysicsConversionManager):
    """
    Concrete implementation of PhysicsConversionManager backed by ConfigurationService.
    """

    def __init__(self, config_service: ConfigurationService):
        """
        Initializes the manager with a configuration service.

        Args:
            config_service: The service to retrieve physics constants from.
        """
        self._config = config_service

    @property
    def kev_conversion_factor(self) -> float:
        """Returns the current ADU-to-keV conversion factor from config."""
        return float(self._config.get("global:physics:kev_conversion", 1.02857e-5))

    @property
    def pedestal_width(self) -> int:
        """Returns the configured pedestal width (background noise level) in ADU."""
        return int(self._config.get("global:physics:ped_width", 1400))

    def calculate_threshold(self, sigma: float) -> float:
        """
        Calculates the signal detection threshold based on sigma and pedestal width.
        """
        return sigma * self.pedestal_width

    def adu_to_kev(self, value: Union[float, np.ndarray]) -> Union[float, np.ndarray]:
        """
        Converts raw ADU (Analog-to-Digital Units) to Energy in keV.
        """
        return value * self.kev_conversion_factor

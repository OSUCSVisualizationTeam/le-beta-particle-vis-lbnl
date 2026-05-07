"""Import smoke-test for the raw_data_view package.

Catches NameError / ImportError at class-definition time — the classic symptom
is a TYPE_CHECKING-guarded annotation used in a method signature without
`from __future__ import annotations`.  No QApplication or display server is
required; importing PySide6 classes is safe in headless CI.
"""
import importlib

import pytest

_PACKAGE_MODULES = [
    "le_beta_vis.frontend.views.raw_data_view",
    "le_beta_vis.frontend.views.raw_data_view.RawDataView",
    "le_beta_vis.frontend.views.raw_data_view._LeftToolbarView",
    "le_beta_vis.frontend.views.raw_data_view._CenterImageAreaView",
    "le_beta_vis.frontend.views.raw_data_view._RightSidebarView",
    "le_beta_vis.frontend.views.raw_data_view._ROIInfoWidget",
    "le_beta_vis.frontend.views.raw_data_view._RawDataManipulationToolbar",
    "le_beta_vis.frontend.views.raw_data_view._RawDataViewStyle",
]


@pytest.mark.parametrize("module_name", _PACKAGE_MODULES)
def test_module_importable(module_name: str) -> None:
    importlib.import_module(module_name)

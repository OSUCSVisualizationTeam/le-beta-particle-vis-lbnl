"""Catalog of Interactive Filter Stack filter types.

First cut for issue #31: a single hardcoded list. The Add Filter menu
enumerates this list to populate its filter-type choices, instantiates
``filter_class()`` when the user picks an entry, and reads the
:class:`FilterSpec` for display name + parameter metadata.

The longer-term direction is filter discovery from a shared library
(class-level ``SPEC`` attributes harvested from a Python package on the
load path, plus eventually user-authored ``.py`` files). When that work
lands, this module either grows a ``discover()`` function returning the
same ``list[FilterSpec]`` shape, or this constant is replaced with a
runtime-populated registry. See ``project_filter_registry_side_chat.md``
in the project memory for the deferred design conversation.
"""

from typing import List

from .FilterSpec import FilterSpec
from .VizFilter import UniformFilter


BUILTIN_FILTERS: List[FilterSpec] = [
    UniformFilter.SubstituteOutOfRange.SPEC,  # Clip to Range
    UniformFilter.Gaussian.SPEC,              # Gaussian Blur
    UniformFilter.Add.SPEC,                   # Offset
    UniformFilter.SubstituteInRange.SPEC,     # Replace In Range
    UniformFilter.ScalarMultiply.SPEC,        # Scale
]

"""Word3 desktop reconstruction pipeline.

Heavy dependencies (torch/gsplat/pycolmap) are imported lazily inside
pipeline.sfm / pipeline.train so that parser & quality modules stay
importable without CUDA (used by CI unit tests).
"""
from .word3 import load, Word3, Word3Error  # noqa: F401

__version__ = "0.1.0"
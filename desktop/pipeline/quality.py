"""Frame quality gating before SfM: blur detection + temporal subsampling."""
from __future__ import annotations

import numpy as np
from pathlib import Path
from PIL import Image

__all__ = [
    "laplacian_variance", "score_frame", "score_all",
    "select_sharp_frames", "subsample_by_interval",
]


def laplacian_variance(img: Image.Image) -> float:
    """Variance of the 3x3 Laplacian on grayscale — higher is sharper."""
    gray = np.asarray(img.convert("L"), dtype=np.float64) / 255.0
    kernel = np.array([[0, 1, 0], [1, -4, 1], [0, 1, 0]], dtype=np.float64)
    lap = _convolve2d(gray, kernel)
    return float(np.var(lap))


def _convolve2d(a: np.ndarray, k: np.ndarray) -> np.ndarray:
    kh, kw = k.shape
    ph, pw = kh // 2, kw // 2
    padded = np.pad(a, ((ph, ph), (pw, pw)), mode="reflect")
    out = np.zeros_like(a)
    for i in range(kh):
        for j in range(kw):
            out += k[i, j] * padded[i:i + a.shape[0], j:j + a.shape[1]]
    return out


def score_frame(path: Path, max_side: int = 640) -> float:
    """Laplacian variance on a downscaled copy (faster, still discriminative)."""
    with Image.open(path) as img:
        img.thumbnail((max_side, max_side), Image.LANCZOS)
        return laplacian_variance(img)


def score_all(image_dir: Path, max_side: int = 640) -> dict:
    """Score every frame in image_dir; returns {name: score}."""
    return {
        jpg.name: score_frame(jpg, max_side=max_side)
        for jpg in sorted(image_dir.glob("*.jpg"))
    }


def select_sharp_frames(
    image_dir: Path,
    variance_threshold: float,
    min_score: float | None = None,
) -> dict:
    """Score every frame; return {name: score} for frames above threshold."""
    scores = {}
    for jpg in sorted(image_dir.glob("*.jpg")):
        score = score_frame(jpg)
        if score >= variance_threshold:
            scores[jpg.name] = score
    return scores


def subsample_by_interval(names: list, interval: int) -> list:
    """Keep every `interval`-th name (e.g. 2 → every other frame)."""
    return names[::interval] if interval > 1 else names
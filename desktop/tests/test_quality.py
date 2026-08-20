import random
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

from pipeline import quality


def _img(size=(640, 480), blur=0) -> Image.Image:
    h, w = size[1], size[0]
    arr = np.zeros((h, w), dtype=np.uint8)
    arr[::2, ::2] = 255
    arr[1::2, 1::2] = 255
    img = Image.fromarray(arr)
    if blur:
        img = img.filter(ImageFilter.GaussianBlur(blur))
    return img


def test_sharp_scores_higher_than_blurred(tmp_path):
    sharp = tmp_path / "sharp.jpg"
    blurred = tmp_path / "blurred.jpg"
    _img().save(sharp)
    _img(blur=4).save(blurred)
    s_sharp = quality.score_frame(sharp)
    s_blur = quality.score_frame(blurred)
    assert s_sharp > s_blur
    assert s_sharp > 0


def test_select_sharp_frames_threshold(tmp_path):
    sharp = tmp_path / "sharp.jpg"
    blurred = tmp_path / "blurred.jpg"
    _img().save(sharp)
    _img(blur=6).save(blurred)
    scores = quality.score_all(tmp_path)
    assert set(scores) == {"blurred.jpg", "sharp.jpg"}
    kept = quality.select_sharp_frames(tmp_path, variance_threshold=8)
    assert "sharp.jpg" in kept


def test_subsample():
    names = [f"{i:06d}.jpg" for i in range(6)]
    assert quality.subsample_by_interval(names, 2) == names[::2]
    assert quality.subsample_by_interval(names, 1) == names
"""Fixture: build a minimal valid .3word in-memory."""
from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import pytest
from PIL import Image


def make_word3(tmp_path: Path, frame_count: int = 3, sensors: bool = True) -> Path:
    path = tmp_path / "test.3word"
    with zipfile.ZipFile(path, "w") as zf:
        manifest = {
            "format": "3word",
            "version": "1.0",
            "captured_at_utc": "2026-08-20T12:00:00.000Z",
            "device_model": "TestPhone",
            "android_version": "14",
            "app_version": "0.1.0",
            "frame_count": frame_count,
            "frame_interval_target_s": 0.9,
            "image_width": 640,
            "image_height": 480,
            "sensors": {
                "gyro": sensors,
                "accel": sensors,
                "magnetometer": sensors,
                "gps": sensors,
            },
            "gps_reference": {"lat": 31.23, "lon": 121.47, "alt_m": 10.0},
        }
        zf.writestr("manifest.json", json.dumps(manifest))
        zf.writestr(
            "calibration.json",
            json.dumps({
                "camera_id": "0", "width": 640, "height": 480,
                "fx": 500.0, "fy": 500.0, "cx": 320.0, "cy": 240.0,
                "distortion": [0.0, 0.0, 0.0, 0.0, 0.0],
                "distortion_model": "OPENCV", "sensor_orientation_degrees": 90,
            }),
        )
        for i in range(frame_count):
            img = Image.new("RGB", (640, 480), color=(30 + i * 20, 60, 90))
            buf = io.BytesIO()
            img.save(buf, "JPEG")
            zf.writestr(f"frames/{i:06d}.jpg", buf.getvalue())

        meta_lines = "\n".join(
            json.dumps({"index": i, "capture_utc_ms": 1755684000000 + i * 900})
            for i in range(frame_count)
        )
        zf.writestr("metadata.jsonl", meta_lines)

        if sensors:
            zf.writestr("sensors/gyro.csv", "utc_ms,wx,wy,wz\n1755684000000,0.1,0.2,0.3\n")
            zf.writestr("sensors/accel.csv", "utc_ms,ax,ay,az\n1755684000000,0.0,9.8,0.0\n")
            zf.writestr("sensors/gps.csv", "utc_ms,lat,lon,alt_m,accuracy_m\n1755684000000,31.23,121.47,10.0,3.0\n")
    return path


@pytest.fixture
def word3_file(tmp_path: Path) -> Path:
    return make_word3(tmp_path)
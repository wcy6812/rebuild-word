"""Parse and extract `.3word` capture files.

Contract: docs/3word-spec.md
"""
from __future__ import annotations

import csv
import io
import json
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

__all__ = [
    "Word3Error", "Manifest", "Calibration", "GpsReference", "FrameMeta",
    "Word3", "load", "iter_frame_bytes", "extract_frames",
]


class Word3Error(Exception):
    """Raised when a .3word file is malformed or missing required parts."""


@dataclass
class GpsReference:
    lat: float
    lon: float
    alt_m: Optional[float] = None


@dataclass
class Manifest:
    format: str
    version: str
    captured_at_utc: str
    device_model: str
    android_version: str
    app_version: str
    frame_count: int
    frame_interval_target_s: float
    image_width: int
    image_height: int
    sensors: dict = field(default_factory=dict)
    gps_reference: Optional[GpsReference] = None
    notes: str = ""


@dataclass
class Calibration:
    camera_id: str
    width: int
    height: int
    fx: float
    fy: float
    cx: float
    cy: float
    distortion: Optional[list] = None
    distortion_model: str = "NONE"
    sensor_orientation_degrees: int = 90

    @property
    def has_intrinsics(self) -> bool:
        return all(v is not None and v > 0 for v in (self.fx, self.fy))


@dataclass
class FrameMeta:
    index: int
    capture_utc_ms: Optional[int] = None
    exposure_us: Optional[int] = None
    iso: Optional[int] = None
    focus_distance_m: Optional[float] = None


@dataclass
class Word3:
    path: Path
    manifest: Manifest
    calibration: Optional[Calibration]
    frame_files: list  # [(name, size_bytes)]
    metadata: list  # [FrameMeta]
    sensor_csvs: dict  # {name: [(utc_ms, row...)]}

    @property
    def frame_names(self) -> list:
        return [name for name, _ in self.frame_files]

    def frame(self, name: str) -> bytes:
        with zipfile.ZipFile(self.path) as zf:
            return zf.read(f"frames/{name}")


def load(path) -> Word3:
    path = Path(path)
    if not path.is_file():
        raise Word3Error(f"文件不存在: {path}")

    with zipfile.ZipFile(path) as zf:
        names = set(zf.namelist())
        if "manifest.json" not in names:
            raise Word3Error("缺少 manifest.json，不是合法的 .3word 文件")

        manifest = _parse_manifest(json.loads(zf.read("manifest.json")))
        calibration = _parse_calibration(json.loads(zf.read("calibration.json"))) if "calibration.json" in names else None

        frame_files = [
            (name.rsplit("/", 1)[-1], zf.getinfo(name).file_size)
            for name in sorted(names)
            if name.startswith("frames/") and name.endswith((".jpg", ".jpeg"))
        ]
        if not frame_files:
            raise Word3Error("没有找到任何 frames/*.jpg 帧")

        metadata = [
            FrameMeta(**json.loads(line))
            for line in _read_text(zf, "metadata.jsonl").splitlines()
            if line.strip()
        ] if "metadata.jsonl" in names else []

        sensor_csvs = {
            name.rsplit("/", 1)[-1].rsplit(".", 1)[0]: _parse_csv(zf, name)
            for name in names
            if name.startswith("sensors/") and name.endswith(".csv")
        }

    return Word3(
        path=path,
        manifest=manifest,
        calibration=calibration,
        frame_files=frame_files,
        metadata=metadata,
        sensor_csvs=sensor_csvs,
    )


def iter_frame_bytes(path, name: str) -> bytes:
    with zipfile.ZipFile(path) as zf:
        return zf.read(f"frames/{name}")


def extract_frames(path, out_dir: Path, names: Optional[list] = None,
                   skip_existing: bool = True) -> list:
    """Extract frames to out_dir as normalised-EXIF JPEG files."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    with zipfile.ZipFile(path) as zf:
        for name in (names or _sorted_frame_names(zf)):
            dest = out_dir / name
            if skip_existing and dest.is_file():
                written.append(dest)
                continue
            dest.write_bytes(zf.read(f"frames/{name}"))
            written.append(dest)
    return written


def _sorted_frame_names(zf: zipfile.ZipFile) -> list:
    return sorted(
        (n.rsplit("/", 1)[-1] for n in zf.namelist()
         if n.startswith("frames/") and n.endswith((".jpg", ".jpeg")))
    )


def _read_text(zf: zipfile.ZipFile, name: str) -> str:
    raw = zf.read(name)
    return raw.decode("utf-8", errors="replace")


def _parse_manifest(data: dict) -> Manifest:
    gps = data.get("gps_reference")
    return Manifest(
        format=data.get("format", "3word"),
        version=data.get("version", "0"),
        captured_at_utc=data.get("captured_at_utc", ""),
        device_model=data.get("device_model", ""),
        android_version=data.get("android_version", ""),
        app_version=data.get("app_version", ""),
        frame_count=int(data.get("frame_count", 0)),
        frame_interval_target_s=float(data.get("frame_interval_target_s", 0.0)),
        image_width=int(data.get("image_width", 0)),
        image_height=int(data.get("image_height", 0)),
        sensors=data.get("sensors", {}),
        gps_reference=GpsReference(gps["lat"], gps["lon"], gps.get("alt_m")) if gps else None,
        notes=data.get("notes", ""),
    )


def _parse_calibration(data: dict) -> Optional[Calibration]:
    try:
        return Calibration(
            camera_id=data.get("camera_id", "0"),
            width=int(data.get("width", 0)),
            height=int(data.get("height", 0)),
            fx=float(data.get("fx", 0)),
            fy=float(data.get("fy", 0)),
            cx=float(data.get("cx", 0)),
            cy=float(data.get("cy", 0)),
            distortion=list(data["distortion"]) if data.get("distortion") else None,
            distortion_model=data.get("distortion_model", "NONE"),
            sensor_orientation_degrees=int(data.get("sensor_orientation_degrees", 90)),
        )
    except (KeyError, TypeError, ValueError):
        return None


def _parse_csv(zf: zipfile.ZipFile, name: str) -> list:
    text = _read_text(zf, name)
    rows = []
    reader = csv.reader(io.StringIO(text))
    try:
        header = next(reader)
    except StopIteration:
        return rows
    for row in reader:
        if not row:
            continue
        try:
            rows.append((int(row[0]), [float(v) for v in row[1:]]))
        except (ValueError, IndexError):
            continue
    return rows
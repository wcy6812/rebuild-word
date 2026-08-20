"""Export helpers: point cloud PLY, ENU geo-reference from GPS."""
from __future__ import annotations

import math
import struct
from pathlib import Path

import numpy as np

__all__ = ["enu_transform", "geodetic_to_enu", "write_points_ply", "points_from_recon"]


def geodetic_to_enu(
    lat_deg: float, lon_deg: float, alt_m: float,
    origin: tuple,
) -> tuple:
    """Convert WGS84 geodetic to local ENU meters relative to origin."""
    a = 6378137.0
    e2 = 6.69437999014e-3
    lat0, lon0, alt0 = origin

    def to_ecef(lat, lon, alt):
        lat, lon = math.radians(lat), math.radians(lon)
        n = a / math.sqrt(1 - e2 * math.sin(lat) ** 2)
        x = (n + alt) * math.cos(lat) * math.cos(lon)
        y = (n + alt) * math.cos(lat) * math.sin(lon)
        z = (n * (1 - e2) + alt) * math.sin(lat)
        return np.array([x, y, z])

    x0, y0, z0 = to_ecef(lat0, lon0, alt0)
    dx, dy, dz = to_ecef(lat_deg, lon_deg, alt_m) - np.array([x0, y0, z0])

    lat0r, lon0r = math.radians(lat0), math.radians(lon0)
    slat, clat = math.sin(lat0r), math.cos(lat0r)
    slon, clon = math.sin(lon0r), math.cos(lon0r)
    e = -slon * dx + clon * dy
    n = -slat * clon * dx - slat * slon * dy + clat * dz
    u = clat * clon * dx + clat * slon * dy + slat * dz
    return float(e), float(n), float(u)


def enu_transform(lat0: float, lon0: float, alt0: float = 0.0):
    """Return a function mapping (lat, lon, alt) -> (e, n, u)."""
    return lambda lat, lon, alt=0.0: geodetic_to_enu(lat, lon, alt, (lat0, lon0, alt0))


def points_from_recon(recon) -> np.ndarray:
    """(N,3) float array of 3D points from a pycolmap reconstruction."""
    pts = []
    for p in recon.points3D.values():
        pts.append(p.xyz)
    return np.asarray(pts, dtype=np.float64).reshape(-1, 3)


def write_points_ply(path: Path, points: np.ndarray, colors: np.ndarray | None = None) -> Path:
    """Write a colored point cloud PLY."""
    points = np.asarray(points, dtype=np.float32)
    n = len(points)
    if colors is None:
        colors = np.full((n, 3), 180, dtype=np.uint8)
    colors = np.asarray(colors, dtype=np.uint8).reshape(-1, 3)

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        header = f"""ply
format binary_little_endian 1.0
element vertex {n}
property float x
property float y
property float z
property uchar red
property uchar green
property uchar blue
end_header
"""
        f.write(header.encode("ascii"))
        for p, c in zip(points, colors):
            f.write(struct.pack("<fffBBB", *p, *c))
    return path
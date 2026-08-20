"""SfM via pycolmap: feature extraction, matching, incremental mapping."""
from __future__ import annotations

import json
from pathlib import Path

try:
    import pycolmap
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "缺少 pycolmap。请安装: pip install pycolmap (需要 CUDA 版 PyTorch 环境)"
    ) from exc

__all__ = ["SfmError", "run_sfm", "export_cameras_json"]


class SfmError(Exception):
    pass


def run_sfm(
    images_dir: Path,
    work_dir: Path,
    camera_model: str = "OPENCV",
    min_num_matches: int = 15,
) -> tuple:
    """Run incremental SfM. Returns (summary: dict, sparse_dir: Path)."""
    images_dir = Path(images_dir)
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    images = sorted(images_dir.glob("*.jpg"))
    if len(images) < 3:
        raise SfmError(f"有效图像不足（{len(images)} 张），至少需要 3 张")

    db_path = str(work_dir / "database.db")
    sparse_dir = work_dir / "sparse"

    db_file = work_dir / "database.db"
    if db_file.exists():
        db_file.unlink()

    feature_options = pycolmap.FeatureExtractionOptions(
        database_path=db_path,
        image_path=str(images_dir),
        camera_model=camera_model,
        sift_max_num_features=8192,
        sift_first_octave=-1,
    )
    pycolmap.extract_features(feature_options)

    matching_options = pycolmap.SiftMatchingOptions(
        max_num_matches=32768,
        min_num_inliers=min_num_matches,
        guided_matching=True,
    )
    pycolmap.match_exhaustive(matching_options, database_path=db_path)

    mapper_options = pycolmap.IncrementalPipelineOptions(
        min_model_size=3,
        max_num_models=1,
    )
    reconstructions = pycolmap.incremental_mapping(
        mapper_options,
        database_path=db_path,
        image_path=str(images_dir),
        output_path=str(sparse_dir),
    )
    if not reconstructions:
        raise SfmError("SfM 未生成任何重建模型（场景纹理不足？）")

    best = max(reconstructions.values(), key=lambda r: _num_reg(r))
    summary = _summarize(best)
    return summary, sparse_dir


def _num_reg(recon) -> int:
    attr = getattr(recon, "num_reg_images", None)
    if callable(attr):
        return attr()
    return recon.num_images()


def _summarize(recon) -> dict:
    return {
        "registered_images": _num_reg(recon),
        "total_images": recon.num_images(),
        "points3D": recon.num_points3D(),
        "cameras": len(recon.cameras),
        "observations": _num_obs(recon),
        "mean_track_length": _mean_track(recon),
    }


def _num_obs(recon) -> int:
    obs = 0
    for p in recon.points3D.values():
        obs += len(p.track.elements)
    return obs


def _mean_track(recon) -> float:
    n = 0
    total = 0
    for p in recon.points3D.values():
        c = len(p.track.elements)
        if c > 0:
            n += 1
            total += c
    return round(total / n, 2) if n else 0.0


def export_cameras_json(recon, out_path: Path, notes: dict | None = None) -> dict:
    """Export COLMAP-style per-image pose + intrinsics as JSON."""
    cam_index = {}
    for cid, cam in recon.cameras.items():
        cam_index[cid] = {
            "model": str(cam.model),
            "width": cam.width,
            "height": cam.height,
            "params": list(cam.params),
        }

    images = []
    for image in recon.images.values():
        images.append({
            "name": image.name,
            "camera_id": image.camera_id,
            "qvec": list(image.qvec),
            "tvec": list(image.tvec),
            "registered": bool(image.has_pose()),
        })

    payload = {
        "format": "word3-cameras",
        "version": "1",
        "num_registered": _num_reg(recon),
        "notes": notes or {},
        "cameras": cam_index,
        "images": images,
    }
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2))
    return payload
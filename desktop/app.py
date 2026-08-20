"""Word3 desktop reconstruction — Gradio UI.

Usage: python app.py   (then open the printed local URL)
"""
from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

import gradio as gr
import plotly.graph_objects as go

from pipeline import sfm, train, quality, export
from pipeline.word3 import load, Word3Error

WORKSPACE = Path(tempfile.gettempdir()) / "word3-desktop"


def _new_workspace(file_name: str) -> Path:
    session = WORKSPACE / file_name.replace(".", "_")
    if session.exists():
        shutil.rmtree(session)
    session.mkdir(parents=True)
    return session


# ---------------------------------------------------------------------------
# Tab 1: import
# ---------------------------------------------------------------------------

def on_import(file_path) -> tuple:
    if not file_path:
        raise gr.Error("请先上传或选择 .3word 文件")
    path = Path(file_path)
    try:
        scene = load(path)
    except Word3Error as e:
        raise gr.Error(str(e))

    ws = _new_workspace(path.stem)
    frames_dir = ws / "images"
    frames_dir.mkdir(exist_ok=True)
    from pipeline.word3 import extract_frames
    files = extract_frames(path, frames_dir)

    thumbs = []
    from PIL import Image
    for f in files[:60]:
        t = ws / "thumbs" / f.name
        t.parent.mkdir(exist_ok=True)
        with Image.open(f) as im:
            im.thumbnail((320, 320))
            im.save(t, "JPEG", quality=80)
        thumbs.append(str(t))

    manifest = {
        "设备": scene.manifest.device_model,
        "安卓版本": scene.manifest.android_version,
        "拍摄时间": scene.manifest.captured_at_utc,
        "帧数": scene.manifest.frame_count,
        "分辨率": f"{scene.manifest.image_width}×{scene.manifest.image_height}",
        "传感器": {k: ("✓" if v else "✗") for k, v in scene.manifest.sensors.items()},
        "GPS参考": scene.manifest.gps_reference,
        "内参": f"fx={scene.calibration.fx:.1f} fy={scene.calibration.fy:.1f}" if scene.calibration and scene.calibration.has_intrinsics else "未提供（将由 COLMAP 估计）",
    }

    gps_fig = None
    gps_rows = scene.sensor_csvs.get("gps")
    if gps_rows:
        fig = go.Figure(
            go.Scatter(
                x=[r[1][1] for r in gps_rows],
                y=[r[1][0] for r in gps_rows],
                mode="lines+markers",
                name="GPS 轨迹",
            )
        )
        fig.update_layout(title="GPS 轨迹（lon/lat）", height=320, margin=dict(l=10, r=10, t=40, b=10))
        gps_fig = fig

    session = {
        "workspace": str(ws),
        "word3_path": str(path),
        "frames_dir": str(frames_dir),
        "manifest": manifest,
    }
    return manifest, thumbs, gps_fig, session


# ---------------------------------------------------------------------------
# Tab 2: rebuild
# ---------------------------------------------------------------------------

def on_rebuild(
    session,
    blur_threshold,
    auto_threshold,
    subsample_interval,
    iterations,
    sh_degree,
    progress=gr.Progress(),
) -> tuple:
    if not session:
        raise gr.Error("请先在「导入」页选择 .3word 文件")
    ws = Path(session["workspace"])
    frames_dir = Path(session["frames_dir"])
    logs: list[str] = []

    def log(msg):
        logs.append(msg)
        print(msg)

    progress(0.05, desc="评分帧质量")
    scores = quality.score_all(frames_dir)
    threshold = blur_threshold
    if auto_threshold and scores:
        import numpy as np
        threshold = float(np.percentile(list(scores.values()), 25))
    kept = {k: v for k, v in scores.items() if v >= threshold}
    names = quality.subsample_by_interval(sorted(kept), int(subsample_interval))
    log(f"帧质量筛选: {len(scores)} → {len(kept)}（阈值 {threshold:.1f}）→ 抽稀后 {len(names)}")

    used_dir = ws / "images_used"
    used_dir.mkdir(exist_ok=True)
    for name in names:
        shutil.copy2(frames_dir / name, used_dir / name)

    progress(0.2, desc="SfM 位姿重建")
    try:
        summary, sparse_dir = sfm.run_sfm(used_dir, ws / "sfm")
    except sfm.SfmError as e:
        raise gr.Error(f"SfM 失败: {e}")
    log(f"SfM: {summary}")

    cameras_path = ws / "sfm" / "cameras.json"
    recon = _best_recon(sparse_dir)
    if recon is not None:
        sfm.export_cameras_json(recon, cameras_path)

    sparse_ply = ws / "output" / "sparse_points.ply"
    export.write_points_ply(sparse_ply, export.points_from_recon(recon))

    progress(0.35, desc="gsplat 训练")
    cfg = train.TrainConfig(iterations=int(iterations), sh_degree=int(sh_degree))
    try:
        ply, metrics = train.train_from_colmap(
            used_dir, sparse_dir, ws / "train", cfg, log=log
        )
    except Exception as e:
        raise gr.Error(f"训练失败: {e}")

    progress(1.0, desc="完成")
    result = {
        "splats": metrics["splats"][-1],
        "psnr": metrics["psnr"][-1] if metrics["psnr"] else None,
        "ssim": metrics["ssim"][-1] if metrics["ssim"] else None,
        "frames_used": len(names),
        "sfm": summary,
    }
    session["scene_ply"] = str(ply)
    session["sparse_ply"] = str(sparse_ply)
    session["cameras_json"] = str(cameras_path)
    session["result"] = result

    preview_fig = _point_cloud_fig(sparse_ply)
    return "\n".join(logs), result, str(ply), str(sparse_ply), str(cameras_path), preview_fig, session


def _best_recon(sparse_dir: Path):
    import pycolmap
    recon_paths = list(sparse_dir.glob("*/"))
    for p in sorted(recon_paths):
        try:
            recon = pycolmap.Reconstruction(str(p))
            if recon.num_images():
                return recon
        except Exception:
            continue
    return None


def _point_cloud_fig(ply_path: Path) -> go.Figure:
    pts = _read_ply_points(ply_path)
    fig = go.Figure(
        go.Scatter3d(
            x=pts[:, 0], y=pts[:, 1], z=pts[:, 2],
            mode="markers", marker=dict(size=1.5, color=pts[:, 2], colorscale="Viridis"),
        )
    )
    fig.update_layout(
        height=480,
        margin=dict(l=0, r=0, t=30, b=0),
        scene=dict(xaxis_title="x", yaxis_title="y", zaxis_title="z"),
        title="稀疏点云预览",
    )
    return fig


def _read_ply_points(path: Path) -> object:
    import numpy as np
    with open(path, "rb") as f:
        lines = []
        while True:
            line = f.readline().decode("ascii")
            lines.append(line)
            if line.startswith("end_header"):
                break
        n = int([l for l in lines if l.startswith("element vertex")][0].split()[-1])
        raw = np.frombuffer(f.read(), dtype=np.float32, count=n * 3)
        return raw.reshape(-1, 3)


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

def build_app() -> gr.Blocks:
    with gr.Blocks(title="Word3 桌面重建", theme=gr.themes.Soft()) as app:
        gr.Markdown(
            "# Word3 桌面重建\n"
            "上传手机采集的 `.3word` 文件 → SfM 位姿重建 → gsplat CUDA 训练 → 导出 3DGS `.ply`。\n"
            "需要 NVIDIA GPU（CUDA）与对应版 PyTorch / gsplat / pycolmap。"
        )
        session = gr.State(None)

        with gr.Tabs():
            with gr.Tab("1️⃣ 导入"):
                with gr.Row():
                    file_in = gr.File(label=".3word 文件", file_types=[".3word", ".zip"])
                    import_btn = gr.Button("解析", variant="primary")
                manifest_out = gr.JSON(label="采集信息")
                thumbs_out = gr.Gallery(label="帧预览（前 60 张）", columns=8, height=260)
                gps_plot = gr.Plot(label="GPS 轨迹")
                import_btn.click(on_import, file_in, [manifest_out, thumbs_out, gps_plot, session])

            with gr.Tab("2️⃣ 重建"):
                with gr.Row():
                    with gr.Column():
                        blur_threshold = gr.Slider(5, 500, value=80, step=5, label="模糊阈值（Laplacian 方差，越高要求越清晰）")
                        auto_threshold = gr.Checkbox(value=True, label="自动阈值（第 25 百分位）")
                        subsample = gr.Slider(1, 6, value=1, step=1, label="抽稀间隔（1=全部保留）")
                        iterations = gr.Slider(1000, 30000, value=7000, step=500, label="训练迭代数")
                        sh_degree = gr.Radio([0, 1, 2], value=1, label="球谐阶数")
                        rebuild_btn = gr.Button("开始重建（SfM + 训练）", variant="primary")
                    with gr.Column():
                        log_out = gr.Textbox(label="日志", lines=14, interactive=False)
                        summary_out = gr.JSON(label="重建摘要")

            with gr.Tab("3️⃣ 输出"):
                with gr.Row():
                    with gr.Column():
                        scene_ply = gr.File(label="3DGS 场景 .ply（SuperSplat/Postshot 可导入）")
                        sparse_ply = gr.File(label="稀疏点云 .ply")
                        cameras_json = gr.File(label="相机位姿 cameras.json（COLMAP 格式）")
                    with gr.Column():
                        pc_preview = gr.Plot(label="点云预览")

        rebuild_btn.click(
            on_rebuild,
            [session, blur_threshold, auto_threshold, subsample, iterations, sh_degree],
            [log_out, summary_out, scene_ply, sparse_ply, cameras_json, pc_preview, session],
        )

    return app


if __name__ == "__main__":
    build_app().launch(server_name="127.0.0.1", server_port=7860, show_error=True)
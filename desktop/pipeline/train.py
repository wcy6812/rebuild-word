"""On-desktop 3D Gaussian Splatting training via gsplat (CUDA)."""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import torch

try:
    import gsplat
    from gsplat import rasterization
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "缺少 gsplat。请安装: pip install gsplat（需 CUDA 版 PyTorch）"
    ) from exc

from .word3 import load as load_word3
from . import sfm

__all__ = [
    "TrainConfig", "train_from_word3", "train_from_colmap",
    "save_gaussian_ply", "SH_C0",
]

SH_C0 = 0.28209479177387814


@dataclass
class TrainConfig:
    iterations: int = 7000
    sh_degree: int = 1
    batch_size: int = 4
    lr: float = 1.6e-2
    lr_min: float = 1.6e-4
    densify_interval: int = 500
    densify_start: int = 500
    densify_stop: int = 15_000
    densify_frac: float = 0.01
    opacity_threshold: float = 0.005
    eval_interval: int = 500
    seed: int = 42


def _device() -> torch.device:
    if not torch.cuda.is_available():
        raise RuntimeError(
            "未检测到 CUDA GPU。桌面重建需要 NVIDIA GPU + CUDA 版 PyTorch，"
            "请按 README 安装（pip install torch --index-url https://download.pytorch.org/whl/cu121）"
        )
    return torch.device("cuda")


# ---------------------------------------------------------------------------
# PLY export (INRIA-compatible 3DGS format)
# ---------------------------------------------------------------------------

def save_gaussian_ply(
    path: Path,
    means: torch.Tensor,
    scales: torch.Tensor,   # log scale
    quats: torch.Tensor,    # (w,x,y,z)
    opacities: torch.Tensor,
    sh0: torch.Tensor,      # (N, 3)
    shN: torch.Tensor | None = None,  # (N, k)
    sh_degree: int = 1,
) -> Path:
    """Export standard 3D Gaussian Splatting .ply readable by SuperSplat etc."""
    device = means.device
    means = means.detach().float().cpu().numpy()
    scales = scales.detach().float().cpu().numpy()
    quats = quats.detach().float().cpu().numpy()
    opacities = opacities.detach().float().cpu().numpy()
    sh0 = sh0.detach().float().cpu().numpy()

    n = len(means)
    rest_dims = 3 * ((sh_degree + 1) ** 2) - 3
    rest = np.zeros((n, rest_dims), dtype=np.float32)
    if shN is not None and shN.numel():
        rest = shN.detach().float().cpu().numpy()[:, :rest_dims]

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        header = f"""ply
format binary_little_endian 1.0
element vertex {n}
property float x
property float y
property float z
property float nx
property float ny
property float nz
property float f_dc_0
property float f_dc_1
property float f_dc_2
"""
        for i in range(rest_dims):
            header += f"property float f_rest_{i}\n"
        header += f"""property float opacity
property float scale_0
property float scale_1
property float scale_2
property float rot_0
property float rot_1
property float rot_2
property float rot_3
end_header
"""
        f.write(header.encode("ascii"))

        zeros = np.zeros((n, 3), dtype=np.float32)
        data = np.concatenate([
            means.astype(np.float32), zeros, sh0.astype(np.float32),
            rest, opacities.reshape(-1, 1).astype(np.float32),
            scales.astype(np.float32), quats.astype(np.float32),
        ], axis=1)
        f.write(data.tobytes())
    return path


# ---------------------------------------------------------------------------
# Gaussian ops (self-contained to avoid gsplat version drift)
# ---------------------------------------------------------------------------

def _clone(means, scales, opacities, sh0, shN, mask):
    n_new = int(mask.sum())
    if n_new == 0:
        return means, scales, opacities, sh0, shN, torch.zeros_like(mask, dtype=torch.bool)
    idx = mask.nonzero(as_tuple=True)[0]
    return (
        torch.cat([means, means[idx]]),
        torch.cat([scales, scales[idx]]),
        torch.cat([opacities, opacities[idx]]),
        torch.cat([sh0, sh0[idx]]),
        torch.cat([shN, shN[idx]]) if shN is not None and shN.numel() else shN,
        mask,
    )


def _split(means, scales, quats, opacities, sh0, shN, mask):
    n_new = int(mask.sum())
    if n_new == 0:
        return means, scales, quats, opacities, sh0, shN, mask
    idx = mask.nonzero(as_tuple=True)[0]
    # split along the largest-scale axis
    sel_scales = scales[idx].exp()
    axis = sel_scales.argmax(dim=1)
    dirs = torch.zeros_like(sel_scales)
    dirs.scatter_(1, axis.unsqueeze(1), 1.0)
    delta = (dirs * sel_scales * 0.5).unsqueeze(1)  # (n,1,3)
    quat = quats[idx]
    rot = quat_to_rotmat(quat)
    delta = torch.bmm(rot, delta.transpose(1, 2)).squeeze(-1)

    m1 = means[idx] + delta
    m2 = means[idx] - delta
    s1 = torch.log(sel_scales * 0.5)
    s2 = s1.clone()

    return (
        torch.cat([means, m1, m2]),
        torch.cat([scales, s1, s2]),
        torch.cat([quats, quat, quat]),
        torch.cat([opacities, opacities[idx], opacities[idx]]),
        torch.cat([sh0, sh0[idx], sh0[idx]]),
        torch.cat([shN, shN[idx], shN[idx]]) if shN is not None and shN.numel() else shN,
        mask,
    )


def quat_to_rotmat(q):
    """Unit quaternion (w,x,y,z) -> rotation matrix (N,3,3)."""
    w, x, y, z = q[..., 0], q[..., 1], q[..., 2], q[..., 3]
    r = torch.stack([
        torch.stack([1 - 2*(y*y + z*z), 2*(x*y - w*z), 2*(x*z + w*y)], dim=-1),
        torch.stack([2*(x*y + w*z), 1 - 2*(x*x + z*z), 2*(y*z - w*x)], dim=-1),
        torch.stack([2*(x*z - w*y), 2*(y*z + w*x), 1 - 2*(x*x + y*y)], dim=-1),
    ], dim=-2)
    return r


def _normalize_quats(q):
    return q / q.norm(dim=-1, keepdim=True).clamp_min(1e-9)


# ---------------------------------------------------------------------------
# Loss helpers
# ---------------------------------------------------------------------------

def _ssim(img1, img2, window_size: int = 11):
    def gaussian_window(size, sigma):
        coords = torch.arange(size, dtype=torch.float32) - (size - 1) / 2
        g = torch.exp(-coords**2 / (2 * sigma**2))
        g = g / g.sum()
        return g.outer(g).view(1, 1, size, size).to(img1.device)

    window = gaussian_window(window_size, 1.5)
    c1, c2 = 0.01**2, 0.03**2
    a = img1.unsqueeze(0)
    b = img2.unsqueeze(0)
    mu1 = torch.nn.functional.conv2d(a, window, padding=window_size // 2)
    mu2 = torch.nn.functional.conv2d(b, window, padding=window_size // 2)
    mu1_sq, mu2_sq, mu1_mu2 = mu1**2, mu2**2, mu1 * mu2
    sigma1_sq = torch.nn.functional.conv2d(a * a, window, padding=window_size // 2) - mu1_sq
    sigma2_sq = torch.nn.functional.conv2d(b * b, window, padding=window_size // 2) - mu2_sq
    sigma12 = torch.nn.functional.conv2d(a * b, window, padding=window_size // 2) - mu1_mu2
    ssim_map = ((2 * mu1_mu2 + c1) * (2 * sigma12 + c2)) / (
        (mu1_sq + mu2_sq + c1) * (sigma1_sq + sigma2_sq + c2))
    return ssim_map.mean()


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------

def train_from_word3(
    word3_path: Path,
    work_dir: Path,
    config: TrainConfig | None = None,
    log: callable | None = None,
) -> dict:
    """End-to-end: SfM then gsplat training. Returns paths dict."""
    word3_path = Path(word3_path)
    work_dir = Path(work_dir)
    config = config or TrainConfig()

    def info(msg):
        if log:
            log(msg)
        else:
            print(msg)

    info("===== 1/3 解析 .3word =====")
    scene = load_word3(word3_path)
    images_dir = work_dir / "images"
    from .quality import select_sharp_frames, subsample_by_interval
    selected = select_sharp_frames(extract_dir(word3_path, images_dir))
    names = subsample_by_interval(sorted(selected), 1)

    info(f"===== 2/3 提取 {len(names)} 帧进行 SfM =====")
    sfm_dir = work_dir / "sfm"
    summary, sparse_dir = sfm.run_sfm(images_dir, sfm_dir)
    info(f"SfM 完成: {summary}")

    info("===== 3/3 gsplat 训练 =====")
    train_ply, metrics = train_from_colmap(
        images_dir, sparse_dir, work_dir, config, log=log
    )
    return {
        "scene_ply": str(train_ply),
        "sparse_dir": str(sparse_dir),
        "sfm_summary": summary,
        "metrics": metrics,
    }


def extract_dir(word3_path: Path, images_dir: Path) -> Path:
    """Extract frames (normalised orientation) and return dir."""
    from .word3.loader import extract_frames
    images_dir.mkdir(parents=True, exist_ok=True)
    extract_frames(word3_path, images_dir)
    return images_dir


def train_from_colmap(
    images_dir: Path,
    sparse_dir: Path,
    work_dir: Path,
    config: TrainConfig | None = None,
    log: callable | None = None,
) -> tuple:
    """Train gaussians from a COLMAP sparse reconstruction. Returns (ply, metrics)."""
    from gsplat.data import COLMAPDataset

    config = config or TrainConfig()
    device = _device()
    torch.manual_seed(config.seed)

    dataset = COLMAPDataset(
        colmap_path=str(sparse_dir),
        image_path=str(images_dir),
    )
    if len(dataset) < 2:
        raise RuntimeError("重建视图不足")

    train_ids = [i for i in range(len(dataset)) if i % 8 != 0]
    test_ids = [i for i in range(len(dataset)) if i % 8 == 0]
    train_ids = train_ids if train_ids else list(range(len(dataset)))

    first = dataset[train_ids[0]]
    h, w = first["image"].shape[1], first["image"].shape[2]

    # init means from sparse point cloud
    import pycolmap
    recon = pycolmap.Reconstruction(str(sparse_dir))
    pts = [p.xyz for p in recon.points3D.values()]
    means = torch.tensor(np.asarray(pts, dtype=np.float32), dtype=torch.float32, device=device)
    if means.numel() == 0:
        raise RuntimeError("稀疏点云为空，无法初始化高斯")
    n_init = means.shape[0]
    if n_init > 200_000:
        keep = torch.randperm(n_init, device=device)[:200_000]
        means = means[keep]
        n_init = means.shape[0]

    params = {
        "means": torch.nn.Parameter(means.requires_grad_(True)),
        "scales": torch.nn.Parameter(torch.log(torch.full((n_init, 3), 0.01, device=device))),
        "quats": torch.nn.Parameter(
            _normalize_quats(torch.randn(n_init, 4, device=device) * 1e-2
                             + torch.tensor([1.0, 0, 0, 0], device=device))
        ),
        "opacities": torch.nn.Parameter(
            torch.full((n_init, 1), 0.0, device=device)  # logit(0.5)
        ),
        "sh0": torch.nn.Parameter(torch.zeros(n_init, 3, device=device)),
    }
    shN = None
    if config.sh_degree > 0:
        rest_dims = 3 * ((config.sh_degree + 1) ** 2) - 3
        shN = torch.nn.Parameter(torch.zeros(n_init, rest_dims, device=device))
        params["shN"] = shN

    gamma = math.exp(math.log(config.lr_min / config.lr) / config.iterations)

    def make_optimizer():
        opt = torch.optim.Adam(params.values(), lr=config.lr)
        sched = torch.optim.lr_scheduler.ExponentialLR(opt, gamma=gamma)
        return opt, sched

    optimizer, scheduler = make_optimizer()

    acc_grad = torch.zeros(n_init, device=device)
    metrics = {"psnr": [], "ssim": [], "splats": []}

    for step in range(1, config.iterations + 1):
        batch = torch.randint(0, len(train_ids), (config.batch_size,), device=device)
        viewmats = []
        Ks = []
        gt = []
        for b in batch:
            item = dataset[train_ids[b.item()]]
            c2w = item["c2w"].to(device).float()
            viewmats.append(torch.linalg.inv(c2w))
            Ks.append(item["K"].to(device).float())
            gt.append(item["image"].to(device).float())
        viewmats = torch.stack(viewmats)
        Ks = torch.stack(Ks)
        gt = torch.stack(gt)

        colors, alphas, meta = rasterization(
            means=params["means"],
            quats=params["quats"],
            scales=params["scales"],
            opacities=params["opacities"].squeeze(-1),
            colors=params["sh0"] if shN is None else torch.cat([params["sh0"], shN], dim=-1),
            viewmats=viewmats,
            Ks=Ks,
            width=w,
            height=h,
            sh_degree=config.sh_degree,
            render_mode="RGB",
            backgrounds=torch.ones(config.batch_size, 3, device=device),
        )
        loss = torch.nn.functional.l1_loss(colors, gt) + 0.2 * (1.0 - _ssim(colors, gt))
        loss.backward()

        with torch.no_grad():
            grads = params["means"].grad
            if grads is not None:
                acc_grad += grads.norm(dim=-1)
            optimizer.step()
            optimizer.zero_grad(set_to_none=True)
            scheduler.step()
            params["quats"].data.copy_(_normalize_quats(params["quats"].data))

            if step % config.densify_interval == 0 and config.densify_start <= step <= config.densify_stop:
                with torch.no_grad():
                    n = params["means"].shape[0]
                    n_densify = max(1, int(n * config.densify_frac))
                    k = min(n_densify, n)
                    scores = acc_grad[:n]
                    _, top_idx = torch.topk(scores, k)
                    mask = torch.zeros(n, dtype=torch.bool, device=device)
                    mask[top_idx] = True
                    # small-scale splats → clone; large-scale → split
                    scale_norm = params["scales"].exp().norm(dim=-1)
                    order = torch.argsort(scale_norm, descending=True)
                    split_mask = torch.zeros(n, dtype=torch.bool, device=device)
                    split_mask[order[: max(1, n // 200)]] = True
                    split_mask &= mask
                    clone_mask = mask & ~split_mask

                    means_n, scales_n, op_n, sh0_n, shN_n, _ = \
                        _clone(params["means"].data, params["scales"].data,
                               params["opacities"].data, params["sh0"].data,
                               shN.data if shN is not None else None, clone_mask)
                    means_n, scales_n, quats_n, op_n, sh0_n, shN_n, _ = \
                        _split(means_n, scales_n, quats_n, op_n, sh0_n, shN_n, split_mask)

                    # cull low-opacity splats
                    cull = (torch.sigmoid(op_n.squeeze(-1)) < config.opacity_threshold)
                    keep = ~cull
                    params["means"] = torch.nn.Parameter(means_n[keep].requires_grad_(True))
                    params["scales"] = torch.nn.Parameter(scales_n[keep].requires_grad_(True))
                    params["quats"] = torch.nn.Parameter(quats_n[keep].requires_grad_(True))
                    params["opacities"] = torch.nn.Parameter(op_n[keep].requires_grad_(True))
                    params["sh0"] = torch.nn.Parameter(sh0_n[keep].requires_grad_(True))
                    if shN is not None:
                        params["shN"] = torch.nn.Parameter(shN_n[keep].requires_grad_(True))
                    acc_grad = torch.zeros(params["means"].shape[0], device=device)
                    optimizer, scheduler = make_optimizer()

        if step % config.eval_interval == 0 or step == config.iterations:
            psnr, ssim = _evaluate(params, dataset, test_ids, device, config, w, h)
            metrics["psnr"].append(round(psnr, 3))
            metrics["ssim"].append(round(ssim, 4))
            metrics["splats"].append(int(params["means"].shape[0]))
            if log:
                log(f"iter {step:5d}  splats={params['means'].shape[0]:6d}  "
                    f"psnr={psnr:6.2f}  ssim={ssim:.4f}")

    out_dir = Path(work_dir) / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    ply = save_gaussian_ply(
        out_dir / "scene.ply",
        params["means"], params["scales"], params["quats"],
        params["opacities"], params["sh0"],
        params["shN"] if shN is not None else None,
        config.sh_degree,
    )
    (out_dir / "metrics.json").write_text(json.dumps(metrics, indent=2))
    return ply, metrics


def _points(recon) -> list:  # noqa: F811
    if hasattr(recon, "points3D"):
        return list(recon.points3D.values())
    return []


@torch.no_grad()
def _evaluate(params, dataset, test_ids, device, config, w, h):
    psnrs, ssims = [], []
    for i in test_ids[:8]:
        item = dataset[i]
        c2w = item["c2w"].to(device).float()
        viewmat = torch.linalg.inv(c2w).unsqueeze(0)
        K = item["K"].to(device).float().unsqueeze(0)
        gt = item["image"].to(device).float()
        colors, _, _ = rasterization(
            means=params["means"], quats=params["quats"], scales=params["scales"],
            opacities=params["opacities"].squeeze(-1),
            colors=params["sh0"] if params.get("shN") is None
            else torch.cat([params["sh0"], params["shN"]], dim=-1),
            viewmats=viewmat, Ks=K, width=w, height=h,
            sh_degree=config.sh_degree, render_mode="RGB",
            backgrounds=torch.ones(1, 3, device=device),
        )
        mse = torch.nn.functional.mse_loss(colors, gt)
        psnrs.append(10 * torch.log10(1.0 / mse.clamp_min(1e-10)).item())
        ssims.append(_ssim(colors, gt).item())
    return (sum(psnrs) / len(psnrs)) if psnrs else 0.0, (sum(ssims) / len(ssims)) if ssims else 0.0
# Word3 — 手机采样 + 桌面 CUDA 重建 3DGS

双端管线：**安卓手机采集打包 `.3word`** → **桌面（Windows/Linux + NVIDIA CUDA）SfM + gsplat 训练** → 输出行业标准 **3DGS `.ply`**。

```
┌─ Android（采集端）──────────────────┐   ┌─ 桌面（重建端, Python+Gradio）──────────┐
│ UI引导 → 相机连拍 + 陀螺仪/加速度计/   │   │ 上传.3word → 模糊帧剔除 → pycolmap SfM │
│ 磁力计 + GPS + 相机内参（全部带时间戳）│ → │ → gsplat CUDA训练 → 导出 3DGS .ply     │
│ → 打包 scene.3word (ZIP)             │   │ （SuperSplat/Postshot 可导入）          │
└──────────────────────────────────┘   └────────────────────────────────────────┘
```

## 目录结构

```
├── android/          # 安卓采集 App（Kotlin + CameraX + Compose）
├── desktop/          # 桌面重建管线（Python）
│   ├── pipeline/
│   │   ├── word3/    # .3word 解析器
│   │   ├── quality.py  # 模糊帧剔除/抽稀
│   │   ├── sfm.py      # pycolmap 封装
│   │   ├── train.py    # gsplat 训练 + 3DGS PLY 导出
│   │   └── export.py   # 点云导出 / ENU 地理参考
│   ├── app.py        # Gradio 界面
│   └── tests/        # 单元测试（CI 运行，无需 GPU）
├── docs/3word-spec.md  # .3word 文件格式规范（两端契约）
└── .github/workflows/  # Android APK 构建 + Python 测试
```

## 快速开始

### 手机端（采集）
- 安装 CI 产出的 APK（Actions → Android Build → artifact）
- 引导流程：授权 → 扫描指南 → 环绕拍摄（自动连拍 + 传感器记录）→ 预览删帧 → 打包分享 `.3word`

### 桌面端（重建，需要 NVIDIA GPU）
```bash
cd desktop
# 1. 安装 CUDA 版 PyTorch（Windows 也支持）
pip install torch --index-url https://download.pytorch.org/whl/cu121
# 2. 安装其余依赖
pip install -r requirements.txt
# 3. 启动
python app.py    # 打开 http://127.0.0.1:7860
```
Gradio 三页：**导入**（解析 `.3word`、帧预览、GPS 轨迹）→ **重建**（质量筛选/SfM/训练，流式日志+指标）→ **输出**（下载 `scene.ply` / 稀疏点云 / `cameras.json`，点云预览）。

## 输出格式

| 文件 | 格式 | 用途 |
|------|------|------|
| `scene.ply` | 3DGS 标准（含球谐系数） | SuperSplat、Postshot、任意 3DGS 渲染器 |
| `sparse_points.ply` | 彩色点云 | 查看/测量 |
| `cameras.json` | COLMAP 位姿+内参 | 二次开发 |

## 开发

```bash
# Python 测试（无 GPU 依赖）
cd desktop && pip install -r requirements-test.txt && pytest -m "not cuda"

# Android 构建（GitHub Actions 自动执行）
cd android && ./gradlew assembleDebug
```

## 状态

- [x] M1 仓库骨架 + 双 CI（APK artifact + pytest）
- [x] M2 安卓采集 App（引导/扫描/传感器/打包分享）
- [x] M3 桌面解析 + Gradio + pycolmap SfM
- [x] M4 gsplat 训练 + 3DGS `.ply` 导出
- [ ] M5 GPS 地理参考 / 端到端实机验证 / 文档完善
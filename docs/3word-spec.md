# .3word 文件格式规范 (v1.0)

`.3word` 是手机采集端与桌面重建端之间的数据交换契约。
它是一个标准 ZIP 包（未压缩目录结构，JPEG 使用 deflate/不压缩以加速随机读取）。

## 目录结构

```
scene.3word
├── manifest.json          # 采集会话元信息（必选）
├── calibration.json       # 相机内参（必选）
├── frames/
│   ├── 000000.jpg         # JPEG 原图，EXIF 含 UTC 时间戳与方向（必选，≥1 张）
│   ├── 000001.jpg
│   └── ...
├── metadata.jsonl         # 每帧逐行 JSON：曝光/ISO/对焦/时间戳（可选）
└── sensors/
    ├── gyro.csv           # 陀螺仪  (可选)
    ├── accel.csv          # 加速度计 (可选)
    ├── magnetometer.csv   # 磁力计   (可选)
    └── gps.csv            # 位置     (可选)
```

## manifest.json

```json
{
  "format": "3word",
  "version": "1.0",
  "captured_at_utc": "2026-08-20T12:00:00.000Z",
  "device_model": "Pixel 8",
  "android_version": "14",
  "app_version": "0.1.0",
  "frame_count": 150,
  "frame_interval_target_s": 0.8,
  "image_width": 4032,
  "image_height": 3024,
  "sensors": {
    "gyro": true,
    "accel": true,
    "magnetometer": true,
    "gps": true
  },
  "gps_reference": { "lat": 31.2304, "lon": 121.4737, "alt_m": 12.0 },
  "notes": "free text, e.g. capture guidance outcome"
}
```

- `gps_reference`：采集会话中的首个有效 GPS 点（可选，`null` 表示无 GPS）。

## calibration.json

相机内参，来自 Android `CameraCharacteristics`（`LENS_INTRINSIC_CALIBRATION` 与 `LENS_DISTORTION`），
映射到**图像像素坐标系**（以完整分辨率原图为准）。

```json
{
  "camera_id": "0",
  "width": 4032,
  "height": 3024,
  "fx": 3456.7,
  "fy": 3455.2,
  "cx": 2015.3,
  "cy": 1510.9,
  "distortion": [0.012, -0.031, 0.0004, 0.0003, 0.008],
  "distortion_model": "OPENCV",   // 或 "NONE"
  "sensor_orientation_degrees": 90  // 原图相对自然方向的旋转
}
```

- 畸变系数按 OPENCV 模型 (k1,k2,p1,p2,k3)，若相机未提供则为 `null`，桌面端用 OPENCV_FISHEYE 或直接忽略。
- 所有时间戳单位：**UTC 毫秒**（epoch ms）。

## metadata.jsonl（每帧一行）

```json
{"index": 0, "capture_utc_ms": 1755684000000, "exposure_us": 8333, "iso": 100, "focus_distance_m": 2.5}
```

## sensors/*.csv

无表头，第一列为 `utc_ms`（整数），后续为传感器值（float）。示例：

```
# gyro.csv: utc_ms, wx(rad/s), wy, wz
1755684000000,0.0012,-0.0008,0.0005
# accel.csv: utc_ms, ax(m/s^2), ay, az
1755684000000,0.02,9.79,0.31
# magnetometer.csv: utc_ms, mx(uT), my, mz
1755684000000,18.2,-3.1,41.5
# gps.csv: utc_ms, lat(deg), lon(deg), alt_m, accuracy_m
1755684000000,31.230400,121.473700,12.0,3.5
```

- 传感器采样频率：IMU ≥ 50Hz 记录；GPS 1Hz（有更新才写行）。
- 行内顺序按 `utc_ms` 递增。

## 时间基准

- 所有传感器时间戳由 `SensorManager.getTimeBase()` 的纳秒时钟换算为 UTC 毫秒：
  `utc_ms = (sensorEvent.timestamp - timeBaseNanos) / 1e6 + System.currentTimeMillis()`
- 照片时间戳在快门时刻记录（CameraX `ImageCapture` 回调即触发时刻）。

## 兼容性规则

1. 桌面端解析器对缺失项必须优雅降级：缺 `sensors/*` 不影响 SfM；缺 `calibration.json` 时用 EXIF 焦距 + 经验公式估计内参（标记为估计值）。
2. 帧文件名固定 6 位十进制序号，桌面端按序号排序读取。
3. 未来扩展字段使用新增键，不允许修改既有键语义；`version` 递增主版本。

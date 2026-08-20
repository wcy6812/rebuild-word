package com.rebuild.word3.camera

import android.content.Context
import android.graphics.ImageFormat
import android.hardware.camera2.CameraCharacteristics
import android.hardware.camera2.CameraManager
import android.util.Size

/**
 * 从 CameraCharacteristics 读取内参，映射到实际输出图像像素坐标系。
 * 像素阵列坐标 -> 输出尺寸坐标：按比例缩放。
 */
data class CameraIntrinsics(
    val cameraId: String,
    val width: Int,
    val height: Int,
    val fx: Double,
    val fy: Double,
    val cx: Double,
    val cy: Double,
    val distortion: List<Double>?,
    val distortionModel: String,
    val sensorOrientationDegrees: Int,
) {
    companion object {
        fun from(context: Context, cameraId: String, outputSize: Size): CameraIntrinsics? {
            return runCatching {
                val manager = context.getSystemService(Context.CAMERA_SERVICE) as CameraManager
                val chars = manager.getCameraCharacteristics(cameraId)
                val array = chars.get(CameraCharacteristics.SENSOR_INFO_PIXEL_ARRAY_SIZE)
                    ?: return null
                val raw = chars.get(CameraCharacteristics.LENS_INTRINSIC_CALIBRATION)
                    ?: return null
                if (raw.size < 4) return null

                val sx = outputSize.width.toDouble() / array.width
                val sy = outputSize.height.toDouble() / array.height
                val distortionRaw = chars.get(CameraCharacteristics.LENS_DISTORTION)?.toList()
                val orientation = chars.get(CameraCharacteristics.SENSOR_ORIENTATION) ?: 90

                CameraIntrinsics(
                    cameraId = cameraId,
                    width = outputSize.width,
                    height = outputSize.height,
                    fx = raw[0] * sx,
                    fy = raw[1] * sy,
                    cx = raw[2] * sx,
                    cy = raw[3] * sy,
                    distortion = if (distortionRaw.isNullOrEmpty()) null else distortionRaw,
                    distortionModel = if (distortionRaw.isNullOrEmpty()) "NONE" else "OPENCV",
                    sensorOrientationDegrees = orientation,
                )
            }.getOrNull()
        }
    }
}
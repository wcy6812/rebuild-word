package com.rebuild.word3.pack

import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json

@Serializable
data class ManifestData(
    val format: String = "3word",
    val version: String = "1.0",
    val captured_at_utc: String,
    val device_model: String,
    val android_version: String,
    val app_version: String,
    val frame_count: Int,
    val frame_interval_target_s: Double,
    val image_width: Int,
    val image_height: Int,
    val sensors: Map<String, Boolean>,
    val gps_reference: GpsPoint? = null,
    val notes: String = "",
)

@Serializable
data class GpsPoint(val lat: Double, val lon: Double, val alt_m: Double? = null)

@Serializable
data class CalibrationData(
    val camera_id: String,
    val width: Int,
    val height: Int,
    val fx: Double,
    val fy: Double,
    val cx: Double,
    val cy: Double,
    val distortion: List<Double>? = null,
    val distortion_model: String = "NONE",
    val sensor_orientation_degrees: Int,
)

@Serializable
data class FrameMeta(
    val index: Int,
    val capture_utc_ms: Long,
    val exposure_us: Long? = null,
    val iso: Int? = null,
    val focus_distance_m: Double? = null,
)

object Word3Json {
    val json = Json { prettyPrint = true; encodeDefaults = true }
}
package com.rebuild.word3

import android.app.Application
import android.graphics.BitmapFactory
import android.os.Build
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.rebuild.word3.camera.CameraController
import com.rebuild.word3.pack.CalibrationData
import com.rebuild.word3.pack.FrameMeta
import com.rebuild.word3.pack.ManifestData
import com.rebuild.word3.pack.Word3Json
import com.rebuild.word3.pack.Word3Packager
import com.rebuild.word3.sensor.LocationTracker
import com.rebuild.word3.sensor.SensorRecorder
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlinx.serialization.encodeToString
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone

data class ScanUiState(
    val isScanning: Boolean = false,
    val isPacking: Boolean = false,
    val frameCount: Int = 0,
    val targetFrames: Int = 150,
    val intervalMs: Long = 900,
    val gyroAvailable: Boolean = false,
    val gpsAvailable: Boolean = false,
    val rotationSinceCaptureDeg: Float = 0f,
    val error: String? = null,
    val packedFile: File? = null,
    val lastCameraError: String? = null,
    val framePaths: List<String> = emptyList(),
)

class ScanViewModel(app: Application) : AndroidViewModel(app) {

    private val _state = MutableStateFlow(ScanUiState())
    val state: StateFlow<ScanUiState> = _state

    private val sensorRecorder = SensorRecorder(app)
    private val locationTracker = LocationTracker(app)
    private var captureJob: Job? = null
    private var camera: CameraController? = null

    var sessionDir: File? = null
        private set

    private val frameFiles = mutableListOf<File>()

    val frames: List<File> get() = frameFiles.toList()

    fun startScan(camera: CameraController) {
        if (_state.value.isScanning) return
        // 清理上一个会话可能残留的传感器监听（未打包直接"重新扫描"的情况）
        sensorRecorder.stop()
        locationTracker.stop()
        val now = System.currentTimeMillis()
        val dir = File(getApplication<Application>().filesDir, "sessions/$now").apply { mkdirs() }
        sessionDir = dir
        frameFiles.clear()
        this.camera = camera

        sensorRecorder.start(dir)
        locationTracker.start(dir)

        _state.value = _state.value.copy(
            isScanning = true,
            error = null,
            packedFile = null,
            framePaths = emptyList(),
            gyroAvailable = sensorRecorder.gyroAvailable,
            gpsAvailable = locationTracker.isAvailable,
        )

        captureJob = viewModelScope.launch {
            var index = 0
            while (isActive) {
                val started = System.currentTimeMillis()
                try {
                    val file = File(dir, "frames/${String.format(Locale.US, "%06d", index)}.jpg")
                    camera.captureToFile(file) {
                        sensorRecorder.resetRotationSinceCapture()
                    }
                    frameFiles += file
                    writeFrameMeta(index, started)
                    index += 1
                    _state.value = _state.value.copy(
                        frameCount = index,
                        framePaths = frameFiles.map { it.absolutePath },
                        rotationSinceCaptureDeg = sensorRecorder.rotationSinceCaptureDeg,
                        lastCameraError = null,
                    )
                } catch (e: Exception) {
                    _state.value = _state.value.copy(lastCameraError = e.message ?: "拍照失败")
                }
                val elapsed = System.currentTimeMillis() - started
                delay((_state.value.intervalMs - elapsed).coerceAtLeast(120))
            }
        }
    }

    private fun writeFrameMeta(index: Int, captureUtcMs: Long) {
        val dir = sessionDir ?: return
        val meta = FrameMeta(index = index, capture_utc_ms = captureUtcMs)
        val line = Word3Json.json.encodeToString(FrameMeta.serializer(), meta)
        File(dir, "metadata.jsonl").appendText(line + "\n")
    }

    fun reportError(message: String) {
        _state.value = _state.value.copy(error = message)
    }

    fun stopScan() {
        captureJob?.cancel()
        captureJob = null
        _state.value = _state.value.copy(isScanning = false)
    }

    fun deleteFrame(index: Int) {
        if (index in frameFiles.indices) {
            frameFiles[index].delete()
            frameFiles.removeAt(index)
            _state.value = _state.value.copy(
                frameCount = frameFiles.size,
                framePaths = frameFiles.map { it.absolutePath },
            )
        }
    }

    /** 结束会话：停止采集、写清单与内参、打包 .3word。 */
    fun finishAndPack(onDone: (File) -> Unit) {
        if (_state.value.isPacking) return
        stopScan()
        sensorRecorder.stop()
        locationTracker.stop()
        val dir = sessionDir ?: return

        viewModelScope.launch {
            _state.value = _state.value.copy(isPacking = true)
            withContext(Dispatchers.IO) {
                writeManifest(dir)
                writeCalibration(dir)
            }
            val outFile = File(dir.parentFile!!, "${dir.name}.3word")
            withContext(Dispatchers.IO) { Word3Packager.pack(dir, outFile) }
            _state.value = _state.value.copy(isPacking = false, packedFile = outFile)
            onDone(outFile)
        }
    }

    private fun writeManifest(dir: File) {
        var width = 0
        var height = 0
        frameFiles.firstOrNull()?.let { f ->
            BitmapFactory.Options().apply { inJustDecodeBounds = true }
                .let { opts ->
                    BitmapFactory.decodeFile(f.absolutePath, opts)
                    width = opts.outWidth
                    height = opts.outHeight
                }
        }
        val gpsRef = locationTracker.reference?.let {
            com.rebuild.word3.pack.GpsPoint(it.latitude, it.longitude, it.altitude)
        }
        val manifest = ManifestData(
            captured_at_utc = dir.name.let { name ->
                SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss.SSS'Z'", Locale.US)
                    .apply { timeZone = TimeZone.getTimeZone("UTC") }
                    .format(Date(name.toLong()))
            },
            device_model = "${Build.MANUFACTURER} ${Build.MODEL}",
            android_version = Build.VERSION.RELEASE,
            app_version = BuildConfig.VERSION_NAME,
            frame_count = frameFiles.size,
            frame_interval_target_s = _state.value.intervalMs / 1000.0,
            image_width = width,
            image_height = height,
            sensors = mapOf(
                "gyro" to _state.value.gyroAvailable,
                "accel" to sensorRecorder.accelAvailable,
                "magnetometer" to sensorRecorder.magAvailable,
                "gps" to _state.value.gpsAvailable,
            ),
            gps_reference = gpsRef,
            notes = "captured via Word3 scanner",
        )
        File(dir, "manifest.json").writeText(Word3Json.json.encodeToString(ManifestData.serializer(), manifest))
    }

    private fun writeCalibration(dir: File) {
        val cam = camera ?: return
        val intrinsics = cam.selectedCameraIntrinsics() ?: return
        val cal = CalibrationData(
            camera_id = intrinsics.cameraId,
            width = intrinsics.width,
            height = intrinsics.height,
            fx = intrinsics.fx,
            fy = intrinsics.fy,
            cx = intrinsics.cx,
            cy = intrinsics.cy,
            distortion = intrinsics.distortion,
            distortion_model = intrinsics.distortionModel,
            sensor_orientation_degrees = intrinsics.sensorOrientationDegrees,
        )
        File(dir, "calibration.json")
            .writeText(Word3Json.json.encodeToString(CalibrationData.serializer(), cal))
    }

    override fun onCleared() {
        stopScan()
        sensorRecorder.stop()
        locationTracker.stop()
        camera?.shutdown()
    }
}
package com.rebuild.word3.sensor

import android.content.Context
import android.hardware.Sensor
import android.hardware.SensorEvent
import android.hardware.SensorEventListener
import android.hardware.SensorManager
import android.os.SystemClock
import java.io.BufferedWriter
import java.io.File
import java.io.FileWriter

/**
 * 记录陀螺仪/加速度计/磁力计，时间戳统一换算为 UTC 毫秒。
 * 采样间隔 SENSOR_DELAY_GAME (~50Hz)。
 */
class SensorRecorder(private val context: Context) {

    private val sensorManager = context.getSystemService(Context.SENSOR_SERVICE) as SensorManager
    private val listeners = mutableListOf<SensorEventListener>()
    private val writers = mutableMapOf<Int, BufferedWriter>()

    @Volatile
    var gyroAvailable = false
        private set
    @Volatile
    var accelAvailable = false
        private set
    @Volatile
    var magAvailable = false
        private set

    /** 自上次拍照以来的偏航角累计（度），用于转动提示。 */
    @Volatile
    var rotationSinceCaptureDeg: Float = 0f
        private set

    @Volatile
    var lastGyroUtcMs: Long = 0L
        private set

    private var lastGyroTimestampNs: Long = 0L

    fun start(sessionDir: File) {
        val sensorsDir = File(sessionDir, "sensors").apply { mkdirs() }
        register(
            Sensor.TYPE_GYROSCOPE,
            File(sensorsDir, "gyro.csv"),
            "utc_ms,wx,wy,wz",
            { e, utc -> "${utc},${e.values[0]},${e.values[1]},${e.values[2]}" },
            { gyroAvailable = true },
        ) { e, utc ->
            if (lastGyroTimestampNs != 0L) {
                val dt = (e.timestamp - lastGyroTimestampNs) / 1e9f
                rotationSinceCaptureDeg += kotlin.math.abs(e.values[2]) * dt * 57.29578f
            }
            lastGyroTimestampNs = e.timestamp
            lastGyroUtcMs = utc
        }
        register(
            Sensor.TYPE_ACCELEROMETER,
            File(sensorsDir, "accel.csv"),
            "utc_ms,ax,ay,az",
            { e, utc -> "${utc},${e.values[0]},${e.values[1]},${e.values[2]}" },
            { accelAvailable = true },
        )
        register(
            Sensor.TYPE_MAGNETIC_FIELD,
            File(sensorsDir, "magnetometer.csv"),
            "utc_ms,mx,my,mz",
            { e, utc -> "${utc},${e.values[0]},${e.values[1]},${e.values[2]}" },
            { magAvailable = true },
        )
    }

    fun resetRotationSinceCapture() {
        rotationSinceCaptureDeg = 0f
    }

    private fun register(
        sensorType: Int,
        csvFile: File,
        header: String,
        line: (SensorEvent, Long) -> String,
        availability: (() -> Unit)? = null,
        extra: ((SensorEvent, Long) -> Unit)? = null,
    ) {
        val sensor = sensorManager.getDefaultSensor(sensorType) ?: return
        availability?.invoke()
        val writer = BufferedWriter(FileWriter(csvFile)).apply { write(header); newLine() }
        writers[sensorType] = writer
        val listener = object : SensorEventListener {
            override fun onSensorChanged(event: SensorEvent) {
                val utcMs = eventUtcMs(event.timestamp)
                writer.write(line(event, utcMs)); writer.newLine()
                extra?.invoke(event, utcMs)
            }

            override fun onAccuracyChanged(sensor: Sensor?, accuracy: Int) = Unit
        }
        listeners += listener
        sensorManager.registerListener(listener, sensor, SensorManager.SENSOR_DELAY_GAME)
    }

    private fun eventUtcMs(timestampNs: Long): Long {
        // sensor timestamps share the CLOCK_MONOTONIC base used by elapsedRealtimeNanos
        return System.currentTimeMillis() + (timestampNs - SystemClock.elapsedRealtimeNanos()) / 1_000_000L
    }

    fun stop() {
        listeners.forEach { sensorManager.unregisterListener(it) }
        listeners.clear()
        writers.values.forEach { runCatching { it.flush() }; runCatching { it.close() } }
        writers.clear()
    }
}
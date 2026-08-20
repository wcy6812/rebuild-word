package com.rebuild.word3.sensor

import android.content.Context
import android.location.Location
import android.os.Looper
import com.google.android.gms.common.GoogleApiAvailability
import com.google.android.gms.location.FusedLocationProviderClient
import com.google.android.gms.location.LocationCallback
import com.google.android.gms.location.LocationRequest
import com.google.android.gms.location.LocationResult
import com.google.android.gms.location.LocationServices
import com.google.android.gms.location.Priority
import java.io.BufferedWriter
import java.io.File
import java.io.FileWriter

class LocationTracker(private val context: Context) {

    private val client: FusedLocationProviderClient =
        LocationServices.getFusedLocationProviderClient(context)

    private var writer: BufferedWriter? = null
    private var callback: LocationCallback? = null
    var reference: Location? = null
        private set

    val isAvailable: Boolean
        get() = runCatching {
            GoogleApiAvailability.getInstance().isGooglePlayServicesAvailable(context)
        }.getOrDefault(0) == 0

    fun start(sessionDir: File) {
        val sensorsDir = File(sessionDir, "sensors").apply { mkdirs() }
        val out = BufferedWriter(FileWriter(File(sensorsDir, "gps.csv")))
        out.write("utc_ms,lat,lon,alt_m,accuracy_m")
        out.newLine()
        writer = out

        val request = LocationRequest.Builder(Priority.PRIORITY_HIGH_ACCURACY, 1000L)
            .setMinUpdateDistanceMeters(0.5f)
            .build()
        val cb = object : LocationCallback() {
            override fun onLocationResult(result: LocationResult) {
                val loc = result.lastLocation ?: return
                if (reference == null) reference = loc
                out.write(
                    "${loc.time},${loc.latitude},${loc.longitude},${loc.altitude},${loc.accuracy}"
                )
                out.newLine()
                out.flush()
            }
        }
        callback = cb
        client.requestLocationUpdates(request, cb, Looper.getMainLooper())
    }

    fun stop() {
        writer?.let { runCatching { it.flush() }; runCatching { it.close() } }
        writer = null
        callback?.let { client.removeLocationUpdates(it) }
        callback = null
    }
}
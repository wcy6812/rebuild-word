package com.rebuild.word3.ui

import android.view.Surface
import androidx.camera.view.PreviewView
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.rebuild.word3.ScanViewModel
import com.rebuild.word3.camera.CameraController
import kotlin.math.min

@Composable
fun ScanScreen(
    viewModel: ScanViewModel,
    camera: CameraController,
    onDone: () -> Unit,
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val lifecycleOwner = LocalLifecycleOwner.current
    val view = LocalView.current

    Box(modifier = Modifier.fillMaxSize()) {
        AndroidView(
            factory = { ctx ->
                PreviewView(ctx).apply {
                    implementationMode = PreviewView.ImplementationMode.COMPATIBLE
                }
            },
            modifier = Modifier.fillMaxSize(),
        ) { previewView ->
            LaunchedEffect(Unit) {
                val rotation = view.display?.rotation ?: Surface.ROTATION_0
                camera.bind(lifecycleOwner, previewView, rotation)
                viewModel.startScan(camera)
            }
        }

        Column(modifier = Modifier.fillMaxSize()) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(Color.Black.copy(alpha = 0.35f))
                    .padding(16.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                CircularProgressIndicator(
                    progress = {
                        min(state.frameCount.toFloat() / state.targetFrames, 1f)
                    },
                    modifier = Modifier.size(40.dp),
                    strokeWidth = 4.dp,
                )
                Spacer(Modifier.width(16.dp))
                Text(
                    "已拍 ${state.frameCount} / ${state.targetFrames} 张",
                    color = Color.White,
                    style = MaterialTheme.typography.titleMedium,
                )
            }
            Spacer(Modifier.height(8.dp))
            Row(modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp)) {
                StatusBadge("陀螺仪", state.gyroAvailable)
                Spacer(Modifier.width(8.dp))
                StatusBadge("GPS", state.gpsAvailable)
                Spacer(Modifier.width(8.dp))
                StatusBadge("拍照", state.lastCameraError == null)
            }
            Spacer(Modifier.weight(1f))
            CaptureHint(rotationDeg = state.rotationSinceCaptureDeg)
            Spacer(Modifier.height(8.dp))
            Button(
                onClick = {
                    viewModel.stopScan()
                    onDone()
                },
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 32.dp),
            ) {
                Text("结束扫描")
            }
            Spacer(Modifier.height(32.dp))
        }
    }
}

@Composable
private fun StatusBadge(label: String, ok: Boolean) {
    Surface(
        shape = CircleShape,
        color = if (ok) Color(0xFF2E7D32) else Color(0xFFC62828),
    ) {
        Text(
            "$label ${if (ok) "●" else "○"}",
            modifier = Modifier.padding(horizontal = 10.dp, vertical = 4.dp),
            color = Color.White,
            style = MaterialTheme.typography.labelMedium,
        )
    }
}

@Composable
private fun CaptureHint(rotationDeg: Float) {
    val (text, color) = when {
        rotationDeg < 5f -> "转动太慢，画面重叠过多" to Color(0xFFFFB300)
        rotationDeg > 30f -> "转动太快，重叠不足" to Color(0xFFE53935)
        else -> "转动速度合适" to Color(0xFF43A047)
    }
    Surface(
        color = Color.Black.copy(alpha = 0.55f),
        shape = MaterialTheme.shapes.medium,
    ) {
        Text(
            "$text（${"%.0f".format(rotationDeg)}°）",
            modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
            color = color,
            style = MaterialTheme.typography.bodyMedium,
        )
    }
}
package com.rebuild.word3

import android.content.Intent
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.viewModels
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.core.content.FileProvider
import com.rebuild.word3.camera.CameraController
import com.rebuild.word3.ui.PermissionScreen
import com.rebuild.word3.ui.PrepareScreen
import com.rebuild.word3.ui.ReviewScreen
import com.rebuild.word3.ui.ScanScreen
import java.io.File

private enum class Step { Permissions, Prepare, Scan, Review }

class MainActivity : ComponentActivity() {

    private val viewModel: ScanViewModel by viewModels()
    private val cameraController by lazy { CameraController(this) }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            MaterialTheme {
                Surface(modifier = Modifier.fillMaxSize()) {
                    Word3App(
                        viewModel = viewModel,
                        camera = cameraController,
                        onShare = { shareWord3(it) },
                    )
                }
            }
        }
    }

    override fun onDestroy() {
        cameraController.shutdown()
        super.onDestroy()
    }

    private fun shareWord3(file: File) {
        val uri = FileProvider.getUriForFile(this, "$packageName.fileprovider", file)
        val intent = Intent(Intent.ACTION_SEND).apply {
            type = "application/zip"
            putExtra(Intent.EXTRA_STREAM, uri)
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        }
        startActivity(Intent.createChooser(intent, "分享 .3word 文件"))
    }
}

@Composable
private fun Word3App(
    viewModel: ScanViewModel,
    camera: CameraController,
    onShare: (File) -> Unit,
) {
    var step by remember { mutableStateOf(Step.Permissions) }

    when (step) {
        Step.Permissions -> PermissionScreen(onNext = { step = Step.Prepare })
        Step.Prepare -> PrepareScreen(onStart = { step = Step.Scan })
        Step.Scan -> ScanScreen(
            viewModel = viewModel,
            camera = camera,
            onDone = { step = Step.Review },
        )
        Step.Review -> ReviewScreen(
            viewModel = viewModel,
            onPacked = { file ->
                onShare(file)
                step = Step.Prepare
            },
            onRescan = { step = Step.Scan },
        )
    }
}
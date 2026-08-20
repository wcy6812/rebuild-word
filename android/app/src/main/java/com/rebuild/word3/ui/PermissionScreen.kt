package com.rebuild.word3.ui

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat

private val REQUIRED_PERMISSIONS = arrayOf(
    Manifest.permission.CAMERA,
    Manifest.permission.ACCESS_FINE_LOCATION,
)

@Composable
fun PermissionScreen(onNext: () -> Unit) {
    val context = LocalContext.current
    var permissionState by remember {
        mutableStateOf(permissionsGranted(context))
    }

    val launcher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { permissionState = permissionsGranted(context) }

    Column(
        modifier = Modifier.fillMaxSize().padding(32.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text("采集需要两项权限", style = MaterialTheme.typography.headlineMedium)
        Spacer(Modifier.height(16.dp))
        Text(
            "相机：拍摄场景照片\n定位：记录 GPS 坐标用于地理参考（可选）",
            style = MaterialTheme.typography.bodyLarge,
            textAlign = TextAlign.Center,
        )
        Spacer(Modifier.height(32.dp))
        if (!permissionState) {
            Button(onClick = { launcher.launch(REQUIRED_PERMISSIONS) }) {
                Text("授权")
            }
            Spacer(Modifier.height(8.dp))
            Text(
                "若此前已拒绝，请到系统设置中为应用开启权限",
                style = MaterialTheme.typography.bodySmall,
            )
        } else {
            Text("权限已就绪", color = MaterialTheme.colorScheme.primary)
        }
        Spacer(Modifier.height(32.dp))
        Button(
            onClick = onNext,
            enabled = permissionState,
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text("下一步")
        }
    }
}

private fun permissionsGranted(context: Context): Boolean =
    REQUIRED_PERMISSIONS.all {
        ContextCompat.checkSelfPermission(context, it) == PackageManager.PERMISSION_GRANTED
    }
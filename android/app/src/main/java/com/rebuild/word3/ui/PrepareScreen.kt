package com.rebuild.word3.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CameraAlt
import androidx.compose.material.icons.filled.Highlight
import androidx.compose.material.icons.filled.Lightbulb
import androidx.compose.material.icons.filled.NearMe
import androidx.compose.material3.Button
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp

private data class Tip(val icon: androidx.compose.ui.graphics.vector.ImageVector, val text: String)

private val TIPS = listOf(
    Tip(Icons.Filled.NearMe, "缓慢环绕目标物体或区域一周，保持画面连续"),
    Tip(Icons.Filled.Highlight, "相邻两帧重叠 ≥50%，转动不要太快"),
    Tip(Icons.Filled.CameraAlt, "避免纯色墙面、镜面反光、强逆光场景"),
    Tip(Icons.Filled.Lightbulb, "光线均匀，手机稳定，可双手持握"),
)

@Composable
fun PrepareScreen(onStart: () -> Unit) {
    Column(
        modifier = Modifier.fillMaxSize().padding(32.dp),
        verticalArrangement = Arrangement.Center,
    ) {
        Text("扫描指南", style = MaterialTheme.typography.headlineMedium)
        Spacer(Modifier.height(24.dp))
        TIPS.forEach { tip ->
            Row(
                modifier = Modifier.fillMaxWidth().padding(vertical = 12.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Icon(tip.icon, contentDescription = null)
                Spacer(Modifier.padding(start = 16.dp))
                Text(tip.text, style = MaterialTheme.typography.bodyLarge)
            }
        }
        Spacer(Modifier.height(32.dp))
        Text(
            "扫描过程中请保持陀螺仪与 GPS 开启；完成后将打包为 .3word 文件，可在电脑端重建。",
            style = MaterialTheme.typography.bodySmall,
        )
        Spacer(Modifier.height(24.dp))
        Button(onClick = onStart, modifier = Modifier.fillMaxWidth()) {
            Text("开始扫描")
        }
    }
}
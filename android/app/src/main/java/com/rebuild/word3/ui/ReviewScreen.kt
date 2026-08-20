package com.rebuild.word3.ui

import android.graphics.BitmapFactory
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.itemsIndexed
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.produceState
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.compose.foundation.Image
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.rebuild.word3.ScanViewModel
import java.io.File

@Composable
fun ReviewScreen(
    viewModel: ScanViewModel,
    onPacked: (File) -> Unit,
    onRescan: () -> Unit,
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val frames = viewModel.frames

    Column(modifier = Modifier.fillMaxSize().padding(16.dp)) {
        Text(
            "已采集 ${frames.size} 帧，点击缩略图可删除",
            style = MaterialTheme.typography.titleMedium,
        )
        Spacer(Modifier.height(12.dp))
        LazyVerticalGrid(
            columns = GridCells.Fixed(4),
            horizontalArrangement = Arrangement.spacedBy(4.dp),
            verticalArrangement = Arrangement.spacedBy(4.dp),
            modifier = Modifier.weight(1f),
        ) {
            itemsIndexed(frames) { index, file ->
                FrameThumb(file = file, onDelete = { viewModel.deleteFrame(index) })
            }
        }
        Spacer(Modifier.height(12.dp))
        if (state.isPacking) {
            Box(modifier = Modifier.fillMaxWidth(), contentAlignment = Alignment.Center) {
                CircularProgressIndicator()
                Spacer(Modifier.height(8.dp))
                Text("正在打包 .3word…")
            }
        } else {
            Row(modifier = Modifier.fillMaxWidth()) {
                Button(onClick = onRescan, modifier = Modifier.weight(1f)) {
                    Text("重新扫描")
                }
                Spacer(Modifier.padding(start = 8.dp))
                Button(
                    onClick = { viewModel.finishAndPack(onPacked) },
                    enabled = frames.isNotEmpty(),
                    modifier = Modifier.weight(1f),
                ) {
                    Text("完成并打包")
                }
            }
        }
    }
}

@Composable
private fun FrameThumb(file: File, onDelete: () -> Unit) {
    val context = LocalContext.current
    val bitmap by produceState<android.graphics.Bitmap?>(null, file) {
        value = decodeSampledBitmap(file, 256)
    }
    Box {
        if (bitmap != null) {
            Image(
                bitmap = bitmap!!.asImageBitmap(),
                contentDescription = null,
                contentScale = ContentScale.Crop,
                modifier = Modifier
                    .fillMaxWidth()
                    .aspectRatio(3f / 4f),
            )
        } else {
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .aspectRatio(3f / 4f)
                    .clickable(onClick = onDelete),
                contentAlignment = Alignment.Center,
            ) {
                Text("加载失败", color = Color.Gray, style = MaterialTheme.typography.labelSmall)
            }
        }
        IconButton(
            onClick = onDelete,
            modifier = Modifier.align(Alignment.TopEnd),
        ) {
            Icon(
                Icons.Filled.Delete,
                contentDescription = "删除该帧",
                tint = Color.White,
            )
        }
    }
}

private fun decodeSampledBitmap(file: File, reqSize: Int): android.graphics.Bitmap? {
    return runCatching {
        val opts = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        BitmapFactory.decodeFile(file.absolutePath, opts)
        var sample = 1
        while (opts.outWidth / sample > reqSize || opts.outHeight / sample > reqSize) {
            sample *= 2
        }
        BitmapFactory.decodeFile(
            file.absolutePath,
            BitmapFactory.Options().apply {
                inSampleSize = sample
                inPreferredConfig = android.graphics.Bitmap.Config.RGB_565
            },
        )
    }.getOrNull()
}
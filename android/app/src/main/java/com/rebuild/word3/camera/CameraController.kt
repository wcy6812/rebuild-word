package com.rebuild.word3.camera

import android.content.Context
import android.util.Size
import androidx.camera.camera2.interop.Camera2CameraInfo
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageCapture
import androidx.camera.core.ImageCaptureException
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.core.content.ContextCompat
import androidx.lifecycle.LifecycleOwner
import kotlinx.coroutines.suspendCancellableCoroutine
import java.io.File
import java.util.concurrent.Executor
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException

class CameraController(private val context: Context) {

    private var cameraProvider: ProcessCameraProvider? = null
    var imageCapture: ImageCapture? = null
        private set
    var outputSize: Size? = null
        private set
    var cameraId: String? = null
        private set

    suspend fun bind(lifecycleOwner: LifecycleOwner, previewView: PreviewView, rotationDegrees: Int) {
        val provider = ProcessCameraProvider.getInstance(context).get()
        cameraProvider = provider
        val selector = CameraSelector.DEFAULT_BACK_CAMERA

        val preview = Preview.Builder().build().also {
            it.setSurfaceProvider(previewView.surfaceProvider)
        }
        val capture = ImageCapture.Builder()
            .setCaptureMode(ImageCapture.CAPTURE_MODE_MINIMIZE_LATENCY)
            .setJpegQuality(95)
            .setTargetRotation(rotationDegrees)
            .build()

        outputSize = capture.resolutionInfo?.resolution
        cameraId = Camera2CameraInfo.from(
            CameraSelector.DEFAULT_BACK_CAMERA
                .filter(provider.availableCameraInfos)
                .first()
        ).cameraId

        provider.unbindAll()
        provider.bindToLifecycle(lifecycleOwner, selector, preview, capture)
        imageCapture = capture
    }

    fun selectedCameraIntrinsics(): CameraIntrinsics? {
        val size = outputSize ?: return null
        val id = cameraId ?: return null
        return CameraIntrinsics.from(context, id, size)
    }

    private fun executor(): Executor = ContextCompat.getMainExecutor(context)

    suspend fun captureToFile(target: File, onShutter: () -> Unit = {}): CaptureOutcome {
        val capture = imageCapture ?: throw IllegalStateException("相机未初始化")
        val options = ImageCapture.OutputFileOptions.Builder(target).build()
        onShutter()
        return suspendCancellableCoroutine { cont ->
            capture.takePicture(
                options,
                executor(),
                object : ImageCapture.OnImageSavedCallback {
                    override fun onImageSaved(outputFileResults: ImageCapture.OutputFileResults) {
                        cont.resume(CaptureOutcome(target))
                    }

                    override fun onError(exception: ImageCaptureException) {
                        cont.resumeWithException(exception)
                    }
                },
            )
        }
    }

    fun shutdown() {
        cameraProvider?.unbindAll()
        cameraProvider = null
        imageCapture = null
    }
}

data class CaptureOutcome(val file: File)
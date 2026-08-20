package com.rebuild.word3.pack

import java.io.BufferedOutputStream
import java.io.File
import java.io.FileOutputStream
import java.io.OutputStream
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream

/**
 * 将采集会话目录打包为 .3word（ZIP）。
 * 目录结构见 docs/3word-spec.md。
 */
object Word3Packager {

    fun pack(sessionDir: File, outFile: File): File {
        ZipOutputStream(BufferedOutputStream(FileOutputStream(outFile))).use { zip ->
            sessionDir.walkTopDown()
                .filter { it.isFile && it.parentFile != null }
                .sortedBy { it.absolutePath }
                .forEach { file ->
                    val relative = file.relativeTo(sessionDir).path.replace(File.separatorChar, '/')
                    zip.putNextEntry(ZipEntry(relative))
                    file.inputStream().use { it.copyTo(zip) }
                    zip.closeEntry()
                }
        }
        return outFile
    }
}
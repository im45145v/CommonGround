package com.commonground.companion

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent

/** Restarts the monitor after a reboot, but only if the user had enabled the gate and usage access is still granted. */
class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != Intent.ACTION_BOOT_COMPLETED) return
        val s = Settings(context)
        if (!s.gateEnabled) return
        if (!Usage.hasPermission(context)) { s.gateEnabled = false; return }
        try { MonitorService.start(context) } catch (e: Exception) { /* OS refused a background start: user can re-enable in app */ }
    }
}

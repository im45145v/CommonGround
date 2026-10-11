package com.commonground.companion

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.os.IBinder
import android.provider.Settings as AndroidSettings
import kotlinx.coroutines.*

/**
 * Opt-in enforcement. A visible foreground service polls usage stats; when the allowance is exhausted and a
 * selected recreational app is in the foreground it shows the soft gate (or a heads-up notification when the
 * OS does not let us start an activity from the background). It can be stopped from the notification or the app.
 *
 * It never gates essential apps (see Usage.candidateApps) and respects the visible override.
 */
class MonitorService : Service() {
    private val scope = CoroutineScope(Dispatchers.Default + SupervisorJob())
    private var job: Job? = null
    private var lastGate = 0L

    override fun onBind(i: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_STOP) { stopSelf(); return START_NOT_STICKY }
        val nm = getSystemService(NotificationManager::class.java)
        nm.createNotificationChannel(NotificationChannel(CH, "Screen-time budget", NotificationManager.IMPORTANCE_LOW))
        nm.createNotificationChannel(NotificationChannel(CH_GATE, "Budget reached", NotificationManager.IMPORTANCE_HIGH))
        val stop = PendingIntent.getService(this, 0, Intent(this, MonitorService::class.java).setAction(ACTION_STOP),
            PendingIntent.FLAG_IMMUTABLE)
        startForeground(1, Notification.Builder(this, CH).setSmallIcon(android.R.drawable.ic_menu_compass)
            .setContentTitle("CommonGround budget monitor is on")
            .setContentText("Watching selected recreational apps. Tap Stop to turn off.")
            .addAction(@Suppress("DEPRECATION") Notification.Action.Builder(android.R.drawable.ic_menu_close_clear_cancel, "Stop", stop).build()).setOngoing(true).build())
        job?.cancel()
        job = scope.launch { while (isActive) { try { tick() } catch (_: Exception) {}; delay(5000) } }
        return START_STICKY
    }

    private fun tick() {
        val s = Settings(this)
        if (!s.gateEnabled) { stopSelf(); return }
        if (!Usage.hasPermission(this)) { // permission revoked: switch enforcement off and say so; never fail silently
            s.gateEnabled = false
            getSystemService(NotificationManager::class.java).notify(3,
                Notification.Builder(this, CH_GATE).setSmallIcon(android.R.drawable.ic_menu_compass)
                    .setContentTitle("Budget monitor turned off")
                    .setContentText("Usage access was revoked, so CommonGround can no longer measure app time.").build())
            stopSelf(); return
        }
        if (s.overrideActive) return
        val gateable = Protection.gateable(s.selectedApps, Usage.protectedPackages(this))
        val fg = Usage.foregroundApp(this) ?: return // usage data unavailable -> do nothing
        if (fg !in gateable) return
        val w = WalletHolder.get(this)
        val used = Usage.minutesToday(this, gateable) ?: return
        val today = Settings.today()
        w.recordUsage(today, used)
        val st = Budget.compute(w.earnedMinutes, w.usedBefore(today), used, s.dailyCapMinutes)
        if (!st.exhausted || System.currentTimeMillis() - lastGate < 20_000) return
        lastGate = System.currentTimeMillis()
        val gate = Intent(this, GateActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        if (AndroidSettings.canDrawOverlays(this)) { // optional "display over other apps" grant
            startActivity(gate)
        } else {
            val pi = PendingIntent.getActivity(this, 1, gate, PendingIntent.FLAG_IMMUTABLE)
            getSystemService(NotificationManager::class.java).notify(2,
                Notification.Builder(this, CH_GATE).setSmallIcon(android.R.drawable.ic_menu_compass)
                    .setContentTitle("Social Battery empty")
                    .setContentText("Time for the outdoors? Tap to see your options.")
                    .setContentIntent(pi).setAutoCancel(true).build())
        }
    }

    override fun onDestroy() { scope.cancel(); super.onDestroy() }

    companion object {
        const val CH = "monitor"; const val CH_GATE = "gate"; const val ACTION_STOP = "stop"
        fun start(c: Context) = c.startForegroundService(Intent(c, MonitorService::class.java))
        fun stop(c: Context) { c.stopService(Intent(c, MonitorService::class.java)) }
    }
}

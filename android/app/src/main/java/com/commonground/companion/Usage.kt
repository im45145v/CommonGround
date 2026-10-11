package com.commonground.companion

import android.app.AppOpsManager
import android.app.usage.UsageEvents
import android.app.usage.UsageStatsManager
import android.content.Context
import android.content.Intent
import android.content.pm.ApplicationInfo
import android.content.pm.PackageManager
import android.os.Process
import android.provider.Settings as AndroidSettings
import android.provider.Telephony
import android.telecom.TelecomManager
import java.util.Calendar

data class AppInfo(val pkg: String, val label: String)

/** Wraps UsageStatsManager. Requires the user-granted "Usage access" special permission. */
object Usage {
    fun hasPermission(c: Context): Boolean {
        val ops = c.getSystemService(Context.APP_OPS_SERVICE) as AppOpsManager
        val mode = if (android.os.Build.VERSION.SDK_INT >= 29)
            ops.unsafeCheckOpNoThrow(AppOpsManager.OPSTR_GET_USAGE_STATS, Process.myUid(), c.packageName)
        else @Suppress("DEPRECATION") ops.checkOpNoThrow(AppOpsManager.OPSTR_GET_USAGE_STATS, Process.myUid(), c.packageName)
        return mode == AppOpsManager.MODE_ALLOWED
    }

    fun settingsIntent() = Intent(AndroidSettings.ACTION_USAGE_ACCESS_SETTINGS).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)

    private fun startOfDay(): Long = Calendar.getInstance().apply {
        set(Calendar.HOUR_OF_DAY, 0); set(Calendar.MINUTE, 0); set(Calendar.SECOND, 0); set(Calendar.MILLISECOND, 0)
    }.timeInMillis

    /** Whole minutes of foreground time today for the given packages; null when permission is missing. */
    fun minutesToday(c: Context, packages: Set<String>): Int? {
        if (!hasPermission(c) || packages.isEmpty()) return if (hasPermission(c)) 0 else null
        val usm = c.getSystemService(Context.USAGE_STATS_SERVICE) as UsageStatsManager
        val stats = try { usm.queryAndAggregateUsageStats(startOfDay(), System.currentTimeMillis()) } catch (e: SecurityException) { return null }
        val ms = packages.sumOf { stats[it]?.totalTimeInForeground ?: 0L }
        return (ms / 60000).toInt()
    }

    /** The app currently in the foreground (from recent usage events), or null. */
    fun foregroundApp(c: Context): String? {
        if (!hasPermission(c)) return null
        val usm = c.getSystemService(Context.USAGE_STATS_SERVICE) as UsageStatsManager
        val now = System.currentTimeMillis()
        val ev = usm.queryEvents(now - 15_000, now)
        val e = UsageEvents.Event()
        var last: String? = null
        while (ev.hasNextEvent()) {
            ev.getNextEvent(e)
            if (e.eventType == UsageEvents.Event.ACTIVITY_RESUMED) last = e.packageName
            else if (e.eventType == UsageEvents.Event.ACTIVITY_PAUSED && e.packageName == last) last = null
        }
        return last
    }

    /**
     * Launchable apps the user may choose as "recreational". Never offered (so never gated): system apps,
     * the default dialer/SMS apps, settings/emergency/accessibility-related packages and this app.
     */
    fun candidateApps(c: Context): List<AppInfo> {
        val pm = c.packageManager
        val protectedPkgs = protectedPackages(c)
        val launch = Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER)
        return pm.queryIntentActivities(launch, 0).mapNotNull { r ->
            val ai = r.activityInfo.applicationInfo
            val pkg = ai.packageName
            val system = ai.flags and ApplicationInfo.FLAG_SYSTEM != 0 && ai.flags and ApplicationInfo.FLAG_UPDATED_SYSTEM_APP == 0
            if (system || isProtected(pkg, protectedPkgs)) null else AppInfo(pkg, r.loadLabel(pm).toString())
        }.distinctBy { it.pkg }.sortedBy { it.label.lowercase() }
    }

    fun protectedPackages(c: Context): Set<String> {
        val s = mutableSetOf(c.packageName)
        try { (c.getSystemService(Context.TELECOM_SERVICE) as TelecomManager).defaultDialerPackage?.let(s::add) } catch (_: Exception) {}
        try { Telephony.Sms.getDefaultSmsPackage(c)?.let(s::add) } catch (_: Exception) {}
        return s
    }

    fun isProtected(pkg: String, extra: Set<String>) = Protection.isProtected(pkg, extra)
}

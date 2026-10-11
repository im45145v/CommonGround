package com.commonground.companion

import android.content.Context
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/** User-controlled settings (all opt-in, all local). */
class Settings(context: Context) {
    private val p = context.getSharedPreferences("settings", Context.MODE_PRIVATE)
    var selectedApps: Set<String>
        get() = p.getStringSet("apps", emptySet()) ?: emptySet()
        set(v) = p.edit().putStringSet("apps", v).apply()
    var dailyCapMinutes: Int
        get() = p.getInt("cap", 60)
        set(v) = p.edit().putInt("cap", v).apply()
    /** Soft gate is OFF until the user turns it on. */
    var gateEnabled: Boolean
        get() = p.getBoolean("gate", false)
        set(v) = p.edit().putBoolean("gate", v).apply()
    var overrideUntil: Long
        get() = p.getLong("override", 0)
        set(v) = p.edit().putLong("override", v).apply()
    val overrideActive get() = System.currentTimeMillis() < overrideUntil
    var lastStationUrl: String
        get() = p.getString("url", "") ?: ""
        set(v) = p.edit().putString("url", v).apply()

    companion object {
        const val OVERRIDE_MINUTES = 10
        fun today(): String = SimpleDateFormat("yyyy-MM-dd", Locale.US).format(Date())
    }
}

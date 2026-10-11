package com.commonground.companion

import android.app.Application
import android.os.Build
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File

class MainViewModel(app: Application) : AndroidViewModel(app) {
    val wallet = WalletHolder.get(app)
    val settings = Settings(app)

    var message by mutableStateOf("")
    var version by mutableStateOf(0) // bump to recompose after wallet/settings changes
    var hasUsagePermission by mutableStateOf(false)
    var status by mutableStateOf(BudgetStatus(0, 0, false))
    var apps by mutableStateOf<List<AppInfo>>(emptyList())

    init { refresh() }

    fun refresh() {
        val c = getApplication<Application>()
        hasUsagePermission = Usage.hasPermission(c)
        val used = Usage.minutesToday(c, settings.selectedApps)
        val today = Settings.today()
        if (used != null) wallet.recordUsage(today, used)
        status = Budget.compute(wallet.earnedMinutes, wallet.usedBefore(today), wallet.usedMinutes(today), settings.dailyCapMinutes)
        version++
    }

    fun loadApps() = viewModelScope.launch {
        apps = withContext(Dispatchers.IO) { Usage.candidateApps(getApplication()) }
    }

    fun connect(url: String, code: String) = io("Pairing…") {
        val client = StationClient(url)
        val st = client.status() // also proves the station is reachable
        val r = client.claim(code.trim(), "${Build.MANUFACTURER} ${Build.MODEL}")
        wallet.pair(client.base, r.optString("station", st.optString("station")), r.getString("public_key"),
            r.getString("token"), r.getString("user_id"))
        settings.lastStationUrl = client.base
        "Paired with ${wallet.stationName}"
    }

    fun sync() = io("Syncing…") {
        if (!wallet.isPaired) return@io "Pair with a station first."
        val r = Sync.run(wallet, StationClient(wallet.stationUrl))
        "Synced: ${r.added} new receipt(s), ${r.rejected} rejected"
    }

    fun addManual(token: String) {
        message = when (wallet.addReceipt(token)) {
            AddResult.Added -> "Receipt verified and added (will be redeemed on the station at next sync)."
            AddResult.Duplicate -> "Receipt already in your wallet."
            AddResult.WrongUser -> "Receipt belongs to a different participant."
            AddResult.Invalid -> if (wallet.isPaired) "Invalid receipt signature." else "Pair with a station first."
        }
        refresh()
    }

    fun toggleApp(pkg: String) { settings.selectedApps = settings.selectedApps.let { if (pkg in it) it - pkg else it + pkg }; refresh() }
    fun setCap(m: Int) { settings.dailyCapMinutes = m; refresh() }
    fun setGate(on: Boolean) {
        val c = getApplication<Application>()
        settings.gateEnabled = on
        if (on) MonitorService.start(c) else MonitorService.stop(c)
        refresh()
    }
    fun override() { settings.overrideUntil = System.currentTimeMillis() + Settings.OVERRIDE_MINUTES * 60_000L; refresh() }
    fun clearOverride() { settings.overrideUntil = 0; refresh() }

    private fun io(start: String, block: () -> String) {
        message = start
        viewModelScope.launch {
            message = try { withContext(Dispatchers.IO) { block() } }
            catch (e: StationException) { "Station error: ${e.message}" }
            catch (e: java.io.IOException) { "Station unreachable (${e.javaClass.simpleName}). Your wallet is still available offline." }
            catch (e: Exception) { "Error: ${e.message}" }
            refresh()
        }
    }
}

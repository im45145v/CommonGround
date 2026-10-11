package com.commonground.companion

import org.json.JSONArray
import org.json.JSONObject
import java.io.File

data class WalletEntry(val receipt: Receipt, val redeemedOnStation: Boolean, val token: String)

sealed class AddResult {
    object Added : AddResult()
    object Duplicate : AddResult()
    object WrongUser : AddResult()
    object Invalid : AddResult()
}

/**
 * The Social Battery wallet. Persisted as a JSON file so it works with no network at all.
 * Receipts are only added after signature verification and are de-duplicated by receipt id.
 */
class Wallet(private val file: File) {
    var stationName: String = ""; private set
    var stationUrl: String = ""; private set
    var publicKey: String = ""; private set
    var deviceToken: String = ""; private set
    var userId: String = ""; private set
    /** Minutes of recreational screen time granted per credit. */
    var minutesPerCredit: Int = 1
    private val entries = LinkedHashMap<String, WalletEntry>()
    /** yyyy-MM-dd -> minutes of recreational app use recorded that day. */
    private val usage = HashMap<String, Int>()

    init { load() }

    val isPaired get() = publicKey.isNotEmpty()
    val history: List<WalletEntry> get() = entries.values.sortedByDescending { it.receipt.issuedAt }
    val earnedMinutes: Int get() = entries.values.sumOf { it.receipt.amount } * minutesPerCredit
    val totalCredits: Int get() = entries.values.sumOf { it.receipt.amount }
    fun has(id: String) = entries.containsKey(id)
    fun unsynced(): List<Pair<String, String>> = entries.values.filter { !it.redeemedOnStation }.map { it.receipt.id to it.token }

    @Synchronized
    fun pair(url: String, name: String, publicKey: String, token: String, userId: String) {
        if (this.userId.isNotEmpty() && this.userId != userId) { entries.clear() } // different identity: don't mix wallets
        stationUrl = url; stationName = name; this.publicKey = publicKey; deviceToken = token; this.userId = userId
        save()
    }

    @Synchronized
    fun unpair() { publicKey = ""; deviceToken = ""; save() } // keeps earned credits and history

    @Synchronized
    fun addReceipt(token: String, redeemed: Boolean = false): AddResult {
        if (publicKey.isEmpty()) return AddResult.Invalid
        val r = ReceiptVerifier.verify(publicKey, token) ?: return AddResult.Invalid
        if (userId.isNotEmpty() && r.userId != userId) return AddResult.WrongUser
        if (entries.containsKey(r.id)) return AddResult.Duplicate
        entries[r.id] = WalletEntry(r, redeemed, token.trim())
        save()
        return AddResult.Added
    }

    @Synchronized
    fun markRedeemed(id: String) {
        entries[id]?.let { entries[id] = it.copy(redeemedOnStation = true); save() }
    }

    // ---- usage / budget ----
    fun usedMinutes(day: String) = usage[day] ?: 0
    fun usedBefore(day: String) = usage.filterKeys { it != day }.values.sum()

    /** Usage only ever goes up within a day (it is re-read from UsageStatsManager). */
    @Synchronized
    fun recordUsage(day: String, minutes: Int) {
        if (minutes > (usage[day] ?: 0)) { usage[day] = minutes; save() }
    }

    @Synchronized
    fun save() {
        val j = JSONObject()
            .put("stationName", stationName).put("stationUrl", stationUrl).put("publicKey", publicKey)
            .put("deviceToken", deviceToken).put("userId", userId).put("minutesPerCredit", minutesPerCredit)
        j.put("entries", JSONArray().also { arr ->
            entries.values.forEach { e ->
                arr.put(JSONObject().put("id", e.receipt.id).put("user", e.receipt.userId).put("amount", e.receipt.amount)
                    .put("quest", e.receipt.quest).put("iat", e.receipt.issuedAt).put("redeemed", e.redeemedOnStation).put("token", e.token))
            }
        })
        j.put("usage", JSONObject().also { u -> usage.forEach { (d, m) -> u.put(d, m) } })
        file.parentFile?.mkdirs()
        val tmp = File(file.path + ".tmp")
        tmp.writeText(j.toString())
        if (!tmp.renameTo(file)) { file.writeText(j.toString()); tmp.delete() }
    }

    private fun load() {
        if (!file.exists()) return
        try {
            val j = JSONObject(file.readText())
            stationName = j.optString("stationName"); stationUrl = j.optString("stationUrl")
            publicKey = j.optString("publicKey"); deviceToken = j.optString("deviceToken")
            userId = j.optString("userId"); minutesPerCredit = j.optInt("minutesPerCredit", 1)
            val arr = j.optJSONArray("entries") ?: JSONArray()
            for (i in 0 until arr.length()) {
                val e = arr.getJSONObject(i)
                entries[e.getString("id")] = WalletEntry(
                    Receipt(e.getString("id"), e.getString("user"), e.getInt("amount"), e.optInt("quest"), e.getLong("iat")),
                    e.optBoolean("redeemed"), e.optString("token"))
            }
            val u = j.optJSONObject("usage")
            u?.keys()?.forEach { usage[it] = u.getInt(it) }
        } catch (e: Exception) {
            file.renameTo(File(file.path + ".corrupt")) // never silently lose a damaged wallet
        }
    }
}

/** Process-wide wallet shared by the UI and the monitor service so writes never clobber each other. */
object WalletHolder {
    @Volatile private var instance: Wallet? = null
    fun get(context: android.content.Context): Wallet = instance ?: synchronized(this) {
        instance ?: Wallet(File(context.applicationContext.filesDir, "wallet.json")).also { instance = it }
    }
}

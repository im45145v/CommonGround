package com.commonground.companion

import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

class StationException(val status: Int, message: String) : Exception(message)

/** Minimal HTTP client for the station API (plain HTTP on the local network). */
class StationClient(baseUrl: String) {
    val base = normalize(baseUrl)

    private fun call(method: String, path: String, body: JSONObject? = null, token: String? = null): JSONObject {
        val c = URL(base + path).openConnection() as HttpURLConnection
        try {
            c.requestMethod = method
            c.connectTimeout = 5000; c.readTimeout = 8000
            c.setRequestProperty("Content-Type", "application/json")
            if (token != null) c.setRequestProperty("Authorization", "Bearer " + token)
            if (body != null) { c.doOutput = true; c.outputStream.use { it.write(body.toString().toByteArray()) } }
            val code = c.responseCode
            val text = (if (code < 400) c.inputStream else c.errorStream)?.bufferedReader()?.readText().orEmpty()
            val json = try { JSONObject(text) } catch (e: Exception) { JSONObject() }
            if (code >= 400) throw StationException(code, json.optString("detail", "HTTP $code"))
            return json
        } finally { c.disconnect() }
    }

    fun status(): JSONObject = call("GET", "/api/status")
    fun claim(code: String, label: String): JSONObject =
        call("POST", "/api/pair/claim", JSONObject().put("code", code).put("label", label))
    fun pendingReceipts(token: String): List<String> {
        val arr = call("GET", "/api/receipts", token = token).getJSONArray("receipts")
        return (0 until arr.length()).map { arr.getString(it) }
    }
    fun redeem(receipt: String, token: String) =
        call("POST", "/api/receipts/redeem", JSONObject().put("receipt", receipt), token)
    /** Best effort: tells the station to forget this device's token. */
    fun revokeSelf(token: String) = call("DELETE", "/api/devices/current", token = token)

    companion object {
        fun normalize(url: String): String {
            var u = url.trim().trimEnd('/')
            if (!u.startsWith("http://") && !u.startsWith("https://")) u = "http://$u"
            return u
        }
    }
}

/**
 * Receipt synchronisation. Each receipt is verified offline first and stored in the wallet (deduplicated by id)
 * BEFORE it is redeemed, so a network failure can never lose a verified credit. Redemption tells the station
 * the receipt has been used; HTTP 409 means it was already redeemed and is treated as done.
 */
object Sync {
    data class Report(val added: Int, val rejected: Int, val redeemed: Int)

    fun run(wallet: Wallet, client: StationClient): Report {
        var added = 0; var rejected = 0; var redeemed = 0
        for (token in client.pendingReceipts(wallet.deviceToken)) {
            when (wallet.addReceipt(token)) {
                AddResult.Added -> added++
                AddResult.Duplicate -> {}
                else -> rejected++
            }
        }
        for ((id, token) in wallet.unsynced()) {
            try {
                client.redeem(token, wallet.deviceToken)
                wallet.markRedeemed(id); redeemed++
            } catch (e: StationException) {
                if (e.status == 409) wallet.markRedeemed(id) else if (e.status == 410) wallet.markRedeemed(id) else throw e
            }
        }
        return Report(added, rejected, redeemed)
    }
}

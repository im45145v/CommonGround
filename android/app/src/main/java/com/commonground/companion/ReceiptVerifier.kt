package com.commonground.companion

import org.json.JSONObject
import java.security.KeyFactory
import java.security.PublicKey
import java.security.Signature
import java.security.spec.X509EncodedKeySpec
import java.util.Base64 as JBase64

/** A receipt whose ECDSA signature has been verified against the station's public key. */
data class Receipt(
    val id: String, val userId: String, val amount: Int, val quest: Int, val issuedAt: Long,
    val audience: String = "", val expiresAt: Long = 0,
)

/**
 * Verifies station receipts offline: `<base64url(json)>.<base64url(DER ECDSA P-256/SHA-256 signature)>`.
 * Only the public key (base64 X.509 SubjectPublicKeyInfo) is needed; the phone cannot create valid receipts.
 */
object ReceiptVerifier {
    fun parsePublicKey(b64: String): PublicKey =
        KeyFactory.getInstance("EC").generatePublic(X509EncodedKeySpec(JBase64.getDecoder().decode(b64.trim())))

    /** Audience id of a station: first 16 hex chars of SHA-256 over its public key (matches the station). */
    fun stationId(publicKeyB64: String): String =
        java.security.MessageDigest.getInstance("SHA-256").digest(JBase64.getDecoder().decode(publicKeyB64.trim()))
            .joinToString("") { "%02x".format(it) }.substring(0, 16)

    /** Returns the receipt, or null if the signature or payload is invalid. */
    fun verify(publicKeyB64: String, token: String): Receipt? = try {
        val parts = token.trim().split(".")
        if (parts.size != 2) null else {
            val urlDecoder = JBase64.getUrlDecoder()
            val payload = urlDecoder.decode(parts[0])
            val sig = urlDecoder.decode(parts[1])
            val ok = Signature.getInstance("SHA256withECDSA").run {
                initVerify(parsePublicKey(publicKeyB64))
                update(payload)
                verify(sig)
            }
            if (!ok) null else {
                val j = JSONObject(String(payload, Charsets.UTF_8))
                val amount = j.getInt("amount")
                if (amount <= 0 || j.getInt("v") != 2) null
                else Receipt(j.getString("id"), j.getString("user"), amount, j.optInt("quest", 0), j.getLong("iat"),
                    j.getString("aud"), j.getLong("exp"))
            }
        }
    } catch (e: Exception) {
        null
    }
}

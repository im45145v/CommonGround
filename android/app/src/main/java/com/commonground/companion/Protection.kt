package com.commonground.companion

/** Packages that are never offered as "recreational" and never gated (essential/communication/safety/settings). */
object Protection {
    private val hints = listOf(
        "dialer", "contacts", "emergency", "accessibility", "settings", "messaging", "sms", "mms", "phone",
        "whatsapp", "telegram", "securesms", "maps", "talkback", "safetycore", "systemui", "launcher", "camera",
    )
    fun isProtected(pkg: String, extra: Set<String> = emptySet()) =
        pkg in extra || hints.any { pkg.contains(it, ignoreCase = true) }

    /** Selected apps minus anything protected: the only apps the monitor may ever act on. */
    fun gateable(selected: Set<String>, extra: Set<String> = emptySet()) = selected.filterNot { isProtected(it, extra) }.toSet()
}

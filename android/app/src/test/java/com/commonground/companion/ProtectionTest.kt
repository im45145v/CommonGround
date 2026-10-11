package com.commonground.companion

import org.junit.Assert.*
import org.junit.Test

class ProtectionTest {
    @Test fun essentialAppsAreProtected() {
        listOf("com.android.dialer", "com.google.android.contacts", "com.whatsapp", "org.thoughtcrime.securesms",
            "com.android.settings", "com.google.android.marvin.talkback", "com.example.emergency").forEach { assertTrue(it, Protection.isProtected(it)) }
    }
    @Test fun recreationalAppsAreNotProtected() {
        listOf("com.instagram.android", "com.zhiliaoapp.musically", "com.reddit.frontpage").forEach { assertFalse(it, Protection.isProtected(it)) }
    }
    @Test fun gateableDropsProtectedAndExtra() {
        val sel = setOf("com.instagram.android", "com.whatsapp", "com.custom.dialerapp", "x.default.sms.pkg")
        assertEquals(setOf("com.instagram.android"), Protection.gateable(sel, setOf("x.default.sms.pkg")))
    }
}

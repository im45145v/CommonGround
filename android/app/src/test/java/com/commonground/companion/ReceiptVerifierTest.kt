package com.commonground.companion

import org.junit.Assert.*
import org.junit.Test

/**
 * Fixtures were produced by the real station code (station/app/receipts.py) with a throwaway key, so this test
 * also proves Python-signed receipts verify on the JVM/Android crypto stack.
 */
object Fixture {
    const val PUBLIC_KEY = "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAE6kGuEJ0iz84dMy2K4TOvhLo6w7JJm7O9l0da6q7UmWJE0dxQMBQzpgqfXVPV5+o40v7TR9eZ2OhQIs/DmRpQVg=="
    const val GOOD = "eyJhbW91bnQiOjUsImlhdCI6MTcwMDAwMDAxMCwiaWQiOiJhYmMxMjMiLCJxdWVzdCI6MSwidXNlciI6InUxIiwidiI6MX0.MEUCIQDCyNIQHfdIoWCcl0SGVPbgbrlSEgIkSkxlwSUfqWSKOAIgZDwZdeKCsGJznJDomAwubbZ3MXRWWvEvo31BRdht3r0"
    const val BAD_SIGNATURE = "eyJhbW91bnQiOjUsImlhdCI6MTcwMDAwMDAxMCwiaWQiOiJhYmMxMjMiLCJxdWVzdCI6MSwidXNlciI6InUxIiwidiI6MX0.MEUCIQDCyNIQHfdIoWCcl0SGVPbgbrlSEgIkSkxlwSUfqWSKOAIgZDwZdeKCsGJznJDomAwubbZ3MXRWWvEvo31BRdhAAAA"
    const val BAD_PAYLOAD = "eyJhbW91bnQiOjUwMCwiaWF0IjoxNzAwMDAwMDEwLCJpZCI6ImFiYzEyMyIsInF1ZXN0IjoxLCJ1c2VyIjoidTEiLCJ2IjoxfQ.MEUCIQDCyNIQHfdIoWCcl0SGVPbgbrlSEgIkSkxlwSUfqWSKOAIgZDwZdeKCsGJznJDomAwubbZ3MXRWWvEvo31BRdht3r0"
    // Public key of a different station key pair
    const val OTHER_KEY = "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAE5EUQ42Orp0j0Rs7Yo/RyCc3C/W75ueP1Qh45cAe7g0oVi/oAigVdicov+F5ssqB2XRJKyfmDIp4s8uiPuaqiNg=="
}

class ReceiptVerifierTest {
    @Test fun validReceiptVerifies() {
        val r = ReceiptVerifier.verify(Fixture.PUBLIC_KEY, Fixture.GOOD)!!
        assertEquals("abc123", r.id); assertEquals(5, r.amount); assertEquals("u1", r.userId)
    }
    @Test fun modifiedSignatureRejected() = assertNull(ReceiptVerifier.verify(Fixture.PUBLIC_KEY, Fixture.BAD_SIGNATURE))
    @Test fun modifiedPayloadRejected() = assertNull(ReceiptVerifier.verify(Fixture.PUBLIC_KEY, Fixture.BAD_PAYLOAD))
    @Test fun garbageRejected() {
        assertNull(ReceiptVerifier.verify(Fixture.PUBLIC_KEY, "garbage"))
        assertNull(ReceiptVerifier.verify(Fixture.PUBLIC_KEY, "a.b.c"))
        assertNull(ReceiptVerifier.verify("not-a-key", Fixture.GOOD))
    }
    @Test fun wrongKeyRejected() = assertNull(ReceiptVerifier.verify(Fixture.OTHER_KEY, Fixture.GOOD))
}

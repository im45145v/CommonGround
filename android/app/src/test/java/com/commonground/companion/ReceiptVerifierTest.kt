package com.commonground.companion

import org.junit.Assert.*
import org.junit.Test

/**
 * Fixtures were produced by the real station code (station/app/receipts.py) with a throwaway key, so this test
 * also proves Python-signed receipts verify on the JVM/Android crypto stack.
 */
object Fixture {
    const val PUBLIC_KEY = "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEjHLHBRbNFsw7HhXWkV03qhMqU/WBe02I9kE1jXrkri39tjV4CYo/YsDkG6u9xNjmV1ryBZ2TOc/RXWjgPaEJjw=="
    const val STATION_ID = "fc04303435e7fe24"
    const val GOOD = "eyJhbW91bnQiOjUsImF1ZCI6ImZjMDQzMDM0MzVlN2ZlMjQiLCJleHAiOjQxMDI0NDQ4MDAsImlhdCI6MTcwMDAwMDAxMCwiaWQiOiJhYmMxMjMiLCJxdWVzdCI6MSwidXNlciI6InUxIiwidiI6Mn0.MEYCIQCoNBPvkDZYZ9WrWMbMslWcdbpQetH33e79jCnM2213YAIhAKAQ9b8xrckbE5xBNHE9DRmohlyCZY335uWIUaSWcwQg"
    const val BAD_SIGNATURE = "eyJhbW91bnQiOjUsImF1ZCI6ImZjMDQzMDM0MzVlN2ZlMjQiLCJleHAiOjQxMDI0NDQ4MDAsImlhdCI6MTcwMDAwMDAxMCwiaWQiOiJhYmMxMjMiLCJxdWVzdCI6MSwidXNlciI6InUxIiwidiI6Mn0.MEYCIQCoNBPvkDZYZ9WrWMbMslWcdbpQetH33e79jCnM2213YAIhAKAQ9b8xrckbE5xBNHE9DRmohlyCZY335uWIUaSWAAAA"
    const val BAD_PAYLOAD = "eyJhbW91bnQiOjUwMCwiYXVkIjoiZmMwNDMwMzQzNWU3ZmUyNCIsImV4cCI6NDEwMjQ0NDgwMCwiaWF0IjoxNzAwMDAwMDEwLCJpZCI6ImFiYzEyMyIsInF1ZXN0IjoxLCJ1c2VyIjoidTEiLCJ2IjoyfQ.MEYCIQCoNBPvkDZYZ9WrWMbMslWcdbpQetH33e79jCnM2213YAIhAKAQ9b8xrckbE5xBNHE9DRmohlyCZY335uWIUaSWcwQg"
    const val EXPIRED = "eyJhbW91bnQiOjUsImF1ZCI6ImZjMDQzMDM0MzVlN2ZlMjQiLCJleHAiOjE3MDAwMDAxMDAsImlhdCI6MTcwMDAwMDAxMCwiaWQiOiJvbGQxIiwicXVlc3QiOjEsInVzZXIiOiJ1MSIsInYiOjJ9.MEUCIBRezSP4dSNtunBe5W6UhB28DHJKeEDtWQfRSoDJ81mZAiEAu-CihNmBVPKmPhyg-5cxNMlybrbv7oOOhzy9QdsIqPI"
    const val WRONG_AUDIENCE = "eyJhbW91bnQiOjUsImF1ZCI6IjAxMjM0NTY3ODlhYmNkZWYiLCJleHAiOjQxMDI0NDQ4MDAsImlhdCI6MTcwMDAwMDAxMCwiaWQiOiJhdWQxIiwicXVlc3QiOjEsInVzZXIiOiJ1MSIsInYiOjJ9.MEQCIGU25-JS_xoTPtoGfJ8ntD1-ND7OV7sMcaECglURSfzCAiAS4aDcD7OipgENjBvQyEp5Ca4jY6R0h0g-o2YaLcmGLw"
    const val LEGACY_V1 = "eyJhbW91bnQiOjUsImlhdCI6MTcwMDAwMDAxMCwiaWQiOiJ2MSIsInF1ZXN0IjoxLCJ1c2VyIjoidTEiLCJ2IjoxfQ.MEQCIDXQOaZqNE8JB9LmqCpPnWsjslESdMmtoRd022-V5_kBAiAktcYKk3cwZDUzldtOr1ZhIIliNzqcXopIXB-N37r5GQ"
    // Public key of a different station key pair
    const val OTHER_KEY = "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEXR1zo+Qp0nYuy6n5oJRjVAkyTE+qTFTCYF+r1zRVjr3ApVJC9s0Inhn3eDCo/+GK4y36bqOCTuic1c98tXnorQ=="
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
    @Test fun stationIdMatchesStationImplementation() = assertEquals(Fixture.STATION_ID, ReceiptVerifier.stationId(Fixture.PUBLIC_KEY))
    @Test fun legacyV1Rejected() = assertNull(ReceiptVerifier.verify(Fixture.PUBLIC_KEY, Fixture.LEGACY_V1))
    @Test fun wrongKeyRejected() = assertNull(ReceiptVerifier.verify(Fixture.OTHER_KEY, Fixture.GOOD))
}

package com.commonground.companion

import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.io.File

class WalletTest {
    @get:Rule val tmp = TemporaryFolder()
    private fun file() = File(tmp.root, "wallet.json")
    private fun paired(f: File = file()) = Wallet(f, clock = { 1_700_000_500L }).also { it.pair("http://x", "Bench", Fixture.PUBLIC_KEY, "tok", "u1") }

    @Test fun addsVerifiedReceiptOnce() {
        val w = paired()
        assertEquals(AddResult.Added, w.addReceipt(Fixture.GOOD))
        assertEquals(AddResult.Duplicate, w.addReceipt(Fixture.GOOD))
        assertEquals(5, w.totalCredits)
        assertEquals(5, w.earnedMinutes)
    }
    @Test fun rejectsInvalidAndOtherUsersReceipts() {
        val w = paired()
        assertEquals(AddResult.Invalid, w.addReceipt(Fixture.BAD_SIGNATURE))
        assertEquals(AddResult.Invalid, w.addReceipt(Fixture.BAD_PAYLOAD))
        assertEquals(0, w.totalCredits)
        val other = Wallet(File(tmp.root, "o.json")).also { it.pair("http://x", "B", Fixture.PUBLIC_KEY, "t", "someone-else") }
        assertEquals(AddResult.WrongUser, other.addReceipt(Fixture.GOOD))
    }
    @Test fun rejectsExpiredWrongStationAndLegacyReceipts() {
        val w = paired()
        assertEquals(AddResult.Expired, w.addReceipt(Fixture.EXPIRED))
        assertEquals(AddResult.WrongStation, w.addReceipt(Fixture.WRONG_AUDIENCE))
        assertEquals(AddResult.Invalid, w.addReceipt(Fixture.LEGACY_V1))
        assertEquals(0, w.totalCredits)
    }
    @Test fun unpairedWalletRejectsReceipts() = assertEquals(AddResult.Invalid, Wallet(file()).addReceipt(Fixture.GOOD))

    @Test fun persistsAcrossRestartAndKeepsDuplicateProtection() {
        val w = paired(); w.addReceipt(Fixture.GOOD); w.recordUsage("2024-01-01", 3)
        val again = Wallet(file(), clock = { 1_700_000_500L })  // simulates app restart, no network
        assertEquals(5, again.totalCredits)
        assertEquals(3, again.usedMinutes("2024-01-01"))
        assertTrue(again.isPaired)
        assertEquals(AddResult.Duplicate, again.addReceipt(Fixture.GOOD))
        assertEquals(listOf("abc123"), again.unsynced().map { it.first })
        again.markRedeemed("abc123")
        assertTrue(Wallet(file()).unsynced().isEmpty())
    }
    @Test fun usageNeverDecreasesWithinADay() {
        val w = paired(); w.recordUsage("d", 10); w.recordUsage("d", 4)
        assertEquals(10, w.usedMinutes("d"))
    }
    @Test fun unpairKeepsCredits() {
        val w = paired(); w.addReceipt(Fixture.GOOD); w.unpair()
        assertEquals(5, Wallet(file()).totalCredits)
    }
    @Test fun corruptWalletIsPreservedNotLost() {
        file().writeText("{not json")
        assertEquals(0, Wallet(file()).totalCredits)
        assertTrue(File(file().path + ".corrupt").exists())
    }
}

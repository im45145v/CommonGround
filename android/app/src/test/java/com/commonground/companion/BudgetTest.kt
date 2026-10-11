package com.commonground.companion

import org.junit.Assert.*
import org.junit.Test

class BudgetTest {
    @Test fun allowanceIsCappedByDailyCap() {
        val s = Budget.compute(earnedMinutes = 100, usedBeforeToday = 0, usedToday = 10, dailyCapMinutes = 30)
        assertEquals(30, s.allowanceToday); assertEquals(20, s.remaining); assertFalse(s.exhausted)
    }
    @Test fun allowanceIsCappedByBattery() {
        val s = Budget.compute(50, 40, 0, 60)
        assertEquals(10, s.allowanceToday)
    }
    @Test fun exhaustedWhenUsedReachesAllowance() = assertTrue(Budget.compute(10, 0, 10, 60).exhausted)
    @Test fun noCreditsMeansExhausted() = assertTrue(Budget.compute(0, 0, 0, 60).exhausted)
    @Test fun neverNegative() {
        val s = Budget.compute(5, 20, 3, 60)
        assertEquals(0, s.allowanceToday); assertEquals(0, s.remaining)
    }
}

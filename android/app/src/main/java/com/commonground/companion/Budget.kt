package com.commonground.companion

data class BudgetStatus(
    val allowanceToday: Int,
    val usedToday: Int,
    val exhausted: Boolean,
) { val remaining get() = (allowanceToday - usedToday).coerceAtLeast(0) }

/**
 * Daily recreational allowance = min(user's daily cap, battery left at the start of today).
 * Battery = minutes earned from verified receipts minus minutes used on earlier days.
 */
object Budget {
    fun compute(earnedMinutes: Int, usedBeforeToday: Int, usedToday: Int, dailyCapMinutes: Int): BudgetStatus {
        val battery = (earnedMinutes - usedBeforeToday).coerceAtLeast(0)
        val allowance = minOf(dailyCapMinutes.coerceAtLeast(0), battery)
        return BudgetStatus(allowance, usedToday, usedToday >= allowance)
    }
}

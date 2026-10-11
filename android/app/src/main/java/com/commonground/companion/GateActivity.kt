package com.commonground.companion

import android.content.Intent
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp

/**
 * The soft gate: a polite full-screen nudge. It is NOT a lock - "Continue anyway" is always visible and
 * "Go home" just leaves. When opened with EXTRA_DEMO it is only a preview and enforces nothing.
 */
class GateActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val demo = intent.getBooleanExtra(EXTRA_DEMO, false)
        val s = Settings(this)
        setContent {
            MaterialTheme { Surface(Modifier.fillMaxSize()) {
                GateScreen(demo,
                    onHome = { startActivity(Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_HOME).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)); finish() },
                    onOverride = { if (!demo) s.overrideUntil = System.currentTimeMillis() + Settings.OVERRIDE_MINUTES * 60_000L; finish() })
            } }
        }
    }
    companion object { const val EXTRA_DEMO = "demo" }
}

@Composable
fun GateScreen(demo: Boolean, onHome: () -> Unit, onOverride: () -> Unit) {
    Column(Modifier.fillMaxSize().padding(24.dp), Arrangement.Center, Alignment.CenterHorizontally) {
        if (demo) Text("DEMO PREVIEW - nothing is being blocked", color = MaterialTheme.colorScheme.error)
        Spacer(Modifier.height(16.dp))
        Text("Your Social Battery is empty", style = MaterialTheme.typography.headlineMedium)
        Spacer(Modifier.height(8.dp))
        Text("Complete an outdoor quest at a CommonGround station to earn more scrolling time.")
        Spacer(Modifier.height(24.dp))
        Button(onClick = onHome) { Text("Go outside (leave this app)") }
        Spacer(Modifier.height(8.dp))
        OutlinedButton(onClick = onOverride) { Text("Continue anyway (${Settings.OVERRIDE_MINUTES} min)") }
    }
}

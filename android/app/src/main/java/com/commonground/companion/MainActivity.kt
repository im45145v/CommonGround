package com.commonground.companion

import android.Manifest
import android.content.Intent
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.viewModels
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import java.text.DateFormat
import java.util.Date

class MainActivity : ComponentActivity() {
    private val vm: MainViewModel by viewModels()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (Build.VERSION.SDK_INT >= 33) requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), 1)
        setContent { MaterialTheme { App(vm) } }
    }

    override fun onResume() { super.onResume(); vm.refresh() } // re-check permission after returning from Settings
}

private val TABS = listOf("Battery", "Station", "Apps", "Budget")

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun App(vm: MainViewModel) {
    var tab by remember { mutableIntStateOf(0) }
    @Suppress("UNUSED_VARIABLE") val v = vm.version
    Scaffold(
        topBar = { TopAppBar(title = { Text("CommonGround") }) },
        bottomBar = { NavigationBar { TABS.forEachIndexed { i, t ->
            NavigationBarItem(selected = tab == i, onClick = { tab = i }, icon = {}, label = { Text(t) }) } } },
    ) { pad ->
        Column(Modifier.padding(pad).padding(16.dp)) {
            if (vm.message.isNotEmpty()) { Text(vm.message, color = MaterialTheme.colorScheme.primary); Spacer(Modifier.height(8.dp)) }
            when (tab) {
                0 -> BatteryScreen(vm)
                1 -> StationScreen(vm)
                2 -> AppsScreen(vm)
                else -> BudgetScreen(vm)
            }
        }
    }
}

@Composable
fun BatteryScreen(vm: MainViewModel) {
    val w = vm.wallet
    val fmt = DateFormat.getDateTimeInstance(DateFormat.SHORT, DateFormat.SHORT)
    Card(Modifier.fillMaxWidth()) { Column(Modifier.padding(16.dp)) {
        Text("Social Battery", style = MaterialTheme.typography.titleMedium)
        Text("${vm.status.remaining} min left today", style = MaterialTheme.typography.headlineMedium)
        Text("Earned in total: ${w.earnedMinutes} min (${w.totalCredits} credits)")
        Text(if (w.isPaired) "Station: ${w.stationName}" else "Not paired - works offline with saved receipts")
    } }
    Spacer(Modifier.height(8.dp))
    Button(onClick = { vm.sync() }, enabled = w.isPaired) { Text("Sync receipts from station") }
    Spacer(Modifier.height(8.dp))
    var paste by remember { mutableStateOf("") }
    OutlinedTextField(paste, { paste = it }, label = { Text("Paste a receipt (offline)") }, modifier = Modifier.fillMaxWidth())
    OutlinedButton(onClick = { vm.addManual(paste); paste = "" }) { Text("Verify & add") }
    Text("Reward history", style = MaterialTheme.typography.titleMedium, modifier = Modifier.padding(top = 12.dp))
    LazyColumn { items(w.history) { e ->
        ListItem(
            headlineContent = { Text("+${e.receipt.amount} credits (${e.receipt.amount * w.minutesPerCredit} min)") },
            supportingContent = { Text(fmt.format(Date(e.receipt.issuedAt * 1000)) + if (e.redeemedOnStation) "" else " · not yet synced") })
    } }
}

@Composable
fun StationScreen(vm: MainViewModel) {
    var url by remember { mutableStateOf(vm.wallet.stationUrl.ifEmpty { vm.settings.lastStationUrl }) }
    var code by remember { mutableStateOf("") }
    Column(Modifier.verticalScroll(rememberScrollState())) {
        Text("Connect to a station", style = MaterialTheme.typography.titleMedium)
        Text("1. Join the station's Wi-Fi. 2. In the station web page open Battery > Pair Android app. 3. Enter the URL and the 6-digit code.")
        OutlinedTextField(url, { url = it }, label = { Text("Station URL, e.g. 192.168.1.20:8000") }, modifier = Modifier.fillMaxWidth())
        OutlinedTextField(code, { code = it }, label = { Text("Pairing code") }, modifier = Modifier.fillMaxWidth())
        Button(onClick = { vm.connect(url, code) }) { Text("Pair") }
        if (vm.wallet.isPaired) {
            Text("Paired: ${vm.wallet.stationName} (${vm.wallet.stationUrl})", modifier = Modifier.padding(top = 12.dp))
            Text("Receipts are verified on this phone using the station's public key (ECDSA P-256).")
            OutlinedButton(onClick = { vm.wallet.unpair(); vm.refresh() }) { Text("Unpair (keeps earned minutes)") }
        }
    }
}

@Composable
fun AppsScreen(vm: MainViewModel) {
    LaunchedEffect(Unit) { vm.loadApps() }
    Text("Choose your recreational apps", style = MaterialTheme.typography.titleMedium)
    Text("Only these are counted. System, phone, messaging, emergency and accessibility apps are never listed.")
    LazyColumn { items(vm.apps) { a ->
        ListItem(headlineContent = { Text(a.label) }, supportingContent = { Text(a.pkg) },
            trailingContent = { Checkbox(a.pkg in vm.settings.selectedApps, { vm.toggleApp(a.pkg) }) })
    } }
}

@Composable
fun BudgetScreen(vm: MainViewModel) {
    val ctx = androidx.compose.ui.platform.LocalContext.current
    val s = vm.settings
    Column(Modifier.verticalScroll(rememberScrollState())) {
        Text("Usage tracking", style = MaterialTheme.typography.titleMedium)
        if (vm.hasUsagePermission) {
            Text("Permission: GRANTED. Used today: ${vm.status.usedToday} min of ${vm.status.allowanceToday} min allowance.")
        } else {
            Text("Permission: NOT GRANTED. CommonGround needs Android's \"Usage access\" to see how long your selected apps are open. " +
                "It only reads app-usage time on this phone, never content, and nothing leaves the device. Without it the budget cannot be measured and no gate is shown.",
                color = MaterialTheme.colorScheme.error)
            Button(onClick = { ctx.startActivity(Usage.settingsIntent()) }) { Text("Open Usage access settings") }
        }
        Text("Daily cap: ${s.dailyCapMinutes} min", modifier = Modifier.padding(top = 12.dp))
        Slider(s.dailyCapMinutes.toFloat(), { vm.setCap(it.toInt() / 5 * 5) }, valueRange = 5f..240f)

        Text("Soft gate (opt-in)", style = MaterialTheme.typography.titleMedium, modifier = Modifier.padding(top = 12.dp))
        Row { Switch(s.gateEnabled, { vm.setGate(it) }, enabled = vm.hasUsagePermission); Spacer(Modifier.width(8.dp))
            Text(if (s.gateEnabled) "ENFORCEMENT ON: a visible notification shows while the monitor runs" else "Enforcement OFF: usage is only tracked") }
        Text("When your allowance is used up and a selected app is open, a screen offers to take you outside. It is not a lock: " +
            "\"Continue anyway\" is always available and the monitor can be switched off here at any time. Android only lets the gate appear on " +
            "top of other apps if you grant \"Display over other apps\"; otherwise you get a notification instead.")
        OutlinedButton(onClick = { ctx.startActivity(overlayPermissionIntent()) }) { Text("Display over other apps (optional)") }
        if (s.overrideActive) { Text("Override active until ${DateFormat.getTimeInstance(DateFormat.SHORT).format(Date(s.overrideUntil))}")
            OutlinedButton(onClick = { vm.clearOverride() }) { Text("End override") } }
        else OutlinedButton(onClick = { vm.override() }) { Text("Override gate for ${Settings.OVERRIDE_MINUTES} min") }

        Text("Demo screen", style = MaterialTheme.typography.titleMedium, modifier = Modifier.padding(top = 12.dp))
        OutlinedButton(onClick = { ctx.startActivity(Intent(ctx, GateActivity::class.java).putExtra(GateActivity.EXTRA_DEMO, true)) }) {
            Text("Preview gate screen (demo only, blocks nothing)") }
    }
}

private fun overlayPermissionIntent() = Intent(android.provider.Settings.ACTION_MANAGE_OVERLAY_PERMISSION)

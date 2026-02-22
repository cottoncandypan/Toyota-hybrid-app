# ToyotaScan — Android APK
### Prius / Toyota Diagnostic App · Veepeak Bluetooth OBD2

---

## HOW TO GET THE APK ON YOUR PHONE
### (No coding knowledge required — 5 steps)

---

### STEP 1 — Create a free GitHub account
Go to **https://github.com** and sign up (free).

---

### STEP 2 — Create a new repository and upload the files

1. Click the **+** button (top right) → **New repository**
2. Name it `toyotascan`, set to **Private**, click **Create repository**
3. Click **uploading an existing file**
4. Drag ALL these files into the upload window:
   - `main.py`
   - `buildozer.spec`
   - `.github/workflows/build.yml`  ← make sure this path is preserved
5. Click **Commit changes**

> **Tip for the workflow file:** GitHub needs the folder structure
> `.github/workflows/build.yml`. When uploading, click "choose your files",
> then navigate into the `.github/workflows/` folder and select `build.yml`.
> GitHub will create the folders automatically.

---

### STEP 3 — Watch the build

1. In your repo, click the **Actions** tab
2. You'll see a workflow run called **"Build ToyotaScan APK"** already running
3. Click it → click **"Build Android APK"** to watch the live log
4. ☕ First build takes **~25–40 minutes** (downloading Android NDK/SDK)
5. Subsequent builds use cache and take **~8–12 minutes**

If the build goes green ✅ — you're done. If it goes red ❌, scroll to the
bottom of the log and check the error. Common issues are listed at the
bottom of this file.

---

### STEP 4 — Download the APK

1. After the build succeeds, click **Artifacts** at the bottom of the run page
2. Click **ToyotaScan-debug** — it downloads a `.zip`
3. Unzip it — inside is `toyotascan-0.1-debug.apk`
4. Transfer it to your Android phone (email it to yourself, Google Drive,
   USB cable — any method works)

---

### STEP 5 — Install on Android

1. On your phone, open the APK file
2. Android will say **"Install from unknown sources"** — tap **Settings**
3. Enable **"Install unknown apps"** for your file manager or browser
4. Go back and tap **Install**
5. Done! ToyotaScan appears in your app drawer.

---

## CONNECTING TO YOUR VEEPEAK ADAPTER

### First time setup (do this once):
1. Plug your Veepeak OBDCheck into the Prius OBD2 port (under dash, driver side)
2. Turn ignition to **ON** (not necessarily engine running)
3. On your Android phone: **Settings → Bluetooth**
4. Tap **Pair new device**
5. Select **VEEPEAK** from the list
6. Enter PIN: **1234**
7. Tap **Pair** — it should pair successfully

### Using ToyotaScan:
1. Open ToyotaScan
2. Tap **SCAN FOR VEEPEAK**
3. VEEPEAK will appear highlighted in teal — tap it
4. Wait ~2 seconds for connection
5. You're in! Tap **▶ START LIVE DATA** on the Live tab

---

## WHAT THE APP DOES

### 📊 LIVE TAB
Real-time data from all 12 standard OBD-II PIDs plus 8 Prius-enhanced
PIDs including HV battery SOC, voltage, current, temperature, MG1/MG2
speeds, inverter temp, and VVT advance. Each parameter shows a live bar
graph that turns amber/red as values approach limits.

### ⚡ HYBRID TAB
Prius-specific hybrid system monitor:
- **Power flow diagram** — shows energy routing Engine→Battery→MG2→Wheels
  with animated arrows that change direction during regen braking
- **Drive mode** — EV / HYBRID / REGEN / CHARGING indicator
- **HV Battery pack** — SOC gauge, pack voltage/current/temp, fan speed,
  state-of-health (SOH %)
- **28-module cell voltage grid** — colour-coded blocks (teal=normal,
  amber=high, red=low). The cell delta (max−min mV) is the key early
  indicator of a failing module — watch for >200mV delta
- **Regenerative braking** — live power bar (max 27kW), energy recovered
- **MG1 / MG2** — speed, torque, power, temperature
- **Hybrid DTCs** — HV ECU, Battery ECU, Inverter ECU fault codes
  (separate from standard OBD-II codes)

### ⚠ DTC TAB
- Read stored and pending fault codes
- Full description for each code
- One-tap clear (with confirmation)

### 🔧 TESTS TAB
Active component tests — directly commands vehicle hardware:
- Cooling fan (low/high/off)
- Fuel pump on/off
- EVAP VSV on/off
- Individual injector cut tests
- MIL (Check Engine Light) on/off
- **HV battery cooling fan** (Prius-specific)

### 📋 CONSOLE TAB
Raw ELM327 command terminal. Useful quick commands:
- `ATI` — ELM327 version
- `ATDP` — detected protocol
- `010C` — engine RPM
- `0105` — coolant temp
- `2101` — Prius HV battery frame 1
- `2110` — HV battery SOC
- `03` — read DTCs
- `04` — clear DTCs

---

## VEEPEAK ADAPTER DETAILS

**Model:** Veepeak OBDCheck BLE / Mini Bluetooth OBD2
**Connection type:** Classic Bluetooth (not BLE) — Serial Port Profile (SPP)
**Bluetooth PIN:** 1234
**Protocol used:** ISO 15765-4 CAN (auto-detected)
**ELM327 compatibility:** Yes — full AT command set supported

---

## TROUBLESHOOTING

| Problem | Fix |
|---------|-----|
| "Scan finds no devices" | Pair Veepeak in Android BT settings first |
| "Connection failed" | Turn ignition ON, wait 5s, try again |
| "NO DATA" on PIDs | Ignition must be ON (engine not required for most PIDs) |
| App crashes on open | Enable "Install unknown apps" permission properly |
| Build fails on GitHub | See common errors below |

### Common GitHub Actions Build Errors

**`NDK not found`** — The cache didn't restore. Re-run the workflow
(Actions tab → Re-run jobs). The NDK downloads fresh (~1.5GB).

**`Cython version error`** — The `buildozer.spec` pins `cython==0.29.37`
which is correct for Kivy 2.3.0. Don't change this.

**`Permission denied` on build**  — Add a blank line at the end of
`buildozer.spec` and re-commit. Triggers a fresh build.

**Build takes >50 minutes and times out** — GitHub Actions free tier has
a 6-hour limit per job. The first build is typically 25–40 minutes.
If it times out, re-run — the cache will be warmer.

---

## UPDATING THE APP

1. Edit `main.py` on GitHub (click the file → pencil icon)
2. Commit the change
3. GitHub Actions automatically starts a new build
4. Download and install the new APK (Android will ask if you want to update)

---

## PRIUS COMPATIBILITY

| Generation | Years    | OBD2 | Standard PIDs | Hybrid PIDs |
|------------|----------|------|---------------|-------------|
| Gen 2      | 2004–09  | ✅   | ✅            | Partial     |
| Gen 3      | 2010–15  | ✅   | ✅            | ✅ Full     |
| Gen 4      | 2016–22  | ✅   | ✅            | ✅ Full     |
| Prius V    | 2012–17  | ✅   | ✅            | ✅ Full     |
| Prius C    | 2012–19  | ✅   | ✅            | Partial     |
| Prius PHV  | 2012+    | ✅   | ✅            | ✅ Full     |

---

## DISCLAIMER

This software is an independent diagnostic tool and is not affiliated with
Toyota Motor Corporation. Veepeak® is a trademark of its respective owner.
Use active tests only when safe to do so. The developer is not responsible
for damage resulting from use of this software.

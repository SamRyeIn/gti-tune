---
source: "Docs/2. SimosTools - Getting Started.docx"
date: 2026-07-05
images_added: 2026-07-06
key_people: Kyle (kr250)
key_concepts: SimosTools app setup, logging modes (Mode22/Mode3E/DSG), log triggers, PID CSV import, gauge/dashboard config, flashing (full vs CAL), log viewer, utilities (DTC/adaptation/info)
---

# SimosTools — App Guide

Walkthrough of the **[[SimosTools]]** Android app, by Kyle (kr250). Assumes the prerequisites in [[tuning-getting-started]] (compatible OBD2 dongle — the [[Macchina A0]]). Beta versions via Google Play Beta Tester signup.

> **Note on screenshots:** images below are from Kyle's original guide (SimosTools v0.76). The **Get Info** captures show an example Audi/DQ250 vehicle (VIN `WAUB8GFF…`, engine `CNTC`, part `5G0906259A`) — **not** this car (`5G0906259L`, see [[index]]). Treat their values as illustrative of the *screen*, not this car's data.

## Main screen

Six buttons: **Logging, Flashing, Log Viewer, Utilities, Settings, Exit.** Connection ribbon along the top: **red = not connected**, **green = connected**, **blue = "Logging"** (actively logging). The green ribbon shows the connected dongle name (e.g. `BLE_TO_ISOTP…`).

![SimosTools main screen — Logging / Flashing / Log Viewer / Utilities / Settings / Exit buttons, red "connecting…" ribbon at top](media/simostools-app-guide/01-main-screen.png)

![Green ribbon once connected to the dongle](media/simostools-app-guide/02-connected-ribbon.png)

## Settings

The Settings screen is tabbed across the top: **GENERAL · CAR · MODE22 · MODE3E · MODEDSG**.

### Logging modes
- **Mode22** — standard diagnostic PIDs (pre-installed list ships with the app; logs out of the box).
- **Mode3E** — high-speed logging, enables additional parameters (PIDs). Requires the bin to be patched with High Speed Logging (HSL) — import an `HSL.CSV`.
- **LogDSG?** checkbox — enables DSG logging.

### Log trigger
Triggered by single or multiple variables via the **"Assign To:"** field in the PID list. Assign a letter to a PID, then set the trigger expression in the General tab. Examples:
- `d` on Pedal Pos, trigger `d>70` → logs above 70% pedal, stops below.
- `a` on boost, trigger `a>20` → logs when boost > 20.
- Cruise-control stalk `c>1` → manual trigger (one of the most common setups).

Don't assign the same letter to two PIDs. **Log lead in / Log end delay** control how quickly logging starts/stops (default 2000 ms each).

### Log output
Where logs are saved on device: **Directory** (Downloads / Documents / Application) plus a **Sub directory** (default `logs`). Ensure storage permissions are granted.

![GENERAL tab — SimosTools v0.76, Mode 22/3E + Log DSG, Log trigger d>70, lead in / end delay 2000 ms, Log output directory](media/simostools-app-guide/03-general-logging-settings.png)

### Import PID CSV
Configure live logging either via the GUI per mode or by importing a CSV. Buttons: **22 CSV / 3E CSV / DSG CSV** to import, and **Reset 22/3E/DSG CSV** to restore defaults. A CSV sets units, equation, format, max/min, warning thresholds, smoothing, and tab assignment (Default, Airflow, Fuel, etc.). Works with or without a dongle connected.

### Gauges
Layout configurable globally — **Bar horizontal, Bar vertical, Basic, or Round** — overridable per parameter via `|BAR_V` or `|Round`.

![Import PID CSV buttons (22/3E/DSG + resets) and the Gauges layout selector (Round selected)](media/simostools-app-guide/04-import-csv-gauges.png)

### Connection settings (advanced)
Older devices may need tuning to raise sample rates so logs aren't jiggy/jaggy. Newer devices (e.g. FireTab HD8plus) shouldn't need this. Fields include **Max display rate** (e.g. 15 Hz), **Max logging rate** (e.g. 100 Hz), **Q correction** (10 ms), **ECU / DSG STMIN** (350 µs), and **ECU / DSG PIDS Per Request** (8 / 6).

![Connection settings — max display/logging rate, Q correction, ECU/DSG STMIN, PIDS per request](media/simostools-app-guide/05-connection-settings.png)

### Options / Car settings
- **Options (Color options)** — every color in the app and gauges: background normal/warning, text, gauge normal/warn, gauge normal/warning background, gauge value, state error/none. Go wild.
- **Car settings (CAR tab)** — car details for speed/HP/torque calc: curb weight, tire diameter, coefficient of drag, frontal area, **Velocity Imperial?** toggle (imperial/metric), and **Gear 1–5+ ratios**.

![Color options list — set background/text/gauge colors](media/simostools-app-guide/06-color-options.png)

![CAR tab — curb weight, tire diameter, Cd, frontal area, imperial toggle, gear ratios](media/simostools-app-guide/07-car-settings.png)

### MODE22 / MODE3E / MODEDSG
Per-mode PID configuration. Each PID entry exposes: **Name, Unit, Address, Length, Gauge Min/Max, Warn Min/Max, Equation, Format, Smoothing, Assign To, Enabled** toggle, and **Tabs** (which live tab it appears on, e.g. FUEL). Up/down arrows reorder PIDs.

![MODE3E PID config — Fuel Flow at address d0013636, gauge/warn limits, equation, format, tab assignment](media/simostools-app-guide/08-pid-config.png)

## Logging (live)
Main tab → LOGGING (ribbon shows "Polling") displays gauges for all PIDs, grouped into tabs per CSV setup (e.g. **DEFAULT · AIRFLOW · FUEL · IGNITION · MISC**). An **fps** readout shows the live refresh rate; **Quick View** and **Back** at the bottom.

![Live dashboard — round gauges for Airmass, Boost, Eth Content, IAT, Ign Avg, Knock Avg across tabbed pages](media/simostools-app-guide/09-live-dashboard.png)

Each gauge shows current value (big), plus **Min (left)** and **Max (right)** since data started. Hold a gauge ~few seconds to reset it.

![Single gauge detail — big current value, min:max below, units](media/simostools-app-guide/10-gauge-detail.png)

## Log viewer
Review logs on-device without a computer — an overlaid multi-trace chart with a scrub cursor showing each PID's value at that point (e.g. Boost, Calc HP, Knock Avg, IAT, Engine Speed). **Zoom `Z[…]` and time `T[…]`** shown top corners. **Load CSV** to load a log; **Set PIDS** to pick chart data; **Set Tabs** to filter by tab groups.

![Log viewer — overlaid PID traces with cursor readouts and Set PIDS / Set Tabs / Load CSV buttons](media/simostools-app-guide/11-log-viewer.png)

## Flashing
The Flashing screen streams per-block progress (erasing → transferring → checksum, then verify → reset ECU → clear DTC) and ends with *"turn key to off for at least 5 seconds before starting vehicle."*
- **Flash Full** — first flash must be a full BIN flash (up to ~7 min). Battery on a charger. Select **unlock** on first flash.
- **Flash CAL** — subsequent changes (e.g. boost/timing tweaks) only need a CAL flash (<1 min, overwrites Block 5 only).
- **Project clarification for patched tune updates** — use a full flash to
  install, remove, or change a patch/code component. Once the ECU already has
  the same verified patch set, subsequent calibration/tune changes may use
  **Flash CAL**; CAL-only must not be used to introduce or upgrade a patch.

![Flashing screen — Block 4/5 erase/transfer/checksum complete, verify/reset/clear-DTC, with Flash CAL / Flash Full / Tune Info / Back buttons](media/simostools-app-guide/12-flashing.png)

## Tune info / Utilities
- **Tune Info** — displays loaded tune file name.
- **DTC** — read codes.
- **Adaptation** — (more info needed).
- **Get Info** — short press: ECU/engine info (VIN, ASAM/ODX ID, calibration version, VW spare part / ASW version, hardware number, engine code, block dates); long press: DSG info.

![Get Info — engine ECU: VIN, ASAM/ODX identifier, calibration version, VW spare part & ASW version, hardware number, engine code, block dates (example vehicle)](media/simostools-app-guide/13-get-info-ecu.png)

![Get Info — DSG (long press): DQ250 transmission ASAM ID, spare part, hardware number (example vehicle)](media/simostools-app-guide/14-get-info-dsg.png)

Related: [[tuning-getting-started]], [[ecu-tuning-basics]]

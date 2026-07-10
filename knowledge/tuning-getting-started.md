---
source: "Docs/1. Getting Started.docx"
date: 2026-07-05
key_people: none
key_concepts: tuning toolchain (editor/flasher/logger), stock BIN acquisition, XDF/XML definition files, BIN editors (TunerPro vs ecuEdit), flashing tools (VW_Flash vs SimosTools), Mode 22 vs high-speed RAM logging
---

# Tuning — Getting Started (Overview)

The foundational overview for VAG (Simos) ECU tuning. Tuning consists of three tools: an **editor** to modify a binary file, a **flashing tool** to write changes to the ECU, and a **data logging** solution.

## BIN background

You can't read the ECU natively (no plug-in-and-read). Stock binaries come from the "Flashdaten" flash data files on the European VAG servers. For USDM-spec cars, the common files to flash:

| Car | File |
|---|---|
| 2015–2018 GTI / A3 | `5G0906259L_0002` |
| 2015–2017 Golf R / S3 | `8V0906259K_0003` |
| 2018 Golf R / S3 | `8V0906259P_0001` |
| 2019+ GTI / GLI / A3 | `5G0906259Q_0003` |
| 2019+ Golf R / S3 | `8V0906259Q_0002` |

- 2015–2018 → [[Simos 18.1]] / 18.6 ECU, **SC8S50** file structure.
- 2019+ → [[Simos 18.10]] ECU, **SCGA05** file structure.

> For a 2017 GTI (this project's car), the relevant file is `5G0906259L_0002` on **Simos 18.1/18.6, SC8S50** structure. The repo already contains `5G0906259L__0002.bin` and matching `SC8S50` XDFs.

Convert the `.frf` into a `.bin` using [[VW_Flash]] (`File -> Extract FRF`). This produces a 4 MB full `.bin` plus 5 smaller block files: **CBOOT** (bootloader), **ASW1/2/3** (application software / OS), and **CAL** (calibration). Tuning = editing the **Calibration**. Recommendation: stick with the 4 MB full bin for everything (a full bin ≈ Eurodyne "loader" file; cal-only ≈ "maestro").

## XDF / XML definition files

A [[XDF]] (TunerPro) or XML (ecuEdit) file maps the tables/axes/values in the calibration into a human-readable format. **The definition file must match your box code / file structure** — e.g. `5G0906259L_0002` needs the **SC8S50** definition.

## BIN editor options

- **[[TunerPro]]** — free, still in development, the "standard" and most popular. Basic feature set. Uses XDF.
- **[[ecuEdit]]** — ~$110 USD, advanced editor features + built-in logging, but hardware-locked to a single device. Uses XML.

## Flashing / datalogging tools

- **[[VW_Flash]]** — original free/open-source. PC-focused GUI (also CLI / Linux SocketCAN). Supports Simos 18.1/6/10 and DQ250 MQB flashing. Dongles: Tactrix OpenPort, Macchina A0 (USB or BLE). High-speed datalogging for ECU only. DQ381 flashing in development.
- **[[SimosTools]]** — Android app. ECU + DQ250 flashing. **Macchina A0 (BLE) only** supported dongle. Standard PID + high-speed datalogging for ECU, plus DSG logging.

The **[[Macchina A0]]** is the most flexible dongle (works with both apps; ECU + DSG flash + full datalogging over Bluetooth). Open-source ESP32-based — buildable if sold out.

## Datalogging background

- **Mode 22** — built-in diagnostic functions of the ECU/TCU. Works well but limited to VW-sanctioned parameters. Sufficient for diagnostics.
- **High-speed RAM logging** — custom, faster, can log *any* measurement in the controller. Highly desirable for tune development.

## Links

- Macchina A0: https://www.macchina.cc/catalog/a0-boards/a0-under-dash
- Tactrix OpenPort: https://www.tactrix.com/
- VW_Flash: https://github.com/bri3d/VW_Flash
- SimosTools: https://play.google.com/store/apps/details?id=com.app.simostools
- TunerPro: https://www.tunerpro.net
- ecuEdit: https://www.epifansoft.com/ecuEdit.html

Related: [[simostools-app-guide]], [[ecu-tuning-basics]]

// ============================================================================
//  Station settings. Copy this file to config.h (same folder) and fill it in.
//  config.h is git-ignored, so the Wi-Fi password and API key stay off GitHub.
//  One config.h per station: only SITE_ID, Wi-Fi, calibration and baseline change.
// ============================================================================
#pragma once

// ---------------- Wi-Fi (up to 3; the strongest one in range is used) ----------------
// For a field install a phone hotspot or a 4G pocket router works fine.
const char* WIFI_SSID_1 = "YOUR_WIFI";
const char* WIFI_PASS_1 = "YOUR_PASSWORD";
const char* WIFI_SSID_2 = "";               // optional, leave "" if unused
const char* WIFI_PASS_2 = "";
const char* WIFI_SSID_3 = "";
const char* WIFI_PASS_3 = "";
// Many ESP32-C3 Super Mini boards have a weak antenna match and fail to join at full
// power. 1 = transmit at 8.5 dBm (fixes most "never connects" boards), 0 = full power.
#define WIFI_LOW_TX_POWER 1

// ---------------- Cloud ----------------
const char* API_URL = "https://nashik-water-api.onrender.com";   // no slash at the end
const char* API_KEY = "PASTE_INGEST_API_KEY_FROM_RENDER";         // Render -> Environment
const char* SITE_ID = "ramkund";   // must match a site id on the website (Admin -> Sites)

// Seconds between readings (each reading is posted straight away).
const uint32_t READ_INTERVAL_S = 10;

// ---------------- Which sensors are connected (1 = yes, 0 = no) ----------------
// With pH only, the station uses the BIS rule (6.5-8.5 = Normal, else Natural change).
// With pH + TDS + turbidity, the on-board decision tree also runs and can raise RED.
#define HAS_TDS  0
#define HAS_TURB 0
#define HAS_TEMP 0   // DS18B20

// ---------------- Pins (ESP32-C3 Super Mini / LOLIN C3 Mini) ----------------
// Analog inputs MUST be on ADC1 = GPIO0..GPIO4 (ADC2 stops working while Wi-Fi is on).
// Avoid GPIO2, GPIO8 and GPIO9 for sensors: they decide how the chip boots.
const int PIN_PH   = 3;    // pH board "Po"/"A" output, through the divider (see HARDWARE.md)
const int PIN_TDS  = 1;    // TDS board "A" output (powered from 3V3, no divider needed)
const int PIN_TURB = 0;    // turbidity board "A" output, through the divider
const int PIN_TEMP = 10;   // DS18B20 data, 4.7 kOhm pull-up to 3V3
const int PIN_STATUS_LED = 8;    // on-board blue LED of the Super Mini (lit when LOW); -1 = none
const int PIN_LED_GREEN = -1;    // optional traffic-light LEDs (220 Ohm), -1 = not fitted
const int PIN_LED_AMBER = -1;
const int PIN_LED_RED   = -1;
const int PIN_BUZZER    = -1;    // optional active buzzer, -1 = not fitted

// Voltage-divider factor in front of each analog pin (sensor volts / pin volts).
// The C3 reads at most ~2.5 V, so 5 V sensor boards go through 10k + 10k (factor 2.0).
const float DIV_PH   = 2.0;
const float DIV_TDS  = 1.0;
const float DIV_TURB = 2.0;

// ---------------- Calibration (sensor-board volts, i.e. after undoing the divider) ----------------
// Run calibration mode (type "cal" in the Serial Monitor) with the probe in each buffer.
// Defaults match the DFRobot-style board (pH = 3.5 x V): 2.00 V at pH 7, 1.15 V at pH 4.
const float PH_V7 = 2.00;     // volts in the pH 7.00 buffer
const float PH_V4 = 1.15;     // volts in the pH 4.01 buffer
const float TDS_K = 1.00;     // known TDS / measured TDS with a standard solution
const float TURB_VCLEAR = 4.20;   // volts in clear (RO / distilled) water

// ---------------- Site baseline (what "normal" looks like at THIS site) ----------------
// Used by the on-board tree. Typical values from the project's field tests:
//   ugamsthan 7.3/110/3   kushavart 7.6/280/10   gangapur_dam 7.6/165/5   someshwar 7.7/210/9
//   ramkund 7.8/343/16.8  tapovan 7.7/420/22     nandini 7.3/650/35
// After a week of real logging, replace with edge/calibrate_baseline.py's output.
const float BASE_PH   = 7.809;
const float BASE_TDS  = 342.9;
const float BASE_TURB = 16.79;

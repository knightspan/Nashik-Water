/*
  4-sensor test for the ESP32-C3 Super Mini   (no Wi-Fi, no website)

  Reads pH, TDS, turbidity and DS18B20 temperature once a second and prints, for each:
  the voltage at the pin, the sensor-board voltage, the converted value, and a warning
  if the wiring looks wrong. Use it to check each sensor BEFORE flashing the station.

  Same pins, formulas and defaults as firmware/esp32c3_station, so the numbers here are
  the numbers the website will get.

  ------------------------------------------------------------------------------------
  Wiring (sensor board -> ESP32-C3 Super Mini)

    pH board        5V  -> 5V        GND -> G     OUT -> GPIO3   (direct, DIV_PH 1.0)
    TDS board       VCC -> 3.3       GND -> G     A   -> GPIO1   (direct, 0-2.3 V)
    Turbidity board VCC -> 5V        GND -> G     A   -> 10k -> GPIO0, GPIO0 -> 10k -> G
                    (switch on the turbidity board set to "A", not "D")
    DS18B20 probe   red -> 3.3       black -> G   yellow -> GPIO10
                    + 4.7 kOhm resistor between yellow (GPIO10) and 3.3
                    (not needed if your probe came on a small board with a resistor)

  !! The turbidity board puts out up to 4.5 V in clear water. Without the two 10 kOhm
  !! resistors that is more than the 3.3 V the ESP32-C3 pin can take. Always fit them.
  ------------------------------------------------------------------------------------

  Arduino IDE: board "ESP32C3 Dev Module" (or MakerGO ESP32 C3 SuperMini),
  Tools -> USB CDC On Boot: Enabled, Serial Monitor at 115200.
  Libraries: OneWire (2.3.8 or newer), DallasTemperature.
*/
#include <OneWire.h>
#include <DallasTemperature.h>

// ---------------- pins ----------------
#define PIN_PH    3
#define PIN_TDS   1
#define PIN_TURB  0
#define PIN_TEMP  10
#define LED       8      // on-board blue LED, lit when LOW

// ---------------- dividers (sensor-board volts / pin volts) ----------------
#define DIV_PH    1.0    // 2.0 if you add 10k + 10k on the pH OUT too
#define DIV_TDS   1.0
#define DIV_TURB  2.0

// ---------------- calibration (same defaults as config.h) ----------------
#define PH_V7        2.00   // board volts in pH 7.00 buffer
#define PH_V4        1.15   // board volts in pH 4.01 buffer
#define TDS_K        1.00   // known TDS / measured TDS
#define TURB_VCLEAR  4.20   // board volts in clear water

const float PIN_MAX_V = 2.5;  // the ESP32-C3 ADC reads accurately up to about 2.5 V

OneWire oneWire(PIN_TEMP);
DallasTemperature ds(&oneWire);
int dsCount = 0;

// Median of 21 calibrated readings, in volts AT THE PIN.
float pinVolts(int pin) {
  int mv[21];
  for (int i = 0; i < 21; i++) { mv[i] = analogReadMilliVolts(pin); delay(4); }
  for (int i = 1; i < 21; i++) {                    // insertion sort
    int v = mv[i], j = i - 1;
    while (j >= 0 && mv[j] > v) { mv[j + 1] = mv[j]; j--; }
    mv[j + 1] = v;
  }
  return mv[10] / 1000.0;
}

float toPH(float v, float t) {
  float slope = (PH_V7 - PH_V4) / (7.00 - 4.01);
  slope *= (273.15 + t) / 298.15;                   // Nernst temperature correction
  return 7.0 + (v - PH_V7) / slope;
}
float toTDS(float v, float t) {
  float vc = v / (1.0 + 0.02 * (t - 25.0));         // compensate to 25 °C
  float ppm = (133.42 * vc * vc * vc - 255.86 * vc * vc + 857.39 * vc) * 0.5;
  return constrain(ppm * TDS_K, 0.0, 2000.0);
}
float toNTU(float v) {
  v = v * (4.2 / TURB_VCLEAR);
  if (v >= 4.2) return 0.0;
  if (v <= 2.56) return 3000.0;
  return constrain(-1120.4 * v * v + 5742.3 * v - 4352.9, 0.0, 3000.0);
}

// Warning text for a pin voltage, or "" if it looks fine.
const char* pinCheck(float vPin) {
  if (vPin < 0.02) return "  <- ~0 V: wire not connected, or board not powered";
  if (vPin > PIN_MAX_V) return "  <- TOO HIGH for the pin: fit the 10k + 10k divider";
  return "";
}

void setup() {
  Serial.begin(115200);
  delay(1500);                                      // let the USB serial port appear
  pinMode(LED, OUTPUT);
  analogReadResolution(12);
  analogSetAttenuation(ADC_11db);                   // 0 to ~2.5 V on the ESP32-C3
  ds.begin();
  ds.setResolution(12);
  dsCount = ds.getDeviceCount();
  Serial.println("\n4-sensor test (ESP32-C3) - pH GPIO3, TDS GPIO1, turbidity GPIO0, DS18B20 GPIO10");
  Serial.printf("DS18B20 probes found: %d%s\n", dsCount,
                dsCount ? "" : "  <- none: check wiring and the 4.7 kOhm pull-up");
}

void loop() {
  // 1. Temperature first: pH and TDS are corrected with it.
  float tempC = NAN;
  ds.requestTemperatures();                         // ~750 ms at 12-bit
  float t = ds.getTempCByIndex(0);
  if (t > -50 && t != 85.0 && t != DEVICE_DISCONNECTED_C) tempC = t;
  float tc = isnan(tempC) ? 25.0 : tempC;

  // 2. pH
  float pPh = pinVolts(PIN_PH), vPh = pPh * DIV_PH, ph = toPH(vPh, tc);

  // 3. TDS (read after pH: the TDS probe's signal can disturb a pH probe in the same water)
  delay(200);
  float pTds = pinVolts(PIN_TDS), vTds = pTds * DIV_TDS, tds = toTDS(vTds, tc);

  // 4. Turbidity
  float pTurb = pinVolts(PIN_TURB), vTurb = pTurb * DIV_TURB, ntu = toNTU(vTurb);

  Serial.println("------------------------------------------------------------");
  if (isnan(tempC)) Serial.println("Temp      : not found (pH/TDS corrected at 25 C)");
  else              Serial.printf("Temp      : %.2f C\n", tempC);
  Serial.printf("pH        : %5.2f      pin %.3f V  board %.3f V%s\n", ph, pPh, vPh, pinCheck(pPh));
  Serial.printf("TDS       : %5.0f mg/L  pin %.3f V  board %.3f V%s\n", tds, pTds, vTds, pinCheck(pTds));
  Serial.printf("Turbidity : %5.1f NTU   pin %.3f V  board %.3f V%s\n", ntu, pTurb, vTurb, pinCheck(pTurb));
  if (ph < 2.0 || ph > 12.0) Serial.println("            pH outside 2-12: probe dry, unplugged, or not calibrated");

  digitalWrite(LED, !digitalRead(LED));             // blink once per loop
  delay(250);
}

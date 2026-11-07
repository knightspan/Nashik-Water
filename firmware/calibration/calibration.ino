/*
  Calibration helper – prints raw board voltages every 2 s (Serial Monitor, 9600 baud).

  1. pH (A0):   rinse, put the probe in pH 7.00 buffer, wait 2 min, note "pH V"  -> PH_V7
                rinse, pH 4.01 buffer, wait 2 min, note "pH V"                    -> PH_V4
  2. Turbidity (A2): probe head in clear RO / distilled water, note "turb V"      -> TURB_VCLEAR
  3. TDS (A1):  in a known standard (e.g. 342 ppm), note "TDS ppm(K=1)";
                TDS_K = standard / reading
  4. Measure the UNO 5 V pin with a multimeter                                    -> VREF
  Enter the values at the top of arduino_node.ino. Repeat the pH check weekly.
*/
#include <OneWire.h>
#include <DallasTemperature.h>

const uint8_t PIN_PH = A0, PIN_TDS = A1, PIN_TURB = A2, PIN_TEMP = 2;
const float VREF = 5.0;
OneWire oneWire(PIN_TEMP);
DallasTemperature ds(&oneWire);

float readVolts(uint8_t pin) {
  long s = 0;
  for (int i = 0; i < 40; i++) { s += analogRead(pin); delay(5); }
  return (s / 40.0) * VREF / 1023.0;
}

void setup() { Serial.begin(9600); ds.begin(); Serial.println(F("CALIBRATION MODE")); }

void loop() {
  ds.requestTemperatures();
  float t = ds.getTempCByIndex(0);
  float vPh = readVolts(PIN_PH);
  delay(500);
  float vTds = readVolts(PIN_TDS), vTurb = readVolts(PIN_TURB);
  float vc = vTds / (1.0 + 0.02 * ((t > -50 ? t : 25.0) - 25.0));
  float ppm = (133.42 * vc * vc * vc - 255.86 * vc * vc + 857.39 * vc) * 0.5;
  Serial.print(F("temp C ")); Serial.print(t, 2);
  Serial.print(F(" | pH V ")); Serial.print(vPh, 3);
  Serial.print(F(" | TDS V ")); Serial.print(vTds, 3);
  Serial.print(F(" ppm(K=1) ")); Serial.print(ppm, 1);
  Serial.print(F(" | turb V ")); Serial.println(vTurb, 3);
  delay(2000);
}

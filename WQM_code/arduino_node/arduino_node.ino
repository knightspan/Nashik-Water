/*
  Smart Water Quality Monitoring – Arduino UNO sensor node
  Reads pH (A0), TDS (A1), turbidity (A2) and DS18B20 temperature (D2),
  converts them to physical units, runs the on-board decision tree every 5 min,
  drives the status LEDs and buzzer, and sends one JSON line per minute to the
  NodeMCU (ESP8266) over SoftwareSerial and to the PC over USB Serial.
  Libraries: OneWire, DallasTemperature (Arduino Library Manager)
*/
#include <OneWire.h>
#include <DallasTemperature.h>
#include <SoftwareSerial.h>
#include "WaterStateTree.h"           // exported from Python with micromlgen

// ---------------- pins ----------------
const uint8_t PIN_PH = A0, PIN_TDS = A1, PIN_TURB = A2, PIN_TEMP = 2;
const uint8_t LED_GREEN = 9, LED_YELLOW = 10, LED_RED = 11, BUZZER = 8;
SoftwareSerial esp(7, 6);              // RX = D7 (from ESP TX), TX = D6 (to ESP RX through 1k/2k divider)
OneWire oneWire(PIN_TEMP);
DallasTemperature ds(&oneWire);
Eloquent::ML::Port::WaterStateTree tree;

// ---------------- calibration (replace with your measured values) ----------------
const char* NODE_ID = "node_01";
float PH_V7 = 2.50, PH_V4 = 3.03;      // volts in pH 7.00 and pH 4.01 buffers
float TDS_K = 1.00;                     // known / measured with TDS standard
float TURB_VCLEAR = 4.20;               // sensor volts in clear (RO/distilled) water
// site baseline learned during the first week at this source (from Python)
float BASE_PH = 7.80, BASE_TDS = 330.0, BASE_TURB = 15.0   // example: Ramkund;

const unsigned long SAMPLE_MS = 60000UL;     // one reading per minute
float sumPh = 0, sumTds = 0, sumTurb = 0; uint8_t nAvg = 0;
float histPh[4], histTds[4], histTurb[4]; uint8_t nHist = 0;   // last 4 five-minute means
int state = 0;                                                  // 0 normal, 1 natural, 2 alert

float readVolts(uint8_t pin) {          // median of 15 samples removes spikes
  int v[15];
  for (int i = 0; i < 15; i++) { v[i] = analogRead(pin); delay(10); }
  for (int i = 0; i < 14; i++) for (int j = i + 1; j < 15; j++) if (v[j] < v[i]) { int t = v[i]; v[i] = v[j]; v[j] = t; }
  return v[7] * 5.0 / 1023.0;
}

float toPH(float v, float t) {
  float slope = (PH_V7 - PH_V4) / 3.0;                 // volts per pH (negative on PH-4502C)
  slope *= (273.15 + t) / 298.15;                       // Nernst temperature correction
  return 7.0 + (v - PH_V7) / slope;
}
float toTDS(float v, float t) {
  float vc = v / (1.0 + 0.02 * (t - 25.0));             // compensate to 25 °C
  float ppm = (133.42 * vc * vc * vc - 255.86 * vc * vc + 857.39 * vc) * 0.5;
  return max(ppm * TDS_K, 0.0);
}
float toNTU(float v) {
  v = v * (4.2 / TURB_VCLEAR);
  float ntu = -1120.4 * v * v + 5742.3 * v - 4352.9;
  return constrain(ntu, 0.0, 3000.0);
}

void setLEDs(int s) {
  digitalWrite(LED_GREEN, s == 0); digitalWrite(LED_YELLOW, s == 1); digitalWrite(LED_RED, s == 2);
  if (s == 2) { for (int i = 0; i < 3; i++) { digitalWrite(BUZZER, HIGH); delay(200); digitalWrite(BUZZER, LOW); delay(150); } }
}

void runTree() {                         // called every 5 minutes
  float ph = sumPh / nAvg, tds = sumTds / nAvg, turb = sumTurb / nAvg;
  sumPh = sumTds = sumTurb = 0; nAvg = 0;
  for (int i = 3; i > 0; i--) { histPh[i] = histPh[i-1]; histTds[i] = histTds[i-1]; histTurb[i] = histTurb[i-1]; }
  histPh[0] = ph; histTds[0] = tds; histTurb[0] = turb;
  if (nHist < 4) { nHist++; return; }    // need 15 min of history
  float x[6] = {
    ph - BASE_PH, tds / BASE_TDS, (turb + 0.5) / (BASE_TURB + 0.5),   // rel_ph, rel_tds, rel_turb
    tds - histTds[3], turb - histTurb[3], ph - histPh[3]               // change over 15 min
  };
  int s = tree.predict(x);
  if (s != state) { state = s; setLEDs(state); }
}

void setup() {
  Serial.begin(9600); esp.begin(9600); ds.begin();
  pinMode(LED_GREEN, OUTPUT); pinMode(LED_YELLOW, OUTPUT); pinMode(LED_RED, OUTPUT); pinMode(BUZZER, OUTPUT);
  setLEDs(0);
  Serial.println(F("WQ_NODE_READY"));
}

unsigned long last = 0; uint8_t minutes = 0;
void loop() {
  if (millis() - last < SAMPLE_MS && last != 0) return;
  last = millis();
  ds.requestTemperatures();
  float t = ds.getTempCByIndex(0);
  bool tOk = (t > -50 && t != 85.0);
  if (!tOk) t = 25.0;
  float vPh = readVolts(PIN_PH);
  delay(1000);                            // keep the TDS excitation away from the pH reading
  float vTds = readVolts(PIN_TDS), vTurb = readVolts(PIN_TURB);
  float ph = toPH(vPh, t), tds = toTDS(vTds, t), ntu = toNTU(vTurb);
  sumPh += ph; sumTds += tds; sumTurb += ntu; nAvg++;
  if (++minutes >= 5) { minutes = 0; runTree(); }

  char line[200], a[8], b[8], c[8], d[8];
  dtostrf(ph, 4, 2, a); dtostrf(tds, 4, 1, b); dtostrf(ntu, 4, 1, c); dtostrf(t, 4, 2, d);
  snprintf(line, sizeof(line),
    "{\"node\":\"%s\",\"ph\":%s,\"tds\":%s,\"turb\":%s,\"temp\":%s,\"temp_ok\":%d,\"edge_state\":%d}",
    NODE_ID, a, b, c, d, tOk, state);
  Serial.println(line);                   // Serial Monitor / CSV logging
  esp.println(line);                      // to NodeMCU -> cloud
}

/*
  Smart Water Quality Monitoring – NodeMCU ESP8266 Wi-Fi gateway   (firmware v2)

  Receives the UNO's JSON lines on the hardware RX pin (9600 baud), publishes every
  reading to the Raspberry Pi's MQTT broker (topic wqi/<node>/reading, retained = no)
  and sends one update every 20 s to ThingSpeak (fields 1-4 pH/TDS/NTU/°C, 5 WQI,
  8 edge state). Reconnects to Wi-Fi and MQTT without blocking the serial input.

  Wiring: UNO D6 (TX) -> 1 kΩ -> ESP RX, with 2 kΩ from ESP RX to GND (5 V -> 3.3 V);
          UNO D7 (RX) <- ESP TX; common GND. Debug output on GPIO2 (Serial1, 115200).
  Libraries: ESP8266 board package, PubSubClient, ArduinoJson (v7).
  Note: disconnect the UNO from ESP RX while uploading to the NodeMCU over USB.
*/
#include <ESP8266WiFi.h>
#include <ESP8266HTTPClient.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>

// ---------------- configure ----------------
const char* WIFI_SSID = "YOUR_WIFI";
const char* WIFI_PASS = "YOUR_PASSWORD";
const char* MQTT_HOST = "192.168.1.50";            // Raspberry Pi 5 address (give it a fixed IP)
const uint16_t MQTT_PORT = 1883;
const char* TS_KEY    = "YOUR_THINGSPEAK_WRITE_KEY";
const unsigned long TS_INTERVAL_MS = 20000UL;      // ThingSpeak free tier: >= 15 s

WiFiClient net; PubSubClient mqtt(net);
unsigned long lastTs = 0, lastMqttTry = 0;
String buf;

float wqi(float ph, float tds, float turb) {        // same formula as the Pi and the website
  const float wPh = 0.3680, wTds = 0.0063, wTurb = 0.6258;
  float qPh = ph >= 7.0 ? 100.0 * (ph - 7.0) / 1.5 : 100.0 * (7.0 - ph) / 0.5;
  return wPh * qPh + wTds * 100.0 * tds / 500.0 + wTurb * 100.0 * turb / 5.0;
}

void ensureMqtt() {
  if (mqtt.connected() || WiFi.status() != WL_CONNECTED) return;
  if (millis() - lastMqttTry < 5000) return;        // retry every 5 s without blocking
  lastMqttTry = millis();
  String id = "wqm-esp-" + String(ESP.getChipId(), HEX);
  if (mqtt.connect(id.c_str())) Serial1.println("MQTT connected");
  else Serial1.printf("MQTT failed rc=%d\n", mqtt.state());
}

void sendThingSpeak(JsonDocument& d) {
  if (WiFi.status() != WL_CONNECTED) return;
  WiFiClient c; HTTPClient http;
  float ph = d["ph"], tds = d["tds"], turb = d["turb"], temp = d["temp"];
  String url = String("http://api.thingspeak.com/update?api_key=") + TS_KEY +
               "&field1=" + String(ph, 2) + "&field2=" + String(tds, 1) +
               "&field3=" + String(turb, 1) + "&field4=" + String(temp, 2) +
               "&field5=" + String(wqi(ph, tds, turb), 1) +
               "&field8=" + String((int)d["edge_state"]);
  http.setTimeout(5000);
  http.begin(c, url); int code = http.GET(); http.end();
  Serial1.printf("ThingSpeak HTTP %d\n", code);
}

void setup() {
  Serial.begin(9600);
  Serial1.begin(115200);
  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setBufferSize(512);
  buf.reserve(256);
}

void loop() {
  ensureMqtt();
  mqtt.loop();
  while (Serial.available()) {
    char ch = Serial.read();
    if (ch == '\n') {
      JsonDocument d;
      if (buf.startsWith("{") && !deserializeJson(d, buf)) {
        String topic = String("wqi/") + (const char*)(d["node"] | "node_01") + "/reading";
        bool ok = mqtt.connected() && mqtt.publish(topic.c_str(), buf.c_str());
        Serial1.printf("%s %s\n", ok ? "MQTT" : "MQTT-DROP", buf.c_str());
        if (millis() - lastTs > TS_INTERVAL_MS) { sendThingSpeak(d); lastTs = millis(); }
      }
      buf = "";
    } else if (ch != '\r' && buf.length() < 250) buf += ch;
  }
}

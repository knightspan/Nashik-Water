/*
  Smart Water Quality Monitoring – NodeMCU ESP8266 Wi-Fi gateway
  Receives JSON lines from the Arduino UNO (Serial, 9600 baud, D7/D6 on the UNO side),
  publishes every reading to the MQTT broker on the Raspberry Pi 5 and sends one
  update every 20 s to the ThingSpeak channel (free-tier limit is 15 s).
  Libraries: ESP8266 board package, PubSubClient, ArduinoJson
*/
#include <ESP8266WiFi.h>
#include <ESP8266HTTPClient.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>

const char* WIFI_SSID = "YOUR_WIFI";
const char* WIFI_PASS = "YOUR_PASSWORD";
const char* MQTT_HOST = "192.168.1.50";        // Raspberry Pi 5 address
const char* TS_KEY    = "YOUR_THINGSPEAK_WRITE_KEY";

WiFiClient net; PubSubClient mqtt(net);
unsigned long lastTs = 0;
String buf;

void connectWiFi() {
  WiFi.mode(WIFI_STA); WiFi.begin(WIFI_SSID, WIFI_PASS);
  while (WiFi.status() != WL_CONNECTED) { delay(500); }
}
void connectMqtt() {
  while (!mqtt.connected()) { mqtt.connect("wqm-esp8266"); if (!mqtt.connected()) delay(2000); }
}

void sendThingSpeak(JsonDocument& d) {
  WiFiClient c; HTTPClient http;
  String url = String("http://api.thingspeak.com/update?api_key=") + TS_KEY +
               "&field1=" + String((float)d["ph"], 2) + "&field2=" + String((float)d["tds"], 1) +
               "&field3=" + String((float)d["turb"], 1) + "&field4=" + String((float)d["temp"], 2) +
               "&field8=" + String((int)d["edge_state"]);
  http.begin(c, url); int code = http.GET(); http.end();
  Serial1.printf("ThingSpeak HTTP %d\n", code);
}

void setup() {
  Serial.begin(9600);               // RX pin receives the UNO's JSON lines
  Serial1.begin(115200);            // debug output on GPIO2 (TX only)
  connectWiFi();
  mqtt.setServer(MQTT_HOST, 1883);
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) connectWiFi();
  connectMqtt(); mqtt.loop();
  while (Serial.available()) {
    char ch = Serial.read();
    if (ch == '\n') {
      JsonDocument d;
      if (!deserializeJson(d, buf)) {
        String topic = String("wqi/") + (const char*)d["node"] + "/reading";
        mqtt.publish(topic.c_str(), buf.c_str());
        if (millis() - lastTs > 20000) { sendThingSpeak(d); lastTs = millis(); }
      }
      buf = "";
    } else if (ch != '\r') buf += ch;
  }
}

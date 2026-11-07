/*
  pH meter test for the ESP32-C3 Super Mini
  (DFRobot SEN0161 "analog pH meter" sample code, ported from the Arduino UNO version)

  Same formula and output as the UNO sketch:  pH = 3.5 x Voltage + Offset
  and the same "Voltage:2.06    pH value: 7.22" lines, so serial_bridge.py still works.

  What changed for the ESP32-C3:
    * 12-bit ADC (0-4095) instead of 10-bit, and 3.3 V logic instead of 5 V.
      analogReadMilliVolts() uses the chip's factory calibration, so no 5.0/1024 maths.
    * The pH board runs on 5 V and its output can go above what the C3 may read
      (~2.5 V usable, 3.3 V absolute max). It goes through a 10k + 10k divider, and
      DIVIDER = 2.0 multiplies the voltage back. Without resistors set DIVIDER 1.0, but
      then pH above ~8.7 reads wrong and above ~11 can damage the pin.
    * Pin GPIO3 instead of A0 (ADC1 pin: still works while Wi-Fi is on).
    * On-board LED is GPIO8 and lights when LOW.

  Wiring (pH board -> ESP32-C3 Super Mini)
    V+ / VCC  -> 5V
    GND / -   -> GND
    Po / A    -> 10 kOhm -> GPIO3,  and GPIO3 -> 10 kOhm -> GND

  Arduino IDE: board "ESP32C3 Dev Module", Tools -> USB CDC On Boot: Enabled,
  Serial Monitor at 115200.
*/
#define SensorPin 3            // GPIO3 (ADC1)
#define Offset 0.00            // deviation compensate (pH in a pH 7.00 buffer: Offset = 7.00 - reading)
#define DIVIDER 2.0            // 10k + 10k divider; 1.0 if the output is wired straight to the pin
#define LED 8                  // on-board blue LED, lit when LOW
#define samplingInterval 20
#define printInterval 800
#define ArrayLenth 40          // times of collection
int pHArray[ArrayLenth];       // store the sensor readings in millivolts (at the pin)
int pHArrayIndex = 0;

double avergearray(int* arr, int number);

void setup(void)
{
  pinMode(LED, OUTPUT);
  Serial.begin(115200);
  delay(1500);                         // give the USB serial port time to appear
  analogReadResolution(12);
  analogSetAttenuation(ADC_11db);      // 0 to ~2.5 V on the ESP32-C3
  for (int i = 0; i < ArrayLenth; i++) pHArray[i] = analogReadMilliVolts(SensorPin);
  Serial.println("pH meter experiment! (ESP32-C3)");
}

void loop(void)
{
  static unsigned long samplingTime = millis();
  static unsigned long printTime = millis();
  static float pHValue, voltage;
  if (millis() - samplingTime > samplingInterval)
  {
    pHArray[pHArrayIndex++] = analogReadMilliVolts(SensorPin);
    if (pHArrayIndex == ArrayLenth) pHArrayIndex = 0;
    voltage = avergearray(pHArray, ArrayLenth) / 1000.0 * DIVIDER;   // board output volts
    pHValue = 3.5 * voltage + Offset;
    samplingTime = millis();
  }
  if (millis() - printTime > printInterval)   // every 800 ms print the value and toggle the LED
  {
    Serial.print("Voltage:");
    Serial.print(voltage, 2);
    Serial.print("    pH value: ");
    Serial.println(pHValue, 2);
    digitalWrite(LED, digitalRead(LED) ^ 1);
    printTime = millis();
  }
}

// Average without the highest and lowest reading (same as the DFRobot sample).
double avergearray(int* arr, int number)
{
  int i;
  int max, min;
  double avg;
  long amount = 0;
  if (number <= 0) {
    Serial.println("Error number for the array to avraging!");
    return 0;
  }
  if (number < 5) {   // less than 5, calculated directly statistics
    for (i = 0; i < number; i++) amount += arr[i];
    avg = (double)amount / number;
    return avg;
  }
  if (arr[0] < arr[1]) { min = arr[0]; max = arr[1]; }
  else { min = arr[1]; max = arr[0]; }
  for (i = 2; i < number; i++) {
    if (arr[i] < min) {
      amount += min;        // arr < min
      min = arr[i];
    } else if (arr[i] > max) {
      amount += max;        // arr > max
      max = arr[i];
    } else {
      amount += arr[i];     // min <= arr <= max
    }
  }
  avg = (double)amount / (number - 2);
  return avg;
}

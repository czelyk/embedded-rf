// ESP32 DevKit (classic ESP32): buttons connect GPIO to GND. No radio APIs.
#include <Arduino.h>

constexpr uint8_t TEST_BUTTON_PIN = 25;
constexpr uint8_t STATUS_BUTTON_PIN = 26;
constexpr unsigned long DEBOUNCE_MS = 40;
bool testMode = false;

struct Button {
  uint8_t pin;
  bool previous = HIGH;
  bool stable = HIGH;
  unsigned long changedAt = 0;
  bool pressed(unsigned long now) {
    bool value = digitalRead(pin);
    if (value != previous) { previous = value; changedAt = now; }
    if (value != stable && now - changedAt >= DEBOUNCE_MS) {
      stable = value;
      return stable == LOW;
    }
    return false;
  }
};
Button testButton{TEST_BUTTON_PIN};
Button statusButton{STATUS_BUTTON_PIN};

void sendState() { Serial.println(testMode ? "STATE ON" : "STATE OFF"); }
void sendStatus() { sendState(); Serial.println("STATUS"); }

void setup() {
  pinMode(TEST_BUTTON_PIN, INPUT_PULLUP);
  pinMode(STATUS_BUTTON_PIN, INPUT_PULLUP);
  Serial.begin(115200);
  sendStatus();
}

void loop() {
  unsigned long now = millis();
  if (testButton.pressed(now)) {
    testMode = !testMode;
    Serial.println(testMode ? "TEST ON" : "TEST OFF");
    sendStatus();
  }
  if (statusButton.pressed(now)) sendStatus();

  // Fixed-size input buffer; reject an entire oversized line.
  static char line[32];
  static size_t used = 0;
  static bool overflow = false;
  // Bound work per loop so noisy input cannot starve button polling.
  for (int count = 0; count < 64 && Serial.available(); ++count) {
    char c = Serial.read();
    if (c == '\n') {
      line[used] = '\0';
      if (!overflow && strcmp(line, "STATUS") == 0) sendStatus();
      used = 0;
      overflow = false;
    } else if (c != '\r' && !overflow) {
      if (used < sizeof(line) - 1) line[used++] = c;
      else overflow = true;
    }
  }
}

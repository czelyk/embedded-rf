#include <Arduino.h>

constexpr unsigned long BAUD_RATE = 115200;
bool testMode = false;

void reportMode()
{
    Serial.print("MODE:");
    Serial.println(testMode ? "TEST" : "NORMAL");
}


void handleCommand(String command)
{
    command.trim();
    command.toUpperCase();

    if (command == "ON") {
        testMode = true;
        Serial.println("OK:TEST_MODE_ENABLED");
        reportMode();
    }
    else if (command == "OFF") {
        testMode = false;
        Serial.println("OK:TEST_MODE_DISABLED");
        reportMode();
    }
    else if (command == "STATUS") {
        reportMode();
    }
    else if (command.length() > 0) {
        Serial.println("ERR:UNKNOWN_COMMAND");
    }
}

void setup()
{
    Serial.begin(BAUD_RATE);
    Serial.setTimeout(50);

    delay(250);

    Serial.println("ESP32_SIM_CONTROLLER:READY");
    reportMode();
}

void loop()
{
    if (Serial.available() > 0) {
        handleCommand(Serial.readStringUntil('\n'));
    }
}

#include <Arduino.h>
#include <WiFi.h>
#include <WiFiUdp.h>

#if __has_include("wifi_config.h")
#include "wifi_config.h"
#else
#include "wifi_config.example.h"
#endif

constexpr unsigned long BAUD_RATE = 115200;
constexpr size_t MAX_LINE_LENGTH = 96;
constexpr unsigned long WIFI_RETRY_MS = 10000;
constexpr unsigned long TELEMETRY_INTERVAL_MS = 5000;
bool testMode = false;
WiFiServer tcpServer(TCP_CONTROL_PORT);
WiFiClient tcpClient;
WiFiUDP telemetryUdp;
bool tcpServerStarted = false;
unsigned long lastWifiAttempt = 0;
unsigned long lastTelemetry = 0;
unsigned long telemetrySequence = 0;

struct LineBuffer {
    char data[MAX_LINE_LENGTH];
    size_t used = 0;
    bool overflow = false;
};
LineBuffer serialLine;
LineBuffer tcpLine;

bool wifiConfigured()
{
    return WIFI_SSID[0] != '\0';
}

void reportMode(Print &output) { output.println(testMode ? "MODE:TEST" : "MODE:NORMAL"); }
void reportMode() { reportMode(Serial); }

void handleCommand(const char *command, Print &output)
{
    if (strcmp(command, "ON") == 0) {
        testMode = true;
        output.println("OK:TEST_MODE_ENABLED");
        reportMode(output);
    }
    else if (strcmp(command, "OFF") == 0) {
        testMode = false;
        output.println("OK:TEST_MODE_DISABLED");
        reportMode(output);
    }
    else if (strcmp(command, "STATUS") == 0) {
        reportMode(output);
    }
    else {
        output.println("ERR:UNKNOWN_COMMAND");
    }
}

void consumeByte(char value, LineBuffer &line, Print &output)
{
    if (value == '\n') {
        if (!line.overflow && line.used > 0) {
            line.data[line.used] = '\0';
            handleCommand(line.data, output);
        } else if (line.overflow) {
            output.println("ERR:LINE_TOO_LONG");
        }
        line.used = 0;
        line.overflow = false;
    } else if (value != '\r' && !line.overflow) {
        if (line.used < MAX_LINE_LENGTH - 1) line.data[line.used++] = value;
        else line.overflow = true;
    }
}

void maintainWifi(unsigned long now)
{
    if (!wifiConfigured()) return;
    if (WiFi.status() == WL_CONNECTED) {
        if (!tcpServerStarted) {
            tcpServer.begin();
            tcpServerStarted = true;
            Serial.print("WIFI:CONNECTED IP:");
            Serial.println(WiFi.localIP());
        }
        return;
    }
    tcpServerStarted = false;
    if (now - lastWifiAttempt >= WIFI_RETRY_MS || lastWifiAttempt == 0) {
        lastWifiAttempt = now;
        Serial.println("WIFI:CONNECTING");
        WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    }
}

void maintainTcp()
{
    if (!tcpServerStarted) return;
    if (!tcpClient || !tcpClient.connected()) {
        if (tcpClient) tcpClient.stop();
        WiFiClient candidate = tcpServer.available();
        if (candidate) {
            tcpClient = candidate;
            tcpLine = LineBuffer{};
            Serial.println("TCP:CLIENT_CONNECTED");
        }
    }
    if (!tcpClient || !tcpClient.connected()) return;
    for (int count = 0; count < 64 && tcpClient.available(); ++count) {
        consumeByte(static_cast<char>(tcpClient.read()), tcpLine, tcpClient);
    }
}

void sendTelemetry(unsigned long now)
{
    if (!tcpServerStarted || TELEMETRY_HOST[0] == '\0' || now - lastTelemetry < TELEMETRY_INTERVAL_MS) return;
    lastTelemetry = now;
    char message[128];
    snprintf(message, sizeof(message), "device=esp32-c3;mode=%s;uptime_ms=%lu;sequence=%lu",
             testMode ? "TEST" : "NORMAL", now, ++telemetrySequence);
    if (telemetryUdp.beginPacket(TELEMETRY_HOST, TELEMETRY_PORT)) {
        telemetryUdp.print(message);
        telemetryUdp.endPacket();
    }
}

void setup()
{
    Serial.begin(BAUD_RATE);
    Serial.setTimeout(50);

    delay(250);

    Serial.println("ESP32_SIM_CONTROLLER:READY");
    reportMode();
    if (!wifiConfigured()) Serial.println("WIFI:CONFIG_REQUIRED");
}

void loop()
{
    for (int count = 0; count < 64 && Serial.available(); ++count)
        consumeByte(static_cast<char>(Serial.read()), serialLine, Serial);
    unsigned long now = millis();
    maintainWifi(now);
    maintainTcp();
    sendTelemetry(now);
}

#include <Arduino.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <ESP32Servo.h>
#include <ESPmDNS.h>
#include <WiFiUdp.h>
#include <ArduinoOTA.h>
#include "time.h"

// --- CONFIGURATION ---
const char *ssid = "Snakebot";
const char *password = "12345678";
const char *mqtt_server = "10.74.194.146"; // Your Hotspot IP

const char *THIS_ESP_ID = "ESP_07"; // 10.74.194.25

const int SERVO_PIN_1 = 32;
const int SERVO_PIN_2 = 33;

// --- Servo Configuration ---
Servo servoH; // Horizontal servo
Servo servoV; // Vertical servo

// Standard servo pulse widths (microseconds)
int minUs = 500;  // Corresponds to 0 degrees
int maxUs = 2500; // Corresponds to 180 degrees

// --- MULTITASKING & QUEUE CONFIG ---
#define MAX_QUEUE_SIZE 200

struct ServoCommand
{
  unsigned long long timestamp;
  int angle1;
  int angle2;
  bool isValid;
};

ServoCommand commandQueue[MAX_QUEUE_SIZE];
volatile int queueHead = 0;
volatile int queueTail = 0;
volatile int queueCount = 0;
portMUX_TYPE queueMux = portMUX_INITIALIZER_UNLOCKED;

TaskHandle_t MqttTaskHandle;
TaskHandle_t ServoOtaTaskHandle;

// Flags for cross-task communication
volatile bool isOTAUpdating = false;

WiFiClient espClient;
PubSubClient client(espClient);
Servo servo1;
Servo servo2;

const char *ntpServer = "pool.ntp.org";
const long gmtOffset_sec = 0;
const int daylightOffset_sec = 0;

// ================================================================
//  HELPER FUNCTIONS
// ================================================================

unsigned long long getCurrentMillis()
{
  struct timeval tv;
  gettimeofday(&tv, NULL);
  return (unsigned long long)(tv.tv_sec) * 1000 + (unsigned long long)(tv.tv_usec) / 1000;
}

// ================================================================
//  TASK 1: MQTT & WIFI (CORE 1)
// ================================================================

void mqttCallback(char *topic, byte *payload, unsigned int length)
{
  StaticJsonDocument<512> doc;
  DeserializationError error = deserializeJson(doc, payload, length);

  if (error)
  {
    Serial.print("JSON Error: ");
    Serial.println(error.f_str());
    return;
  }

  if (doc["data"].containsKey(THIS_ESP_ID))
  {
    unsigned long long ts = doc["ts"];
    int a1 = doc["data"][THIS_ESP_ID][0];
    int a2 = doc["data"][THIS_ESP_ID][1];

    // ✅ FIX 1: Call getCurrentMillis() here instead of using the local
    //           variable 'currentMs' which only exists in servoAndOtaTask
    unsigned long long currentMs = getCurrentMillis();

    portENTER_CRITICAL(&queueMux);

    // Discard commands that are too old (more than 500ms late)
    while (queueHead != queueTail &&
           commandQueue[queueHead].timestamp < currentMs - 500)
    {
      Serial.printf("[WARN] Discarding stale command (ts=%llu)\n",
                    commandQueue[queueHead].timestamp);
      queueHead = (queueHead + 1) % MAX_QUEUE_SIZE;
      queueCount--;
    }

    int nextTail = (queueTail + 1) % MAX_QUEUE_SIZE;
    if (nextTail != queueHead)
    {
      commandQueue[queueTail].timestamp = ts;
      commandQueue[queueTail].angle1 = a1;
      commandQueue[queueTail].angle2 = a2;
      commandQueue[queueTail].isValid = true;
      queueTail = nextTail;
      queueCount++;
    }

    portEXIT_CRITICAL(&queueMux);

    // Log lead time
    unsigned long long arrivalTs = getCurrentMillis();
    long leadTime = (long)(ts - arrivalTs);
    Serial.print("[MQTT] Packet Arrived. ");
    Serial.printf("Target: %llu | Arrival: %llu | Lead Time: %ld ms\n", ts / 1000, arrivalTs / 1000, leadTime / 1000);
  }
}

void reconnectMQTT()
{
  while (!client.connected())
  {
    Serial.print("Connecting to MQTT (Core 1)...");
    String clientId = "ESP32-" + String(THIS_ESP_ID) + "-";
    clientId += String(random(0xffff), HEX);

    if (client.connect(clientId.c_str()))
    {
      Serial.println("Connected");
      client.subscribe("servos/sync_command");
    }
    else
    {
      Serial.print("failed, rc=");
      Serial.print(client.state());
      delay(2000);
    }
  }
}

void mqttTask(void *parameter)
{
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED)
  {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi Connected (Core 1).");

  Serial.print("My IP Address is: ");
  Serial.println(WiFi.localIP());

  configTime(gmtOffset_sec, daylightOffset_sec, ntpServer);
  struct tm timeinfo;
  Serial.print("Syncing Time");
  while (!getLocalTime(&timeinfo))
  {
    Serial.print(".");
    delay(100);
  }
  Serial.println("\nTime Synced!");

  client.setServer(mqtt_server, 1883);
  client.setCallback(mqttCallback);

  for (;;)
  {
    if (!client.connected())
    {
      reconnectMQTT();
    }
    client.loop();
    delay(10);
  }
}

// ================================================================
//  TASK 2: SERVOS & OTA (CORE 0)
// ================================================================

void setupOTA()
{
  String hostname = "Snakebot-" + String(THIS_ESP_ID);
  ArduinoOTA.setHostname(hostname.c_str());

  ArduinoOTA.onStart([]()
                     {
    String type;
    if (ArduinoOTA.getCommand() == U_FLASH) type = "sketch";
    else type = "filesystem";
    Serial.println("Start updating " + type);
    isOTAUpdating = true;
    servo1.detach();
    servo2.detach(); });

  ArduinoOTA.onEnd([]()
                   {
    Serial.println("\nEnd");
    isOTAUpdating = false; });

  ArduinoOTA.onProgress([](unsigned int progress, unsigned int total)
                        { Serial.printf("Progress: %u%%\r", (progress / (total / 100))); });

  ArduinoOTA.onError([](ota_error_t error)
                     {
    Serial.printf("Error[%u]: ", error);
    isOTAUpdating = false;
    servo1.attach(SERVO_PIN_1);
    servo2.attach(SERVO_PIN_2); });

  ArduinoOTA.begin();
  Serial.println("OTA Ready (Core 0)");
}

void servoAndOtaTask(void *parameter)
{
  Serial.println("Core 0 waiting for WiFi...");
  while (WiFi.status() != WL_CONNECTED)
  {
    delay(100);
  }

  setupOTA();

  servo1.attach(SERVO_PIN_1, minUs, maxUs);
  servo2.attach(SERVO_PIN_2, minUs, maxUs);

  Serial.println("Servos Attached. Moving to Home (90).");
  servo1.write(90);
  servo2.write(90);

  for (;;)
  {
    ArduinoOTA.handle();

    if (!isOTAUpdating)
    {
      unsigned long long currentMs = getCurrentMillis();
      bool shouldExecute = false;
      ServoCommand cmd;

      portENTER_CRITICAL(&queueMux);
      if (queueHead != queueTail)
      {
        if (commandQueue[queueHead].timestamp <= currentMs)
        {

          cmd = commandQueue[queueHead];
          shouldExecute = true;
          queueHead = (queueHead + 1) % MAX_QUEUE_SIZE;
          queueCount--;
        }
      }
      portEXIT_CRITICAL(&queueMux); // ✅ FIX 2: Moved outside the if(queueHead != queueTail)
                                    //           block so critical section always exits

      if (shouldExecute)
      {
        Serial.printf("Executing Command: Angle1=%d, Angle2=%d at %llu ms\n", cmd.angle1, cmd.angle2, currentMs);
        servo1.write(cmd.angle1);
        servo2.write(cmd.angle2);
      }
    }

    delay(1);
  }
} // ✅ FIX 3: Closed servoAndOtaTask here — setup() and loop() were
  //           previously nested inside this function

// ================================================================
//  MAIN SETUP & LOOP
// ================================================================

void setup()
{
  Serial.begin(115200);

  // Core 1: MQTT & WiFi (The "Brain")
  xTaskCreatePinnedToCore(mqttTask, "MqttTask", 10000, NULL, 1, &MqttTaskHandle, 1);

  // Core 0: Servos & OTA (The "Muscle")
  xTaskCreatePinnedToCore(servoAndOtaTask, "ServoOtaTask", 10000, NULL, 1, &ServoOtaTaskHandle, 0);
}

void loop()
{
  vTaskDelete(NULL);
}

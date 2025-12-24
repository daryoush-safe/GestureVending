#include "WifiCam.hpp"
#include <WiFi.h>
#include <HTTPClient.h>

static const char* WIFI_SSID = "Kalle mahi khor";
static const char* WIFI_PASS = "pjtr8569";

/* 🔴 CHANGE THIS */
static const char* SERVER_IP = "10.143.138.111";
static const int   SERVER_PORT = 5000;

esp32cam::Resolution initialResolution;

void setup() {
  Serial.begin(115200);
  Serial.println();

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);

  Serial.print("Connecting WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi connected");
  Serial.println(WiFi.localIP());

  using namespace esp32cam;

  initialResolution = Resolution::find(640, 480);

  Config cfg;
  cfg.setPins(pins::AiThinker);
  cfg.setResolution(initialResolution);
  cfg.setJpeg(80);

  if (!Camera.begin(cfg)) {
    Serial.println("Camera init failed");
    ESP.restart();
  }

  Serial.println("Camera ready");
}

void loop() {
  using namespace esp32cam;

  auto frame = Camera.capture();
  if (!frame) {
    Serial.println("Capture failed");
    delay(100);
    return;
  }

  HTTPClient http;
  String url = String("http://") + SERVER_IP + ":" + SERVER_PORT + "/video_feed";

  http.begin(url);
  http.addHeader("Content-Type", "image/jpeg");

  int httpCode = http.POST(frame->data(), frame->size());

  if (httpCode > 0) {
    Serial.printf("Sent frame, HTTP %d\n", httpCode);
  } else {
    Serial.printf("POST failed: %s\n", http.errorToString(httpCode).c_str());
  }

  http.end();

  delay(33); // ~30 FPS
}

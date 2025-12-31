#include "esp_camera.h"
#include <WiFi.h>
#include <WiFiUdp.h>
#include <WiFiManager.h>

#define FLASH_GPIO_NUM 4
#define CAMERA_MODEL_AI_THINKER
#include "camera_pins.h"

// =======================
// SETTINGS
// =======================
// const char* wifiSsid = "Alos";
// const char* wifiPassword = "alos12345";
const char* serverIp = "10.217.4.111"; // YOUR LAPTOP IP
const int serverPort = 5000;

WiFiUDP udp;

// Packet size (keep under 1460 for standard MTU)
#define MAX_UDP_SIZE 1000 

void setup() {
  Serial.begin(115200);

  WiFiManager wm;
  bool res;
  res = wm.autoConnect("AutoConnectAP","password");
  if(!res) {
      Serial.println("Failed to connect");
      // ESP.restart();
  } 
  else {
      //if you get here you have connected to the WiFi    
      Serial.println("connected...yeey :)");
  }
  
  // Flash setup
  pinMode(FLASH_GPIO_NUM, OUTPUT);
  digitalWrite(FLASH_GPIO_NUM, HIGH);

  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;
  config.pin_sscb_sda = SIOD_GPIO_NUM;
  config.pin_sscb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;

  // Use QVGA for high FPS over UDP
  config.frame_size = FRAMESIZE_VGA; 
  config.jpeg_quality = 12; // 10-15 is good balance
  config.fb_count = 2;

  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("Camera init failed 0x%x", err);
    return;
  }

  // Camera Sensor Adjustments
  sensor_t * s = esp_camera_sensor_get();
  if (s->id.PID == OV3660_PID) {
    s->set_vflip(s, 1);
    s->set_brightness(s, 1);
    s->set_saturation(s, -2);
  }

  // WiFi Connection
  // WiFi.begin(wifiSsid, wifiPassword);
  // while (WiFi.status() != WL_CONNECTED) {
  //   delay(500);
  //   Serial.print(".");
  // }
  // Serial.println("\nWiFi connected");
  
  // Start UDP
  udp.begin(serverPort);
}

void sendFrameUDP() {
  camera_fb_t * fb = esp_camera_fb_get();
  if (!fb) return;

  // Split frame into chunks
  // We loop through the frame buffer 'MAX_UDP_SIZE' bytes at a time
  for (size_t i = 0; i < fb->len; i += MAX_UDP_SIZE) {
    size_t chunkSize = ((fb->len - i) < MAX_UDP_SIZE) ? (fb->len - i) : MAX_UDP_SIZE;
    
    udp.beginPacket(serverIp, serverPort);
    udp.write(fb->buf + i, chunkSize);
    udp.endPacket();
    
    // Tiny delay to prevent flooding router buffers
    // If image tears/glitches, increase this to delayMicroseconds(500)
    delayMicroseconds(100); 
  }

  esp_camera_fb_return(fb);
}

void loop() {
  sendFrameUDP();
  // No delay here = Max FPS
}
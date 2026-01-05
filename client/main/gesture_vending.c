#include <stdio.h>
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/event_groups.h" // [1] Include Event Groups
#include "esp_system.h"
#include "esp_wifi.h"
#include "esp_event.h"
#include "esp_log.h"
#include "nvs_flash.h"
#include "lwip/err.h"
#include "lwip/sockets.h"
#include "lwip/sys.h"
#include "esp_camera.h"
#include "esp_rom_sys.h" // For delays if needed

// =======================
// CONFIGURATION
// =======================
#define WIFI_SSID      "Alos"
#define WIFI_PASS      "alos12345"
#define SERVER_IP      "10.217.4.111"
#define SERVER_PORT    5000
#define MAX_UDP_SIZE   1000

// =======================
// PIN DEFINITIONS (AI THINKER)
// =======================
#define CAM_PIN_PWDN 32
#define CAM_PIN_RESET -1
#define CAM_PIN_XCLK 0
#define CAM_PIN_SIOD 26
#define CAM_PIN_SIOC 27
#define CAM_PIN_D7 35
#define CAM_PIN_D6 34
#define CAM_PIN_D5 39
#define CAM_PIN_D4 36
#define CAM_PIN_D3 21
#define CAM_PIN_D2 19
#define CAM_PIN_D1 18
#define CAM_PIN_D0 5
#define CAM_PIN_VSYNC 25
#define CAM_PIN_HREF 23
#define CAM_PIN_PCLK 22

#define FLASH_GPIO_NUM 4

static const char *TAG = "CAMERA_UDP";

// [2] Event Group Handles
static EventGroupHandle_t s_wifi_event_group;
#define WIFI_CONNECTED_BIT BIT0

// =======================
// WIFI HANDLER
// =======================
static void wifi_event_handler(void* arg, esp_event_base_t event_base,
                               int32_t event_id, void* event_data)
{
    if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_START) {
        esp_wifi_connect();
    } else if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_DISCONNECTED) {
        ESP_LOGI(TAG, "Disconnected. Retrying...");
        esp_wifi_connect();
        // Clear the bit so main loop knows we lost connection
        xEventGroupClearBits(s_wifi_event_group, WIFI_CONNECTED_BIT); 
    } else if (event_base == IP_EVENT && event_id == IP_EVENT_STA_GOT_IP) {
        ip_event_got_ip_t* event = (ip_event_got_ip_t*) event_data;
        ESP_LOGI(TAG, "Connected! IP: " IPSTR, IP2STR(&event->ip_info.ip));
        // [3] Set the bit to signal main loop
        xEventGroupSetBits(s_wifi_event_group, WIFI_CONNECTED_BIT);
    }
}

void wifi_init_sta(void)
{
    // Initialize the Event Group
    s_wifi_event_group = xEventGroupCreate();

    esp_netif_init();
    esp_event_loop_create_default();
    esp_netif_create_default_wifi_sta();

    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    esp_wifi_init(&cfg);

    esp_event_handler_instance_t instance_any_id;
    esp_event_handler_instance_t instance_got_ip;
    esp_event_handler_instance_register(WIFI_EVENT, ESP_EVENT_ANY_ID, &wifi_event_handler, NULL, &instance_any_id);
    esp_event_handler_instance_register(IP_EVENT, IP_EVENT_STA_GOT_IP, &wifi_event_handler, NULL, &instance_got_ip);

    wifi_config_t wifi_config = {
        .sta = {
            .ssid = WIFI_SSID,
            .password = WIFI_PASS,
            .threshold.authmode = WIFI_AUTH_WPA2_PSK,
        },
    };
    esp_wifi_set_mode(WIFI_MODE_STA);
    esp_wifi_set_config(WIFI_IF_STA, &wifi_config);
    esp_wifi_start();
}

// =======================
// CAMERA INIT
// =======================
static esp_err_t init_camera()
{
    camera_config_t config;
    config.ledc_channel = LEDC_CHANNEL_0;
    config.ledc_timer = LEDC_TIMER_0;
    config.pin_d0 = CAM_PIN_D0;
    config.pin_d1 = CAM_PIN_D1;
    config.pin_d2 = CAM_PIN_D2;
    config.pin_d3 = CAM_PIN_D3;
    config.pin_d4 = CAM_PIN_D4;
    config.pin_d5 = CAM_PIN_D5;
    config.pin_d6 = CAM_PIN_D6;
    config.pin_d7 = CAM_PIN_D7;
    config.pin_xclk = CAM_PIN_XCLK;
    config.pin_pclk = CAM_PIN_PCLK;
    config.pin_vsync = CAM_PIN_VSYNC;
    config.pin_href = CAM_PIN_HREF;
    config.pin_sccb_sda = CAM_PIN_SIOD; // Updated to new naming (sccb)
    config.pin_sccb_scl = CAM_PIN_SIOC; // Updated to new naming (sccb)
    config.pin_pwdn = CAM_PIN_PWDN;
    config.pin_reset = CAM_PIN_RESET;
    config.xclk_freq_hz = 20000000;
    config.pixel_format = PIXFORMAT_JPEG;
    config.frame_size = FRAMESIZE_VGA; 
    config.jpeg_quality = 12;
    config.fb_count = 2;
    config.fb_location = CAMERA_FB_IN_PSRAM;
    config.grab_mode = CAMERA_GRAB_LATEST;

    esp_err_t err = esp_camera_init(&config);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Camera init failed with error 0x%x", err);
        return err;
    }

    sensor_t * s = esp_camera_sensor_get();
    if (s->id.PID == OV3660_PID) {
        s->set_vflip(s, 1);
        s->set_brightness(s, 1);
        s->set_saturation(s, -2);
    }
    
    return ESP_OK;
}

// =======================
// MAIN APP
// =======================
void app_main(void)
{
    // Initialize NVS
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
      ESP_ERROR_CHECK(nvs_flash_erase());
      ret = nvs_flash_init();
    }
    ESP_ERROR_CHECK(ret);

    gpio_reset_pin(FLASH_GPIO_NUM);
    gpio_set_direction(FLASH_GPIO_NUM, GPIO_MODE_OUTPUT);
    gpio_set_level(FLASH_GPIO_NUM, 1);

    ESP_LOGI(TAG, "Starting WiFi...");
    wifi_init_sta();

    // [4] BLOCK HERE until WiFi is actually connected
    ESP_LOGI(TAG, "Waiting for WiFi connection...");
    xEventGroupWaitBits(s_wifi_event_group, WIFI_CONNECTED_BIT, pdFALSE, pdFALSE, portMAX_DELAY);
    ESP_LOGI(TAG, "WiFi Connected. Starting Camera & UDP.");

    if(init_camera() != ESP_OK) {
        return;
    }

    int sock = socket(AF_INET, SOCK_DGRAM, IPPROTO_IP);
    if (sock < 0) {
        ESP_LOGE(TAG, "Unable to create socket: errno %d", errno);
        return;
    }
    
    struct sockaddr_in dest_addr;
    dest_addr.sin_addr.s_addr = inet_addr(SERVER_IP);
    dest_addr.sin_family = AF_INET;
    dest_addr.sin_port = htons(SERVER_PORT);

    ESP_LOGI(TAG, "Starting UDP Stream to %s:%d", SERVER_IP, SERVER_PORT);

    while (1) {
        // [5] Check if we are still connected before trying to capture
        if (xEventGroupGetBits(s_wifi_event_group) & WIFI_CONNECTED_BIT) {
            
            camera_fb_t * fb = esp_camera_fb_get();
            if (!fb) {
                ESP_LOGE(TAG, "Camera capture failed");
                vTaskDelay(pdMS_TO_TICKS(100));
                continue;
            }

            size_t fb_len = fb->len;
            for (size_t i = 0; i < fb_len; i += MAX_UDP_SIZE) {
                size_t chunkSize = ((fb_len - i) < MAX_UDP_SIZE) ? (fb_len - i) : MAX_UDP_SIZE;

                int err = sendto(sock, fb->buf + i, chunkSize, 0, (struct sockaddr *)&dest_addr, sizeof(dest_addr));
                
                if (err < 0) {
                    // Log error but don't crash, just break this frame
                    if (errno == 12) {
                        // Buffers full! Wait a tiny bit and try again or skip frame
                        vTaskDelay(pdMS_TO_TICKS(5));
                        break; 
                    }
                    ESP_LOGE(TAG, "Error sending chunk: errno %d", errno);
                    break;
                }

                // [6] CRITICAL: Yield to the WiFi task
                // 1 tick (approx 10ms) allows LwIP to clear buffers.
                // If this is too slow, try "ets_delay_us(1000)" but watch for ENOMEM.
                vTaskDelay(pdMS_TO_TICKS(1)); 
            }

            esp_camera_fb_return(fb);

        } else {
            // If lost connection, wait a bit
             ESP_LOGI(TAG, "Waiting for WiFi reconnection...");
             vTaskDelay(pdMS_TO_TICKS(1000));
        }
    }
}
#include "camera.h"
#include "config.h"
#include "esp_log.h"

static const char* TAG = "CameraInit";

esp_err_t init_camera() {
    camera_config_t config;
    
    // إيقاف دبابيس الطاقة والريست الفردية
    config.pin_pwdn = -1;
    config.pin_reset = -1;
    config.xclk_freq_hz = 20000000;
    config.ledc_timer = LEDC_TIMER_0;
    config.ledc_channel = LEDC_CHANNEL_0;
    
    // صيغة البكسل: نحتاج RGB888 لفك ضغط الصورة مباشرة وتغذيتها لنموذج YOLO/ESP-DL
    config.pixel_format = PIXFORMAT_RGB888;
    config.frame_size = FRAMESIZE_QVGA; // الدقة القياسية للسرعة وتوفير الذاكرة (320x240)
    config.jpeg_quality = 12;
    config.fb_count = 1;
    config.fb_location = CAMERA_FB_IN_PSRAM; // PSRAM تفعيل استخدام الذاكرة المؤقتة الخارجية

#if CAMERA_BOARD == 1
    // ESP32-S3-EYE لوحة
    ESP_LOGI(TAG, "Configuring pins for ESP32-S3-EYE...");
    config.pin_d0 = 11;
    config.pin_d1 = 9;
    config.pin_d2 = 8;
    config.pin_d3 = 10;
    config.pin_d4 = 12;
    config.pin_d5 = 18;
    config.pin_d6 = 17;
    config.pin_d7 = 16;
    config.pin_xclk = 15;
    config.pin_pclk = 21;
    config.pin_vsync = 6;
    config.pin_href = 7;
    config.pin_sccb_sda = 4;
    config.pin_sccb_scl = 5;

#elif CAMERA_BOARD == 2
    // Freenove ESP32-S3 Board
    ESP_LOGI(TAG, "Configuring pins for Freenove ESP32-S3...");
    config.pin_d0 = 11;
    config.pin_d1 = 9;
    config.pin_d2 = 8;
    config.pin_d3 = 10;
    config.pin_d4 = 12;
    config.pin_d5 = 18;
    config.pin_d6 = 17;
    config.pin_d7 = 16;
    config.pin_xclk = 15;
    config.pin_pclk = 13;
    config.pin_vsync = 6;
    config.pin_href = 7;
    config.pin_sccb_sda = 4;
    config.pin_sccb_scl = 5;

#elif CAMERA_BOARD == 3
    // XIAO ESP32-S3 Sense
    ESP_LOGI(TAG, "Configuring pins for XIAO ESP32-S3 Sense...");
    config.pin_d0 = 39;
    config.pin_d1 = 40;
    config.pin_d2 = 41;
    config.pin_d3 = 42;
    config.pin_d4 = 15;
    config.pin_d5 = 16;
    config.pin_d6 = 17;
    config.pin_d7 = 18;
    config.pin_xclk = 6;
    config.pin_pclk = 13;
    config.pin_vsync = 38;
    config.pin_href = 47;
    config.pin_sccb_sda = 5;
    config.pin_sccb_scl = 4;
#else
    #error "Unknown Developer Board selected in config.h!"
#endif

    // تهيئة مستشعر الكاميرا
    esp_err_t err = esp_camera_init(&config);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Camera initialization failed with error 0x%x", err);
        return err;
    }
    
    sensor_t * s = esp_camera_sensor_get();
    if (s != nullptr) {
        // تعديل اتجاه الكاميرا الافتراضي
        s->set_hmirror(s, 1);
        s->set_vflip(s, 1);
    }
    
    ESP_LOGI(TAG, "Camera initialized successfully.");
    return ESP_OK;
}

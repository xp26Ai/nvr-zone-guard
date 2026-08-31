#include <stdio.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "nvs_flash.h"

#include "config.h"
#include "camera.h"
#include "wifi.h"
#include "telegram.h"
#include "zone.h"
#include "detect.h"

// مكوّن تحويل صيغ الفريمات (لتحويل RGB888 إلى JPEG)
#include "img_converters.h"

static const char* TAG = "MainApp";

extern "C" void app_main(void) {
    // 1. تهيئة ذاكرة الفلاش غير المتطايرة (NVS) المطلوبة لإعدادات الواي فاي
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    ESP_ERROR_CHECK(ret);

    // 2. تهيئة وتوصيل شبكة الواي فاي
    wifi_init_sta();

    // 3. تهيئة كاميرا الـ ESP32-S3
    if (init_camera() != ESP_OK) {
        ESP_LOGE(TAG, "Camera initialization failed! Stopping execution.");
        return;
    }

    // 4. تهيئة كاشف الوجوه البشرية
    if (!detect_init()) {
        ESP_LOGE(TAG, "Detector initialization failed! Stopping execution.");
        return;
    }

    ESP_LOGI(TAG, "All systems initialized. Running detection loop...");

    uint64_t intrusion_start_ms = 0;
    uint64_t last_alert_ms = 0;

    while (true) {
        // التقاط إطار صورة حي من مستشعر الكاميرا
        camera_fb_t* fb = esp_camera_fb_get();
        if (!fb) {
            ESP_LOGE(TAG, "Camera capture failed");
            vTaskDelay(pdMS_TO_TICKS(100));
            continue;
        }

        // تشغيل كشف الوجوه على إطار الـ RGB888
        std::vector<FaceBox> faces = detect_faces(fb->buf, fb->width, fb->height);
        
        bool someone_inside = false;
        
        for (const auto& face : faces) {
            // حساب مركز أسفل الصندوق المحيط بالوجه كإحداثي تداخل
            int center_x = (face.x1 + face.x2) / 2;
            int bottom_y = face.y2;
            Point bottom_center = { center_x, bottom_y };
            
            // التحقق من تداخل النقطة مع مضلع المنطقة الأمنية المحددة في config.h
            if (is_point_in_polygon(bottom_center, ZONE_POINTS)) {
                someone_inside = true;
                ESP_LOGI(TAG, "Intrusion detected inside zone at point: (%d, %d)", center_x, bottom_y);
                break; // يكفي تداخل شخص واحد لتفعيل حالة الإنذار
            }
        }

        uint64_t current_time_ms = esp_timer_get_time() / 1000;

        if (someone_inside) {
            if (intrusion_start_ms == 0) {
                // تداخل جديد للمرة الأولى
                intrusion_start_ms = current_time_ms;
                ESP_LOGI(TAG, "Person entered the zone. Dwell timer started.");
            } else {
                // التحقق من مدة الاستقرار والبقاء الكلية داخل المضلع
                uint64_t dwell_duration = current_time_ms - intrusion_start_ms;
                ESP_LOGI(TAG, "Dwell duration: %llu ms", dwell_duration);
                
                if (dwell_duration >= DWELL_MS) {
                    // التحقق من انقضاء فترة التهدئة الأمنية
                    if (current_time_ms - last_alert_ms >= ALERT_COOLDOWN_MS) {
                        ESP_LOGI(TAG, "Dwell threshold reached. Capturing alert frame...");
                        
                        uint8_t *jpg_buf = NULL;
                        size_t jpg_buf_len = 0;
                        
                        // تحويل إطار الـ RGB888 الملتقط إلى JPEG لإرساله لتيليجرام
                        bool jpeg_converted = fmt2jpg(fb->buf, fb->width * fb->height * 3, 
                                                       fb->width, fb->height, 
                                                       PIXFORMAT_RGB888, 15, 
                                                       &jpg_buf, &jpg_buf_len);
                        
                        if (jpeg_converted && jpg_buf) {
                            ESP_LOGI(TAG, "Sending alert photo to Telegram...");
                            esp_err_t err = telegram_send_photo(jpg_buf, jpg_buf_len, 
                                "⚠️ تنبيه أمني: شخص داخل المنطقة المراقَبة!");
                            
                            if (err == ESP_OK) {
                                last_alert_ms = current_time_ms;
                                ESP_LOGI(TAG, "Telegram alert sent successfully.");
                            } else {
                                ESP_LOGE(TAG, "Failed to send photo to Telegram.");
                            }
                            free(jpg_buf);
                        } else {
                            ESP_LOGE(TAG, "Failed to convert raw RGB frame to JPEG.");
                        }
                    } else {
                        ESP_LOGI(TAG, "Alert suppressed (cooldown active).");
                    }
                }
            }
        } else {
            // لا توجد كشوفات داخل المضلع
            if (intrusion_start_ms != 0) {
                ESP_LOGI(TAG, "Zone cleared. Resetting dwell timer.");
                intrusion_start_ms = 0;
            }
        }

        // إرجاع الإطار إلى الكاميرا لتهيئة المستشعر للقطة القادمة وتوفير الذاكرة
        esp_camera_fb_return(fb);

        // مهلة بسيطة لراحة المعالج وتشغيل بقية المهام (شريط الواي فاي، نظام التشغيل، إلخ)
        vTaskDelay(pdMS_TO_TICKS(50));
    }
}

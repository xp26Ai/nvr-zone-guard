#include "telegram.h"
#include "config.h"
#include "esp_http_client.h"
#include "esp_log.h"
#include "esp_crt_bundle.h"
#include <string.h>

static const char* TAG = "TelegramClient";
#define BOUNDARY "----ESP32ZoneGuardBoundary"

esp_err_t telegram_send_photo(uint8_t* jpeg_data, size_t jpeg_size, const char* caption) {
    char url[256];
    snprintf(url, sizeof(url), "https://api.telegram.org/bot%s/sendPhoto", TG_BOT_TOKEN);

    esp_http_client_config_t config = {};
    config.url = url;
    config.crt_bundle_attach = esp_crt_bundle_attach; // استخدام الشهادات الافتراضية المدمجة
    config.method = HTTP_METHOD_POST;
    
    esp_http_client_handle_t client = esp_http_client_init(&config);
    if (!client) {
        ESP_LOGE(TAG, "Failed to initialize HTTP client");
        return ESP_FAIL;
    }

    // بناء الأجزاء النصية للمرسل المتعدد (Multipart Form-Data)
    char header_chat_id[128];
    snprintf(header_chat_id, sizeof(header_chat_id),
             "--" BOUNDARY "\r\n"
             "Content-Disposition: form-data; name=\"chat_id\"\r\n\r\n"
             "%s\r\n", TG_CHAT_ID);

    char header_caption[256];
    snprintf(header_caption, sizeof(header_caption),
             "--" BOUNDARY "\r\n"
             "Content-Disposition: form-data; name=\"caption\"\r\n\r\n"
             "%s\r\n", caption);

    char header_photo[192];
    snprintf(header_photo, sizeof(header_photo),
             "--" BOUNDARY "\r\n"
             "Content-Disposition: form-data; name=\"photo\"; filename=\"capture.jpg\"\r\n"
             "Content-Type: image/jpeg\r\n\r\n");

    const char* footer = "\r\n--" BOUNDARY "--\r\n";

    // حساب الطول الإجمالي الدقيق لترويسة الـ Content-Length
    size_t total_length = strlen(header_chat_id) +
                          strlen(header_caption) +
                          strlen(header_photo) +
                          jpeg_size +
                          strlen(footer);

    esp_http_client_set_header(client, "Content-Type", "multipart/form-data; boundary=" BOUNDARY);
    
    ESP_LOGI(TAG, "Uploading photo to Telegram, content size: %zu bytes", total_length);
    
    esp_err_t err = esp_http_client_open(client, total_length);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Failed to open HTTP connection: %s", esp_err_to_name(err));
        esp_http_client_cleanup(client);
        return err;
    }

    // إرسال البيانات بشكل متدفق (Streaming) لتقليل استهلاك الذاكرة العشوائية RAM
    esp_http_client_write(client, header_chat_id, strlen(header_chat_id));
    esp_http_client_write(client, header_caption, strlen(header_caption));
    esp_http_client_write(client, header_photo, strlen(header_photo));
    
    // إرسال مصفوفة بايتات صورة الـ JPEG
    int written = esp_http_client_write(client, (const char*)jpeg_data, jpeg_size);
    if (written < 0) {
        ESP_LOGE(TAG, "Failed to write JPEG data");
        esp_http_client_cleanup(client);
        return ESP_FAIL;
    }
    
    esp_http_client_write(client, footer, strlen(footer));

    // قراءة ترويسة الاستجابة ثم جلب رمز الحالة الفعلي (fetch_headers يرجع طول المحتوى لا رمز الحالة)
    esp_http_client_fetch_headers(client);
    int status_code = esp_http_client_get_status_code(client);
    if (status_code >= 200 && status_code < 300) {
        ESP_LOGI(TAG, "Alert sent successfully! HTTP Status: %d", status_code);
        err = ESP_OK;
    } else {
        ESP_LOGE(TAG, "Failed to send photo. HTTP Status Code: %d", status_code);
        err = ESP_FAIL;
    }

    esp_http_client_cleanup(client);
    return err;
}

#pragma once
#include <stddef.h>
#include <stdint.h>
#include "esp_err.h"

// إرسال صورة JPEG بصيغة ثنائية إلى بوت تيليجرام باستخدام multipart/form-data
esp_err_t telegram_send_photo(uint8_t* jpeg_data, size_t jpeg_size, const char* caption);

#pragma once
#include <vector>
#include <stdint.h>

struct FaceBox {
    int x1;
    int y1;
    int x2;
    int y2;
};

// تهيئة نموذج الكشف
bool detect_init();

// الكشف عن الوجوه البشرية وإرجاع قائمة الصناديق المحيطة بها
std::vector<FaceBox> detect_faces(uint8_t* image_data, int width, int height);

#include "detect.h"
#include "human_face_detect.hpp"
#include "dl_image.hpp"
#include "esp_log.h"

static const char* TAG = "FaceDetect";
static HumanFaceDetect* s_face_detector = nullptr;

bool detect_init() {
    if (s_face_detector != nullptr) {
        return true;
    }
    ESP_LOGI(TAG, "Initializing HumanFaceDetect model from esp-dl...");
    // تهيئة نموذج كشف الوجه البشري
    s_face_detector = new HumanFaceDetect();
    return s_face_detector != nullptr;
}

std::vector<FaceBox> detect_faces(uint8_t* image_data, int width, int height) {
    std::vector<FaceBox> boxes;
    if (!s_face_detector) {
        ESP_LOGE(TAG, "Detector is not initialized!");
        return boxes;
    }

    // تجهيز الإدخال كصورة ثلاثية القنوات (RGB888) لـ esp-dl
    // dl::image::make_shared هي دالة التعبئة القياسية في المكتبة
    dl::image::shared_ptr<dl::image::Image> img = dl::image::make_shared(image_data, height, width, 3);
    
    // تشغيل نموذج كشف الوجه
    auto results = s_face_detector->run(*img);
    
    // استخراج الإحداثيات وتعبئة الصناديق المحيطة بالوجوه
    for (auto const& res : results) {
        FaceBox box;
        box.x1 = res.box[0];
        box.y1 = res.box[1];
        box.x2 = res.box[2];
        box.y2 = res.box[3];
        boxes.push_back(box);
    }
    
    return boxes;
}

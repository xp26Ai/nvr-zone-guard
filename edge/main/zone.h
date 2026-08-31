#pragma once
#include <vector>
#include "config.h"

// التحقق مما إذا كانت نقطة تقع داخل مضلع المنطقة الأمنية ثنائية الأبعاد
bool is_point_in_polygon(Point p, const std::vector<Point>& polygon);

#include "zone.h"

bool is_point_in_polygon(Point p, const std::vector<Point>& polygon) {
    int n = polygon.size();
    if (n < 3) return false;

    bool inside = false;
    
    // خوارزمية شعاع المسح (Ray Casting Algorithm)
    // تدور حول أضلاع المضلع وتفحص تقاطعات الخط الأفقي الوهمي
    for (int i = 0, j = n - 1; i < n; j = i++) {
        if (((polygon[i].y > p.y) != (polygon[j].y > p.y)) &&
            (p.x < (polygon[j].x - polygon[i].x) * (p.y - polygon[i].y) / (polygon[j].y - polygon[i].y) + polygon[i].x)) {
            inside = !inside;
        }
    }
    return inside;
}

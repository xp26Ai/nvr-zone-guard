# -*- coding: utf-8 -*-
from typing import List, Tuple
import cv2
import numpy as np

def is_point_in_polygon(point: Tuple[int, int], polygon_points: List[List[int]]) -> bool:
    """
    التحقق مما إذا كانت النقطة تقع داخل المضلع المحدد للمنطقة الأمنية.
    polygon_points: قائمة من النقاط [[x1, y1], [x2, y2], ...]
    """
    if not polygon_points or len(polygon_points) < 3:
        return False
    
    # تحويل النقاط إلى مصفوفة numpy بالشكل المطلوب لـ OpenCV
    polygon = np.array(polygon_points, dtype=np.int32)
    # cv2.pointPolygonTest تتطلب نقطة كـ tuple من الأرقام العشرية
    # البارامتر الأخير False لتحديد ما إذا كانت النقطة بالداخل (>= 0) أو الخارج (< 0)
    result = cv2.pointPolygonTest(polygon, (float(point[0]), float(point[1])), False)
    return result >= 0

def get_bottom_center(bbox: Tuple[int, int, int, int]) -> Tuple[int, int]:
    """
    حساب نقطة التماس مع الأرض للشخص (مركز أسفل الصندوق المحيط).
    الصندوق بالشكل (x1, y1, x2, y2)
    """
    x1, y1, x2, y2 = bbox
    bottom_center_x = int((x1 + x2) / 2)
    bottom_center_y = int(y2)
    return (bottom_center_x, bottom_center_y)

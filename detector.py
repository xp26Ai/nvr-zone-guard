# -*- coding: utf-8 -*-
from typing import List, Tuple, Any
import logging
from ultralytics import YOLO

logger = logging.getLogger(__name__)

class PersonDetector:
    """
    مكتشف الأشخاص بالاعتماد على نموذج YOLOv8 من Ultralytics.
    """
    def __init__(self, model_name: str = "yolov8n.pt", conf_threshold: float = 0.4):
        logger.info(f"جاري تحميل نموذج YOLOv8: {model_name}...")
        self.model = YOLO(model_name)
        self.conf_threshold = conf_threshold
        # رقم فئة الشخص في قائمة تصنيفات COCO هو 0
        self.person_class_id = 0

    def detect_people(self, frame: Any) -> List[Tuple[Tuple[int, int, int, int], float]]:
        """
        الكشف عن الأشخاص في الإطار وإرجاع إحداثيات الصناديق المحيطة ونسبة الثقة.
        يعيد قائمة من: ((x1, y1, x2, y2), conf)
        """
        try:
            # تشغيل المكتشف مع تصفية الكائنات للبحث عن فئة الأشخاص فقط (classes=[0])
            results = self.model(frame, classes=[self.person_class_id], conf=self.conf_threshold, verbose=False)
            
            detected_people = []
            if not results:
                return detected_people
                
            for result in results:
                boxes = result.boxes
                for box in boxes:
                    xyxy = box.xyxy[0].cpu().numpy()
                    x1, y1, x2, y2 = map(int, xyxy)
                    conf = float(box.conf[0].cpu().numpy())
                    
                    detected_people.append(((x1, y1, x2, y2), conf))
            
            return detected_people
        except Exception as e:
            logger.error(f"حدث خطأ أثناء الكشف عن الأشخاص: {e}")
            return []

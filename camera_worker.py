# -*- coding: utf-8 -*-
import os
import time
import json
import logging
from collections import deque
from datetime import datetime
from typing import List, Tuple, Dict, Any, Optional

import cv2
import numpy as np
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtGui import QImage

import db
from detector import PersonDetector
from recorder import VideoRecorder
from telegram_sender import TelegramVideoSender
from zone import is_point_in_polygon, get_bottom_center

logger = logging.getLogger(__name__)

# إنشاء نسخة عامة من مرسل التليجرام لمشاركتها عبر خيوط الكاميرات المختلفة
telegram_sender_instance = TelegramVideoSender()

class CameraWorker(QThread):
    """
    خيط معالجة مستقل لكاميرا معينة.
    يقوم بالتقاط البث المباشر، وكشف الحركة/الأشخاص، وتسجيل الأحداث، وبث الإطارات للمعاينة.
    """
    frame_ready = pyqtSignal(QImage)
    status_changed = pyqtSignal(str)
    event_logged = pyqtSignal(dict)

    def __init__(self, camera_id: int, parent=None):
        super().__init__(parent)
        self.camera_id = camera_id
        self.is_running = True
        
        # تحميل بيانات الكاميرا من قاعدة البيانات مباشرة لتحديثها
        self.load_camera_config()
        
        # مخزن لتسجيل توقيت الإطارات لحساب الـ FPS الفعلي بدقة
        self.frame_timestamps = deque(maxlen=50)

    def load_camera_config(self):
        """تحميل أو تحديث إعدادات الكاميرا من قاعدة البيانات"""
        conn = db.get_db_connection()
        row = conn.execute("SELECT * FROM cameras WHERE id = ?", (self.camera_id,)).fetchone()
        conn.close()
        
        if not row:
            raise ValueError(f"الكاميرا رقم {self.camera_id} غير موجودة في قاعدة البيانات.")
            
        camera_data = dict(row)
        self.name = camera_data.get("name", "كاميرا")
        self.number = camera_data.get("number", "0")
        self.rtsp_url = camera_data.get("rtsp_url", "")
        self.enabled = bool(camera_data.get("enabled", 1))
        
        # فك نقاط المنطقة الأمنية
        zone_points_str = camera_data.get("zone_points", "[]")
        try:
            self.zone_points = json.loads(zone_points_str)
        except Exception:
            self.zone_points = []
            
        self.enter_seconds = camera_data.get("enter_seconds", 4)
        self.clip_seconds = camera_data.get("clip_seconds", 10)
        self.person_conf = camera_data.get("person_conf", 0.4)
        self.pre_buffer_seconds = camera_data.get("pre_buffer_seconds", 5)

    def run(self):
        logger.info(f"بدء تشغيل خيط المراقبة للكاميرا: {self.name} (ID: {self.camera_id})")
        self.status_changed.emit("جاري الاتصال...")
        
        # إعداد خيارات ffmpeg قبل فتح البث عبر OpenCV
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp|stimeout;8000000"
        
        # تهيئة الكشف والمسجل
        detector = PersonDetector(conf_threshold=self.person_conf)
        recorder = VideoRecorder(
            output_dir="clips",
            default_fps=10.0,
            pre_buffer_seconds=self.pre_buffer_seconds
        )
        
        cap = None
        intrusion_start_time = None
        clip_start_time = None
        current_event_id = None
        
        # متغير تتبع الاتصال
        reconnect_attempts = 0
        
        while not self.isInterruptionRequested() and self.is_running:
            if cap is None or not cap.isOpened():
                logger.info(f"[{self.name}] جاري محاولة فتح رابط RTSP...")
                cap = cv2.VideoCapture(self.rtsp_url)
                if not cap.isOpened():
                    reconnect_attempts += 1
                    self.status_changed.emit(f"فشل الاتصال ({reconnect_attempts})")
                    self.msleep(3000)
                    continue
                else:
                    reconnect_attempts = 0
                    self.status_changed.emit("متصل - نشط")
                    logger.info(f"[{self.name}] تم الاتصال بالبث المباشر بنجاح.")
            
            ret, frame = cap.read()
            if not ret:
                logger.warning(f"[{self.name}] فشل قراءة الإطار من الكاميرا. جاري إعادة الاتصال...")
                self.status_changed.emit("انقطع الاتصال")
                if cap is not None:
                    cap.release()
                    cap = None
                self.msleep(2000)
                continue
            
            # تسجيل زمن معالجة الفريم
            now = time.time()
            self.frame_timestamps.append(now)
            
            # إضافة الإطار الأصلي إلى الذاكرة الدائرية قبل الرسم
            recorder.add_to_buffer(frame)
            
            # الحصول على الأبعاد
            height, width, _ = frame.shape
            
            # حساب الـ FPS الفعلي الحالي
            actual_fps = 10.0
            if len(self.frame_timestamps) > 1:
                duration = self.frame_timestamps[-1] - self.frame_timestamps[0]
                if duration > 0:
                    actual_fps = len(self.frame_timestamps) / duration
            
            # الكشف عن الأشخاص
            detected_people = detector.detect_people(frame)
            
            # التحقق من وجود تداخل داخل المنطقة
            someone_inside = False
            bottom_centers_inside = []
            
            for bbox, conf in detected_people:
                bottom_center = get_bottom_center(bbox)
                
                # إذا لم يتم رسم منطقة، نعتبر كامل الإطار هو المنطقة الأمنية
                if not self.zone_points or len(self.zone_points) < 3:
                    someone_inside = True
                    bottom_centers_inside.append((bottom_center, True))
                else:
                    inside = is_point_in_polygon(bottom_center, self.zone_points)
                    bottom_centers_inside.append((bottom_center, inside))
                    if inside:
                        someone_inside = True

            # رسم المنطقة والأهداف للتصدير والمعاينة
            visual_frame = frame.copy()
            zone_color = (0, 0, 255) if someone_inside else (0, 255, 0)
            
            if self.zone_points and len(self.zone_points) >= 3:
                pts = np.array(self.zone_points, dtype=np.int32)
                cv2.polylines(visual_frame, [pts], True, zone_color, 2)
                overlay = visual_frame.copy()
                cv2.fillPoly(overlay, [pts], zone_color)
                cv2.addWeighted(overlay, 0.15, visual_frame, 0.85, 0, dst=visual_frame)

            for i, (bbox, conf) in enumerate(detected_people):
                x1, y1, x2, y2 = bbox
                bottom_center, inside = bottom_centers_inside[i]
                box_color = (0, 0, 255) if inside else (255, 0, 0)
                
                cv2.rectangle(visual_frame, (x1, y1), (x2, y2), box_color, 2)
                cv2.circle(visual_frame, bottom_center, 6, box_color, -1)
                
                # نص الكشف باللغة الإنجليزية
                cv2.putText(visual_frame, f"Person {conf:.2f}", (x1, y1 - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, box_color, 2)

            # بث الإطار إلى المعاينة بالواجهة الرسومية
            self._emit_frame(visual_frame)

            # منطق التسجيل والإنذار
            if someone_inside:
                if intrusion_start_time is None:
                    intrusion_start_time = now
                    logger.info(f"[{self.name}] كشف حركة داخل المنطقة. بدء العداد المسبق...")
                    self.status_changed.emit("رصد حركة...")
                
                # التحقق من استمرار التداخل
                intrusion_duration = now - intrusion_start_time
                if intrusion_duration >= self.enter_seconds:
                    if not recorder.is_recording:
                        # بدء التسجيل من الذاكرة الدائرية بـ FPS الفعلي
                        clip_path = recorder.start_recording(width, height, actual_fps)
                        clip_start_time = now
                        self.status_changed.emit("تسجيل حدث أمني...")
                        logger.info(f"[{self.name}] تم بدء كتابة المقطع الأمني.")
                        
                        # إرسال وتوثيق الحدث في قاعدة البيانات
                        ts_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        current_event_id = db.add_event(
                            camera_id=self.camera_id,
                            ts=ts_str,
                            type_="بداية اختراق المنطقة",
                            clip_path=clip_path,
                            sent_ok=0
                        )
                        self.event_logged.emit({
                            "id": current_event_id,
                            "camera_name": self.name,
                            "ts": ts_str,
                            "type": "بداية اختراق",
                            "clip_path": clip_path,
                            "sent_ok": 0
                        })
                    else:
                        # كتابة الإطار المزين بالفيديو المباشر
                        recorder.write_frame(visual_frame)
                        
                        # تدوير المقطع بعد انقضاء المدة المحددة
                        clip_duration = now - clip_start_time
                        if clip_duration >= self.clip_seconds:
                            old_clip_path = recorder.rotate_clip(actual_fps)
                            if old_clip_path:
                                # إرسال المقطع المكتمل عبر تيليجرام
                                token = db.get_setting("telegram_bot_token")
                                chat_id = db.get_setting("telegram_chat_id")
                                caption = f"⚠️ تنبيه كاميرا [{self.name}]: استمرار وجود حركة داخل المنطقة المحمية!"
                                telegram_sender_instance.send_video(
                                    file_path=old_clip_path,
                                    caption=caption,
                                    event_id=current_event_id,
                                    bot_token=token,
                                    chat_id=chat_id
                                )
                                
                            # إعداد الحدث التالي للمقطع الدائري الجديد
                            ts_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            clip_path = recorder.current_clip_path
                            current_event_id = db.add_event(
                                camera_id=self.camera_id,
                                ts=ts_str,
                                type_="استمرار الاختراق",
                                clip_path=clip_path,
                                sent_ok=0
                            )
                            self.event_logged.emit({
                                "id": current_event_id,
                                "camera_name": self.name,
                                "ts": ts_str,
                                "type": "استمرار الاختراق",
                                "clip_path": clip_path,
                                "sent_ok": 0
                            })
                            clip_start_time = now
            else:
                # خروج الأشخاص من المنطقة الأمنية
                if intrusion_start_time is not None:
                    logger.info(f"[{self.name}] خلت المنطقة من الأشخاص. جاري إنهاء التسجيل...")
                    self.status_changed.emit("متصل - نشط")
                    
                    if recorder.is_recording:
                        recorder.write_frame(visual_frame)
                        clip_path = recorder.stop_recording()
                        if clip_path:
                            token = db.get_setting("telegram_bot_token")
                            chat_id = db.get_setting("telegram_chat_id")
                            caption = f"✅ تنبيه كاميرا [{self.name}]: خروج الأشخاص وانتهاء التسلل."
                            telegram_sender_instance.send_video(
                                file_path=clip_path,
                                caption=caption,
                                event_id=current_event_id,
                                bot_token=token,
                                chat_id=chat_id
                            )
                    
                    intrusion_start_time = None
                    clip_start_time = None
                    current_event_id = None
            
            # مهلة صغيرة لحفظ موارد المعالج
            self.msleep(10)

        # تنظيف أخير عند التوقف
        if recorder.is_recording:
            clip_path = recorder.stop_recording()
            if clip_path:
                token = db.get_setting("telegram_bot_token")
                chat_id = db.get_setting("telegram_chat_id")
                caption = f"ℹ️ تنبيه كاميرا [{self.name}]: إيقاف تشغيل المحرك وحفظ المقطع الأخير."
                telegram_sender_instance.send_video(
                    file_path=clip_path,
                    caption=caption,
                    event_id=current_event_id if current_event_id else 0,
                    bot_token=token,
                    chat_id=chat_id
                )

        if cap is not None:
            cap.release()
            
        self.status_changed.emit("متوقف")
        logger.info(f"خيط المراقبة للكاميرا {self.name} انتهى بنجاح.")

    def _emit_frame(self, frame_bgr):
        """تحويل فريم OpenCV BGR إلى QImage وبثه عبر الإشارة"""
        try:
            rgb_frame = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_frame.shape
            bytes_per_line = ch * w
            qimg = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
            # يجب عمل نسخ للبيانات لأن numpy array سيتم تدميره أو تعديله
            self.frame_ready.emit(qimg.copy())
        except Exception as e:
            logger.error(f"حدث خطأ أثناء تحويل وبث الإطار: {e}")

    def stop(self):
        """إيقاف تشغيل الخيط بشكل آمن"""
        self.is_running = False
        self.requestInterruption()
        self.wait()

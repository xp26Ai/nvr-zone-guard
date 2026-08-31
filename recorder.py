# -*- coding: utf-8 -*-
from collections import deque
import os
import time
import logging
from typing import Any, Optional

import cv2

logger = logging.getLogger(__name__)

class VideoRecorder:
    """
    إدارة تسجيل مقاطع الفيديو بشكل دائري مع حفظ الثواني السابقة لحدث الدخول.
    يقيس معدل الإطارات الفعلي ويكتب به مقطع الفيديو لتفادي تسريع أو إبطاء العرض.
    """
    def __init__(self, output_dir: str = "clips", default_fps: float = 10.0, pre_buffer_seconds: int = 5):
        self.output_dir = output_dir
        self.fps = default_fps
        self.pre_buffer_seconds = pre_buffer_seconds
        
        # إنشاء مجلد لحفظ مقاطع الفيديو إذا لم يكن موجوداً
        os.makedirs(self.output_dir, exist_ok=True)
        
        # الذاكرة الدائرية لحفظ الإطارات السابقة لحدث الدخول
        # نستخدم سعة أقصى تقريبية بناءً على 30 إطار بالثانية كحد أقصى لتجنب نفاد الذاكرة
        self.buffer_maxlen = max(1, int(30 * pre_buffer_seconds))
        self.frame_buffer = deque(maxlen=self.buffer_maxlen)
        self.timestamp_buffer = deque(maxlen=self.buffer_maxlen)
        
        self.writer = None
        self.current_clip_path = None
        self.is_recording = False
        self.frame_width = 0
        self.frame_height = 0
        
        # إحصائيات للمقطع الحالي
        self.frames_written_in_clip = 0
        self.clip_start_real_time = 0.0

    def add_to_buffer(self, frame: Any):
        """حفظ نسخة من الإطار الحالي وتوقيته في الذاكرة الدائرية المؤقتة"""
        self.frame_buffer.append(frame.copy())
        self.timestamp_buffer.append(time.time())

    def start_recording(self, frame_width: int, frame_height: int, actual_fps: float) -> str:
        """بدء تسجيل مقطع فيديو جديد بكتابة إطارات الذاكرة الدائرية أولاً باستخدام FPS الفعلي"""
        if self.is_recording:
            return self.current_clip_path

        self.frame_width = frame_width
        self.frame_height = frame_height
        
        # تحديث قيمة الـ FPS الفعلي وقصرها بين حدين منطقيين (مثلاً 1 إلى 30)
        self.fps = max(1.0, min(actual_fps, 30.0))
        self.is_recording = True
        self.frames_written_in_clip = 0
        self.clip_start_real_time = time.time()
        
        # توليد اسم المقطع بناءً على الطابع الزمني
        filename = f"clip_{int(time.time())}.mp4"
        self.current_clip_path = os.path.join(self.output_dir, filename)
        
        # استخدام ترميز mp4v الشائع لحاويات mp4
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        self.writer = cv2.VideoWriter(self.current_clip_path, fourcc, self.fps, (self.frame_width, self.frame_height))
        
        logger.info(f"بدأ تسجيل مقطع جديد: {self.current_clip_path} بمعدل إطارات فعلي: {self.fps:.2f} FPS")
        
        # إفراغ وكتابة الإطارات المخزنة في الذاكرة المؤقتة لتوثيق لحظة الدخول
        buffered_count = len(self.frame_buffer)
        logger.info(f"كتابة {buffered_count} إطاراً من الذاكرة الدائرية قبل الدخول الفعلي...")
        
        while self.frame_buffer:
            buffered_frame = self.frame_buffer.popleft()
            self.writer.write(buffered_frame)
            self.frames_written_in_clip += 1
            
        self.timestamp_buffer.clear()
        return self.current_clip_path

    def write_frame(self, frame: Any):
        """كتابة إطار حي في الملف أثناء استمرار التسجيل"""
        if self.is_recording and self.writer:
            self.writer.write(frame)
            self.frames_written_in_clip += 1

    def stop_recording(self) -> Optional[str]:
        """إيقاف التسجيل وإغلاق ملف الفيديو مع إرجاع المسار النهائي"""
        if not self.is_recording:
            return None
            
        self.is_recording = False
        clip_path = self.current_clip_path
        
        if self.writer:
            self.writer.release()
            self.writer = None
            
        duration = time.time() - self.clip_start_real_time
        avg_fps = self.frames_written_in_clip / duration if duration > 0 else 0
        logger.info(f"تم إغلاق ملف التسجيل: {clip_path} | إجمالي الإطارات: {self.frames_written_in_clip} | مدة حقيقية: {duration:.2f}ث | معدل إطارات حقيقي: {avg_fps:.2f} FPS")
        
        self.current_clip_path = None
        self.frame_buffer.clear()
        self.timestamp_buffer.clear()
        
        return clip_path

    def rotate_clip(self, next_fps: float) -> Optional[str]:
        """إنهاء الملف الحالي وبدء ملف تسجيل جديد فوراً لضمان التسجيل المستمر مع تحديث الـ FPS"""
        if not self.is_recording:
            return None
            
        # إغلاق المقطع الحالي
        old_clip_path = self.stop_recording()
        
        # فتح مقطع جديد فوراً وإكمال كتابة الفريمات بالـ FPS الجديد
        self.start_recording(self.frame_width, self.frame_height, next_fps)
        
        return old_clip_path

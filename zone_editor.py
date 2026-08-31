# -*- coding: utf-8 -*-
import os
import cv2
import json
import logging
from PyQt5.QtCore import QThread, pyqtSignal, Qt, QPoint
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QMessageBox, QWidget)
from PyQt5.QtGui import QImage, QPixmap, QPainter, QPen, QColor, QPolygon, QBrush

logger = logging.getLogger(__name__)

class FrameGrabber(QThread):
    """خيط مستقل لجلب إطار واحد من الكاميرا لرسم المنطقة عليه"""
    frame_grabbed = pyqtSignal(bool, object, str)

    def __init__(self, rtsp_url: str):
        super().__init__()
        self.rtsp_url = rtsp_url

    def run(self):
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp|stimeout;4000000"
        cap = cv2.VideoCapture(self.rtsp_url)
        if not cap.isOpened():
            self.frame_grabbed.emit(False, None, "فشل فتح قناة البث: الكاميرا غير متصلة بالشبكة.")
            return
        
        ret, frame = cap.read()
        cap.release()
        
        if ret:
            try:
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w, ch = rgb_frame.shape
                bytes_per_line = ch * w
                qimg = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format_RGB888).copy()
                self.frame_grabbed.emit(True, qimg, "تم جلب الإطار بنجاح.")
            except Exception as e:
                self.frame_grabbed.emit(False, None, f"خطأ معالجة الإطار: {e}")
        else:
            self.frame_grabbed.emit(False, None, "تعذر التقاط إطار من البث المباشر.")

class ZoneLabel(QLabel):
    """تسمية مخصصة لعرض الإطار ورسم النقاط والمضلع عليه بشكل متفاعل"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.original_pixmap = None
        self.points = []  # النقاط بالإحداثيات الأصلية للإطار [[x1, y1], [x2, y2], ...]
        self.setMouseTracking(True)
        self.setScaledContents(True)
        self.setAlignment(Qt.AlignCenter)

    def set_frame(self, qimage: QImage):
        self.original_pixmap = QPixmap.fromImage(qimage)
        self.setPixmap(self.original_pixmap)
        self.update()

    def mousePressEvent(self, event):
        if self.original_pixmap is None or self.original_pixmap.isNull():
            return
            
        if event.button() == Qt.LeftButton:
            lx = event.x()
            ly = event.y()
            
            # أبعاد العرض الحالية
            lw = self.width()
            lh = self.height()
            
            # الأبعاد الحقيقية للصورة الأصلية
            ow = self.original_pixmap.width()
            oh = self.original_pixmap.height()
            
            if lw > 0 and lh > 0:
                # تحويل الإحداثيات من العرض على الشاشة إلى إحداثيات الإطار الأصلي بدقة
                ox = int(lx * (ow / lw))
                oy = int(ly * (oh / lh))
                
                # قصر الإحداثيات داخل حدود الصورة
                ox = max(0, min(ox, ow - 1))
                oy = max(0, min(oy, oh - 1))
                
                self.points.append([ox, oy])
                self.update()

    def paintEvent(self, event):
        # رسم الصورة أولاً عبر الكلاس الأساسي
        super().paintEvent(event)
        
        if self.original_pixmap is None or self.original_pixmap.isNull() or not self.points:
            return
            
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        lw = self.width()
        lh = self.height()
        ow = self.original_pixmap.width()
        oh = self.original_pixmap.height()
        
        # تحويل إحداثيات النقاط الأصلية إلى إحداثيات شاشة العرض
        label_points = []
        for pt in self.points:
            lx = int(pt[0] * (lw / ow))
            ly = int(pt[1] * (lh / oh))
            label_points.append(QPoint(lx, ly))
            
        # رسم الخطوط والمضلع المظلل
        poly = QPolygon(label_points)
        
        # لون المنطقة الأمنية (تظليل أخضر شبه شفاف)
        brush = QBrush(QColor(0, 255, 0, 60))
        painter.setBrush(brush)
        
        # حدود المنطقة
        pen = QPen(QColor(0, 255, 0), 2, Qt.SolidLine)
        painter.setPen(pen)
        
        if len(label_points) >= 3:
            painter.drawPolygon(poly)
        else:
            # رسم خطوط مؤقتة في حال وجود نقطتين
            for i in range(len(label_points) - 1):
                painter.drawLine(label_points[i], label_points[i+1])
                
        # رسم رؤوس المضلع بنقاط حمراء مميزة
        pen_pt = QPen(QColor(255, 0, 0), 8, Qt.SolidLine)
        painter.setPen(pen_pt)
        for pt in label_points:
            painter.drawPoint(pt)

    def undo_last_point(self):
        if self.points:
            self.points.pop()
            self.update()

    def clear_all_points(self):
        self.points.clear()
        self.update()

class ZoneEditor(QDialog):
    """حوار رسم المنطقة الأمنية التفاعلي"""
    def __init__(self, camera_name: str, rtsp_url: str, current_points_str: str, parent=None):
        super().__init__(parent)
        self.camera_name = camera_name
        self.rtsp_url = rtsp_url
        self.grabber = None
        
        # تفكيك النقاط الحالية إن وجدت
        try:
            self.initial_points = json.loads(current_points_str)
        except Exception:
            self.initial_points = []
            
        self.init_ui()
        self.start_grabbing_frame()

    def init_ui(self):
        self.setWindowTitle(f"رسم المنطقة الأمنية - {self.camera_name}")
        self.resize(850, 600)
        self.setLayoutDirection(Qt.RightToLeft)
        
        layout = QVBoxLayout(self)
        
        # نص توضيحي علوي
        self.lbl_info = QLabel("جاري الاتصال بالكاميرا وجلب إطار حي...")
        self.lbl_info.setStyleSheet("font-size: 13px; font-weight: bold; color: #ddd;")
        layout.addWidget(self.lbl_info)
        
        # محرك الرسم
        self.zone_label = ZoneLabel()
        self.zone_label.setStyleSheet("border: 2px dashed #555; background: #111;")
        self.zone_label.points = list(self.initial_points)
        layout.addWidget(self.zone_label, 1) # يأخذ المساحة المتاحة بالكامل
        
        # شريط الأزرار والتحكم بالرسم
        btn_layout = QHBoxLayout()
        
        self.btn_undo = QPushButton("تراجع ↩️")
        self.btn_undo.clicked.connect(self.zone_label.undo_last_point)
        btn_layout.addWidget(self.btn_undo)
        
        self.btn_clear = QPushButton("مسح الكل 🗑️")
        self.btn_clear.clicked.connect(self.zone_label.clear_all_points)
        btn_layout.addWidget(self.btn_clear)
        
        btn_layout.addStretch()
        
        self.btn_save = QPushButton("حفظ المنطقة 💾")
        self.btn_save.clicked.connect(self.on_save)
        self.btn_save.setEnabled(False) # لا يتم التفعيل إلا بعد نجاح الاتصال
        btn_layout.addWidget(self.btn_save)
        
        btn_cancel = QPushButton("إلغاء ❌")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)
        
        layout.addLayout(btn_layout)

    def start_grabbing_frame(self):
        self.grabber = FrameGrabber(self.rtsp_url)
        self.grabber.frame_grabbed.connect(self.on_frame_grabbed)
        self.grabber.start()

    def on_frame_grabbed(self, success: bool, qimg: QImage, msg: str):
        if success and qimg:
            self.lbl_info.setText("انقر بالماوس على الصورة لرسم رؤوس المضلع للمنطقة الأمنية. يجب وضع 3 نقاط على الأقل.")
            self.zone_label.set_frame(qimg)
            self.btn_save.setEnabled(True)
        else:
            self.lbl_info.setText("تعذر جلب البث المباشر. تم تحميل إطار تخيلي أسود للرسم عليه كبديل.")
            # إطار أسود كبديل في حال تعذر الاتصال بالكاميرا
            dummy_frame = QImage(640, 360, QImage.Format_RGB888)
            dummy_frame.fill(Qt.black)
            self.zone_label.set_frame(dummy_frame)
            self.btn_save.setEnabled(True)
            QMessageBox.warning(self, "تحذير البث", f"{msg}\nتم فتح لوحة رسم فارغة مؤقتاً.")

    def on_save(self):
        pts = self.zone_label.points
        if pts and len(pts) < 3:
            QMessageBox.warning(self, "تنبيه", "يجب رسم مضلع مغلق يحتوي على 3 نقاط (رؤوس) على الأقل.")
            return
            
        self.saved_points_json = json.dumps(pts)
        self.accept()

# -*- coding: utf-8 -*-
import os
import cv2
import logging
from PyQt5.QtCore import QThread, pyqtSignal, Qt
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, 
                             QCheckBox, QPushButton, QFormLayout, QGroupBox, 
                             QMessageBox, QStackedWidget, QWidget)
from PyQt5.QtGui import QImage, QPixmap

logger = logging.getLogger(__name__)

class ConnectionTester(QThread):
    """خيط مستقل لاختبار الاتصال برابط RTSP والتقاط إطار للمعاينة"""
    finished_test = pyqtSignal(bool, object, str)

    def __init__(self, rtsp_url: str):
        super().__init__()
        self.rtsp_url = rtsp_url

    def run(self):
        # مهلة اتصّال قصيرة 3 ثوانٍ
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp|stimeout;3000000"
        cap = cv2.VideoCapture(self.rtsp_url)
        if not cap.isOpened():
            self.finished_test.emit(False, None, "فشل فتح البث: لا يمكن الاتصال بالرابط.")
            return
        
        ret, frame = cap.read()
        cap.release()
        
        if ret:
            try:
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w, ch = rgb_frame.shape
                bytes_per_line = ch * w
                qimg = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format_RGB888).copy()
                self.finished_test.emit(True, qimg, "تم الاتصال بالبث بنجاح وجلب لقطة حية!")
            except Exception as e:
                self.finished_test.emit(False, None, f"خطأ في معالجة الصورة: {e}")
        else:
            self.finished_test.emit(False, None, "فشل التقاط صورة من البث: البث فارغ أو محمي.")

class CameraDialog(QDialog):
    """حوار إضافة وتعديل الكاميرا"""
    def __init__(self, camera_data=None, parent=None):
        super().__init__(parent)
        self.camera_data = camera_data or {}
        self.tester_thread = None
        self.init_ui()
        
    def init_ui(self):
        self.setWindowTitle("إعدادات الكاميرا" if self.camera_data else "إضافة كاميرا جديدة")
        self.resize(550, 650)
        self.setLayoutDirection(Qt.RightToLeft)
        
        # التنسيق الرئيسي
        layout = QVBoxLayout(self)
        
        # حقول الكاميرا العامة
        form_layout = QFormLayout()
        
        self.txt_name = QLineEdit()
        self.txt_name.setPlaceholderText("مثال: كاميرا المدخل الرئيسي")
        self.txt_name.setText(self.camera_data.get("name", ""))
        form_layout.addRow("اسم الكاميرا:", self.txt_name)
        
        self.txt_number = QLineEdit()
        self.txt_number.setPlaceholderText("مثال: 1 أو 01")
        self.txt_number.setText(self.camera_data.get("number", ""))
        form_layout.addRow("رقم الكاميرا:", self.txt_number)
        
        # طريقة الاتصال
        self.combo_conn_type = QComboBox()
        self.combo_conn_type.addItems(["رابط RTSP مباشر", "كاميرا Hikvision NVR/IP"])
        form_layout.addRow("نوع الاتصال:", self.combo_conn_type)
        
        layout.addLayout(form_layout)
        
        # محول المدخلات (الرابط المباشر مقابل هيكفيجن)
        self.stack_conn = QStackedWidget()
        
        # 1. واجهة الرابط المباشر
        self.widget_direct = QWidget()
        direct_layout = QVBoxLayout(self.widget_direct)
        direct_layout.setContentsMargins(0, 0, 0, 0)
        self.txt_rtsp_url = QLineEdit()
        self.txt_rtsp_url.setPlaceholderText("rtsp://<user>:<pass>@<ip>:<port>/h264/ch1/main/av_stream")
        self.txt_rtsp_url.setText(self.camera_data.get("rtsp_url", ""))
        direct_layout.addWidget(QLabel("رابط RTSP الكامل للمراقبة:"))
        direct_layout.addWidget(self.txt_rtsp_url)
        self.stack_conn.addWidget(self.widget_direct)
        
        # 2. واجهة هيكفيجن
        self.widget_hik = QWidget()
        hik_layout = QFormLayout(self.widget_hik)
        hik_layout.setContentsMargins(0, 0, 0, 0)
        
        self.txt_hik_ip = QLineEdit()
        self.txt_hik_ip.setPlaceholderText("عنوان IP الكاميرا على الشبكة المحلية")
        self.txt_hik_port = QLineEdit("554")
        self.txt_hik_user = QLineEdit()
        self.txt_hik_user.setPlaceholderText("اسم مستخدم الكاميرا")
        self.txt_hik_pass = QLineEdit()
        self.txt_hik_pass.setEchoMode(QLineEdit.Password)
        self.txt_hik_channel = QSpinBox()
        self.txt_hik_channel.setRange(1, 128)
        self.txt_hik_channel.setValue(1)
        self.combo_hik_stream = QComboBox()
        self.combo_hik_stream.addItems(["رئيسي (Main Stream)", "فرعي (Sub Stream)"])
        
        hik_layout.addRow("عنوان IP الكاميرا:", self.txt_hik_ip)
        hik_layout.addRow("المنفذ RTSP Port:", self.txt_hik_port)
        hik_layout.addRow("اسم المستخدم:", self.txt_hik_user)
        hik_layout.addRow("كلمة المرور:", self.txt_hik_pass)
        hik_layout.addRow("رقم القناة Channel:", self.txt_hik_channel)
        hik_layout.addRow("نوع البث Stream:", self.combo_hik_stream)
        
        self.stack_conn.addWidget(self.widget_hik)
        
        layout.addWidget(self.stack_conn)
        
        # ربط تغيرات النوع بالصفحات وتحديث الرابط تلقائياً
        self.combo_conn_type.currentIndexChanged.connect(self.on_conn_type_changed)
        
        # ربط تغير الحقول في هيكفيجن لتحديث الرابط تلقائياً
        self.txt_hik_ip.textChanged.connect(self.update_hik_rtsp_url)
        self.txt_hik_port.textChanged.connect(self.update_hik_rtsp_url)
        self.txt_hik_user.textChanged.connect(self.update_hik_rtsp_url)
        self.txt_hik_pass.textChanged.connect(self.update_hik_rtsp_url)
        self.txt_hik_channel.valueChanged.connect(self.update_hik_rtsp_url)
        self.combo_hik_stream.currentIndexChanged.connect(self.update_hik_rtsp_url)
        
        # إعدادات معالجة الحركة
        group_params = QGroupBox("بارامترات الكشف والحراسة")
        params_layout = QFormLayout(group_params)
        
        self.spin_enter = QSpinBox()
        self.spin_enter.setRange(1, 300)
        self.spin_enter.setValue(self.camera_data.get("enter_seconds", 4))
        params_layout.addRow("مدة استقرار التداخل للإنذار (ثواني):", self.spin_enter)
        
        self.spin_clip = QSpinBox()
        self.spin_clip.setRange(3, 600)
        self.spin_clip.setValue(self.camera_data.get("clip_seconds", 10))
        params_layout.addRow("مدة مقطع الفيديو (ثواني):", self.spin_clip)
        
        self.spin_conf = QDoubleSpinBox()
        self.spin_conf.setRange(0.1, 1.0)
        self.spin_conf.setSingleStep(0.05)
        self.spin_conf.setValue(self.camera_data.get("person_conf", 0.4))
        params_layout.addRow("ثقة كشف الأشخاص Person Conf:", self.spin_conf)
        
        self.spin_pre = QSpinBox()
        self.spin_pre.setRange(0, 30)
        self.spin_pre.setValue(self.camera_data.get("pre_buffer_seconds", 5))
        params_layout.addRow("التسجيل المسبق قبل الدخول (ثواني):", self.spin_pre)
        
        self.chk_enabled = QCheckBox("الكاميرا مفعلة وتعمل تلقائياً")
        self.chk_enabled.setChecked(bool(self.camera_data.get("enabled", 1)))
        params_layout.addRow("", self.chk_enabled)
        
        layout.addWidget(group_params)
        
        # قسم اختبار الاتصال والتقاط فريم
        self.lbl_preview = QLabel("اضغط على 'اختبار الاتصال' للتحقق من الرابط والتقاط صورة حية.")
        self.lbl_preview.setFixedSize(320, 180)
        self.lbl_preview.setStyleSheet("border: 1px solid #444; background: #222; color: #888;")
        self.lbl_preview.setAlignment(Qt.AlignCenter)
        self.lbl_preview.setScaledContents(True)
        
        preview_container = QHBoxLayout()
        preview_container.addStretch()
        preview_container.addWidget(self.lbl_preview)
        preview_container.addStretch()
        layout.addLayout(preview_container)
        
        # أزرار الحوار
        btn_layout = QHBoxLayout()
        
        self.btn_test = QPushButton("اختبار الاتصال ⚡")
        self.btn_test.clicked.connect(self.on_test_connection)
        btn_layout.addWidget(self.btn_test)
        
        btn_layout.addStretch()
        
        self.btn_save = QPushButton("حفظ الكاميرا ✅")
        self.btn_save.clicked.connect(self.on_save)
        btn_layout.addWidget(self.btn_save)
        
        btn_cancel = QPushButton("إلغاء ❌")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)
        
        layout.addLayout(btn_layout)
        
        # تحليل نوع الرابط عند الفتح لتحديد الواجهة المناسبة
        rtsp = self.camera_data.get("rtsp_url", "")
        if rtsp and "/Streaming/Channels/" in rtsp:
            self.combo_conn_type.setCurrentIndex(1)
            self.parse_hik_url(rtsp)
        else:
            self.combo_conn_type.setCurrentIndex(0)

    def on_conn_type_changed(self, index):
        self.stack_conn.setCurrentIndex(index)
        if index == 1:
            self.update_hik_rtsp_url()

    def update_hik_rtsp_url(self):
        """بناء رابط Hikvision RTSP ديناميكياً"""
        ip = self.txt_hik_ip.text().strip()
        port = self.txt_hik_port.text().strip()
        user = self.txt_hik_user.text().strip()
        pwd = self.txt_hik_pass.text()
        channel = self.txt_hik_channel.value()
        # 101 للمجرى الرئيسي و 102 للمجرى الفرعي لقناة 1
        stream = "01" if self.combo_hik_stream.currentIndex() == 0 else "02"
        channel_code = f"{channel}{stream}"
        
        credentials = f"{user}:{pwd}"
        url = f"rtsp://{credentials}@{ip}:{port}/Streaming/Channels/{channel_code}"
        self.txt_rtsp_url.setText(url)

    def parse_hik_url(self, url: str):
        """تحليل الرابط وتعبئة حقول هيكفيجن في حال تعديل كاميرا موجودة"""
        try:
            # rtsp://<user>:<pass>@<ip>:<port>/Streaming/Channels/101
            if not url.startswith("rtsp://"):
                return
            
            main_part = url[7:] # remove rtsp://
            if "@" not in main_part:
                return
            
            auth, host_path = main_part.split("@", 1)
            user, pwd = auth.split(":", 1)
            
            host, path = host_path.split("/", 1)
            if ":" in host:
                ip, port = host.split(":", 1)
            else:
                ip, port = host, "554"
                
            channel_code = path.split("/")[-1]
            channel = int(channel_code[:-2])
            stream_idx = 0 if channel_code.endswith("01") else 1
            
            self.txt_hik_ip.setText(ip)
            self.txt_hik_port.setText(port)
            self.txt_hik_user.setText(user)
            self.txt_hik_pass.setText(pwd)
            self.txt_hik_channel.setValue(channel)
            self.combo_hik_stream.setCurrentIndex(stream_idx)
        except Exception as e:
            logger.warning(f"تعذر تحليل رابط Hikvision: {e}")

    def on_test_connection(self):
        """تشغيل اختبار الاتصال بالخلفية بدون تجميد الواجهة"""
        url = self.txt_rtsp_url.text().strip()
        if not url:
            QMessageBox.warning(self, "خطأ", "يرجى إدخال رابط RTSP أو بيانات كاميرا Hikvision.")
            return
            
        self.btn_test.setEnabled(False)
        self.btn_test.setText("جاري الاختبار...")
        self.lbl_preview.setText("جاري محاولة الاتصال بالبث...")
        
        self.tester_thread = ConnectionTester(url)
        self.tester_thread.finished_test.connect(self.on_test_finished)
        self.tester_thread.start()

    def on_test_finished(self, success: bool, qimg: QImage, msg: str):
        self.btn_test.setEnabled(True)
        self.btn_test.setText("اختبار الاتصال ⚡")
        
        if success and qimg:
            pixmap = QPixmap.fromImage(qimg)
            self.lbl_preview.setPixmap(pixmap)
            QMessageBox.information(self, "نجاح", msg)
        else:
            self.lbl_preview.clear()
            self.lbl_preview.setText("فشل الاتصال بالبث.")
            QMessageBox.critical(self, "فشل الاتصال", msg)

    def on_save(self):
        """التحقق من صحة المدخلات وإغلاق الحوار مع إرجاع البيانات"""
        name = self.txt_name.text().strip()
        rtsp_url = self.txt_rtsp_url.text().strip()
        
        if not name:
            QMessageBox.warning(self, "تنبيه", "يرجى تحديد اسم للكاميرا.")
            return
        if not rtsp_url:
            QMessageBox.warning(self, "تنبيه", "يرجى تحديد رابط البث RTSP.")
            return
            
        # تجهيز مصفوفة البيانات لإعادتها إلى النافذة الحاضنة
        self.camera_data.update({
            "name": name,
            "number": self.txt_number.text().strip(),
            "rtsp_url": rtsp_url,
            "enabled": 1 if self.chk_enabled.isChecked() else 0,
            "enter_seconds": self.spin_enter.value(),
            "clip_seconds": self.spin_clip.value(),
            "person_conf": self.spin_conf.value(),
            "pre_buffer_seconds": self.spin_pre.value()
        })
        
        self.accept()

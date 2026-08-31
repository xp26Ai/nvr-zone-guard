# -*- coding: utf-8 -*-
import logging
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QGridLayout, QScrollArea, QFrame, 
                             QMessageBox, QSizePolicy)
from PyQt5.QtGui import QImage, QPixmap

import db
from camera_worker import CameraWorker
from camera_dialog import CameraDialog
from zone_editor import ZoneEditor

logger = logging.getLogger(__name__)

class CameraCard(QFrame):
    """بطاقة عرض كاميرا مستقلة تحتوي على المعاينة المباشرة وأزرار التحكم"""
    def __init__(self, camera_data: dict, parent=None):
        super().__init__(parent)
        self.camera_data = camera_data
        self.camera_id = camera_data['id']
        self.init_ui()

    def init_ui(self):
        self.setFrameShape(QFrame.StyledPanel)
        self.setObjectName("CameraCard")
        # ستايل بطاقة الكاميرا
        self.setStyleSheet("""
            #CameraCard {
                background-color: #1a1a1a;
                border: 2px solid #2d2d2d;
                border-radius: 10px;
            }
            #CameraCard:hover {
                border-color: #007acc;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # الرأس (الاسم، الرقم، لمبة الحالة)
        header_layout = QHBoxLayout()
        
        self.lbl_status_dot = QLabel()
        self.lbl_status_dot.setFixedSize(12, 12)
        self.set_status_dot("stopped")
        header_layout.addWidget(self.lbl_status_dot)
        
        self.lbl_title = QLabel(f"{self.camera_data['name']} (#{self.camera_data['number']})")
        self.lbl_title.setStyleSheet("font-weight: bold; font-size: 14px; color: #ffffff;")
        header_layout.addWidget(self.lbl_title, 1)
        
        self.lbl_status_text = QLabel("متوقف")
        self.lbl_status_text.setStyleSheet("color: #888888; font-size: 12px;")
        header_layout.addWidget(self.lbl_status_text)
        
        layout.addLayout(header_layout)
        
        # شاشة المعاينة
        self.lbl_preview = QLabel("البث متوقف")
        self.lbl_preview.setFixedSize(320, 180)
        self.lbl_preview.setAlignment(Qt.AlignCenter)
        self.lbl_preview.setStyleSheet("background-color: #0d0d0d; border-radius: 6px; color: #555555; font-size: 14px; border: 1px solid #252525;")
        self.lbl_preview.setScaledContents(True)
        layout.addWidget(self.lbl_preview, 0, Qt.AlignCenter)
        
        # شريط أزرار التحكم
        btn_layout = QHBoxLayout()
        
        self.btn_toggle = QPushButton("تشغيل ▶️")
        self.btn_toggle.setStyleSheet("background-color: #2e7d32; color: white; font-weight: bold; border-radius: 4px; padding: 5px;")
        btn_layout.addWidget(self.btn_toggle)
        
        self.btn_zone = QPushButton("المنطقة 📐")
        self.btn_zone.setStyleSheet("background-color: #37474f; color: white; border-radius: 4px; padding: 5px;")
        btn_layout.addWidget(self.btn_zone)
        
        self.btn_edit = QPushButton("تعديل 📝")
        self.btn_edit.setStyleSheet("background-color: #1565c0; color: white; border-radius: 4px; padding: 5px;")
        btn_layout.addWidget(self.btn_edit)
        
        self.btn_delete = QPushButton("حذف 🗑️")
        self.btn_delete.setStyleSheet("background-color: #c62828; color: white; border-radius: 4px; padding: 5px;")
        btn_layout.addWidget(self.btn_delete)
        
        layout.addLayout(btn_layout)

    def set_status_dot(self, state: str):
        """تحديث لون لمبة الحالة"""
        if state == "running":
            # أخضر
            self.lbl_status_dot.setStyleSheet("background-color: #4caf50; border-radius: 6px;")
        elif state == "connecting":
            # برتقالي
            self.lbl_status_dot.setStyleSheet("background-color: #ff9800; border-radius: 6px;")
        else:
            # أحمر
            self.lbl_status_dot.setStyleSheet("background-color: #f44336; border-radius: 6px;")


class CamerasPage(QWidget):
    """صفحة استعراض الكاميرات وإدارتها بالتوازي"""
    event_logged = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.workers = {}  # خيوط العمل النشطة {camera_id: CameraWorker}
        self.cards = {}    # كروت العرض الرسومية {camera_id: CameraCard}
        self.init_ui()

    def init_ui(self):
        self.setLayoutDirection(Qt.RightToLeft)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        
        # شريط الأدوات العلوي لقسم الكاميرات
        toolbar = QHBoxLayout()
        
        lbl_section = QLabel("لوحة تحكم الكاميرات 🎥")
        lbl_section.setStyleSheet("font-size: 18px; font-weight: bold; color: #ffffff;")
        toolbar.addWidget(lbl_section)
        
        toolbar.addStretch()
        
        self.btn_add_cam = QPushButton("إضافة كاميرا جديدة ➕")
        self.btn_add_cam.setStyleSheet("background-color: #007acc; color: white; font-weight: bold; padding: 8px 15px; border-radius: 5px;")
        self.btn_add_cam.clicked.connect(self.on_add_camera)
        toolbar.addWidget(self.btn_add_cam)
        
        self.btn_start_all = QPushButton("تشغيل الكل ▶️")
        self.btn_start_all.setStyleSheet("background-color: #2e7d32; color: white; font-weight: bold; padding: 8px 15px; border-radius: 5px;")
        self.btn_start_all.clicked.connect(self.on_start_all)
        toolbar.addWidget(self.btn_start_all)
        
        self.btn_stop_all = QPushButton("إيقاف الكل ⏹️")
        self.btn_stop_all.setStyleSheet("background-color: #c62828; color: white; font-weight: bold; padding: 8px 15px; border-radius: 5px;")
        self.btn_stop_all.clicked.connect(self.on_stop_all)
        toolbar.addWidget(self.btn_stop_all)
        
        main_layout.addLayout(toolbar)
        
        # منطقة تمرير شبكة الكاميرات
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background-color: transparent; border: none;")
        
        self.grid_widget = QWidget()
        self.grid_widget.setStyleSheet("background-color: transparent;")
        self.grid_layout = QGridLayout(self.grid_widget)
        self.grid_layout.setSpacing(15)
        
        scroll.setWidget(self.grid_widget)
        main_layout.addWidget(scroll, 1)
        
        # تحميل الكاميرات من قاعدة البيانات
        self.load_cameras()

    def load_cameras(self):
        """جلب الكاميرات من قاعدة البيانات وبناء الكروت الرسومية وإعادة ربط خيوط العمل"""
        # مسح الكروت الرسومية القديمة
        for card in self.cards.values():
            self.grid_layout.removeWidget(card)
            card.deleteLater()
        self.cards.clear()
        
        cameras = db.get_cameras()
        
        cols = 3  # عدد الكروت في الصف الواحد
        for index, cam in enumerate(cameras):
            cid = cam['id']
            card = CameraCard(cam, self)
            
            # ربط أزرار الكرت بالأحداث
            card.btn_toggle.clicked.connect(lambda checked, c=cid: self.toggle_camera(c))
            card.btn_zone.clicked.connect(lambda checked, c=cid: self.edit_zone(c))
            card.btn_edit.clicked.connect(lambda checked, c=cid: self.edit_camera(c))
            card.btn_delete.clicked.connect(lambda checked, c=cid: self.delete_camera(c))
            
            # تحديد الموقع بالشبكة
            row = index // cols
            col = index % cols
            self.grid_layout.addWidget(card, row, col)
            self.cards[cid] = card
            
            # في حال وجود خيط عمل شغال مسبقاً، أعد ربطه بالكرت الجديد
            if cid in self.workers and self.workers[cid].isRunning():
                worker = self.workers[cid]
                # فصل الإشارات القديمة لتفادي التكرار
                try:
                    worker.frame_ready.disconnect()
                    worker.status_changed.disconnect()
                    worker.event_logged.disconnect()
                except TypeError:
                    pass
                
                # ربط الإشارات بالكرت الجديد
                worker.frame_ready.connect(lambda qimg, c=cid: self.update_preview(c, qimg))
                worker.status_changed.connect(lambda status, c=cid: self.update_status(c, status))
                worker.event_logged.connect(self.forward_event)
                
                card.btn_toggle.setText("إيقاف ⏹️")
                card.btn_toggle.setStyleSheet("background-color: #c62828; color: white; font-weight: bold; border-radius: 4px; padding: 5px;")
                # تحديث اللمبة
                card.set_status_dot("running")
                card.lbl_status_text.setText("متصل - نشط")

    def toggle_camera(self, camera_id: int):
        """بدء أو إيقاف خيط المراقبة للكاميرا المعنية"""
        card = self.cards.get(camera_id)
        if not card:
            return
            
        if camera_id in self.workers and self.workers[camera_id].isRunning():
            # إيقاف تشغيل الكاميرا
            self.stop_worker(camera_id)
        else:
            # تشغيل الكاميرا
            self.start_worker(camera_id)

    def start_worker(self, camera_id: int):
        card = self.cards.get(camera_id)
        if not card:
            return
            
        # إنشاء وتشغيل الخيط
        try:
            worker = CameraWorker(camera_id, self)
            worker.frame_ready.connect(lambda qimg: self.update_preview(camera_id, qimg))
            worker.status_changed.connect(lambda status: self.update_status(camera_id, status))
            worker.event_logged.connect(self.forward_event)
            
            self.workers[camera_id] = worker
            worker.start()
            
            card.btn_toggle.setText("إيقاف ⏹️")
            card.btn_toggle.setStyleSheet("background-color: #c62828; color: white; font-weight: bold; border-radius: 4px; padding: 5px;")
        except Exception as e:
            logger.error(f"فشل تشغيل خيط الكاميرا: {e}")
            QMessageBox.critical(self, "خطأ تشغيل", f"لم نتمكن من تشغيل الكاميرا: {e}")

    def stop_worker(self, camera_id: int):
        card = self.cards.get(camera_id)
        if camera_id in self.workers:
            worker = self.workers[camera_id]
            worker.stop()
            self.workers.pop(camera_id)
            
        if card:
            card.btn_toggle.setText("تشغيل ▶️")
            card.btn_toggle.setStyleSheet("background-color: #2e7d32; color: white; font-weight: bold; border-radius: 4px; padding: 5px;")
            card.set_status_dot("stopped")
            card.lbl_status_text.setText("متوقف")
            card.lbl_preview.clear()
            card.lbl_preview.setText("البث متوقف")

    def update_preview(self, camera_id: int, qimg: QImage):
        """تحديث شاشة عرض المعاينة عند استقبال إطار جديد"""
        card = self.cards.get(camera_id)
        if card:
            pixmap = QPixmap.fromImage(qimg)
            card.lbl_preview.setPixmap(pixmap)

    def update_status(self, camera_id: int, status: str):
        """تحديث نصوص وألوان واجهة الكاميرا بناءً على حالتها"""
        card = self.cards.get(camera_id)
        if not card:
            return
            
        card.lbl_status_text.setText(status)
        
        if "نشط" in status or "تسجيل" in status or "حركة" in status:
            card.set_status_dot("running")
        elif "جاري" in status or "اتصال" in status:
            card.set_status_dot("connecting")
        else:
            card.set_status_dot("stopped")

    def forward_event(self, event_data: dict):
        """إعادة توجيه إشارة الحدث إلى النافذة الرئيسية لتحديث جدول التنبيهات"""
        self.event_logged.emit(event_data)

    def on_add_camera(self):
        """فتح حوار إضافة كاميرا جديدة وحفظها في قاعدة البيانات"""
        dialog = CameraDialog(parent=self)
        if dialog.exec_() == CameraDialog.Accepted:
            try:
                db.add_camera(dialog.camera_data)
                self.load_cameras()
                QMessageBox.information(self, "تمت الإضافة", "تمت إضافة الكاميرا الجديدة بنجاح.")
            except Exception as e:
                QMessageBox.critical(self, "خطأ", f"حدث خطأ أثناء حفظ الكاميرا: {e}")

    def edit_camera(self, camera_id: int):
        """تعديل بيانات الكاميرا مع إيقاف خيط المراقبة مؤقتاً لتطبيق الإعدادات الجديدة"""
        # جلب بيانات الكاميرا الحالية
        conn = db.get_db_connection()
        row = conn.execute("SELECT * FROM cameras WHERE id = ?", (camera_id,)).fetchone()
        conn.close()
        
        if not row:
            return
            
        camera_data = dict(row)
        
        # الاحتفاظ بحالة تشغيل الخيط
        was_running = camera_id in self.workers and self.workers[camera_id].isRunning()
        
        dialog = CameraDialog(camera_data=camera_data, parent=self)
        if dialog.exec_() == CameraDialog.Accepted:
            # إيقاف الخيط أولاً
            if was_running:
                self.stop_worker(camera_id)
                
            try:
                db.update_camera(camera_id, dialog.camera_data)
                self.load_cameras()
                
                # إعادة تشغيل الكاميرا بالإعدادات الجديدة
                if was_running or dialog.camera_data.get("enabled", 1):
                    self.start_worker(camera_id)
                    
                QMessageBox.information(self, "تم التعديل", "تم حفظ إعدادات الكاميرا بنجاح.")
            except Exception as e:
                QMessageBox.critical(self, "خطأ", f"حدث خطأ أثناء التحديث: {e}")

    def edit_zone(self, camera_id: int):
        """فتح محرر رسم المنطقة التفاعلي للكاميرا"""
        card = self.cards.get(camera_id)
        if not card:
            return
            
        # الاحتفاظ بحالة تشغيل الكاميرا
        was_running = camera_id in self.workers and self.workers[camera_id].isRunning()
        
        # إيقاف الخيط مؤقتاً لتجنب استهلاك الكاميرا لموارد البث أثناء الرسم
        if was_running:
            self.stop_worker(camera_id)
            
        # جلب تفاصيل الكاميرا الحالية
        conn = db.get_db_connection()
        row = conn.execute("SELECT name, rtsp_url, zone_points FROM cameras WHERE id = ?", (camera_id,)).fetchone()
        conn.close()
        
        if not row:
            return
            
        editor = ZoneEditor(
            camera_name=row['name'],
            rtsp_url=row['rtsp_url'],
            current_points_str=row['zone_points'] or "[]",
            parent=self
        )
        
        if editor.exec_() == ZoneEditor.Accepted:
            try:
                # تحديث نقاط المنطقة في قاعدة البيانات
                conn = db.get_db_connection()
                conn.execute("UPDATE cameras SET zone_points = ? WHERE id = ?", (editor.saved_points_json, camera_id))
                conn.commit()
                conn.close()
                QMessageBox.information(self, "تم الحفظ", "تم تحديث منطقة الحماية الأمنية للكاميرا.")
            except Exception as e:
                QMessageBox.critical(self, "خطأ", f"تعذر حفظ المنطقة: {e}")
                
        # إعادة تشغيل الكاميرا
        if was_running:
            self.start_worker(camera_id)

    def delete_camera(self, camera_id: int):
        """حذف الكاميرا نهائياً من النظام بعد التأكيد"""
        card = self.cards.get(camera_id)
        if not card:
            return
            
        reply = QMessageBox.question(
            self, "تأكيد الحذف", 
            f"هل أنت متأكد من رغبتك في حذف كاميرا '{card.camera_data['name']}' نهائياً؟\nسيؤدي هذا لحذف كافة سجلاتها.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # إيقاف المحرك
            self.stop_worker(camera_id)
            try:
                db.delete_camera(camera_id)
                self.load_cameras()
                QMessageBox.information(self, "تم الحذف", "تم إزالة الكاميرا بنجاح.")
            except Exception as e:
                QMessageBox.critical(self, "خطأ", f"فشل الحذف: {e}")

    def on_start_all(self):
        """تشغيل جميع الكاميرات المتاحة"""
        for cid in self.cards.keys():
            if cid not in self.workers:
                self.start_worker(cid)

    def on_stop_all(self):
        """إيقاف جميع خيوط العمل الشغالة"""
        active_ids = list(self.workers.keys())
        for cid in active_ids:
            self.stop_worker(cid)

    def stop_all_workers(self):
        """دالة عامة تُستدعى عند إغلاق التطبيق للتأكد من تنظيف كافة خيوط العمل"""
        self.on_stop_all()

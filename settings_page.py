# -*- coding: utf-8 -*-
import os
import logging
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QLineEdit, QPushButton, QTableWidget, QTableWidgetItem, 
                             QHeaderView, QMessageBox, QGroupBox, QFormLayout)

import db
from telegram_sender import send_telegram_message

logger = logging.getLogger(__name__)

class SettingsPage(QWidget):
    """صفحة الإعدادات العامة وسجل الأحداث الأمنية"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        self.load_settings()

    def init_ui(self):
        self.setLayoutDirection(Qt.RightToLeft)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)
        
        # العنوان
        lbl_title = QLabel("إعدادات النظام وسجل التنبيهات ⚙️")
        lbl_title.setStyleSheet("font-size: 18px; font-weight: bold; color: #ffffff;")
        main_layout.addWidget(lbl_title)
        
        # قسم إعدادات تيليجرام
        group_tg = QGroupBox("إعدادات الاتصال بـ Telegram Bot")
        tg_layout = QFormLayout(group_tg)
        
        self.txt_bot_token = QLineEdit()
        self.txt_bot_token.setPlaceholderText("أدخل Bot Token...")
        tg_layout.addRow("توكن البوت Token:", self.txt_bot_token)
        
        self.txt_chat_id = QLineEdit()
        self.txt_chat_id.setPlaceholderText("أدخل Chat ID...")
        tg_layout.addRow("معرف الدردشة Chat ID:", self.txt_chat_id)
        
        # أزرار حفظ واختبار تيليجرام
        tg_btn_layout = QHBoxLayout()
        self.btn_save_tg = QPushButton("حفظ إعدادات تيليجرام 💾")
        self.btn_save_tg.setStyleSheet("background-color: #007acc; color: white; font-weight: bold; padding: 6px 12px; border-radius: 4px;")
        self.btn_save_tg.clicked.connect(self.save_settings)
        tg_btn_layout.addWidget(self.btn_save_tg)
        
        self.btn_test_tg = QPushButton("إرسال رسالة اختبار ⚡")
        self.btn_test_tg.setStyleSheet("background-color: #37474f; color: white; padding: 6px 12px; border-radius: 4px;")
        self.btn_test_tg.clicked.connect(self.test_telegram)
        tg_btn_layout.addWidget(self.btn_test_tg)
        
        tg_btn_layout.addStretch()
        tg_layout.addRow("", tg_btn_layout)
        
        main_layout.addWidget(group_tg)
        
        # قسم سجل التنبيهات
        group_events = QGroupBox("سجل التنبيهات والأحداث الأخيرة")
        events_layout = QVBoxLayout(group_events)
        
        # شريط أزرار السجل
        events_bar = QHBoxLayout()
        self.btn_refresh = QPushButton("تحديث السجل 🔄")
        self.btn_refresh.setStyleSheet("background-color: #2e7d32; color: white; padding: 5px 10px; border-radius: 4px;")
        self.btn_refresh.clicked.connect(self.refresh_events)
        events_bar.addWidget(self.btn_refresh)
        
        lbl_hint = QLabel("نصيحة: انقر نقراً مزدوجاً على أي صف لفتح المجلد المحتوي على مقطع الفيديو.")
        lbl_hint.setStyleSheet("color: #888888; font-size: 11px;")
        events_bar.addStretch()
        events_bar.addWidget(lbl_hint)
        
        events_layout.addLayout(events_bar)
        
        # جدول الأحداث
        self.table_events = QTableWidget()
        self.table_events.setColumnCount(6)
        self.table_events.setHorizontalHeaderLabels(["المعرف", "توقيت الحدث", "اسم الكاميرا", "نوع الحدث", "مسار الفيديو", "حالة الإرسال"])
        self.table_events.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_events.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table_events.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.table_events.setStyleSheet("""
            QTableWidget {
                background-color: #1e1e1e;
                gridline-color: #2d2d2d;
                color: #ffffff;
                border-radius: 5px;
            }
            QHeaderView::section {
                background-color: #2d2d2d;
                color: white;
                padding: 6px;
                border: 1px solid #1a1a1a;
            }
            QTableWidget::item:selected {
                background-color: #007acc;
            }
        """)
        self.table_events.doubleClicked.connect(self.on_row_double_clicked)
        events_layout.addWidget(self.table_events)
        
        main_layout.addWidget(group_events, 1) # يأخذ السجل المساحة المتبقية

    def load_settings(self):
        """تحميل الإعدادات المخزنة بقاعدة البيانات"""
        bot_token = db.get_setting("telegram_bot_token", "")
        chat_id = db.get_setting("telegram_chat_id", "")
        self.txt_bot_token.setText(bot_token)
        self.txt_chat_id.setText(chat_id)
        self.refresh_events()

    def save_settings(self):
        """حفظ إعدادات تيليجرام بقاعدة البيانات"""
        token = self.txt_bot_token.text().strip()
        chat = self.txt_chat_id.text().strip()
        
        try:
            db.set_setting("telegram_bot_token", token)
            db.set_setting("telegram_chat_id", chat)
            QMessageBox.information(self, "تم الحفظ", "تم حفظ إعدادات تيليجرام بنجاح.")
        except Exception as e:
            QMessageBox.critical(self, "خطأ", f"حدث خطأ أثناء الحفظ: {e}")

    def test_telegram(self):
        """إرسال رسالة تجريبية فورية للتحقق من صحة التوكن والمعرف"""
        token = self.txt_bot_token.text().strip()
        chat = self.txt_chat_id.text().strip()
        
        if not token or not chat:
            QMessageBox.warning(self, "تنبيه", "يرجى تعبئة التوكن ومعرف الدردشة أولاً للاختبار.")
            return
            
        self.btn_test_tg.setEnabled(False)
        self.btn_test_tg.setText("جاري الإرسال...")
        
        success = send_telegram_message(token, chat, "🔔 رسالة اختبارية من نظام NVR Zone Guard الذكي لمراقبة الكاميرات.")
        
        self.btn_test_tg.setEnabled(True)
        self.btn_test_tg.setText("إرسال رسالة اختبار ⚡")
        
        if success:
            QMessageBox.information(self, "نجاح", "تم إرسال رسالة الاختبار بنجاح! يرجى التحقق من تطبيق تيليجرام.")
        else:
            QMessageBox.critical(self, "فشل", "فشل إرسال رسالة الاختبار. يرجى التأكد من التوكن ومعرف الدردشة ومن توفر اتصال بالإنترنت.")

    def refresh_events(self):
        """تحديث جدول سجل الأحداث بالبيانات الحالية من قاعدة البيانات"""
        try:
            events = db.get_events(limit=50)
            self.table_events.setRowCount(0)
            
            for row_idx, ev in enumerate(events):
                self.table_events.insertRow(row_idx)
                
                # إعداد العناصر
                item_id = QTableWidgetItem(str(ev['id']))
                item_id.setTextAlignment(Qt.AlignCenter)
                
                item_ts = QTableWidgetItem(str(ev['ts']))
                item_ts.setTextAlignment(Qt.AlignCenter)
                
                item_cam = QTableWidgetItem(str(ev['camera_name'] or f"كاميرا (ID: {ev['camera_id']})"))
                item_cam.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                
                item_type = QTableWidgetItem(str(ev['type']))
                item_type.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                
                item_path = QTableWidgetItem(str(ev['clip_path']))
                item_path.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                
                # حالة الإرسال
                sent_txt = "تم الإرسال ✅" if ev['sent_ok'] == 1 else "فشل / معلق ❌"
                item_sent = QTableWidgetItem(sent_txt)
                item_sent.setTextAlignment(Qt.AlignCenter)
                if ev['sent_ok'] == 1:
                    item_sent.setForeground(Qt.green)
                else:
                    item_sent.setForeground(Qt.red)
                    
                # إضافة للجدول
                self.table_events.setItem(row_idx, 0, item_id)
                self.table_events.setItem(row_idx, 1, item_ts)
                self.table_events.setItem(row_idx, 2, item_cam)
                self.table_events.setItem(row_idx, 3, item_type)
                self.table_events.setItem(row_idx, 4, item_path)
                self.table_events.setItem(row_idx, 5, item_sent)
                
        except Exception as e:
            logger.error(f"حدث خطأ أثناء تحديث جدول الأحداث: {e}")

    def on_row_double_clicked(self, index):
        """عند النقر المزدوج على صف، فتح مسار المجلد المحتوي على الفيديو المقطع"""
        row = index.row()
        path_item = self.table_events.item(row, 4)
        if path_item:
            clip_path = path_item.text()
            if clip_path and os.path.exists(clip_path):
                # فتح المجلد وتحديد الملف
                try:
                    abs_path = os.path.abspath(clip_path)
                    os.system(f'explorer /select,"{abs_path}"')
                except Exception as e:
                    logger.error(f"تعذر فتح مسار الملف: {e}")
            else:
                QMessageBox.warning(self, "غير موجود", "تعذر العثور على الملف المحلي، ربما تم حذفه بعد رفعه بنجاح لتيليجرام.")

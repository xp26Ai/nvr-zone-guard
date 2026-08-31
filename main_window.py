# -*- coding: utf-8 -*-
import logging
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtWidgets import (QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, 
                             QFrame, QPushButton, QStackedWidget, QLabel, 
                             QSpacerItem, QSizePolicy)
from PyQt5.QtGui import QIcon, QFont

from cameras_page import CamerasPage
from settings_page import SettingsPage

logger = logging.getLogger(__name__)

# الاستايل الاحترافي الداكن للنظام (QSS)
DARK_STYLESHEET = """
QMainWindow {
    background-color: #121212;
}
QWidget {
    font-family: 'Segoe UI', 'Tahoma', 'Arial', sans-serif;
    color: #e0e0e0;
    font-size: 13px;
}
#Sidebar {
    background-color: #181818;
    border-left: 1px solid #262626; /* خط فاصل لليمين لأن التوجيه RTL */
    min-width: 220px;
    max-width: 220px;
}
#SidebarTitle {
    color: #007acc;
    font-size: 18px;
    font-weight: bold;
    padding: 20px 10px;
    border-bottom: 1px solid #262626;
}
#VersionLabel {
    color: #555555;
    font-size: 11px;
    padding: 10px;
}
QPushButton {
    background-color: #262626;
    border: 1px solid #363636;
    border-radius: 4px;
    color: #ffffff;
    padding: 6px 14px;
    font-weight: bold;
}
QPushButton:hover {
    background-color: #333333;
    border-color: #007acc;
}
QPushButton:pressed {
    background-color: #005999;
}
/* أزرار السايدبار المخصصة */
QPushButton.NavButton {
    background-color: transparent;
    border: none;
    color: #aaaaaa;
    text-align: right;
    padding: 12px 15px;
    font-size: 14px;
    font-weight: normal;
    border-radius: 0px;
}
QPushButton.NavButton:hover {
    background-color: #222222;
    color: #ffffff;
}
QPushButton.NavButton[active="true"] {
    background-color: #1a2634;
    color: #007acc;
    font-weight: bold;
    border-right: 4px solid #007acc; /* خط تأكيد على اليمين في لغة RTL */
}
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background-color: #1e1e1e;
    border: 1px solid #333333;
    border-radius: 4px;
    padding: 6px;
    color: #ffffff;
}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
    border-color: #007acc;
}
QGroupBox {
    font-weight: bold;
    border: 1px solid #262626;
    border-radius: 6px;
    margin-top: 15px;
    padding-top: 15px;
    color: #ffffff;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top right; /* جهة اليمين للغة العربية */
    padding: 0 10px;
}
QScrollBar:vertical {
    border: none;
    background: #121212;
    width: 8px;
}
QScrollBar::handle:vertical {
    background: #2a2a2a;
    min-height: 20px;
    border-radius: 4px;
}
QScrollBar::handle:vertical:hover {
    background: #007acc;
}
"""

class MainWindow(QMainWindow):
    """النافذة الرئيسية للتطبيق وبها السايدبار والصفحات التراكمية"""
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("NVR Zone Guard 🛡️ - نظام المراقبة الذكي للمناطق الأمنية")
        self.resize(1200, 800)
        self.setLayoutDirection(Qt.RightToLeft)
        self.setStyleSheet(DARK_STYLESHEET)
        
        # حاوية رئيسية أفقية
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 1. السايدبار الجانبي (يسار)
        self.sidebar = QFrame()
        self.sidebar.setObjectName("Sidebar")
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)
        
        # عنوان السايدبار
        lbl_logo = QLabel("NVR Zone Guard 🛡️")
        lbl_logo.setObjectName("SidebarTitle")
        lbl_logo.setAlignment(Qt.AlignCenter)
        sidebar_layout.addWidget(lbl_logo)
        
        sidebar_layout.addSpacing(15)
        
        # أزرار التنقل
        self.btn_nav_cameras = QPushButton("🎥 شاشة المراقبة")
        self.btn_nav_cameras.setProperty("class", "NavButton")
        self.btn_nav_cameras.setProperty("active", True)
        self.btn_nav_cameras.clicked.connect(lambda: self.switch_page(0))
        sidebar_layout.addWidget(self.btn_nav_cameras)
        
        self.btn_nav_settings = QPushButton("⚙️ إعدادات النظام")
        self.btn_nav_settings.setProperty("class", "NavButton")
        self.btn_nav_settings.setProperty("active", False)
        self.btn_nav_settings.clicked.connect(lambda: self.switch_page(1))
        sidebar_layout.addWidget(self.btn_nav_settings)
        
        sidebar_layout.addStretch()
        
        # حاشية السايدبار
        lbl_version = QLabel("إصدار سطح المكتب v2.0")
        lbl_version.setObjectName("VersionLabel")
        lbl_version.setAlignment(Qt.AlignCenter)
        sidebar_layout.addWidget(lbl_version)
        
        main_layout.addWidget(self.sidebar)
        
        # 2. الصفحات المتراكمة (يمين)
        self.stacked_widget = QStackedWidget()
        
        self.cameras_page = CamerasPage(self)
        self.settings_page = SettingsPage(self)
        
        self.stacked_widget.addWidget(self.cameras_page)
        self.stacked_widget.addWidget(self.settings_page)
        
        main_layout.addWidget(self.stacked_widget, 1)
        
        # ربط أحداث الإطارات بالحدث لتحديث جدول التنبيهات في صفحة الإعدادات تلقائياً
        self.cameras_page.event_logged.connect(self.on_event_logged)

    def switch_page(self, index: int):
        """التبديل بين الصفحات وتحديث مظهر الأزرار بالسايدبار"""
        self.stacked_widget.setCurrentIndex(index)
        
        self.btn_nav_cameras.setProperty("active", index == 0)
        self.btn_nav_settings.setProperty("active", index == 1)
        
        # إجبار PyQt على إعادة رسم أسلوب الأزرار بعد تغيير الخاصية
        self.btn_nav_cameras.style().unpolish(self.btn_nav_cameras)
        self.btn_nav_cameras.style().polish(self.btn_nav_cameras)
        self.btn_nav_settings.style().unpolish(self.btn_nav_settings)
        self.btn_nav_settings.style().polish(self.btn_nav_settings)
        
        # في حال الانتقال لصفحة الإعدادات، قم بتحديث السجل تلقائياً
        if index == 1:
            self.settings_page.refresh_events()

    def on_event_logged(self, event_data: dict):
        """عند استلام حدث جديد من كاميرا، نقوم بتحديث السجل فوراً إذا كان مفتوحاً أو بالخلفية"""
        logger.info(f"تم استقبال إشارة حدث جديد: {event_data}")
        # نقوم بتحديث جدول الأحداث بصفحة الإعدادات بشكل مباشر
        self.settings_page.refresh_events()

    def closeEvent(self, event):
        """عند إغلاق التطبيق، نقوم بإيقاف جميع محركات الكاميرات وخيوط العمل لمنع تعليق البرنامج"""
        logger.info("جاري إغلاق التطبيق وتصفية خيوط العمل...")
        try:
            self.cameras_page.stop_all_workers()
        except Exception as e:
            logger.error(f"خطأ أثناء إيقاف خيوط العمل عند الخروج: {e}")
        event.accept()

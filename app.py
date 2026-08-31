# -*- coding: utf-8 -*-
# مهم: استيراد torch قبل PyQt5 لتفادي تعارض تحميل مكتبات DLL على ويندوز (WinError 1114).
import torch  # noqa: F401
import sys
import logging
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt

import db
from main_window import MainWindow

def setup_global_logging():
    """تهيئة المسجل العام للنظام لحفظ السجلات في ملف zone_guard.log وطباعتها"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("zone_guard.log", encoding="utf-8")
        ]
    )
    # تقليل سجلات مكتبة urllib3 وتيليجرام لعدم إغراق المخرجات
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)

def main():
    # 1. تهيئة السجلات
    setup_global_logging()
    logger = logging.getLogger("AppMain")
    logger.info("جاري بدء تشغيل تطبيق NVR Zone Guard...")

    # 2. تهيئة قاعدة البيانات واستيراد الإعدادات القديمة إن وجدت
    try:
        db.init_db()
        logger.info("تمت تهيئة قاعدة البيانات بنجاح.")
    except Exception as e:
        logger.critical(f"فشل تهيئة قاعدة البيانات: {e}")
        sys.exit(1)

    # 3. تشغيل واجهة المستخدم PyQt5
    app = QApplication(sys.argv)
    
    # دعم اللغة العربية والاتجاه من اليمين لليسار على مستوى التطبيق
    app.setLayoutDirection(Qt.RightToLeft)
    
    # إنشاء النافذة الرئيسية
    window = MainWindow()
    window.show()

    # تشغيل حلقة التطبيق
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
import os
import queue
import threading
import logging
import requests
import sqlite3
from typing import Optional

logger = logging.getLogger(__name__)

def send_telegram_message(bot_token: str, chat_id: str, text: str) -> bool:
    """إرسال رسالة نصية بسيطة إلى تيليجرام لاختبار الاتصال"""
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        data = {
            'chat_id': chat_id,
            'text': text
        }
        response = requests.post(url, data=data, timeout=10)
        if response.status_code == 200:
            logger.info("تم إرسال رسالة اختبار تيليجرام بنجاح.")
            return True
        else:
            logger.error(f"فشل إرسال رسالة الاختبار: {response.status_code}, {response.text}")
            return False
    except Exception as e:
        logger.error(f"خطأ أثناء إرسال رسالة الاختبار إلى تيليجرام: {e}")
        return False

class TelegramVideoSender:
    """
    إرسال مقاطع الفيديو الملتقطة إلى تيليجرام في خيط مستقل (Thread) لتجنب تجميد معالجة الفريمات.
    يقوم بتحديث حالة الإرسال في قاعدة البيانات وحذف الملف بعد الإرسال الناجح.
    """
    def __init__(self):
        self.queue = queue.Queue()
        self.thread = threading.Thread(target=self._worker, daemon=True)
        self.thread.start()

    def send_video(self, file_path: str, caption: str, event_id: int, bot_token: str, chat_id: str):
        """إضافة مقطع فيديو مع تفاصيل الإرسال إلى طابور الإرسال"""
        self.queue.put((file_path, caption, event_id, bot_token, chat_id))
        logger.info(f"تمت إضافة الفيديو {file_path} (حدث: {event_id}) إلى طابور إرسال تيليجرام.")

    def _worker(self):
        while True:
            file_path, caption, event_id, bot_token, chat_id = self.queue.get()
            try:
                if not bot_token or not chat_id:
                    logger.error(f"إعدادات تيليجرام غير صالحة للحدث {event_id}. إلغاء الإرسال.")
                    continue
                self._upload_video(file_path, caption, event_id, bot_token, chat_id)
            except Exception as e:
                logger.error(f"خطأ أثناء معالجة إرسال الفيديو {file_path}: {e}")
            finally:
                self.queue.task_done()

    def _upload_video(self, file_path: str, caption: str, event_id: int, bot_token: str, chat_id: str):
        if not os.path.exists(file_path):
            logger.error(f"الملف {file_path} غير موجود لإرساله.")
            return

        url = f"https://api.telegram.org/bot{bot_token}/sendVideo"
        logger.info(f"جاري إرسال الفيديو {file_path} إلى تيليجرام...")
        
        try:
            with open(file_path, 'rb') as video_file:
                files = {'video': video_file}
                data = {
                    'chat_id': chat_id,
                    'caption': caption
                }
                # إرسال الفيديو مع مهلة كافية
                response = requests.post(url, files=files, data=data, timeout=90)
                
            if response.status_code == 200:
                logger.info(f"تم إرسال الفيديو {file_path} بنجاح إلى تيليجرام للحدث {event_id}.")
                
                # تحديث حالة الإرسال في قاعدة البيانات
                self._update_event_sent_status(event_id, 1)
                
                # إزالة المقطع محلياً بعد الإرسال لتوفير المساحة
                try:
                    os.remove(file_path)
                    logger.info(f"تم حذف الملف المحلي {file_path} بعد إرساله بنجاح.")
                except Exception as e:
                    logger.warning(f"تعذر حذف الملف المحلي {file_path}: {e}")
            else:
                logger.error(f"فشل إرسال الفيديو للحدث {event_id}. رمز الحالة: {response.status_code}, الرد: {response.text}")
                self._update_event_sent_status(event_id, 0)
        except Exception as e:
            logger.error(f"حدث استثناء أثناء رفع الفيديو للحدث {event_id}: {e}")
            self._update_event_sent_status(event_id, 0)

    def _update_event_sent_status(self, event_id: int, sent_ok: int):
        """تحديث حقل sent_ok في قاعدة البيانات للحدث"""
        try:
            from db import DB_PATH
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("UPDATE events SET sent_ok = ? WHERE id = ?", (sent_ok, event_id))
            conn.commit()
            conn.close()
            logger.info(f"تم تحديث حالة الحدث {event_id} في قاعدة البيانات إلى sent_ok={sent_ok}.")
        except Exception as e:
            logger.error(f"فشل تحديث حالة الحدث {event_id} في قاعدة البيانات: {e}")

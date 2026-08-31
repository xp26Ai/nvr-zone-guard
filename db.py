# -*- coding: utf-8 -*-
import os
import sqlite3
import json
import logging
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)

DB_PATH = "data.db"

def get_db_connection() -> sqlite3.Connection:
    """إنشاء اتصال بقاعدة بيانات SQLite"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """تهيئة قاعدة البيانات وإنشاء الجداول إذا لم تكن موجودة، واستيراد config.json القديم إن وجد"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # جدول الكاميرات
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS cameras (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        number TEXT,
        rtsp_url TEXT NOT NULL,
        enabled INTEGER DEFAULT 1,
        zone_points TEXT, -- JSON array of points [[x, y], ...]
        enter_seconds INTEGER DEFAULT 4,
        clip_seconds INTEGER DEFAULT 10,
        person_conf REAL DEFAULT 0.4,
        pre_buffer_seconds INTEGER DEFAULT 5
    )
    """)
    
    # جدول الإعدادات العامة
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)
    
    # جدول الأحداث والتنبيهات
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        camera_id INTEGER,
        ts TEXT,
        type TEXT,
        clip_path TEXT,
        sent_ok INTEGER,
        FOREIGN KEY (camera_id) REFERENCES cameras (id) ON DELETE CASCADE
    )
    """)
    
    conn.commit()
    
    # استيراد إعدادات config.json القديمة لمرة واحدة فقط
    cursor.execute("SELECT value FROM settings WHERE key = 'config_imported'")
    imported = cursor.fetchone()
    
    if not imported:
        config_path = "config.json"
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                
                # استخراج القيم
                rtsp_url = config_data.get("rtsp_url", "")
                token = config_data.get("telegram_bot_token", "")
                chat_id = config_data.get("telegram_chat_id", "")
                zone_pts = config_data.get("zone_points", [])
                
                # حفظ إعدادات تيليجرام
                if token:
                    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('telegram_bot_token', ?)", (token,))
                if chat_id:
                    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('telegram_chat_id', ?)", (chat_id,))
                
                # إنشاء الكاميرا الأولى
                if rtsp_url:
                    cursor.execute("""
                    INSERT INTO cameras (name, number, rtsp_url, enabled, zone_points, enter_seconds, clip_seconds, person_conf, pre_buffer_seconds)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        "الكاميرا المستوردة", 
                        "1", 
                        rtsp_url, 
                        1, 
                        json.dumps(zone_pts),
                        config_data.get("enter_seconds", 4),
                        config_data.get("clip_seconds", 10),
                        config_data.get("person_conf", 0.4),
                        config_data.get("pre_buffer_seconds", 5)
                    ))
                
                logger.info("تم استيراد الإعدادات من config.json القديم بنجاح.")
            except Exception as e:
                logger.error(f"حدث خطأ أثناء استيراد الملف config.json: {e}")
        
        # وضع علامة الاستيراد لمنع التكرار
        cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('config_imported', '1')")
        conn.commit()
        
    conn.close()

# --- عمليات CRUD للكاميرات ---

def get_cameras() -> List[Dict[str, Any]]:
    """جلب جميع الكاميرات من قاعدة البيانات"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM cameras")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def add_camera(camera_data: Dict[str, Any]) -> int:
    """إضافة كاميرا جديدة وإرجاع المعرف الخاص بها"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO cameras (name, number, rtsp_url, enabled, zone_points, enter_seconds, clip_seconds, person_conf, pre_buffer_seconds)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        camera_data.get("name"),
        camera_data.get("number"),
        camera_data.get("rtsp_url"),
        camera_data.get("enabled", 1),
        camera_data.get("zone_points", "[]"),
        camera_data.get("enter_seconds", 4),
        camera_data.get("clip_seconds", 10),
        camera_data.get("person_conf", 0.4),
        camera_data.get("pre_buffer_seconds", 5)
    ))
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    return new_id

def update_camera(camera_id: int, camera_data: Dict[str, Any]):
    """تحديث بيانات كاميرا موجودة"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE cameras
    SET name = ?, number = ?, rtsp_url = ?, enabled = ?, zone_points = ?, 
        enter_seconds = ?, clip_seconds = ?, person_conf = ?, pre_buffer_seconds = ?
    WHERE id = ?
    """, (
        camera_data.get("name"),
        camera_data.get("number"),
        camera_data.get("rtsp_url"),
        camera_data.get("enabled", 1),
        camera_data.get("zone_points", "[]"),
        camera_data.get("enter_seconds", 4),
        camera_data.get("clip_seconds", 10),
        camera_data.get("person_conf", 0.4),
        camera_data.get("pre_buffer_seconds", 5),
        camera_id
    ))
    conn.commit()
    conn.close()

def delete_camera(camera_id: int):
    """حذف كاميرا من قاعدة البيانات"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM cameras WHERE id = ?", (camera_id,))
    conn.commit()
    conn.close()

# --- عمليات الإعدادات ---

def get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    """جلب قيمة إعداد معين"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return row['value']
    return default

def set_setting(key: str, value: str):
    """حفظ أو تحديث إعداد معين"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()

# --- عمليات الأحداث ---

def add_event(camera_id: int, ts: str, type_: str, clip_path: str, sent_ok: int) -> int:
    """تسجيل حدث جديد في قاعدة البيانات"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO events (camera_id, ts, type, clip_path, sent_ok)
    VALUES (?, ?, ?, ?, ?)
    """, (camera_id, ts, type_, clip_path, sent_ok))
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    return new_id

def get_events(limit: int = 50) -> List[Dict[str, Any]]:
    """جلب آخر الأحداث المسجلة مع اسم الكاميرا"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT events.*, cameras.name as camera_name 
    FROM events 
    LEFT JOIN cameras ON events.camera_id = cameras.id
    ORDER BY events.id DESC 
    LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

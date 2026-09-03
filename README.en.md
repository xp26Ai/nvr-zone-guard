# nvr-zone-guard

[العربية](README.md)

**An RTSP camera stream goes in. A video clip of the intrusion lands in Telegram.**

A PyQt5 desktop app built on OpenCV and YOLOv8. It is 2,273 lines of Python across 12 files. It opens several NVR cameras at once, each one in its own `QThread`. For each camera it checks if a person's feet are inside a guard polygon.

It ran for 3 days on two cameras. The dwell counter started 138 times. It wrote 21 clips. The filter dropped everything else.

---

## The problem

Motion detection on commercial NVRs alarms on anything that moves. A cat, a shadow, a branch, a change in light.

The alerts become noise, so the operator turns them off. A camera with no alarm is a camera that is off.

I needed a filter. It must separate "something moved in the frame" from "a person entered the guarded area and stayed there."

---

## How it works

| Module | What it does |
|---|---|
| `camera_worker.py` | One `QThread` per camera. It reads the stream, detects, draws, and records. The UI never freezes |
| `detector.py` | YOLOv8n limited to COCO class 0 (person) only, confidence threshold 0.4 |
| `zone.py` | `cv2.pointPolygonTest` on the **bottom-center of the box**, where the feet touch the ground |
| `recorder.py` | A `deque` ring buffer keeps the last 5 seconds. It writes them at the head of the clip |
| `telegram_sender.py` | Upload queue on its own thread. It sets `sent_ok` in SQLite and deletes the file after success |
| `db.py` | SQLite: `cameras`, `events`, `settings` tables. Each camera has its own polygon and thresholds |

**RTSP over TCP:** I use `rtsp_transport;tcp` instead of the default UDP. UDP drops packets. That gives torn frames, and the detector reads them wrong. **Recovery:** over 3 days the stream dropped 384 times. Automatic reconnect worked 381 times. I did nothing by hand.

---

## The key design decision

A simple alarm has one condition: "the pixels changed." That is where the noise comes from.

**The decision: an alarm needs three conditions together.**

1. The object is a **person**. This is a YOLOv8 classification, not a pixel diff.
2. **Its feet are inside the polygon.** I use the ground contact point, not the center of the box. A person outside the fence does not trigger the alarm. His head can show in the frame. It changes nothing.
3. **It stayed 4 continuous seconds.** Quick crossings and short flickers fall out.

Measured over 3 days: the counter started 138 times. The clips were 21. The filter dropped 84% of detections before they became an alarm.

**The cost:** the dwell condition gives 4 blind seconds at the start of every event. Those four seconds matter most. They are the entry itself.

**The payment:** the ring buffer holds frames all the time. On an alarm, the recorder writes them to the file first. In the log below: 100 buffered frames before recording starts. The clip starts before the entry, not four seconds after it.

**A supporting decision:** the recorder writes the clip at the measured FPS, not a fixed value. Real processing ran between 6.17 and 7.26 frames per second. The default is 10.0. At that speed the clip would show the intrusion 1.5x faster than real life.

---

## The edge version

The same logic runs on an ESP32-S3 with a camera. It is 549 lines of C++ on ESP-IDF 5.x, in the `edge/` folder.

| Difference | Desktop (PyQt5) | Edge (ESP32-S3) |
|---|---|---|
| Detection | YOLOv8n, the whole body | `HumanFaceDetect` from esp-dl, the face only |
| Polygon | `cv2.pointPolygonTest` | Hand-written ray casting, 18 lines |
| Dwell | `enter_seconds` = 4 | `DWELL_MS` = 4000 |
| Alert | MP4 clip with pre-roll | A single JPEG snapshot, 30-second cooldown |
| Source | NVR stream over the network | Sensor attached to the board, QVGA 320×240 |

The known limit: face detection fails if the intruder turns his back. The full version detects the body. The board is cheaper and less accurate.

---

## Running it

```bash
pip install -r requirements.txt
cp config.example.json config.json      # fill in the values, do not commit it
python app.py
```

For the edge build: copy `edge/main/config.h.example` to `edge/main/config.h`. Fill in its values, then run `idf.py build flash`. `.gitignore` blocks the real file.

| Setting | Default | Meaning |
|---|---|---|
| `enter_seconds` | 4 | Seconds of continuous dwell before the alarm |
| `pre_buffer_seconds` | 5 | Seconds before entry kept in the ring buffer |
| `clip_seconds` | 10 | Clip length. Then it rotates and sends the previous clip |
| `person_conf` | 0.4 | Minimum confidence to accept a detection as a person |

A real run log. Note the reject at 20:48:34 and the accept exactly 4 seconds later:

```
20:48:33,847 - ZoneGuard - INFO - تم الكشف عن حركة شخص داخل المنطقة الأمنية. بدء العداد المسبق...
20:48:34,029 - ZoneGuard - INFO - خلت المنطقة من الأشخاص. إيقاف التسجيل...
20:48:35,051 - ZoneGuard - INFO - تم الكشف عن حركة شخص داخل المنطقة الأمنية. بدء العداد المسبق...
20:48:39,064 - recorder  - INFO - بدأ تسجيل المقطع الأمني الجديد: clips\clip_1781632119.mp4
20:48:39,064 - recorder  - INFO - كتابة 100 إطاراً من الذاكرة الدائرية قبل الدخول الفعلي...
20:48:39,761 - ZoneGuard - INFO - تجاوز التداخل 4 ثوانٍ متواصلة. تم تفعيل كتابة المقطع الأمني.
20:48:49,169 - recorder  - INFO - تم إغلاق ملف التسجيل وحفظه في: clips\clip_1781632119.mp4
```

Across those three days: 21 uploads to Telegram, zero failures.

---

## Why I built it

I work as an IT supervisor, and I run surveillance cameras that alarm on every shadow.

I built the filter that dropped 84% of the alarms, so the alerts stayed readable.

# nvr-zone-guard

[العربية](README.md)

**An RTSP camera stream goes in. A video clip of the intrusion lands in Telegram.**

A PyQt5 desktop app built on OpenCV and YOLOv8 (2,273 lines of Python across 12 files). It opens several NVR cameras at once, each in its own `QThread`, and tests where a person's feet are against a guard polygon drawn for that one camera.

It ran for 3 days on two cameras: the dwell counter started 138 times, and 21 clips were written. Everything else died in the filter.

---

## The problem

Motion detection on commercial NVRs alarms on anything that moves: a cat, a shadow, a branch, a shift in light.

The alerts turn into noise, so the operator switches them off. A camera with no alarm is a camera that is off.

What is needed is a filter that separates "something moved in the frame" from "a person entered the guarded area and stayed there."

---

## How it works

| Module | What it does |
|---|---|
| `camera_worker.py` | One `QThread` per camera: read the stream, detect, draw, record. The UI never freezes |
| `detector.py` | YOLOv8n restricted to COCO class 0 (person) only, confidence threshold 0.4 |
| `zone.py` | `cv2.pointPolygonTest` on the **bottom-center of the box** — where the feet touch the ground |
| `recorder.py` | A `deque` ring buffer holding the last 5 seconds, written at the head of the clip |
| `telegram_sender.py` | Upload queue on its own thread; sets `sent_ok` in SQLite and deletes the file after success |
| `db.py` | SQLite: `cameras`, `events`, `settings` tables. Every camera carries its own polygon and thresholds |

**RTSP over TCP:** `rtsp_transport;tcp` instead of the default UDP, because UDP drops packets and produces torn frames that fool the detector. **Recovery:** over 3 days the stream dropped 384 times, and automatic reconnect succeeded 381 times. Zero manual intervention.

---

## The key design decision

A naive alarm has one condition: "the pixels changed." That is where the noise comes from.

**The decision: an alarm requires three conditions together.**

1. The object is a **person** — a YOLOv8 classification, not a pixel diff.
2. **Its feet are inside the polygon** — the ground contact point, not the center of the box. Someone standing outside the fence whose head shows up in the frame does not trigger.
3. **It stayed 4 continuous seconds** — quick crossings and momentary flickers fall out.

Measured over 3 days: the counter started 138 times, the clips numbered 21. The filter dropped 84% of detections before they became an alarm.

**The cost:** the dwell condition means 4 blind seconds at the start of every event — and those are the four seconds that matter most: the entry itself.

**The payment:** the ring buffer holds frames all the time. On an alarm they are written to the file first. In the log below: 100 buffered frames before recording starts. The clip begins before the entry, not four seconds after it.

**A supporting decision:** the clip is written at the FPS actually measured, not a fixed value. Real processing ranged between 6.17 and 7.26 frames per second, while the default is 10.0 — writing at that speed would show the intrusion 1.5x faster than reality.

---

## The edge version

The same logic on an ESP32-S3 with a camera: 549 lines of C++ on ESP-IDF 5.x, in the `edge/` folder.

| Difference | Desktop (PyQt5) | Edge (ESP32-S3) |
|---|---|---|
| Detection | YOLOv8n — the whole body | `HumanFaceDetect` from esp-dl — the face only |
| Polygon | `cv2.pointPolygonTest` | Hand-written ray casting, 18 lines |
| Dwell | `enter_seconds` = 4 | `DWELL_MS` = 4000 |
| Alert | MP4 clip with pre-roll | A single JPEG snapshot, 30-second cooldown |
| Source | NVR stream over the network | Sensor attached to the board, QVGA 320×240 |

The stated limit: face detection fails if the intruder turns his back. The full version detects the body. The board is cheaper and less accurate.

---

## Running it

```bash
pip install -r requirements.txt
cp config.example.json config.json      # fill in the values, do not commit it
python app.py
```

For the edge build: copy `edge/main/config.h.example` to `edge/main/config.h`, fill in its values, then `idf.py build flash`. The real file is excluded in `.gitignore`.

| Setting | Default | Meaning |
|---|---|---|
| `enter_seconds` | 4 | Seconds of continuous dwell before the alarm |
| `pre_buffer_seconds` | 5 | Seconds before entry kept in the ring buffer |
| `clip_seconds` | 10 | Clip length before it rotates and the previous one is sent |
| `person_conf` | 0.4 | Minimum confidence to accept a detection as a person |

A real run log — note the rejection at 20:48:34 and the acceptance exactly 4 seconds later:

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

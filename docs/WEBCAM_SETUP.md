# Connecting a Webcam to AetherShield

## Fastest way (UI)

1. Start the app (`start.bat` or backend + frontend).
2. Login as **admin** (`admin@aethershield.io` / `admin123`).
3. Open **Cameras** in the left sidebar.
4. Click **Detect webcams** → pick an index that says Available (usually `0`).
5. Click **Connect webcam**.
6. Open **Live View** — your webcam appears with YOLO overlays.

## Windows tips

- Grant camera permission when Windows prompts.
- Close **Zoom / Teams / Camera** if OpenCV cannot open the device.
- Built-in laptop cams are almost always index `0`.
- External USB cams may be index `1`.

## RTSP / IP camera

On the Cameras page, paste:

```text
rtsp://username:password@192.168.1.10:554/stream1
```

## API (optional)

```http
POST /api/advanced/webcam/connect?index=0&name=Desk%20Cam
Authorization: Bearer <token>
```

## What AI does on webcam

- Person / vehicle / etc. (YOLOv11)
- Face match against enrolled known / blacklist
- License plate OCR when a vehicle is seen (EasyOCR if installed)
- Activity heatmap builds as detections accumulate
- Critical alerts toast live over WebSocket

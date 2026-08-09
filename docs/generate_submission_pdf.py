"""Generate A-1 Launchpad 2026 — 3-page professional case study PDF."""

from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, inch
from reportlab.lib.colors import HexColor, white, black
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether, ListFlowable, ListItem, PageBreak,
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

OUT = Path(__file__).resolve().parents[1] / "docs" / "TeamName_CollegeName_A-1Launchpad_2026.pdf"
OUT.parent.mkdir(parents=True, exist_ok=True)

# Brand palette — enterprise teal/slate (not purple AI cliché)
INK = HexColor("#0f172a")
MUTED = HexColor("#475569")
ACCENT = HexColor("#0d9488")
ACCENT_DARK = HexColor("#0f766e")
LINE = HexColor("#cbd5e1")
SOFT = HexColor("#f1f5f9")
SOFT2 = HexColor("#e2e8f0")
WHITE = white


def header_footer(canvas, doc):
    canvas.saveState()
    w, h = A4
    # top rule
    canvas.setStrokeColor(ACCENT)
    canvas.setLineWidth(2.2)
    canvas.line(18 * mm, h - 12 * mm, w - 18 * mm, h - 12 * mm)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(MUTED)
    canvas.drawString(18 * mm, h - 10 * mm, "AetherShield VMS  ·  A-1 Launchpad 2026")
    canvas.drawRightString(w - 18 * mm, h - 10 * mm, "Smart Video Management System")
    # bottom
    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(0.6)
    canvas.line(18 * mm, 14 * mm, w - 18 * mm, 14 * mm)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(MUTED)
    canvas.drawString(18 * mm, 9 * mm, "Confidential — Academic Submission")
    canvas.drawRightString(w - 18 * mm, 9 * mm, f"Page {doc.page} of 3")
    canvas.restoreState()


def styles():
    return {
        "h1": ParagraphStyle(
            "h1", fontName="Helvetica-Bold", fontSize=16, textColor=INK,
            spaceAfter=6, spaceBefore=2, leading=20,
        ),
        "h2": ParagraphStyle(
            "h2", fontName="Helvetica-Bold", fontSize=11, textColor=ACCENT_DARK,
            spaceBefore=10, spaceAfter=4, leading=14,
        ),
        "h3": ParagraphStyle(
            "h3", fontName="Helvetica-Bold", fontSize=9.5, textColor=INK,
            spaceBefore=6, spaceAfter=2, leading=12,
        ),
        "body": ParagraphStyle(
            "body", fontName="Helvetica", fontSize=9, textColor=INK,
            alignment=TA_JUSTIFY, leading=12.5, spaceAfter=4,
        ),
        "small": ParagraphStyle(
            "small", fontName="Helvetica", fontSize=8, textColor=MUTED,
            leading=11, spaceAfter=2,
        ),
        "bullet": ParagraphStyle(
            "bullet", fontName="Helvetica", fontSize=9, textColor=INK,
            leading=12, leftIndent=8, spaceAfter=1.5,
        ),
        "center": ParagraphStyle(
            "center", fontName="Helvetica", fontSize=9, textColor=MUTED,
            alignment=TA_CENTER, leading=12,
        ),
        "label": ParagraphStyle(
            "label", fontName="Helvetica-Bold", fontSize=8, textColor=ACCENT_DARK,
            leading=10,
        ),
        "mono": ParagraphStyle(
            "mono", fontName="Courier", fontSize=7.5, textColor=INK, leading=10,
        ),
        "video": ParagraphStyle(
            "video", fontName="Helvetica-Bold", fontSize=9, textColor=ACCENT_DARK,
            alignment=TA_CENTER, leading=12, spaceBefore=4, spaceAfter=4,
        ),
    }


def section_rule():
    return HRFlowable(width="100%", thickness=0.6, color=LINE, spaceBefore=2, spaceAfter=6)


def kv_table(rows, col_widths):
    data = [[Paragraph(a, styles()["label"]), Paragraph(b, styles()["small"])] for a, b in rows]
    t = Table(data, colWidths=col_widths)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), SOFT),
        ("BACKGROUND", (1, 0), (1, -1), WHITE),
        ("BOX", (0, 0), (-1, -1), 0.5, LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


def feature_grid(items):
    """2-column feature cards."""
    s = styles()
    cells = []
    row = []
    for title, desc in items:
        block = [
            Paragraph(title, s["h3"]),
            Paragraph(desc, s["small"]),
        ]
        inner = Table([[block[0]], [block[1]]], colWidths=[85 * mm])
        inner.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), SOFT),
            ("BOX", (0, 0), (-1, -1), 0.5, LINE),
            ("LEFTPADDING", (0, 0), (-1, -1), 7),
            ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        row.append(inner)
        if len(row) == 2:
            cells.append(row)
            row = []
    if row:
        row.append("")
        cells.append(row)
    t = Table(cells, colWidths=[88 * mm, 88 * mm])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    return t


def build():
    s = styles()
    doc = SimpleDocTemplate(
        str(OUT),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title="AetherShield VMS — A-1 Launchpad 2026 Case Study",
        author="AetherShield Team",
    )
    story = []

    # ═══════════════ PAGE 1 ═══════════════
    story.append(Paragraph("Smart Video Management System (VMS)", s["h1"]))
    story.append(Paragraph(
        "<b>AetherShield</b> — Enterprise-grade AI surveillance platform for live monitoring, "
        "intelligent event detection, and timeline-linked investigation.",
        s["body"],
    ))
    story.append(section_rule())

    story.append(Paragraph("1. Problem Context", s["h2"]))
    story.append(Paragraph(
        "Traditional CCTV workflows separate live monitoring from recorded playback, forcing operators "
        "to switch tools during incidents and manually scrub hours of footage. False alerts from "
        "unbounded motion detection further degrade response quality. This case study required a unified "
        "prototype that combines live feeds, historical playback, AI intrusion/motion detection, "
        "configurable detection zones, timeline navigation, an event list, and an operations dashboard.",
        s["body"],
    ))

    story.append(Paragraph("2. Solution Overview", s["h2"]))
    story.append(Paragraph(
        "<b>AetherShield VMS</b> is a full-stack prototype inspired by commercial platforms "
        "(Verkada, Eagle Eye Networks, Milestone). Operators monitor multi-camera live grids, "
        "investigate via a colored AI event timeline, draw detection zones with sensitivity controls, "
        "and jump from any event to the exact recording window (−10s / +20s). Beyond the brief, the "
        "system adds natural-language search, face &amp; plate intelligence, incident workflow, "
        "heatmaps, PDF reports, and role-based access — while remaining runnable locally for demos.",
        s["body"],
    ))

    # Video placeholder box
    video_data = [[Paragraph(
        "VIDEO DEMONSTRATION LINK<br/><font color='#0d9488'><b>[ INSERT YOUR VIDEO URL HERE ]</b></font><br/>"
        "<font size='7.5' color='#475569'>Paste the Unstop / YouTube / Drive link before final submission.</font>",
        s["video"],
    )]]
    vt = Table(video_data, colWidths=[174 * mm])
    vt.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), HexColor("#ecfdf5")),
        ("BOX", (0, 0), (-1, -1), 1.2, ACCENT),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(Spacer(1, 4))
    story.append(vt)
    story.append(Spacer(1, 4))

    story.append(Paragraph("3. System Architecture", s["h2"]))
    story.append(Paragraph(
        "Cameras (sample files, laptop webcam, RTSP/HTTP remote devices) feed parallel pipelines: "
        "<b>live MJPEG streaming</b> for the operator UI, and an <b>AI detection worker</b> "
        "(YOLOv11 + ByteTrack) that writes structured events to SQLite. A timeline generator indexes "
        "events by camera and timestamp. The React dashboard consumes REST + WebSocket alerts for "
        "real-time operations. Recordings are segmented MP4 files with metadata for seek/replay.",
        s["body"],
    ))

    arch_rows = [
        ["Layer", "Technology"],
        ["Frontend", "React 19, TypeScript, Vite, Tailwind CSS, Recharts, Zustand"],
        ["Backend", "FastAPI (Python), SQLAlchemy, JWT + RBAC (Admin / Operator / Viewer)"],
        ["AI / Vision", "Ultralytics YOLOv11n, ByteTrack, OpenCV zones, face match, plate OCR"],
        ["Media", "OpenCV capture → MJPEG live + MP4 segment recording"],
        ["Data", "SQLite (Postgres-ready), local storage for clips/snapshots"],
        ["Deploy", "Docker Compose ready; local Windows start scripts for demos"],
    ]
    arch = Table(
        [[Paragraph(f"<b>{r[0]}</b>", s["small"]), Paragraph(r[1], s["small"])] for r in arch_rows],
        colWidths=[32 * mm, 142 * mm],
    )
    arch.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), INK),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("BACKGROUND", (0, 1), (-1, -1), WHITE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, SOFT]),
        ("BOX", (0, 0), (-1, -1), 0.6, LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    # Fix header row - first row needs white text via Paragraph
    arch_rows_p = []
    for i, r in enumerate(arch_rows):
        if i == 0:
            arch_rows_p.append([
                Paragraph(f"<font color='white'><b>{r[0]}</b></font>", s["small"]),
                Paragraph(f"<font color='white'><b>{r[1]}</b></font>", s["small"]),
            ])
        else:
            arch_rows_p.append([
                Paragraph(f"<b>{r[0]}</b>", s["small"]),
                Paragraph(r[1], s["small"]),
            ])
    arch = Table(arch_rows_p, colWidths=[32 * mm, 142 * mm])
    arch.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), INK),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, SOFT]),
        ("BOX", (0, 0), (-1, -1), 0.6, LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(arch)

    story.append(Paragraph("4. Data Flow (simplified)", s["h2"]))
    story.append(Paragraph(
        "<font face='Courier' size='7.5'>Cameras → Live Stream + YOLO/Track → Zone Intrusion Check → "
        "Event DB / Alerts / Incidents → Timeline + Dashboard + Playback Seek → AI Search / Chat / PDF</font>",
        s["body"],
    ))

    story.append(PageBreak())

    # ═══════════════ PAGE 2 ═══════════════
    story.append(Paragraph("5. Case Study Requirements — Coverage", s["h2"]))
    story.append(Paragraph(
        "Every mandatory capability is implemented and demonstrated in the product UI:",
        s["body"],
    ))
    req_items = [
        ("Live camera feeds", "Multi-camera MJPEG grid with 1 / 2 / 4 / 9 / 16 layouts; webcam, RTSP, and HTTP device sources."),
        ("Recorded playback + timeline", "Scrollable colored markers; click seeks recording with −10s replay context."),
        ("AI intrusion / motion", "YOLOv11 object classes + motion fallback; zone-scoped intrusion = critical priority."),
        ("Detection zones", "Draw rectangle/polygon/circle; sensitivity, enable/disable, class filters."),
        ("Event list", "Timestamp, camera, confidence, track ID, priority; one-click evidence open."),
        ("Operations dashboard", "Camera health, today’s detections, storage forecast, CPU/RAM, alerts, weekly charts."),
    ]
    story.append(feature_grid(req_items))

    story.append(Paragraph("6. Differentiating Capabilities (Beyond the Brief)", s["h2"]))
    story.append(Paragraph(
        "To resemble a commercial VMS rather than a classroom prototype, AetherShield includes:",
        s["body"],
    ))
    bullets = [
        "<b>Natural-language AI search</b> — e.g. “Show all people after 9 PM”, “intrusions today”.",
        "<b>Chat with video</b> — RAG over event metadata; 24-hour AI summary.",
        "<b>Face intelligence</b> — enroll known / blacklist; unknown face alerts.",
        "<b>License plate search</b> — OCR when vehicles appear; plate → clip navigation.",
        "<b>Incident management</b> — open / investigating / resolved / false alarm / escalated.",
        "<b>Live WebSocket alerts</b> — in-app toasts + browser notifications on critical events.",
        "<b>Activity heatmap</b> — detection density overlay per camera.",
        "<b>Clip export &amp; PDF security report</b> — evidence packaging for operators.",
        "<b>Demo vs live camera control</b> — toggle sample feeds OFF when using real cameras only.",
        "<b>RBAC</b> — Admin, Operator, Viewer permission sets with JWT authentication.",
    ]
    for b in bullets:
        story.append(Paragraph(f"• {b}", s["bullet"]))

    story.append(Paragraph("7. Implementation Approach", s["h2"]))
    story.append(Paragraph(
        "Development prioritized a reliable end-to-end demo path first (seeded cameras, synthetic videos, "
        "auth, dashboard, playback), then accuracy and operator UX (zones, tracking, event→seek), then "
        "portfolio differentiators (NL search, faces/plates, incidents, remote device connect). "
        "AI runs in per-camera worker threads with cooldowns to avoid event spam. When YOLO tracking "
        "dependencies are unavailable, the pipeline degrades gracefully to prediction-only or motion "
        "detection so demos never hard-fail.",
        s["body"],
    ))
    story.append(Paragraph(
        "<b>Camera operations:</b> Operators can connect this PC’s webcam, remote phones (HTTP MJPEG), "
        "or IP cameras (RTSP), disconnect live sources individually or in bulk, and disable demo cameras "
        "so Live View shows only real feeds — critical for field demos with four physical cameras.",
        s["body"],
    ))

    story.append(PageBreak())

    # ═══════════════ PAGE 3 ═══════════════
    story.append(Paragraph("8. Key UI Surfaces", s["h2"]))
    ui_rows = [
        ["Surface", "Purpose"],
        ["Dashboard", "Command center: health, storage days remaining, weekly detections, alerts"],
        ["Live View", "Multi-grid monitoring with LIVE badges and AI overlays"],
        ["Playback", "Investigation: zones, timeline, seek, heatmap, clip export"],
        ["Cameras", "Connect/disconnect devices; demo ON/OFF master switch"],
        ["Faces &amp; Plates", "Enrollment + plate search across recordings"],
        ["AI Search / Chat", "Operator queries in plain English over event history"],
        ["Incidents", "Workflow status for critical security events"],
        ["Camera Map", "Floor-plan placement; click opens camera evidence"],
    ]
    ui_p = []
    for i, r in enumerate(ui_rows):
        if i == 0:
            ui_p.append([
                Paragraph(f"<font color='white'><b>{r[0]}</b></font>", s["small"]),
                Paragraph(f"<font color='white'><b>{r[1]}</b></font>", s["small"]),
            ])
        else:
            ui_p.append([Paragraph(f"<b>{r[0]}</b>", s["small"]), Paragraph(r[1], s["small"])])
    ui_t = Table(ui_p, colWidths=[38 * mm, 136 * mm])
    ui_t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), INK),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, SOFT]),
        ("BOX", (0, 0), (-1, -1), 0.6, LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(ui_t)

    story.append(Paragraph("9. Suggested Demonstration Script", s["h2"]))
    story.append(Paragraph(
        "1) Login as Admin → Dashboard health cards. 2) Live View multi-grid. 3) Playback → draw a zone → "
        "trigger/person event → click timeline marker → auto-seek. 4) AI Search: “people today”. "
        "5) Toggle Demo OFF; note Live View filters to live sources. 6) Export PDF report. "
        "7) Show incident status change. <i>(Replace this narrative with your recorded walkthrough; "
        "keep the video under a clear, well-lit narration.)</i>",
        s["body"],
    ))

    story.append(Paragraph("10. Repository &amp; Reproducibility", s["h2"]))
    story.append(Paragraph(
        "Source code is organized as a monorepo: <font face='Courier'>backend/</font> (FastAPI), "
        "<font face='Courier'>frontend/</font> (React), <font face='Courier'>docs/</font> (architecture, "
        "schema, webcam guide), <font face='Courier'>sample-data/</font>, and Docker Compose. "
        "API documentation is available at <font face='Courier'>/docs</font> (OpenAPI). "
        "Demo accounts: admin / operator / viewer with documented passwords in README. "
        "Third-party libraries (Ultralytics YOLO, OpenCV, FastAPI, React, Recharts, ReportLab, EasyOCR) "
        "are acknowledged in project documentation.",
        s["body"],
    ))

    story.append(Paragraph("11. Outcomes &amp; Evaluation Fit", s["h2"]))
    story.append(Paragraph(
        "AetherShield fully satisfies the case-study mandate while presenting an operator experience "
        "closer to commercial VMS software: unified live+playback, AI events on a navigable timeline, "
        "zone-constrained alerting, and a real dashboard. Differentiating modules (NL search, identity, "
        "incidents, remote camera ops) strengthen placement-portfolio value without compromising the "
        "core evaluation criteria. The architecture is intentionally modular so judges can inspect "
        "streaming, AI, and API layers independently.",
        s["body"],
    ))

    story.append(Paragraph("12. Acknowledgements", s["h2"]))
    story.append(Paragraph(
        "Ultralytics YOLOv11; OpenCV; FastAPI / Starlette; React / Vite / Tailwind CSS; Recharts; "
        "ReportLab; ByteTrack (via Ultralytics track mode); EasyOCR (optional plate path). "
        "Case study brief: A-1 Launchpad 2026 — Smart Video Management System.",
        s["small"],
    ))

    story.append(Spacer(1, 8))
    story.append(section_rule())
    story.append(Paragraph(
        "<b>GitHub Repository:</b> [ INSERT REPOSITORY URL ] &nbsp;&nbsp;|&nbsp;&nbsp; "
        "<b>Video:</b> [ INSERT VIDEO URL — also on page 1 ]",
        s["center"],
    ))
    story.append(Paragraph(
        "Prepared for Unstop submission · Maximum 3 content pages (this document) · "
        "Cover page &amp; resumes attached separately by the team",
        s["center"],
    ))

    doc.build(story, onFirstPage=header_footer, onLaterPages=header_footer)
    print(f"Wrote {OUT}")
    return OUT


if __name__ == "__main__":
    build()

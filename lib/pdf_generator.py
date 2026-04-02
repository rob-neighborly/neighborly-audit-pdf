"""
Neighborly Voice AI — Missed Call Audit PDF Generator
Generates a branded 2-page PDF report for home service business leads.
"""

from reportlab.lib.pagesizes import letter
from reportlab.lib.colors import HexColor, white
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from datetime import datetime
import os
import io
import json
import urllib.request


# ── Zip Code → City Lookup ──
def zip_to_city(zip_code):
    """Resolve a US zip code to 'City, ST' via zippopotam.us API.
    Falls back to just the zip code if lookup fails."""
    if not zip_code:
        return "your area"
    zip_code = str(zip_code).strip()[:5]
    try:
        url = f"https://api.zippopotam.us/us/{zip_code}"
        req = urllib.request.Request(url, headers={"User-Agent": "NeighborlyVoiceAI/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            city = data["places"][0]["place name"]
            state = data["places"][0]["state abbreviation"]
            return f"{city}, {state}"
    except Exception:
        return f"Zip Code {zip_code}"


# ── Brand Colors ──
CHARCOAL = HexColor("#182522")
BLUE = HexColor("#2B73F3")
GREEN = HexColor("#35C459")
RED = HexColor("#DC2626")
LIGHT_RED_BG = HexColor("#FEF2F2")
LIGHT_GREEN_BG = HexColor("#F0FDF4")
LIGHT_GRAY = HexColor("#F3F4F6")
MEDIUM_GRAY = HexColor("#6B7280")
DARK_TEXT = HexColor("#111827")
BORDER_GRAY = HexColor("#E5E7EB")
WHITE = white
STEP_GREEN = HexColor("#22C55E")

# ── Page Setup ──
W, H = letter  # 612 x 792
MARGIN = 50
CONTENT_W = W - 2 * MARGIN

# ── Service Type Config ──
AVG_JOB_VALUES = {
    "Plumbing": 325,
    "HVAC": 400,
    "Electrical": 275,
    "Garage Door Repair": 300,
    "Pest Control": 225,
    "Other home services": 300,
}

MISS_RATE = 0.32
CONVERSION_RATE = 0.45

MONTHLY_CALL_MAP = {
    "Under 50": 45,
    "50–100": 75,
    "50-100": 75,
    "100–200": 150,
    "100-200": 150,
    "200–300": 250,
    "200-300": 250,
    "300+": 350,
}


def calculate_metrics(monthly_calls_label, service_type):
    monthly_calls = MONTHLY_CALL_MAP.get(monthly_calls_label, 120)
    avg_job = AVG_JOB_VALUES.get(service_type, 325)
    missed = round(monthly_calls * MISS_RATE)
    convertible = missed * CONVERSION_RATE
    monthly_loss = round(convertible * avg_job)
    annual_loss = monthly_loss * 12
    return {
        "monthly_calls": monthly_calls,
        "miss_rate": MISS_RATE,
        "missed_per_month": missed,
        "avg_job": avg_job,
        "conversion_rate": CONVERSION_RATE,
        "monthly_loss": monthly_loss,
        "annual_loss": annual_loss,
    }


def fmt_currency(n):
    return f"${n:,.0f}"


def _get_date_label():
    """Return current month + year, e.g. 'April 2026'."""
    return datetime.utcnow().strftime("%B %Y")


def draw_rounded_rect(c, x, y, w, h, radius=8, fill=None, stroke=None, stroke_width=1):
    p = c.beginPath()
    p.roundRect(x, y, w, h, radius)
    if fill:
        c.setFillColor(fill)
    if stroke:
        c.setStrokeColor(stroke)
        c.setLineWidth(stroke_width)
    if fill and stroke:
        c.drawPath(p, fill=1, stroke=1)
    elif fill:
        c.drawPath(p, fill=1, stroke=0)
    elif stroke:
        c.drawPath(p, fill=0, stroke=1)


def draw_circle(c, cx, cy, r, fill_color):
    c.setFillColor(fill_color)
    c.circle(cx, cy, r, fill=1, stroke=0)


def _get_logo_path():
    """Resolve logo path relative to this file."""
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "logo.png")


def draw_header(c, page_label="MISSED CALL AUDIT"):
    bar_h = 56
    y = H - bar_h
    date_label = _get_date_label()

    c.setFillColor(CHARCOAL)
    c.rect(0, y, W, bar_h, fill=1, stroke=0)

    logo_path = _get_logo_path()
    if os.path.exists(logo_path):
        logo_h = 32
        logo_w = logo_h * (2000 / 625)
        c.drawImage(
            ImageReader(logo_path),
            MARGIN - 8, y + (bar_h - logo_h) / 2,
            width=logo_w, height=logo_h,
            mask="auto",
        )

    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 10)
    c.drawRightString(W - MARGIN, y + bar_h / 2 + 4, page_label)
    c.setFont("Helvetica", 8.5)
    c.setFillColor(HexColor("#9CA3AF"))
    c.drawRightString(W - MARGIN, y + bar_h / 2 - 10, date_label)

    c.setFillColor(BLUE)
    c.rect(0, y - 3, W, 3, fill=1, stroke=0)

    return y - 3


def draw_footer(c, company_name, page_num, total_pages=2):
    bar_h = 32
    date_label = _get_date_label()

    c.setFillColor(GREEN)
    c.rect(0, bar_h, W, 3, fill=1, stroke=0)

    c.setFillColor(CHARCOAL)
    c.rect(0, 0, W, bar_h, fill=1, stroke=0)

    c.setFillColor(HexColor("#9CA3AF"))
    c.setFont("Helvetica", 7.5)
    c.drawString(MARGIN, 12, f"Prepared for {company_name}  ·  {date_label}  ·  NeighborlyVoiceAI.com")
    c.drawRightString(W - MARGIN, 12, f"Page {page_num} of {total_pages}")


def _wrap_text(c, text, font_name, font_size, max_width):
    """Wrap text to fit within max_width. Returns list of lines."""
    words = text.split()
    lines = []
    line = ""
    for word in words:
        test = line + " " + word if line else word
        if c.stringWidth(test, font_name, font_size) < max_width:
            line = test
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


# ═══════════════════════════════════════════
#  PAGE 1
# ═══════════════════════════════════════════
def draw_page_1(c, company_name, city, metrics, service_type):
    bottom_header = draw_header(c)
    draw_footer(c, company_name, 1)

    y = bottom_header - 40

    # ── Company Name ──
    c.setFillColor(DARK_TEXT)
    c.setFont("Helvetica-Bold", 28)
    c.drawString(MARGIN, y, company_name)
    y -= 22

    c.setFillColor(MEDIUM_GRAY)
    c.setFont("Helvetica", 11)
    subtitle = f"Missed Call Revenue Analysis  ·  {city}"
    c.drawString(MARGIN, y, subtitle)
    y -= 8

    c.setStrokeColor(BORDER_GRAY)
    c.setLineWidth(1)
    c.line(MARGIN, y, W - MARGIN, y)
    y -= 40

    # ── BIG Revenue Box ──
    box_h = 100
    box_y = y - box_h
    draw_rounded_rect(c, MARGIN, box_y, CONTENT_W, box_h, radius=10, fill=HexColor("#FFFAF0"))
    c.setStrokeColor(HexColor("#FECACA"))
    c.setLineWidth(1.5)
    c.setDash(6, 3)
    p = c.beginPath()
    p.roundRect(MARGIN, box_y, CONTENT_W, box_h, 10)
    c.drawPath(p, fill=0, stroke=1)
    c.setDash()

    c.setFillColor(RED)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(MARGIN + 20, box_y + box_h - 25, "ESTIMATED ANNUAL REVENUE LEFT ON THE TABLE")

    c.setFillColor(RED)
    c.setFont("Helvetica-Bold", 48)
    annual_str = fmt_currency(metrics["annual_loss"])
    c.drawString(MARGIN + 20, box_y + 18, annual_str)

    c.setFillColor(MEDIUM_GRAY)
    c.setFont("Helvetica", 14)
    monthly_str = f"({fmt_currency(metrics['monthly_loss'])}/month)"
    annual_w = c.stringWidth(annual_str, "Helvetica-Bold", 48)
    c.drawString(MARGIN + 20 + annual_w + 14, box_y + 28, monthly_str)

    y = box_y - 24

    # ── 4 Metric Cards ──
    card_w = (CONTENT_W - 18) / 4
    card_h = 68
    card_y = y - card_h

    card_data = [
        (str(metrics["monthly_calls"]), "MONTHLY CALLS", BLUE),
        (f"{int(metrics['miss_rate']*100)}%", "MISSED CALL RATE", BLUE),
        (str(metrics["missed_per_month"]), "MISSED CALLS/MONTH", BLUE),
        (fmt_currency(metrics["avg_job"]), "AVG. JOB VALUE", BLUE),
    ]

    for i, (value, label, color) in enumerate(card_data):
        cx = MARGIN + i * (card_w + 6)
        draw_rounded_rect(c, cx, card_y, card_w, card_h, radius=8, fill=LIGHT_GRAY)

        c.setFillColor(color)
        c.setFont("Helvetica-Bold", 24)
        c.drawString(cx + 14, card_y + card_h - 30, value)

        c.setFillColor(MEDIUM_GRAY)
        c.setFont("Helvetica-Bold", 7.5)
        c.drawString(cx + 14, card_y + 12, label)

    y = card_y - 36

    # ── How We Calculated This ──
    c.setFillColor(DARK_TEXT)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(MARGIN, y, "How we calculated this")
    y -= 6
    c.setStrokeColor(BORDER_GRAY)
    c.setLineWidth(0.5)
    c.line(MARGIN, y, W - MARGIN, y)
    y -= 28

    service_label = "home service" if service_type == "Other home services" else ("HVAC" if service_type == "HVAC" else service_type.lower())

    steps = [
        (
            f"{metrics['monthly_calls']} estimated monthly calls",
            f"Based on your business size, service area, and industry benchmarks for {service_label} companies in your market.",
        ),
        (
            f"{int(metrics['miss_rate']*100)}% missed call rate",
            "Home service businesses miss 20–40% of inbound calls during jobs, after hours, and weekends. Your listed hours leave evenings and weekends uncovered.",
        ),
        (
            f"{int(metrics['conversion_rate']*100)}% conversion rate",
            "Industry data shows roughly 40–50% of missed calls are real job opportunities — not spam, solicitors, or existing customers.",
        ),
        (
            f"{fmt_currency(metrics['avg_job'])} average job value",
            f"Based on average {service_label} service call revenue in your market, factoring in both smaller repairs and larger jobs.",
        ),
    ]

    for i, (title, desc) in enumerate(steps):
        circle_r = 13
        circle_cx = MARGIN + circle_r + 2
        circle_cy = y - 2

        draw_circle(c, circle_cx, circle_cy, circle_r, STEP_GREEN)
        c.setFillColor(WHITE)
        c.setFont("Helvetica-Bold", 12)
        num_w = c.stringWidth(str(i + 1), "Helvetica-Bold", 12)
        c.drawString(circle_cx - num_w / 2, circle_cy - 4.5, str(i + 1))

        text_x = MARGIN + 40

        c.setFillColor(DARK_TEXT)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(text_x, y, title)

        c.setFillColor(MEDIUM_GRAY)
        c.setFont("Helvetica", 9)
        lines = _wrap_text(c, desc, "Helvetica", 9, CONTENT_W - 50)

        desc_y = y - 16
        for ln in lines:
            c.drawString(text_x, desc_y, ln)
            desc_y -= 13

        y = desc_y - 14

    # ── Teaser to Page 2 ──
    teaser_y = y - 10
    c.setFillColor(BLUE)
    c.setFont("Helvetica-Bold", 10)
    line1 = "The good news? Most of this revenue is recoverable."
    tw1 = c.stringWidth(line1, "Helvetica-Bold", 10)
    c.drawString((W - tw1) / 2, teaser_y, line1)
    # "See how." on next line
    line2 = "See how."
    tw2 = c.stringWidth(line2, "Helvetica-Bold", 10)
    c.drawString((W - tw2) / 2, teaser_y - 16, line2)
    # Down arrow below
    c.setFont("Helvetica-Bold", 14)
    arrow = "\u2193"
    aw = c.stringWidth(arrow, "Helvetica-Bold", 14)
    c.drawString((W - aw) / 2, teaser_y - 34, arrow)


# ═══════════════════════════════════════════
#  PAGE 2
# ═══════════════════════════════════════════
def draw_page_2(c, company_name, metrics):
    bottom_header = draw_header(c, "MISSED CALL AUDIT")
    draw_footer(c, company_name, 2)

    y = bottom_header - 40

    # ── Section Title ──
    c.setFillColor(DARK_TEXT)
    c.setFont("Helvetica-Bold", 22)
    c.drawString(MARGIN, y, "Your voicemail is losing you jobs.")
    y -= 28
    c.setFillColor(BLUE)
    c.setFont("Helvetica-Bold", 22)
    c.drawString(MARGIN, y, "An AI Receptionist fixes that.")
    y -= 24
    c.setFillColor(MEDIUM_GRAY)
    c.setFont("Helvetica", 10)
    c.drawString(MARGIN, y, "80% of callers who hit voicemail won\u2019t leave a message \u2014 they\u2019ll call your competitor instead.")
    y -= 12
    c.setStrokeColor(BORDER_GRAY)
    c.setLineWidth(0.5)
    c.line(MARGIN, y, W - MARGIN, y)
    y -= 28

    # ── Before / After Comparison ──
    half_w = (CONTENT_W - 16) / 2
    box_h = 160

    without_x = MARGIN
    without_y = y - box_h
    draw_rounded_rect(c, without_x, without_y, half_w, box_h, radius=10, fill=LIGHT_RED_BG)
    c.setStrokeColor(HexColor("#FECACA"))
    c.setLineWidth(1)
    p = c.beginPath()
    p.roundRect(without_x, without_y, half_w, box_h, 10)
    c.drawPath(p, fill=0, stroke=1)

    c.setFillColor(RED)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(without_x + 16, without_y + box_h - 22, "WITH VOICEMAIL")

    without_items = [
        f"~{fmt_currency(metrics['monthly_loss'])}/mo in lost revenue",
        f"{metrics['missed_per_month']} calls go to voicemail every month",
        "Callers hear voicemail and hang up",
        "Nights & weekends \u2014 no one\u2019s answering",
        "Competitors take your customers",
    ]
    item_y = without_y + box_h - 42
    for item in without_items:
        c.setFillColor(HexColor("#991B1B"))
        c.setFont("Helvetica", 10)
        c.drawString(without_x + 18, item_y, "\u2717")
        c.setFillColor(DARK_TEXT)
        c.drawString(without_x + 34, item_y, item)
        item_y -= 22

    with_x = MARGIN + half_w + 16
    draw_rounded_rect(c, with_x, without_y, half_w, box_h, radius=10, fill=LIGHT_GREEN_BG)
    c.setStrokeColor(HexColor("#BBF7D0"))
    p = c.beginPath()
    p.roundRect(with_x, without_y, half_w, box_h, 10)
    c.drawPath(p, fill=0, stroke=1)

    c.setFillColor(HexColor("#166534"))
    c.setFont("Helvetica-Bold", 10)
    c.drawString(with_x + 16, without_y + box_h - 22, "WITH AI RECEPTIONIST")

    with_items = [
        f"Up to {fmt_currency(metrics['monthly_loss'])}/mo in recovered revenue",
        "100% of calls answered, 24/7",
        "Appointments booked directly on your calendar",
        "Nights, weekends & holidays \u2014 fully covered",
        "Callers hear your business name, not a beep",
    ]
    item_y = without_y + box_h - 42
    for item in with_items:
        c.setFillColor(HexColor("#166534"))
        c.setFont("Helvetica", 10)
        c.drawString(with_x + 18, item_y, "\u2713")
        c.setFillColor(DARK_TEXT)
        c.drawString(with_x + 34, item_y, item)
        item_y -= 22

    y = without_y - 30

    # ── How It Works ──
    c.setFillColor(DARK_TEXT)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(MARGIN, y, "How it works")
    y -= 6
    c.setStrokeColor(BORDER_GRAY)
    c.setLineWidth(0.5)
    c.line(MARGIN, y, W - MARGIN, y)
    y -= 26

    how_steps = [
        (
            "We replace your voicemail",
            "Your existing number forwards unanswered calls to the AI instead of voicemail. Setup takes 7 days or less.",
        ),
        (
            "AI answers like your best receptionist",
            "We learn your services, hours, service area, and how you like to talk to customers. The AI greets callers by your business name and sounds natural \u2014 not robotic, not generic.",
        ),
        (
            "Jobs land on your calendar",
            "The AI checks your real-time availability, picks the right technician, and confirms the appointment. You get a text instantly.",
        ),
        (
            "You show up and get paid",
            "No more phone tag. No more lost leads. Just booked jobs waiting on your calendar every morning.",
        ),
    ]

    for i, (title, desc) in enumerate(how_steps):
        circle_r = 13
        circle_cx = MARGIN + circle_r + 2
        circle_cy = y - 2

        draw_circle(c, circle_cx, circle_cy, circle_r, STEP_GREEN)
        c.setFillColor(WHITE)
        c.setFont("Helvetica-Bold", 12)
        num_w = c.stringWidth(str(i + 1), "Helvetica-Bold", 12)
        c.drawString(circle_cx - num_w / 2, circle_cy - 4.5, str(i + 1))

        text_x = MARGIN + 40

        c.setFillColor(DARK_TEXT)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(text_x, y, title)

        c.setFillColor(MEDIUM_GRAY)
        c.setFont("Helvetica", 9)
        lines = _wrap_text(c, desc, "Helvetica", 9, CONTENT_W - 50)

        desc_y = y - 16
        for ln in lines:
            c.drawString(text_x, desc_y, ln)
            desc_y -= 13

        y = desc_y - 12

    y -= 8

    # ── CTA Box ──
    cta_h = 100
    cta_y = y - cta_h
    draw_rounded_rect(c, MARGIN, cta_y, CONTENT_W, cta_h, radius=12, fill=CHARCOAL)

    c.setStrokeColor(HexColor("#374151"))
    c.setLineWidth(1)
    c.setDash(8, 4)
    p = c.beginPath()
    p.roundRect(MARGIN, cta_y, CONTENT_W, cta_h, 12)
    c.drawPath(p, fill=0, stroke=1)
    c.setDash()

    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 18)
    cta_title = "Ready to ditch your voicemail?"
    tw = c.stringWidth(cta_title, "Helvetica-Bold", 18)
    c.drawString((W - tw) / 2, cta_y + cta_h - 30, cta_title)

    c.setFillColor(HexColor("#D1D5DB"))
    c.setFont("Helvetica", 10)
    sub = "Try it risk free. No contracts. Cancel anytime."
    sw = c.stringWidth(sub, "Helvetica", 10)
    c.drawString((W - sw) / 2, cta_y + cta_h - 48, sub)

    btn_text = "neighborlyvoiceai.com/book-audit"
    btn_font_size = 11
    c.setFont("Helvetica-Bold", btn_font_size)
    btn_tw = c.stringWidth(btn_text, "Helvetica-Bold", btn_font_size)
    btn_w = btn_tw + 40
    btn_h = 30
    btn_x = (W - btn_w) / 2
    btn_y = cta_y + 12

    draw_rounded_rect(c, btn_x, btn_y, btn_w, btn_h, radius=6, fill=BLUE)
    c.setFillColor(WHITE)
    c.drawString(btn_x + 20, btn_y + 9, btn_text)

    # Make the button a clickable link
    c.linkURL(
        "https://neighborlyvoiceai.com/book-audit",
        (btn_x, btn_y, btn_x + btn_w, btn_y + btn_h),
        relative=0,
    )


# ═══════════════════════════════════════════
#  PUBLIC API
# ═══════════════════════════════════════════
def generate_audit_pdf(
    output_path=None,
    company_name="Bluewave Plumbing",
    first_name="Mike",
    city=None,
    zip_code=None,
    monthly_calls_label="100-200",
    service_type="Plumbing",
):
    """Generate a Missed Call Audit PDF.

    Args:
        output_path: File path to save PDF. If None, returns PDF bytes.
        company_name: Business name.
        first_name: Contact first name (for future personalization).
        city: City, ST string. If not provided, resolved from zip_code.
        zip_code: US zip code. Used to resolve city if city not provided.
        monthly_calls_label: One of the MONTHLY_CALL_MAP keys.
        service_type: One of the AVG_JOB_VALUES keys.

    Returns:
        If output_path is None, returns PDF as bytes.
        Otherwise writes to output_path and returns the path.
    """
    # Resolve city
    if not city and zip_code:
        city = zip_to_city(zip_code)
    elif not city:
        city = "your area"

    metrics = calculate_metrics(monthly_calls_label, service_type)

    # Write to file or to bytes buffer
    if output_path:
        c = canvas.Canvas(output_path, pagesize=letter)
    else:
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)

    c.setTitle(f"Missed Call Audit \u2014 {company_name}")
    c.setAuthor("Neighborly Voice AI")

    draw_page_1(c, company_name, city, metrics, service_type)
    c.showPage()
    draw_page_2(c, company_name, metrics)
    c.showPage()
    c.save()

    if output_path:
        return output_path
    else:
        buffer.seek(0)
        return buffer.read()

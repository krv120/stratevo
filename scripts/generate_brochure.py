import io
import math
import shutil
import subprocess
import fitz
import qrcode
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import HexColor
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont as RLTTFont
from reportlab.lib.utils import ImageReader

# 1. Extract static TTF instances from STRATEVO's exact Inter webfont
woff2_bytes = subprocess.check_output(
    ["git", "show", "b0b22c9d0a4cab9e9b5ac424847ae74ece97e82f:web/fonts/inter-latin.woff2"]
)
for name, wght in [
    ("Inter-Regular", 400),
    ("Inter-Medium", 500),
    ("Inter-SemiBold", 600),
    ("Inter-Bold", 700),
    ("Inter-ExtraBold", 800),
]:
    f = TTFont(io.BytesIO(woff2_bytes))
    f.flavor = None
    inst = instancer.instantiateVariableFont(f, {"wght": wght})
    ttf_path = f"/tmp/{name}.ttf"
    inst.save(ttf_path)
    pdfmetrics.registerFont(RLTTFont(name, ttf_path))

W, H = A4  # 595.27559 x 841.88976 pt
MARGIN = 26.0
CONTENT_W = W - 2 * MARGIN  # 543.28 pt

# Brand Palette from stratevo.online + Executive Print Palette
NAVY_DEEP = HexColor("#070B12")
NAVY_HERO = HexColor("#0B121F")
NAVY_PANEL = HexColor("#111C2E")
NAVY_CARD = HexColor("#17263F")
NAVY_LINE = HexColor("#263B5E")

COBALT_DARK = HexColor("#0F45A8")
COBALT_PRIMARY = HexColor("#1458D2")
COBALT_BRIGHT = HexColor("#2569E6")
COBALT_GLOW = HexColor("#5C95FF")
ICE_BLUE = HexColor("#8FB6FF")
ICE_LIGHT = HexColor("#D6E5FF")
TEXT_WHITE = HexColor("#F4F8FF")
TEXT_MUTED_DARK = HexColor("#B0C0D8")

BG_PAGE = HexColor("#F3F6FB")
CARD_SHADOW = HexColor("#E2E9F5")
CARD_WHITE = HexColor("#FFFFFF")
CARD_SLATE = HexColor("#EDF2FA")
CARD_WARN_BG = HexColor("#FFF5F5")
CARD_WARN_BORDER = HexColor("#F5C2C7")
CARD_WARN_TXT = HexColor("#9B1C2C")
CARD_OK_BG = HexColor("#ECFDF3")
CARD_OK_TXT = HexColor("#0D6838")

BORDER_LIGHT = HexColor("#CED9EC")
INK_DARK = HexColor("#0A1222")
INK_BODY = HexColor("#28374E")
INK_MUTED = HexColor("#566782")


def draw_wrapped_text(c, text, x, y, max_w, font_name, font_size, leading, color):
    """Draws word-wrapped text starting at baseline y, returns next baseline y."""
    c.setFont(font_name, font_size)
    c.setFillColor(color)
    words = text.split(" ")
    lines = []
    cur = ""
    for w in words:
        test = (cur + " " + w).strip()
        if pdfmetrics.stringWidth(test, font_name, font_size) <= max_w:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    cur_y = y
    for line in lines:
        c.drawString(x, cur_y, line)
        cur_y -= leading
    return cur_y


def draw_elevated_card(c, x, y, w, h, radius=7, bg=CARD_WHITE, border=BORDER_LIGHT, lw=0.85, shadow=True):
    """Draws a crisp card with a subtle offset shadow for executive depth."""
    if shadow:
        c.setFillColor(CARD_SHADOW)
        c.roundRect(x + 1.5, y - 2.0, w, h, radius, stroke=0, fill=1)
    c.setFillColor(bg)
    c.setStrokeColor(border)
    c.setLineWidth(lw)
    c.roundRect(x, y, w, h, radius, stroke=1, fill=1)


def draw_check_badge(c, cx, cy, r=5.0, bg=COBALT_PRIMARY, fg=TEXT_WHITE):
    """Draws a filled circle with a crisp vector checkmark inside."""
    c.saveState()
    c.setFillColor(bg)
    c.circle(cx, cy, r, stroke=0, fill=1)
    c.setStrokeColor(fg)
    c.setLineWidth(1.25)
    c.setLineCap(1)
    c.setLineJoin(1)
    p = c.beginPath()
    p.moveTo(cx - r * 0.45, cy - r * 0.02)
    p.lineTo(cx - r * 0.12, cy - r * 0.36)
    p.lineTo(cx + r * 0.48, cy + r * 0.34)
    c.drawPath(p, stroke=1, fill=0)
    c.restoreState()


def draw_check_icon(c, x, y, size=6.0, color=COBALT_PRIMARY):
    """Draws a standalone crisp vector checkmark near baseline (x, y)."""
    c.saveState()
    c.setStrokeColor(color)
    c.setLineWidth(1.35)
    c.setLineCap(1)
    c.setLineJoin(1)
    p = c.beginPath()
    p.moveTo(x, y + size * 0.45)
    p.lineTo(x + size * 0.35, y + size * 0.08)
    p.lineTo(x + size * 0.95, y + size * 0.85)
    c.drawPath(p, stroke=1, fill=0)
    c.restoreState()


def draw_right_arrow(c, cx, cy, r=6.5):
    """Draws a circular cobalt badge with a crisp white right arrow at center (cx, cy)."""
    c.saveState()
    c.setFillColor(COBALT_PRIMARY)
    c.circle(cx, cy, r, stroke=0, fill=1)
    c.setStrokeColor(TEXT_WHITE)
    c.setLineWidth(1.35)
    c.setLineCap(1)
    c.setLineJoin(1)
    p = c.beginPath()
    p.moveTo(cx - 2.8, cy)
    p.lineTo(cx + 2.6, cy)
    p.moveTo(cx + 0.3, cy + 2.3)
    p.lineTo(cx + 2.8, cy)
    p.lineTo(cx + 0.3, cy - 2.3)
    c.drawPath(p, stroke=1, fill=0)
    c.restoreState()


def draw_ne_arrow(c, x, y, size=6.8, color=TEXT_WHITE, lw=1.45):
    """Draws a north-east external link arrow at bottom-left (x, y)."""
    c.saveState()
    c.setStrokeColor(color)
    c.setLineWidth(lw)
    c.setLineCap(1)
    c.setLineJoin(1)
    p = c.beginPath()
    p.moveTo(x, y)
    p.lineTo(x + size, y + size)
    p.moveTo(x + size * 0.25, y + size)
    p.lineTo(x + size, y + size)
    p.lineTo(x + size, y + size * 0.25)
    c.drawPath(p, stroke=1, fill=0)
    c.restoreState()


def draw_pillar_icon(c, kind, cx, cy, color=ICE_BLUE):
    """Draws a custom geometric vector icon for each of the 3 pillars."""
    c.saveState()
    c.setStrokeColor(color)
    c.setLineWidth(1.2)
    c.setLineCap(1)
    c.setLineJoin(1)
    if kind == "factory":
        # Precision gear / building node icon
        c.roundRect(cx - 5.5, cy - 5.5, 11, 11, 2, stroke=1, fill=0)
        c.circle(cx, cy, 2.3, stroke=1, fill=0)
    elif kind == "scale":
        # Two balanced comparison bars
        c.line(cx - 5.5, cy + 3, cx + 5.5, cy + 3)
        c.line(cx - 5.5, cy, cx + 2.5, cy)
        c.line(cx - 5.5, cy - 3, cx + 4.0, cy - 3)
    elif kind == "shield":
        # Shield outline with checkmark
        p = c.beginPath()
        p.moveTo(cx, cy + 6.0)
        p.lineTo(cx + 5.2, cy + 3.8)
        p.lineTo(cx + 5.2, cy - 0.8)
        p.curveTo(cx + 5.2, cy - 3.8, cx + 2.5, cy - 5.5, cx, cy - 6.2)
        p.curveTo(cx - 2.5, cy - 5.5, cx - 5.2, cy - 3.8, cx - 5.2, cy - 0.8)
        p.lineTo(cx - 5.2, cy + 3.8)
        p.close()
        c.drawPath(p, stroke=1, fill=0)
    c.restoreState()


def draw_stratevo_logo(c, x, y, size=24):
    """Draws the exact STRATEVO vector icon from favicon.svg at (x, y) bottom-left."""
    c.saveState()
    c.translate(x, y)
    scale = size / 48.0
    c.scale(scale, scale)
    c.setFillColor(COBALT_PRIMARY)
    c.roundRect(0, 0, 48, 48, 10, stroke=0, fill=1)
    c.translate(0, 48)
    c.scale(1, -1)
    c.translate(7, 8)
    p = c.beginPath()
    p.moveTo(32, 2)
    p.lineTo(13, 2)
    p.curveTo(3, 2, 0, 11, 8, 16)
    p.lineTo(22, 24)
    p.lineTo(5, 24)
    p.lineTo(1, 31)
    p.lineTo(21, 31)
    p.curveTo(32, 31, 35, 22, 26, 16)
    p.lineTo(13, 9)
    p.lineTo(28, 9)
    p.close()
    c.setFillColor(HexColor("#FFFFFF"))
    c.drawPath(p, stroke=0, fill=1)
    c.restoreState()


def build_pdf(output_path):
    c = canvas.Canvas(output_path, pagesize=A4)
    c.setTitle("STRATEVO Sourcing & Advisory Overview")
    c.setAuthor("Vasilis (Billy) Krevatsoulis - STRATEVO (stratevo.online)")
    c.setSubject("STRATEVO Sourcing & Advisory Overview - Independent B2B Sourcing Consultant Based in Europe")
    c.setKeywords(
        "STRATEVO, Sourcing & Advisory Overview, Independent B2B Sourcing Consultant Europe, Manufacturer Matching, Quote Comparison, Risk Assessment, Minup"
    )

    # Full page soft architectural slate background
    c.setFillColor(BG_PAGE)
    c.rect(0, 0, W, H, stroke=0, fill=1)

    # =========================================================================
    # 1. EXECUTIVE HERO BANNER (y = 684 to 841.89, height = 158pt)
    # =========================================================================
    HERO_BOTTOM = 684
    HERO_H = H - HERO_BOTTOM
    c.setFillColor(NAVY_DEEP)
    c.rect(0, HERO_BOTTOM, W, HERO_H, stroke=0, fill=1)

    # Subtle architectural grid pattern in top-right of Hero
    c.saveState()
    c.setStrokeColor(HexColor("#111D33"))
    c.setLineWidth(0.5)
    for gx in range(int(W - 220), int(W), 22):
        c.line(gx, HERO_BOTTOM + 28, gx, H - 5)
    for gy in range(int(HERO_BOTTOM + 28), int(H - 5), 22):
        c.line(W - 220, gy, W, gy)
    c.restoreState()

    # Top cobalt brand bar
    c.setFillColor(COBALT_PRIMARY)
    c.rect(0, H - 4.5, W, 4.5, stroke=0, fill=1)

    # Top Header Bar: Logo + Document Title Pill + Website Link
    draw_stratevo_logo(c, MARGIN, H - 36, size=22)
    c.setFont("Inter-ExtraBold", 13.5)
    c.setFillColor(TEXT_WHITE)
    c.drawString(MARGIN + 29, H - 29.5, "STRATEVO")

    # Document Title Pill: "STRATEVO Sourcing & Advisory Overview"
    PILL_X = MARGIN + 108
    c.setFillColor(NAVY_CARD)
    c.setStrokeColor(HexColor("#33507F"))
    c.setLineWidth(0.75)
    c.roundRect(PILL_X, H - 34, 174, 16.5, 4, stroke=1, fill=1)
    c.setFont("Inter-Bold", 6.8)
    c.setFillColor(ICE_LIGHT)
    c.drawCentredString(PILL_X + 87, H - 28.2, "SOURCING & ADVISORY OVERVIEW")

    # Top-Right Website Button
    WEB_W = 94
    WEB_X = W - MARGIN - WEB_W
    c.setFillColor(NAVY_PANEL)
    c.setStrokeColor(COBALT_GLOW)
    c.setLineWidth(0.75)
    c.roundRect(WEB_X, H - 34, WEB_W, 16.5, 4, stroke=1, fill=1)
    c.setFont("Inter-SemiBold", 7.3)
    c.setFillColor(ICE_BLUE)
    c.drawString(WEB_X + 9, H - 28.2, "stratevo.online")
    draw_ne_arrow(c, WEB_X + WEB_W - 14, H - 28.5, size=5.2, color=ICE_BLUE, lw=1.2)
    c.linkURL("https://stratevo.online", (WEB_X, H - 35, W - MARGIN, H - 17), relative=0)

    c.setFont("Inter-Medium", 7.0)
    c.setFillColor(TEXT_MUTED_DARK)
    c.drawRightString(WEB_X - 8, H - 28.2, "Europe-Based Independent B2B Consultancy")

    # Hairline below brand bar
    c.setStrokeColor(HexColor("#1C2C47"))
    c.setLineWidth(0.6)
    c.line(MARGIN, H - 43, W - MARGIN, H - 43)

    # Hero Eyebrow
    c.setFont("Inter-Bold", 7.0)
    c.setFillColor(ICE_BLUE)
    c.drawString(MARGIN, H - 56, "CHINA MANUFACTURING ADVISORY  ·  BUILT FOR E-COMMERCE, PRIVATE LABEL & B2B BUYERS")

    # Hero Main Headlines (Punchy, high-contrast, human voice)
    c.setFont("Inter-ExtraBold", 19.5)
    c.setFillColor(TEXT_WHITE)
    c.drawString(MARGIN, H - 77, "Find the Right Manufacturer in China.")
    c.setFillColor(ICE_BLUE)
    c.drawString(MARGIN, H - 99, "See What Is Missing From the Quote Before You Pay.")

    # Hero Subcopy
    c.setFont("Inter-Regular", 8.4)
    c.setFillColor(TEXT_MUTED_DARK)
    c.drawString(
        MARGIN,
        H - 116,
        "We turn rough product specs into a clear brief, compare factory quotes on equal terms, and check compliance evidence before you commit.",
    )

    # Bottom Strip inside Hero: 3 Instant Credibility Pillars (y = 684 to 714)
    STRIP_H = 27
    c.setFillColor(NAVY_PANEL)
    c.rect(0, HERO_BOTTOM, W, STRIP_H, stroke=0, fill=1)
    c.setStrokeColor(NAVY_LINE)
    c.setLineWidth(0.6)
    c.line(0, HERO_BOTTOM + STRIP_H, W, HERO_BOTTOM + STRIP_H)
    c.setStrokeColor(COBALT_PRIMARY)
    c.setLineWidth(1.2)
    c.line(0, HERO_BOTTOM, W, HERO_BOTTOM)

    hero_pills = [
        ("0% Factory Kickbacks", "Paid only by the buyer. Zero supplier commissions."),
        ("100% Factory-Direct", "You contract and pay the vetted factory directly."),
        ("EU Time-Zone Accountability", "Led by Vasilis (Billy) Krevatsoulis in Europe (Greece)."),
    ]
    col_w_hero = CONTENT_W / 3.0
    for idx, (hp_title, hp_sub) in enumerate(hero_pills):
        hx = MARGIN + idx * col_w_hero
        draw_check_badge(c, hx + 6, HERO_BOTTOM + 13.5, r=4.8, bg=COBALT_PRIMARY, fg=TEXT_WHITE)
        c.setFont("Inter-Bold", 7.2)
        c.setFillColor(TEXT_WHITE)
        c.drawString(hx + 15, HERO_BOTTOM + 15.5, hp_title)
        c.setFont("Inter-Regular", 6.3)
        c.setFillColor(TEXT_MUTED_DARK)
        c.drawString(hx + 15, HERO_BOTTOM + 7.0, hp_sub)

    # =========================================================================
    # 2. SECTION 1: WHO WE ARE (y = 574 to 672, height = 98pt)
    # =========================================================================
    S1_TOP = 672
    S1_H = 98
    S1_Y = S1_TOP - S1_H

    draw_elevated_card(c, MARGIN, S1_Y, CONTENT_W, S1_H, radius=7)

    # Left cobalt bar
    c.setFillColor(COBALT_PRIMARY)
    c.roundRect(MARGIN, S1_Y, 4.5, S1_H, 2.5, stroke=0, fill=1)

    LX = MARGIN + 16
    LW = 334
    c.setFont("Inter-Bold", 7.0)
    c.setFillColor(COBALT_PRIMARY)
    c.drawString(LX, S1_TOP - 15, "01 / WHO WE ARE  ·  INDEPENDENT B2B SOURCING CONSULTANT IN EUROPE")

    c.setFont("Inter-Bold", 10.4)
    c.setFillColor(INK_DARK)
    c.drawString(LX, S1_TOP - 30, "Why Buyers Separate Sourcing Advice From Factory Sales")

    who_text_1 = (
        "On supplier directories, 'Verified' badges are paid ads, and most top listings are trading "
        "middlemen. Meanwhile, traditional sourcing agents quietly take a 5% to 10% factory kickback, "
        "so they earn more money when you pay a higher unit price."
    )
    ny = draw_wrapped_text(c, who_text_1, LX, S1_TOP - 42.5, LW, "Inter-Regular", 7.55, 10.1, INK_BODY)

    who_text_2 = (
        "STRATEVO works strictly for the buyer under a fixed written scope. Founded by Vasilis (Billy) "
        "Krevatsoulis in Greece, we vet factories, audit quotes, and connect you factory-direct."
    )
    draw_wrapped_text(c, who_text_2, LX, ny - 1.5, LW, "Inter-SemiBold", 7.55, 10.1, INK_DARK)

    # Vertical divider inside Section 1
    DIV_X = MARGIN + 360
    c.setStrokeColor(BORDER_LIGHT)
    c.setLineWidth(0.75)
    c.line(DIV_X, S1_Y + 10, DIV_X, S1_TOP - 10)

    # Right Column inside Section 1: Sourcing Coverage (4 Categories from stratevo.online)
    RX = DIV_X + 12
    RW = CONTENT_W - 360 - 22  # 161.28pt
    c.setFont("Inter-Bold", 6.8)
    c.setFillColor(COBALT_PRIMARY)
    c.drawString(RX, S1_TOP - 15, "SOURCING COVERAGE AREAS")

    cats = [
        ("Consumer & OEM Products", "Electronics · Apparel · Homewares"),
        ("Packaging & Materials", "Rigid boxes · Corrugated · Barrier films"),
        ("Industrial Components", "Machining · Castings · Motors · Fasteners"),
        ("Food & Specialty Goods", "Dry goods · Ingredients · Traceability"),
    ]
    cy_cat = S1_TOP - 28.5
    for c_name, c_sub in cats:
        c.setFillColor(CARD_SLATE)
        c.roundRect(RX, cy_cat - 7.5, RW, 16.5, 3, stroke=0, fill=1)
        draw_check_icon(c, RX + 6, cy_cat - 1.5, size=5.0, color=COBALT_PRIMARY)
        c.setFont("Inter-Bold", 7.0)
        c.setFillColor(INK_DARK)
        c.drawString(RX + 15, cy_cat + 1.2, c_name)
        c.setFont("Inter-Regular", 6.1)
        c.setFillColor(INK_MUTED)
        c.drawString(RX + 15, cy_cat - 5.5, c_sub)
        cy_cat -= 18.8

    # =========================================================================
    # 3. SECTION 2: WHAT WE DO + REALITY CHECK STRIP (y = 336 to 562)
    # =========================================================================
    S2_TOP_Y = 559
    c.setFont("Inter-Bold", 7.0)
    c.setFillColor(COBALT_PRIMARY)
    c.drawString(MARGIN, S2_TOP_Y, "02 / WHAT WE DO  ·  THREE CORE ADVISORY SERVICES")
    c.setFont("Inter-Medium", 7.0)
    c.setFillColor(INK_MUTED)
    c.drawRightString(W - MARGIN, S2_TOP_Y, "Finding a listing, comparing an offer, and verifying a factory are different tasks.")

    c.setFont("Inter-Bold", 12.0)
    c.setFillColor(INK_DARK)
    c.drawString(MARGIN, S2_TOP_Y - 13.5, "What We Check Before You Wire a Single Euro to China")

    CARD_Y = 408
    CARD_H = 131
    GAP = 9.5
    CARD_W = (CONTENT_W - 2 * GAP) / 3.0

    pillars = [
        {
            "num": "01",
            "icon": "factory",
            "title": "Manufacturer Matching",
            "trap": "Avoids: Trading middlemen posing as factories",
            "desc": (
                "We turn your product requirements, target cost, and volume into a structured brief. Then we "
                "filter out middlemen and shortlist manufacturers whose real production lines fit your order size."
            ),
            "checks": [
                "Business license & legal entity check",
                "Actual factory vs. reseller screening",
                "MOQ, tooling & lead-time compatibility",
            ],
        },
        {
            "num": "02",
            "icon": "scale",
            "title": "Quote Comparison",
            "trap": "Avoids: 'Cheap' unit quotes that add 25% later",
            "desc": (
                "Suppliers often strip out mold fees, export cartons, or local port charges to win your inquiry. "
                "We normalize every quote onto one identical specification and commercial baseline."
            ),
            "checks": [
                "Separate unit price from NRE / mold tooling",
                "Normalize EXW, FOB & DDP Incoterms",
                "Compare packaging, samples & payment terms",
            ],
        },
        {
            "num": "03",
            "icon": "shield",
            "title": "Risk Assessment",
            "trap": "Avoids: Fake PDFs & mass-production defects",
            "desc": (
                "A directory badge or emailed PDF is not proof of compliance. We check who issued a certificate, "
                "confirm it covers your exact product and factory entity, and set clear sample & QC rules."
            ),
            "checks": [
                "CE, REACH, RoHS & ISO provenance check",
                "Measurable sample acceptance criteria",
                "Pre-shipment quality inspection plan",
            ],
        },
    ]

    for idx, p in enumerate(pillars):
        cx = MARGIN + idx * (CARD_W + GAP)
        draw_elevated_card(c, cx, CARD_Y, CARD_W, CARD_H, radius=7)

        # Dark header strip on each card
        c.setFillColor(NAVY_PANEL)
        c.roundRect(cx, CARD_Y + CARD_H - 25, CARD_W, 25, 7, stroke=0, fill=1)
        c.rect(cx, CARD_Y + CARD_H - 25, CARD_W, 10, stroke=0, fill=1)

        draw_pillar_icon(c, p["icon"], cx + 14, CARD_Y + CARD_H - 12.5, color=ICE_BLUE)
        c.setFont("Inter-Bold", 9.4)
        c.setFillColor(TEXT_WHITE)
        c.drawString(cx + 25, CARD_Y + CARD_H - 15.5, p["title"])

        c.setFont("Inter-Bold", 7.2)
        c.setFillColor(ICE_BLUE)
        c.drawRightString(cx + CARD_W - 10, CARD_Y + CARD_H - 15.5, p["num"])

        # Highlighted "Trap Avoided" pill
        c.setFillColor(CARD_SLATE)
        c.roundRect(cx + 9, CARD_Y + CARD_H - 40, CARD_W - 18, 11.5, 3, stroke=0, fill=1)
        c.setFont("Inter-SemiBold", 6.2)
        c.setFillColor(COBALT_PRIMARY)
        c.drawString(cx + 13, CARD_Y + CARD_H - 36.2, p["trap"])

        # Body text (strictly 4 lines so plenty of air above checklist)
        draw_wrapped_text(
            c, p["desc"], cx + 10, CARD_Y + CARD_H - 51.5, CARD_W - 20, "Inter-Regular", 7.05, 9.5, INK_BODY
        )

        # Divider above checklist
        c.setStrokeColor(BORDER_LIGHT)
        c.setLineWidth(0.55)
        c.line(cx + 10, CARD_Y + 38, cx + CARD_W - 10, CARD_Y + 38)

        cy_chk = CARD_Y + 27.5
        for chk in p["checks"]:
            draw_check_icon(c, cx + 10, cy_chk - 0.5, size=5.2, color=COBALT_PRIMARY)
            c.setFont("Inter-Medium", 6.55)
            c.setFillColor(INK_DARK)
            c.drawString(cx + 19, cy_chk, chk)
            cy_chk -= 10.5

    # Compact Visual Reality-Check Bar right below the 3 cards (y = 335 to 399, height = 64pt)
    BAR_TOP = 399
    BAR_H = 64
    BAR_Y = BAR_TOP - BAR_H

    c.setFillColor(NAVY_PANEL)
    c.setStrokeColor(NAVY_LINE)
    c.setLineWidth(0.85)
    c.roundRect(MARGIN, BAR_Y, CONTENT_W, BAR_H, 6, stroke=1, fill=1)

    c.setFont("Inter-Bold", 6.6)
    c.setFillColor(ICE_BLUE)
    c.drawString(
        MARGIN + 12,
        BAR_TOP - 12.5,
        "REAL-WORLD QUOTE AUDIT  ·  WHY THE LOWEST UNIT PRICE OFTEN COSTS MORE LANDED",
    )
    c.setFont("Inter-Regular", 6.2)
    c.setFillColor(TEXT_MUTED_DARK)
    c.drawRightString(W - MARGIN - 12, BAR_TOP - 12.5, "Illustrative audit · stratevo.online/methodology")

    # Two side-by-side comparison boxes inside the bar
    BOX_W = (CONTENT_W - 32) / 2.0
    B1_X = MARGIN + 11
    B2_X = B1_X + BOX_W + 10
    BOX_Y = BAR_Y + 7
    BOX_H = 39

    # Box 1: Unchecked Quote A
    c.setFillColor(HexColor("#1D1824"))
    c.setStrokeColor(HexColor("#6E303B"))
    c.setLineWidth(0.7)
    c.roundRect(B1_X, BOX_Y, BOX_W, BOX_H, 4.5, stroke=1, fill=1)
    c.setFont("Inter-Bold", 7.1)
    c.setFillColor(HexColor("#FF9E9E"))
    c.drawString(B1_X + 9, BOX_Y + 26.5, "Supplier A Quote: $7.80 / unit EXW  (Looks Cheaper)")
    c.setFont("Inter-Regular", 6.4)
    c.setFillColor(TEXT_MUTED_DARK)
    c.drawString(B1_X + 9, BOX_Y + 15.5, "Excluded: $1,450 mold tooling + $680 local port trucking + export cartons.")
    c.setFont("Inter-SemiBold", 6.5)
    c.setFillColor(HexColor("#FFD1D1"))
    c.drawString(B1_X + 9, BOX_Y + 5.5, "True Landed Reality: $9.93 / unit  +  Trading company with 3rd-party CE PDF")

    # Box 2: Normalized Quote B
    c.setFillColor(HexColor("#112629"))
    c.setStrokeColor(HexColor("#286656"))
    c.setLineWidth(0.7)
    c.roundRect(B2_X, BOX_Y, BOX_W, BOX_H, 4.5, stroke=1, fill=1)
    c.setFont("Inter-Bold", 7.1)
    c.setFillColor(HexColor("#8CE99A"))
    c.drawString(B2_X + 9, BOX_Y + 26.5, "Supplier B Quote: $8.35 / unit FOB Ningbo  (STRATEVO Audited)")
    c.setFont("Inter-Regular", 6.4)
    c.setFillColor(TEXT_MUTED_DARK)
    c.drawString(B2_X + 9, BOX_Y + 15.5, "Included: Custom tooling, export packaging & FOB port clearance all itemized.")
    c.setFont("Inter-SemiBold", 6.5)
    c.setFillColor(HexColor("#C3FAE8"))
    c.drawString(B2_X + 9, BOX_Y + 5.5, "True Landed Reality: $8.35 / unit FOB  (16% cheaper landed + verified factory)")

    # =========================================================================
    # 4. SECTION 3: HOW IT WORKS (y = 200 to 324, height = 124pt)
    # =========================================================================
    S3_TOP_Y = 323
    c.setFont("Inter-Bold", 7.0)
    c.setFillColor(COBALT_PRIMARY)
    c.drawString(MARGIN, S3_TOP_Y, "03 / HOW IT WORKS  ·  THREE STEPS FROM BRIEF TO FACTORY")
    c.setFont("Inter-Medium", 7.0)
    c.setFillColor(INK_MUTED)
    c.drawRightString(W - MARGIN, S3_TOP_Y, "No upfront retainer to talk. Any paid scope is agreed in writing first.")

    c.setFont("Inter-Bold", 12.0)
    c.setFillColor(INK_DARK)
    c.drawString(MARGIN, S3_TOP_Y - 13.5, "How We Take You From Idea to Factory-Direct Introduction")

    STEP_Y = 199
    STEP_H = 103
    STEP_GAP = 14.0
    STEP_W = (CONTENT_W - 2 * STEP_GAP) / 3.0

    steps = [
        {
            "badge": "STEP 1",
            "meta": "Free · 15 Minutes",
            "title": "1. Consultation on Minup",
            "desc": (
                "Book a free 15-minute call on our Minup calendar. We walk through your product, target volume, "
                "budget, and timeline, and tell you straight if we can add value."
            ),
            "outcome": "Next: Written scope proposal (if we fit)",
            "active": True,
        },
        {
            "badge": "STEP 2",
            "meta": "Fixed Written Scope",
            "title": "2. Research & Matching",
            "desc": (
                "We shortlist capable manufacturers, check their business registration and compliance documents, "
                "and compare their quotes side by side on equal commercial terms."
            ),
            "outcome": "Deliverable: Side-by-side quote & risk brief",
            "active": False,
        },
        {
            "badge": "STEP 3",
            "meta": "0% Ongoing Markup",
            "title": "3. Factory-Direct Intro",
            "desc": (
                "Once you review the evidence and pick your preferred supplier, we introduce you directly to the "
                "factory so you sign contracts and place orders with them directly."
            ),
            "outcome": "Outcome: You own the factory relationship",
            "active": False,
        },
    ]

    for idx, st in enumerate(steps):
        sx = MARGIN + idx * (STEP_W + STEP_GAP)
        draw_elevated_card(
            c,
            sx,
            STEP_Y,
            STEP_W,
            STEP_H,
            radius=7,
            border=COBALT_PRIMARY if st["active"] else BORDER_LIGHT,
            lw=1.15 if st["active"] else 0.85,
        )

        # Badge pill
        c.setFillColor(COBALT_PRIMARY if st["active"] else CARD_SLATE)
        c.roundRect(sx + 10, STEP_Y + STEP_H - 20, 42, 12.5, 3, stroke=0, fill=1)
        c.setFont("Inter-Bold", 6.5)
        c.setFillColor(TEXT_WHITE if st["active"] else COBALT_PRIMARY)
        c.drawCentredString(sx + 31, STEP_Y + STEP_H - 15.8, st["badge"])

        c.setFont("Inter-SemiBold", 6.5)
        c.setFillColor(INK_MUTED)
        c.drawRightString(sx + STEP_W - 10, STEP_Y + STEP_H - 15.5, st["meta"])

        # Step Title
        c.setFont("Inter-Bold", 9.6)
        c.setFillColor(INK_DARK)
        c.drawString(sx + 10, STEP_Y + STEP_H - 34, st["title"])

        # Step Description (strictly 4 lines max)
        draw_wrapped_text(
            c, st["desc"], sx + 10, STEP_Y + STEP_H - 46.5, STEP_W - 20, "Inter-Regular", 7.1, 9.6, INK_BODY
        )

        # Bottom outcome pill inside step card
        c.setFillColor(CARD_SLATE)
        c.roundRect(sx + 7, STEP_Y + 6.5, STEP_W - 14, 14, 3, stroke=0, fill=1)
        c.setFont("Inter-SemiBold", 6.2)
        c.setFillColor(COBALT_PRIMARY if st["active"] else INK_DARK)
        c.drawString(sx + 12, STEP_Y + 11.2, st["outcome"])

        if st["active"]:
            c.linkURL("https://app.minup.io/book/stratevo", (sx, STEP_Y, sx + STEP_W, STEP_Y + STEP_H), relative=0)

        if idx < 2:
            ax = sx + STEP_W + STEP_GAP / 2.0
            ay = STEP_Y + STEP_H / 2.0
            draw_right_arrow(c, ax, ay, r=6.0)

    # =========================================================================
    # 5. SECTION 4: BIG CALL TO ACTION + PREP CHECKLIST + MINUP QR (y = 18 to 188)
    # =========================================================================
    CTA_Y = 18
    CTA_H = 170
    CTA_TOP = CTA_Y + CTA_H

    c.setFillColor(NAVY_DEEP)
    c.setStrokeColor(COBALT_PRIMARY)
    c.setLineWidth(1.5)
    c.roundRect(MARGIN, CTA_Y, CONTENT_W, CTA_H, 9, stroke=1, fill=1)

    # Top inner cobalt bar
    c.setFillColor(COBALT_PRIMARY)
    c.roundRect(MARGIN, CTA_TOP - 4.5, CONTENT_W, 4.5, 2, stroke=0, fill=1)

    CTA_LX = MARGIN + 16
    CTA_LW = 352

    c.setFont("Inter-Bold", 6.8)
    c.setFillColor(ICE_BLUE)
    c.drawString(CTA_LX, CTA_TOP - 19, "04 / BOOK YOUR FREE CONSULTATION  ·  DIRECT MINUP CALENDAR")

    c.setFont("Inter-ExtraBold", 14.5)
    c.setFillColor(TEXT_WHITE)
    c.drawString(CTA_LX, CTA_TOP - 36, "Book a Free 15-Minute Sourcing Call With Billy")

    cta_sub = (
        "Have a product you want to source from China or an existing quote that feels incomplete? "
        "Grab a 15-minute slot on Minup. No hard sell and no obligation."
    )
    draw_wrapped_text(c, cta_sub, CTA_LX, CTA_TOP - 49.5, CTA_LW, "Inter-Regular", 7.6, 10.4, TEXT_MUTED_DARK)

    # What to bring checklist (2x2 grid)
    c.setFont("Inter-Bold", 6.3)
    c.setFillColor(ICE_LIGHT)
    c.drawString(CTA_LX, CTA_TOP - 73.5, "USEFUL TO BRING TO YOUR CALL (EVEN IF PROVISIONAL):")

    prep = [
        (CTA_LX, CTA_TOP - 84, "Product photo, link, or shareable spec"),
        (CTA_LX + 174, CTA_TOP - 84, "Target order quantity & destination country"),
        (CTA_LX, CTA_TOP - 94.5, "Rough budget, timeline, or supplier quote"),
        (CTA_LX + 174, CTA_TOP - 94.5, "Custom branding or compliance requirements"),
    ]
    for px, py, ptxt in prep:
        draw_check_icon(c, px, py - 0.5, size=5.0, color=ICE_BLUE)
        c.setFont("Inter-Medium", 6.55)
        c.setFillColor(TEXT_WHITE)
        c.drawString(px + 9, py, ptxt)

    # BIG CALL-TO-ACTION BUTTON linking directly to https://app.minup.io/book/stratevo
    BTN_X = CTA_LX
    BTN_Y = CTA_Y + 24
    BTN_W = CTA_LW
    BTN_H = 42

    c.setFillColor(HexColor("#0D337A"))
    c.roundRect(BTN_X + 2, BTN_Y - 2.5, BTN_W, BTN_H, 6.5, stroke=0, fill=1)

    c.setFillColor(COBALT_BRIGHT)
    c.setStrokeColor(COBALT_GLOW)
    c.setLineWidth(1.3)
    c.roundRect(BTN_X, BTN_Y, BTN_W, BTN_H, 6.5, stroke=1, fill=1)

    btn_label = "BOOK YOUR FREE 15-MIN SOURCING CALL ON MINUP"
    c.setFont("Inter-ExtraBold", 10.8)
    c.setFillColor(TEXT_WHITE)
    lbl_w = pdfmetrics.stringWidth(btn_label, "Inter-ExtraBold", 10.8)
    lbl_x = BTN_X + (BTN_W - lbl_w - 15) / 2.0
    c.drawString(lbl_x, BTN_Y + 23.0, btn_label)
    draw_ne_arrow(c, lbl_x + lbl_w + 5, BTN_Y + 23.2, size=7.0, color=TEXT_WHITE, lw=1.5)

    c.setFont("Inter-SemiBold", 7.4)
    c.setFillColor(ICE_LIGHT)
    c.drawCentredString(
        BTN_X + BTN_W / 2.0,
        BTN_Y + 9.0,
        "Click to open calendar:  https://app.minup.io/book/stratevo",
    )

    c.linkURL(
        "https://app.minup.io/book/stratevo",
        (BTN_X, BTN_Y, BTN_X + BTN_W, BTN_Y + BTN_H),
        relative=0,
    )

    c.setFont("Inter-Regular", 6.1)
    c.setFillColor(TEXT_MUTED_DARK)
    c.drawString(
        CTA_LX,
        CTA_Y + 10.5,
        "Independent B2B facilitator: STRATEVO does not sell goods. Paid work starts with a separate written proposal.",
    )

    # Right Consultant Contact & QR Box inside CTA
    RBOX_X = MARGIN + 380
    RBOX_Y = CTA_Y + 11
    RBOX_W = CONTENT_W - 392  # 151.28pt
    RBOX_H = CTA_H - 24       # 146pt

    c.setFillColor(NAVY_PANEL)
    c.setStrokeColor(NAVY_LINE)
    c.setLineWidth(0.85)
    c.roundRect(RBOX_X, RBOX_Y, RBOX_W, RBOX_H, 6.5, stroke=1, fill=1)

    qr = qrcode.QRCode(version=2, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=1)
    qr.add_data("https://app.minup.io/book/stratevo")
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="#070B12", back_color="#FFFFFF").convert("RGB")
    qr_buf = io.BytesIO()
    qr_img.save(qr_buf, format="PNG")
    qr_buf.seek(0)

    QR_SIZE = 50
    QR_X = RBOX_X + RBOX_W - QR_SIZE - 9
    QR_Y = RBOX_Y + RBOX_H - QR_SIZE - 10
    c.setFillColor(CARD_WHITE)
    c.roundRect(QR_X - 2.5, QR_Y - 2.5, QR_SIZE + 5, QR_SIZE + 5, 4, stroke=0, fill=1)
    c.drawImage(ImageReader(qr_buf), QR_X, QR_Y, width=QR_SIZE, height=QR_SIZE)
    c.linkURL(
        "https://app.minup.io/book/stratevo",
        (QR_X - 3, QR_Y - 3, QR_X + QR_SIZE + 3, QR_Y + QR_SIZE + 3),
        relative=0,
    )

    CX = RBOX_X + 9
    CY = RBOX_Y + RBOX_H - 14
    c.setFont("Inter-Bold", 6.0)
    c.setFillColor(ICE_BLUE)
    c.drawString(CX, CY, "DIRECT CONTACT")

    c.setFont("Inter-Bold", 8.1)
    c.setFillColor(TEXT_WHITE)
    c.drawString(CX, CY - 12, "Vasilis (Billy)")
    c.drawString(CX, CY - 21.5, "Krevatsoulis")

    c.setFont("Inter-Regular", 6.2)
    c.setFillColor(TEXT_MUTED_DARK)
    c.drawString(CX, CY - 32, "Founder, STRATEVO")
    c.drawString(CX, CY - 40.5, "Europe (Greece)")

    c.setFillColor(NAVY_CARD)
    c.setStrokeColor(COBALT_GLOW)
    c.setLineWidth(0.5)
    c.roundRect(CX, CY - 53.5, 74, 10, 2.5, stroke=1, fill=1)
    c.setFont("Inter-Bold", 5.5)
    c.setFillColor(ICE_LIGHT)
    c.drawCentredString(CX + 37, CY - 50, "SCAN QR TO BOOK")

    LINE_Y = QR_Y - 9
    c.setStrokeColor(NAVY_LINE)
    c.setLineWidth(0.6)
    c.line(CX, LINE_Y, RBOX_X + RBOX_W - 9, LINE_Y)

    contacts = [
        ("Web:", "stratevo.online", "https://stratevo.online"),
        ("Minup:", "app.minup.io/book/stratevo", "https://app.minup.io/book/stratevo"),
        ("Email:", "info@stratevo.store", "mailto:info@stratevo.store"),
        ("Phone:", "+30 6989472740", "tel:+306989472740"),
    ]
    cy_row = LINE_Y - 11.5
    for lbl, val, url in contacts:
        c.setFont("Inter-SemiBold", 6.1)
        c.setFillColor(TEXT_MUTED_DARK)
        c.drawString(CX, cy_row, lbl)
        c.setFont("Inter-SemiBold", 6.2)
        c.setFillColor(ICE_BLUE if ("minup" in val or "stratevo.online" in val) else TEXT_WHITE)
        c.drawString(CX + 26, cy_row, val)
        c.linkURL(url, (CX, cy_row - 2, RBOX_X + RBOX_W - 9, cy_row + 8), relative=0)
        cy_row -= 12.0

    c.showPage()
    c.save()


if __name__ == "__main__":
    p1 = "/home/user/stratevo/STRATEVO_Sourcing_and_Advisory_Overview.pdf"
    build_pdf(p1)
    shutil.copyfile(p1, p2)
    doc = fitz.open(p1)
    pix = doc[0].get_pixmap(dpi=250)
    pix.save("/home/user/stratevo/STRATEVO_Sourcing_and_Advisory_Overview_Preview.png")
    pix.save("/tmp/brochure_v3.png")
    print("Generated upgraded PDFs and high-DPI PNG successfully.")

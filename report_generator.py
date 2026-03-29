from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from datetime import datetime
import os

# ── BRAND COLORS ──────────────────────────────────────────────────────────────
DARK_BG     = colors.HexColor("#0D1117")
ACCENT      = colors.HexColor("#3B82F6")   # blue
ACCENT2     = colors.HexColor("#10B981")   # green
WARN        = colors.HexColor("#F59E0B")   # amber
DANGER      = colors.HexColor("#EF4444")   # red
LIGHT_GRAY  = colors.HexColor("#F3F4F6")
MID_GRAY    = colors.HexColor("#6B7280")
DARK_TEXT   = colors.HexColor("#111827")
WHITE       = colors.white

W, H = A4

def score_color(score: float):
    if score >= 70: return ACCENT2
    if score >= 40: return WARN
    return DANGER

def threat_color(level: str):
    l = level.lower()
    if "high" in l: return DANGER
    if "medium" in l or "med" in l: return WARN
    return ACCENT2

def fmt_millions(val):
    if not val or val <= 0: return "N/A"
    if val >= 1000: return f"${val/1000:.1f}B"
    return f"${val:.1f}M"

def build_styles():
    base = getSampleStyleSheet()
    s = {}

    s["cover_company"] = ParagraphStyle("cover_company",
        fontSize=32, textColor=WHITE, fontName="Helvetica-Bold",
        spaceAfter=4, leading=36)

    s["cover_sub"] = ParagraphStyle("cover_sub",
        fontSize=13, textColor=colors.HexColor("#93C5FD"),
        fontName="Helvetica", spaceAfter=2)

    s["section_header"] = ParagraphStyle("section_header",
        fontSize=13, textColor=ACCENT, fontName="Helvetica-Bold",
        spaceBefore=14, spaceAfter=6, leading=16)

    s["field_label"] = ParagraphStyle("field_label",
        fontSize=8, textColor=MID_GRAY, fontName="Helvetica-Bold",
        spaceAfter=1, leading=10)

    s["field_value"] = ParagraphStyle("field_value",
        fontSize=10, textColor=DARK_TEXT, fontName="Helvetica",
        spaceAfter=4, leading=13)

    s["body"] = ParagraphStyle("body",
        fontSize=9.5, textColor=DARK_TEXT, fontName="Helvetica",
        spaceAfter=4, leading=14)

    s["verdict_text"] = ParagraphStyle("verdict_text",
        fontSize=9, textColor=DARK_TEXT, fontName="Helvetica",
        spaceAfter=3, leading=13)

    s["footer"] = ParagraphStyle("footer",
        fontSize=7.5, textColor=MID_GRAY, fontName="Helvetica",
        alignment=TA_CENTER)

    s["tag"] = ParagraphStyle("tag",
        fontSize=8, textColor=WHITE, fontName="Helvetica-Bold",
        alignment=TA_CENTER)

    return s


def kv_row(label, value, s):
    """Two-column key-value block."""
    return [
        Paragraph(label.upper(), s["field_label"]),
        Paragraph(str(value) if value else "N/A", s["field_value"])
    ]


def section_line(s):
    return HRFlowable(width="100%", thickness=0.5,
                      color=colors.HexColor("#E5E7EB"), spaceAfter=6)


def generate_report(startup, output_path: str = "/mnt/user-data/outputs/scout_report.pdf"):
    """
    Generate a VC-grade PDF dossier from a StartupState object or dict.
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Accept both Pydantic model and plain dict
    if hasattr(startup, "model_dump"):
        d = startup.model_dump()
    else:
        d = dict(startup)

    s = build_styles()
    doc = SimpleDocTemplate(
        output_path, pagesize=A4,
        leftMargin=18*mm, rightMargin=18*mm,
        topMargin=14*mm, bottomMargin=14*mm
    )

    story = []
    score = d.get("investment_score", 0) or 0

    # ── COVER HEADER ──────────────────────────────────────────────────────────
    cover_data = [[
        Paragraph(d.get("company_name", "Unknown"), s["cover_company"]),
        ""
    ]]
    cover_table = Table(cover_data, colWidths=[W*0.65, W*0.27])
    cover_table.setStyle(TableStyle([
        ("BACKGROUND",   (0,0), (-1,-1), DARK_BG),
        ("TOPPADDING",   (0,0), (-1,-1), 16),
        ("BOTTOMPADDING",(0,0), (-1,-1), 16),
        ("LEFTPADDING",  (0,0), (-1,-1), 14),
        ("RIGHTPADDING", (0,0), (-1,-1), 14),
        ("ROUNDEDCORNERS", (0,0), (-1,-1), [6,6,6,6]),
    ]))
    story.append(cover_table)

    # Meta row: industry | website | date
    meta_parts = []
    if d.get("industry"): meta_parts.append(d["industry"])
    if d.get("website"):  meta_parts.append(d["website"])
    meta_parts.append(f"Generated {datetime.now().strftime('%b %d, %Y')}")
    story.append(Spacer(1, 5))
    story.append(Paragraph(" · ".join(meta_parts), s["cover_sub"]))
    story.append(Spacer(1, 10))

    # ── SCORE BANNER ──────────────────────────────────────────────────────────
    verdict_raw = d.get("critic_verdict", "")
    verdict_label = "Watchlist"
    for word in ["Should Buy", "Don't Buy", "Watchlist"]:
        if word.lower() in verdict_raw.lower():
            verdict_label = word
            break

    score_color_val = score_color(score)
    banner = Table([[
        Paragraph(f"<b>SCOUT SCORE</b><br/><font size=26>{int(score)}</font>/100",
                  ParagraphStyle("sc", fontSize=10, textColor=WHITE,
                                 fontName="Helvetica-Bold", alignment=TA_CENTER, leading=30)),
        Paragraph(f"<b>VERDICT</b><br/><font size=18>{verdict_label}</font>",
                  ParagraphStyle("vd", fontSize=10, textColor=WHITE,
                                 fontName="Helvetica-Bold", alignment=TA_CENTER, leading=26)),
        Paragraph(f"<b>STAGE</b><br/><font size=13>{'Public' if d.get('is_public') else 'Private'}</font>",
                  ParagraphStyle("st", fontSize=10, textColor=WHITE,
                                 fontName="Helvetica-Bold", alignment=TA_CENTER, leading=20)),
        Paragraph(f"<b>HIRING</b><br/><font size=13>{d.get('hiring_status','Unknown')}</font>",
                  ParagraphStyle("hr", fontSize=10, textColor=WHITE,
                                 fontName="Helvetica-Bold", alignment=TA_CENTER, leading=20)),
    ]], colWidths=[45*mm, 60*mm, 40*mm, 40*mm])

    banner.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (0,0), score_color_val),
        ("BACKGROUND",    (1,0), (1,0), ACCENT),
        ("BACKGROUND",    (2,0), (2,0), colors.HexColor("#1E293B")),
        ("BACKGROUND",    (3,0), (3,0), colors.HexColor("#1E293B")),
        ("TOPPADDING",    (0,0), (-1,-1), 10),
        ("BOTTOMPADDING", (0,0), (-1,-1), 10),
        ("ALIGN",         (0,0), (-1,-1), "CENTER"),
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
        ("ROUNDEDCORNERS",(0,0), (-1,-1), [4,4,4,4]),
        ("GRID",          (0,0), (-1,-1), 0.5, colors.HexColor("#374151")),
    ]))
    story.append(banner)
    story.append(Spacer(1, 12))

    # ── FINANCIALS GRID ───────────────────────────────────────────────────────
    story.append(Paragraph("💰 Financials", s["section_header"]))
    story.append(section_line(s))

    fin_data = [
        [Paragraph("TOTAL FUNDING", s["field_label"]),
         Paragraph("LATEST VALUATION", s["field_label"]),
         Paragraph("ANNUAL REVENUE", s["field_label"]),
         Paragraph("HEADCOUNT", s["field_label"])],
        [Paragraph(fmt_millions(d.get("total_funding")), ParagraphStyle("fv", fontSize=16, fontName="Helvetica-Bold", textColor=ACCENT)),
         Paragraph(fmt_millions(d.get("latest_valuation")), ParagraphStyle("fv2", fontSize=16, fontName="Helvetica-Bold", textColor=ACCENT2)),
         Paragraph(fmt_millions(d.get("annual_revenue")), ParagraphStyle("fv3", fontSize=16, fontName="Helvetica-Bold", textColor=DARK_TEXT)),
         Paragraph(str(d.get("headcount") or "N/A"), ParagraphStyle("fv4", fontSize=16, fontName="Helvetica-Bold", textColor=DARK_TEXT))],
        [Paragraph("RUNWAY", s["field_label"]),
         Paragraph("MONTHLY BURN", s["field_label"]),
         Paragraph("OPEN ROLES", s["field_label"]),
         Paragraph("VIBE SCORE", s["field_label"])],
        [Paragraph(f"{d.get('runway_months', 0):.1f} mo", ParagraphStyle("fv5", fontSize=13, fontName="Helvetica-Bold", textColor=WARN)),
         Paragraph(fmt_millions((d.get("estimated_monthly_burn") or 0)/1_000_000), ParagraphStyle("fv6", fontSize=13, fontName="Helvetica-Bold", textColor=DARK_TEXT)),
         Paragraph(str(d.get("open_roles") or 0), ParagraphStyle("fv7", fontSize=13, fontName="Helvetica-Bold", textColor=DARK_TEXT)),
         Paragraph(f"{d.get('vibe_score', 5):.1f}/10", ParagraphStyle("fv8", fontSize=13, fontName="Helvetica-Bold", textColor=score_color(d.get('vibe_score',5)*10)))],
    ]
    fin_table = Table(fin_data, colWidths=[42*mm]*4)
    fin_table.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,-1), LIGHT_GRAY),
        ("TOPPADDING",    (0,0), (-1,-1), 8),
        ("BOTTOMPADDING", (0,0), (-1,-1), 8),
        ("LEFTPADDING",   (0,0), (-1,-1), 8),
        ("GRID",          (0,0), (-1,-1), 0.4, colors.HexColor("#D1D5DB")),
        ("ROWBACKGROUNDS",(0,0), (-1,-1), [WHITE, LIGHT_GRAY, WHITE, LIGHT_GRAY]),
    ]))
    story.append(fin_table)
    story.append(Spacer(1, 10))

    # ── FUNDING HISTORY ───────────────────────────────────────────────────────
    funding_history = d.get("funding_history", [])
    if funding_history:
        story.append(Paragraph("📈 Funding History", s["section_header"]))
        story.append(section_line(s))
        fh_rows = [[
            Paragraph("ROUND", s["field_label"]),
            Paragraph("AMOUNT", s["field_label"]),
            Paragraph("DATE", s["field_label"]),
            Paragraph("INVESTORS", s["field_label"]),
        ]]
        for rnd in funding_history:
            if isinstance(rnd, dict):
                investors = rnd.get("investors", [])
                round_name = rnd.get("round_name", "N/A")
                amount = rnd.get("amount", 0)
                date = rnd.get("date", "N/A")
            else:
                investors = getattr(rnd, "investors", [])
                round_name = getattr(rnd, "round_name", "N/A")
                amount = getattr(rnd, "amount", 0)
                date = getattr(rnd, "date", "N/A")

            investor_str = ", ".join(investors) if investors else "Undisclosed"
            fh_rows.append([
                Paragraph(str(round_name), s["body"]),
                Paragraph(fmt_millions(amount), ParagraphStyle("amt", fontSize=10, fontName="Helvetica-Bold", textColor=ACCENT2)),
                Paragraph(str(date), s["body"]),
                Paragraph(investor_str[:80], s["body"]),
            ])
        fh_table = Table(fh_rows, colWidths=[28*mm, 25*mm, 28*mm, 87*mm])
        fh_table.setStyle(TableStyle([
            ("BACKGROUND",    (0,0), (-1,0), DARK_BG),
            ("TEXTCOLOR",     (0,0), (-1,0), WHITE),
            ("ROWBACKGROUNDS",(0,1), (-1,-1), [WHITE, LIGHT_GRAY]),
            ("GRID",          (0,0), (-1,-1), 0.4, colors.HexColor("#D1D5DB")),
            ("TOPPADDING",    (0,0), (-1,-1), 6),
            ("BOTTOMPADDING", (0,0), (-1,-1), 6),
            ("LEFTPADDING",   (0,0), (-1,-1), 6),
        ]))
        story.append(fh_table)
        story.append(Spacer(1, 10))

    # ── FOUNDERS ──────────────────────────────────────────────────────────────
    founders = d.get("founders", [])
    if founders:
        story.append(Paragraph("👥 Founding Team", s["section_header"]))
        story.append(section_line(s))
        for f in founders:
            if isinstance(f, dict):
                name = f.get("name", "Unknown")
                role = f.get("role", "Founder")
                bio  = f.get("bio", "")
                li   = f.get("linkedin", "")
            else:
                name = getattr(f, "name", "Unknown")
                role = getattr(f, "role", "Founder")
                bio  = getattr(f, "bio", "")
                li   = getattr(f, "linkedin", "")

            li_str = f" · {li}" if li and li.lower() != "unknown" else ""
            founder_row = Table([[
                Paragraph(f"<b>{name}</b> · <i>{role}</i>{li_str}", s["body"]),
            ]], colWidths=[168*mm])
            founder_row.setStyle(TableStyle([
                ("BACKGROUND",    (0,0), (-1,-1), colors.HexColor("#EFF6FF")),
                ("LEFTPADDING",   (0,0), (-1,-1), 8),
                ("TOPPADDING",    (0,0), (-1,-1), 5),
                ("BOTTOMPADDING", (0,0), (-1,-1), 2),
                ("ROUNDEDCORNERS",(0,0), (-1,-1), [3,3,3,3]),
            ]))
            story.append(founder_row)
            if bio:
                story.append(Paragraph(bio, s["body"]))
            story.append(Spacer(1, 4))
        story.append(Spacer(1, 6))

    # ── MOAT ──────────────────────────────────────────────────────────────────
    moat = d.get("moat_description", "")
    if moat:
        story.append(Paragraph("🏰 Competitive Moat", s["section_header"]))
        story.append(section_line(s))
        moat_box = Table([[Paragraph(moat, s["body"])]], colWidths=[168*mm])
        moat_box.setStyle(TableStyle([
            ("BACKGROUND",    (0,0), (-1,-1), colors.HexColor("#F0FDF4")),
            ("LEFTPADDING",   (0,0), (-1,-1), 10),
            ("TOPPADDING",    (0,0), (-1,-1), 8),
            ("BOTTOMPADDING", (0,0), (-1,-1), 8),
            ("LINEAFTER",     (0,0), (0,-1), 3, ACCENT2),
        ]))
        story.append(moat_box)
        story.append(Spacer(1, 10))

    # ── COMPETITORS ───────────────────────────────────────────────────────────
    competitors = d.get("competitors", [])
    if competitors:
        story.append(Paragraph("⚔️ Competitor Matrix", s["section_header"]))
        story.append(section_line(s))
        comp_rows = [[
            Paragraph("COMPANY", s["field_label"]),
            Paragraph("DESCRIPTION", s["field_label"]),
            Paragraph("THREAT", s["field_label"]),
        ]]
        for c in competitors:
            if isinstance(c, dict):
                name  = c.get("name", "")
                desc  = c.get("description", "")
                level = c.get("threat_level", "Medium")
            else:
                name  = getattr(c, "name", "")
                desc  = getattr(c, "description", "")
                level = getattr(c, "threat_level", "Medium")

            tc = threat_color(level)
            comp_rows.append([
                Paragraph(f"<b>{name}</b>", s["body"]),
                Paragraph(desc, s["body"]),
                Paragraph(level, ParagraphStyle("tl", fontSize=8, fontName="Helvetica-Bold",
                                                 textColor=tc, alignment=TA_CENTER)),
            ])
        comp_table = Table(comp_rows, colWidths=[38*mm, 108*mm, 22*mm])
        comp_table.setStyle(TableStyle([
            ("BACKGROUND",    (0,0), (-1,0), DARK_BG),
            ("TEXTCOLOR",     (0,0), (-1,0), WHITE),
            ("ROWBACKGROUNDS",(0,1), (-1,-1), [WHITE, LIGHT_GRAY]),
            ("GRID",          (0,0), (-1,-1), 0.4, colors.HexColor("#D1D5DB")),
            ("TOPPADDING",    (0,0), (-1,-1), 6),
            ("BOTTOMPADDING", (0,0), (-1,-1), 6),
            ("LEFTPADDING",   (0,0), (-1,-1), 6),
            ("ALIGN",         (2,0), (2,-1), "CENTER"),
        ]))
        story.append(comp_table)
        story.append(Spacer(1, 10))

    # ── COMMUNITY SENTIMENT ───────────────────────────────────────────────────
    sentiment = d.get("community_sentiment", "")
    vibe = d.get("vibe_score", 5)
    if sentiment:
        story.append(Paragraph("💬 Community Sentiment", s["section_header"]))
        story.append(section_line(s))
        sent_box = Table([[
            Paragraph(f"<b>Vibe Score: {vibe}/10</b><br/>{sentiment}", s["body"])
        ]], colWidths=[168*mm])
        sent_box.setStyle(TableStyle([
            ("BACKGROUND",  (0,0), (-1,-1), colors.HexColor("#FFF7ED")),
            ("LEFTPADDING", (0,0), (-1,-1), 10),
            ("TOPPADDING",  (0,0), (-1,-1), 8),
            ("BOTTOMPADDING",(0,0),(-1,-1), 8),
            ("LINEAFTER",   (0,0), (0,-1), 3, WARN),
        ]))
        story.append(sent_box)
        story.append(Spacer(1, 10))

    # ── CRITIC VERDICT ────────────────────────────────────────────────────────
    if verdict_raw:
        story.append(Paragraph("🧐 Scout Verdict", s["section_header"]))
        story.append(section_line(s))

        # Clean up the verdict text
        clean_verdict = verdict_raw.replace("**", "").replace("*", "•")
        for line in clean_verdict.split("\n"):
            line = line.strip()
            if not line: continue
            if line.startswith("FINAL SCOUT SCORE"): continue
            story.append(Paragraph(line, s["verdict_text"]))
        story.append(Spacer(1, 10))

    # ── SOURCES ───────────────────────────────────────────────────────────────
    sources = d.get("sources", {})
    if sources:
        story.append(Paragraph("🔗 Sources", s["section_header"]))
        story.append(section_line(s))
        for k, v in sources.items():
            if v and v.lower() not in ("unknown", "not found", "n/a"):
                story.append(Paragraph(
                    f"<b>{k.replace('_',' ').title()}:</b> {v}",
                    ParagraphStyle("src", fontSize=7.5, textColor=MID_GRAY,
                                   fontName="Helvetica", leading=11, spaceAfter=2)
                ))
        story.append(Spacer(1, 6))

    # ── FOOTER ────────────────────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=0.5, color=MID_GRAY))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        f"🛡️ The Startup Scout · Autonomous VC Due Diligence · {datetime.now().strftime('%B %d, %Y')} · CONFIDENTIAL",
        s["footer"]
    ))

    doc.build(story)
    return output_path


# ── STANDALONE TEST ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    sample = {
        "company_name": "Artisan AI",
        "industry": "AI Sales Agents / SaaS",
        "website": "https://artisan.co",
        "is_public": False,
        "investment_score": 69,
        "total_funding": 46.1,
        "latest_valuation": 125,
        "annual_revenue": 7,
        "headcount": 88,
        "estimated_monthly_burn": 1650000,
        "runway_months": 27.94,
        "open_roles": 10,
        "vibe_score": 5.0,
        "hiring_status": "Aggressive",
        "community_sentiment": "Mixed sentiment — some Reddit users disappointed by overpromising marketing vs actual product delivery.",
        "moat_description": "Artisan's moat lies in its focus on creating autonomous AI employees rather than assistants. Their 'Stop Hiring Humans' campaign generated significant brand awareness. Strong VC backing and rapid ARR growth indicate product-market fit.",
        "founders": [
            {"name": "Jaspar Carmichael-Jack", "role": "CEO", "bio": "Third-time founder, Oxford alumnus, previously at Meta and IBM.", "linkedin": "https://linkedin.com/in/jaspar-carmichael-jack"},
            {"name": "Sam Stallings", "role": "CPO", "bio": "8 years at IBM, founding engineer at a YC startup.", "linkedin": "Unknown"},
            {"name": "Rupert Henry Dodkins", "role": "Former Co-Founder", "bio": "Co-founded Artisan in 2023.", "linkedin": "Unknown"},
        ],
        "funding_history": [
            {"round_name": "Pre-Seed", "amount": 2.3, "date": "2023", "investors": []},
            {"round_name": "Seed", "amount": 11.5, "date": "September 2024", "investors": ["HubSpot Ventures", "Y Combinator"]},
            {"round_name": "Series A", "amount": 25.0, "date": "April 2025", "investors": ["Glade Brook Capital", "HubSpot Ventures", "Y Combinator", "BOND"]},
        ],
        "competitors": [
            {"name": "11x.ai", "description": "Fully autonomous AI SDRs for enterprise.", "threat_level": "High"},
            {"name": "Apollo.io", "description": "Sales intelligence and engagement platform.", "threat_level": "Medium"},
            {"name": "AiSDR", "description": "Budget-friendly AI BDR with LinkedIn workflows.", "threat_level": "Medium"},
        ],
        "critic_verdict": "**VERDICT:** Watchlist\n\n**OPPORTUNITIES:**\n- Strong founding team with YC and IBM pedigree\n- $46M raised with real ARR traction at $7M\n- Unique 'AI employee' positioning vs chatbot competitors\n\n**RED FLAGS:**\n- Rapidly evolving competitive landscape\n- Marketing overpromise vs product delivery gap on Reddit\n\n**STRATEGIC NARRATIVE:**\nArtisan has genuine traction and differentiated positioning in a crowded market. The 'Stop Hiring Humans' brand is polarizing but memorable. With 28 months of runway and aggressive hiring, they have time to prove out the full AI employee vision beyond outbound sales.\n\nFINAL SCOUT SCORE: 69.0",
        "sources": {
            "total_funding": "https://tracxn.com/d/companies/artisan",
            "annual_revenue": "https://techcrunch.com/2025/04/09/artisan-raises-25m",
            "headcount": "https://tracxn.com/d/companies/artisan",
        }
    }
    path = generate_report(sample, "/home/claude/test_report.pdf")
    print(f"✅ Report generated: {path}")

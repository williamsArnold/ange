"""
Générateur de rapport M&A au format PDF professionnel.
Utilise ReportLab pour produire un document structuré de 10-15 pages.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    HRFlowable,
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from src.analyzer import CompanyAnalysis, analyze_consolidated
from src.extractor import CompanyData

# ---------------------------------------------------------------------------
# Palette de couleurs
# ---------------------------------------------------------------------------
COLOR_NAVY = colors.HexColor("#1A2B4A")
COLOR_GOLD = colors.HexColor("#C9963A")
COLOR_LIGHT_BLUE = colors.HexColor("#EBF2FB")
COLOR_MID_GRAY = colors.HexColor("#6B7280")
COLOR_GREEN = colors.HexColor("#166534")
COLOR_RED = colors.HexColor("#9B1C1C")
COLOR_TABLE_HEADER = colors.HexColor("#1A2B4A")
COLOR_TABLE_ALT = colors.HexColor("#F3F7FC")
COLOR_WHITE = colors.white

PAGE_WIDTH, PAGE_HEIGHT = A4

# ---------------------------------------------------------------------------
# Styles de paragraphes
# ---------------------------------------------------------------------------

def _build_styles() -> dict:
    base = getSampleStyleSheet()
    styles = {}

    styles["cover_title"] = ParagraphStyle(
        "cover_title",
        fontSize=26,
        fontName="Helvetica-Bold",
        textColor=COLOR_WHITE,
        alignment=TA_CENTER,
        spaceAfter=8,
        leading=32,
    )
    styles["cover_subtitle"] = ParagraphStyle(
        "cover_subtitle",
        fontSize=14,
        fontName="Helvetica",
        textColor=COLOR_WHITE,
        alignment=TA_CENTER,
        spaceAfter=6,
        leading=20,
    )
    styles["cover_meta"] = ParagraphStyle(
        "cover_meta",
        fontSize=10,
        fontName="Helvetica",
        textColor=colors.HexColor("#C0C8D8"),
        alignment=TA_CENTER,
        leading=16,
    )
    styles["h1"] = ParagraphStyle(
        "h1",
        fontSize=16,
        fontName="Helvetica-Bold",
        textColor=COLOR_NAVY,
        spaceBefore=14,
        spaceAfter=6,
        leading=20,
        borderPad=4,
    )
    styles["h2"] = ParagraphStyle(
        "h2",
        fontSize=13,
        fontName="Helvetica-Bold",
        textColor=COLOR_NAVY,
        spaceBefore=10,
        spaceAfter=4,
        leading=17,
    )
    styles["h3"] = ParagraphStyle(
        "h3",
        fontSize=11,
        fontName="Helvetica-Bold",
        textColor=COLOR_GOLD,
        spaceBefore=8,
        spaceAfter=3,
        leading=15,
    )
    styles["body"] = ParagraphStyle(
        "body",
        fontSize=9.5,
        fontName="Helvetica",
        textColor=colors.black,
        alignment=TA_JUSTIFY,
        spaceAfter=4,
        leading=14,
    )
    styles["bullet"] = ParagraphStyle(
        "bullet",
        fontSize=9.5,
        fontName="Helvetica",
        textColor=colors.black,
        leftIndent=12,
        bulletIndent=0,
        spaceAfter=2,
        leading=13,
    )
    styles["label"] = ParagraphStyle(
        "label",
        fontSize=9,
        fontName="Helvetica-Bold",
        textColor=COLOR_NAVY,
        spaceAfter=1,
    )
    styles["value"] = ParagraphStyle(
        "value",
        fontSize=9,
        fontName="Helvetica",
        textColor=colors.black,
        spaceAfter=3,
    )
    styles["highlight"] = ParagraphStyle(
        "highlight",
        fontSize=10,
        fontName="Helvetica-Bold",
        textColor=COLOR_NAVY,
        alignment=TA_CENTER,
        spaceAfter=4,
    )
    styles["disclaimer"] = ParagraphStyle(
        "disclaimer",
        fontSize=7.5,
        fontName="Helvetica-Oblique",
        textColor=COLOR_MID_GRAY,
        alignment=TA_CENTER,
        leading=11,
    )
    styles["footer"] = ParagraphStyle(
        "footer",
        fontSize=7,
        fontName="Helvetica",
        textColor=COLOR_MID_GRAY,
        alignment=TA_CENTER,
    )
    return styles


# ---------------------------------------------------------------------------
# Helpers de mise en forme
# ---------------------------------------------------------------------------

def _fmt(value: float, decimals: int = 0) -> str:
    """Formate une valeur en K€ ou M€."""
    if value == 0:
        return "N/D"
    if abs(value) >= 1_000_000:
        return f"{value / 1_000_000:.{decimals}f} M€"
    if abs(value) >= 1_000:
        return f"{value / 1_000:.{decimals}f} K€"
    return f"{value:.{decimals}f} €"


def _pct(value: float) -> str:
    return f"{value:.1f} %"


def _fmt_ratio(num: float, denom: float) -> float:
    if denom == 0:
        return 0.0
    return num / denom * 100


def _hr(styles: dict) -> HRFlowable:
    return HRFlowable(
        width="100%", thickness=1, color=COLOR_GOLD, spaceAfter=6, spaceBefore=2
    )


def _section_title(text: str, styles: dict) -> list:
    """Retourne un titre de section avec séparateur."""
    return [
        Spacer(1, 4 * mm),
        Paragraph(text, styles["h1"]),
        HRFlowable(width="100%", thickness=2, color=COLOR_NAVY, spaceAfter=4),
    ]


def _subsection_title(text: str, styles: dict) -> Paragraph:
    return Paragraph(text, styles["h2"])


def _sub_subsection_title(text: str, styles: dict) -> Paragraph:
    return Paragraph(text, styles["h3"])


# ---------------------------------------------------------------------------
# Tableaux
# ---------------------------------------------------------------------------

TABLE_STYLE_BASE = TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), COLOR_TABLE_HEADER),
    ("TEXTCOLOR", (0, 0), (-1, 0), COLOR_WHITE),
    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
    ("FONTSIZE", (0, 0), (-1, -1), 8.5),
    ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
    ("ALIGN", (0, 0), (0, -1), "LEFT"),
    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [COLOR_WHITE, COLOR_TABLE_ALT]),
    ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#D1D5DB")),
    ("TOPPADDING", (0, 0), (-1, -1), 3),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
])


def _valuation_table_style(n_rows: int) -> TableStyle:
    style = TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), COLOR_TABLE_HEADER),
        ("TEXTCOLOR", (0, 0), (-1, 0), COLOR_WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("ALIGN", (-1, 0), (-1, -1), "LEFT"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [COLOR_WHITE, COLOR_TABLE_ALT]),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#D1D5DB")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("FONTNAME", (0, n_rows), (-1, n_rows), "Helvetica-Bold"),
        ("BACKGROUND", (0, n_rows), (-1, n_rows), colors.HexColor("#E8F0FB")),
        ("TEXTCOLOR", (0, n_rows), (-1, n_rows), COLOR_NAVY),
    ])
    return style


# ---------------------------------------------------------------------------
# Page de couverture
# ---------------------------------------------------------------------------

def _cover_page(story: list, styles: dict, today: str) -> None:
    """Génère la page de couverture du rapport."""
    # Fond coloré via un grand tableau
    cover_data = [[""]]
    cover_table = Table(cover_data, colWidths=[PAGE_WIDTH - 4 * cm], rowHeights=[7 * cm])
    cover_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), COLOR_NAVY),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(cover_table)
    story.append(Spacer(1, -7 * cm))

    # Texte superposé (centré)
    story.append(Spacer(1, 1.5 * cm))
    story.append(Paragraph("RAPPORT DE DIAGNOSTIC M&amp;A", styles["cover_title"]))
    story.append(Paragraph("Mandat de Cession n°1326", styles["cover_subtitle"]))
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph(
        "SAS ARCH'ANGE3 &amp; SAS LAVANGE<br/>Franchises ANGE — Boulangerie-Pâtisserie",
        styles["cover_subtitle"],
    ))
    story.append(Spacer(1, 0.5 * cm))
    story.append(Paragraph(
        f"Date : {today} &nbsp;&nbsp;|&nbsp;&nbsp; CONFIDENTIEL",
        styles["cover_meta"],
    ))
    story.append(Paragraph(
        "Axe Avenir — Conseil en Haut de Bilan | CNCEF n°05/917",
        styles["cover_meta"],
    ))
    story.append(Spacer(1, 4 * cm))

    # Bandeau doré
    gold_bar = Table([[""]], colWidths=[PAGE_WIDTH - 4 * cm], rowHeights=[0.3 * cm])
    gold_bar.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), COLOR_GOLD)]))
    story.append(gold_bar)
    story.append(Spacer(1, 0.5 * cm))

    # Résumé exécutif en cover
    story.append(Paragraph(
        "Diagnostic 360° réalisé sur la base du mémorandum d'information (Mandat 1326). "
        "Ce rapport présente la valorisation, l'analyse stratégique et les recommandations "
        "pour l'acquisition des deux franchises ANGE en Bretagne / Pays de la Loire.",
        styles["body"],
    ))
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph(
        "<b>Document strictement confidentiel — Réservé à l'acquéreur potentiel</b>",
        ParagraphStyle(
            "conf",
            fontSize=9,
            fontName="Helvetica-Bold",
            textColor=COLOR_RED,
            alignment=TA_CENTER,
        ),
    ))
    story.append(PageBreak())


# ---------------------------------------------------------------------------
# Fiche d'identité
# ---------------------------------------------------------------------------

def _fiche_identite(company: CompanyData, styles: dict) -> list:
    fy = next((y for y in company.sorted_years if y.chiffre_affaires > 0), None)
    ca = _fmt(fy.chiffre_affaires) if fy else "N/D"
    rn = _fmt(fy.resultat_net) if fy else "N/D"

    data = [
        ["Raison sociale", company.name],
        ["SIREN", company.siren],
        ["Forme juridique", company.legal_form],
        ["Adresse", company.address],
        ["Secteur", company.sector],
        ["Convention collective", "Boulangerie-pâtisserie artisanale (IDCC 843)"],
        ["Effectif", f"{company.employees} salariés (dont apprentis)"],
        ["CA dernier exercice", ca],
        ["Résultat net dernier exercice", rn],
        ["Enseigne", "ANGE — 2ème réseau boulangerie France (+250 unités)"],
    ]

    table = Table(data, colWidths=[5 * cm, 11.5 * cm])
    table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (0, -1), COLOR_NAVY),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [COLOR_WHITE, COLOR_TABLE_ALT]),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#D1D5DB")),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return [table, Spacer(1, 4 * mm)]


# ---------------------------------------------------------------------------
# Tableau synoptique financier
# ---------------------------------------------------------------------------

def _tableau_synoptique(company: CompanyData, styles: dict) -> list:
    years = company.sorted_years[:3]
    header = ["Indicateur (€)"] + [f"Exercice {y.year}" for y in years]

    def row_data(label: str, attr: str) -> list:
        return [label] + [_fmt(getattr(y, attr)) for y in years]

    data = [
        header,
        row_data("Chiffre d'affaires", "chiffre_affaires"),
        row_data("Marge commerciale", "marge_commerciale"),
        row_data("EBE (brut)", "ebe"),
        row_data("Résultat d'exploitation", "resultat_exploitation"),
        row_data("Résultat net", "resultat_net"),
        row_data("Capitaux propres", "capitaux_propres"),
        row_data("Dettes financières LT", "emprunts_lt"),
        row_data("Total Bilan", "total_actif"),
    ]

    n_cols = len(header)
    col_widths = [6 * cm] + [(16.5 - 6) / max(n_cols - 1, 1) * cm] * (n_cols - 1)
    table = Table(data, colWidths=col_widths)
    table.setStyle(TABLE_STYLE_BASE)
    return [table, Spacer(1, 4 * mm)]


# ---------------------------------------------------------------------------
# Ratios financiers
# ---------------------------------------------------------------------------

def _ratios_table(analysis: CompanyAnalysis, styles: dict) -> list:
    data = [
        ["Ratio", "Valeur", "Seuil / Commentaire"],
        ["Marge nette", _pct(analysis.ratio_marge_nette),
         "✓ Bonne si > 5% en boulangerie franchise"],
        ["Marge EBE", _pct(analysis.ratio_marge_ebe),
         "Secteur : 8-14% attendu"],
        ["Levier (dette nette / EBE)", f"{analysis.ratio_endettement:.1f}x",
         "Acceptable si < 3x"],
        ["BFR", _fmt(analysis.bfr),
         f"{_fmt_ratio(analysis.bfr, analysis.company.sorted_years[0].chiffre_affaires):.1f}% du CA"],
        ["EBE normatif retenu", _fmt(analysis.ebitda_normalise), "Base de valorisation"],
        ["Dette nette", _fmt(analysis.dette_nette), "À déduire de la VE"],
    ]

    col_widths = [5 * cm, 3.5 * cm, 8 * cm]
    table = Table(data, colWidths=col_widths)
    table.setStyle(TABLE_STYLE_BASE)
    return [table, Spacer(1, 4 * mm)]


# ---------------------------------------------------------------------------
# Valorisation
# ---------------------------------------------------------------------------

def _valorisation_section(analysis: CompanyAnalysis, styles: dict) -> list:
    items = []

    # KPIs clés
    kpi_data = [
        ["EBE normatif", "EBIT normatif", "Dette nette", "Valeur des Titres"],
        [
            _fmt(analysis.ebitda_normalise),
            _fmt(analysis.ebit_normalise),
            _fmt(max(analysis.dette_nette, 0)),
            _fmt(analysis.valeur_titres),
        ],
    ]
    kpi_table = Table(kpi_data, colWidths=[4.1 * cm] * 4)
    kpi_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), COLOR_NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), COLOR_WHITE),
        ("BACKGROUND", (0, 1), (-1, 1), COLOR_LIGHT_BLUE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 1), (-1, 1), COLOR_NAVY),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#D1D5DB")),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    items.append(kpi_table)
    items.append(Spacer(1, 3 * mm))

    # Tableau des méthodes de valorisation
    header = ["Méthode", "Bas", "Central", "Haut", "Hypothèses clés"]
    rows = [header]
    for v in analysis.valuations:
        note = v.notes[:65] + "…" if len(v.notes) > 65 else v.notes
        rows.append([v.method, _fmt(v.low), _fmt(v.mid), _fmt(v.high), note])

    # Ligne de fourchette retenue
    ve_low = (
        analysis.valuations[0].low * 0.5
        + analysis.valuations[1].low * 0.3
        + analysis.valuations[2].low * 0.2
    )
    ve_high = (
        analysis.valuations[0].high * 0.5
        + analysis.valuations[1].high * 0.3
        + analysis.valuations[2].high * 0.2
    )
    rows.append(["Fourchette pondérée (50/30/20)", _fmt(ve_low), "", _fmt(ve_high), "Retenue"])

    n_data_rows = len(rows)
    col_widths = [4.5 * cm, 2.2 * cm, 2.2 * cm, 2.2 * cm, 5.4 * cm]
    val_table = Table(rows, colWidths=col_widths)
    val_table.setStyle(_valuation_table_style(n_data_rows - 1))
    items.append(val_table)
    items.append(Spacer(1, 3 * mm))

    # Passage VE → Valeur des titres
    passage = Paragraph(
        f"<b>→ Valeur d'Entreprise centrale retenue : {_fmt(analysis.valeur_entreprise_retenue)}</b>"
        f" &nbsp;|&nbsp; "
        f"<b>Valeur des Titres = VE − Dette nette ({_fmt(max(analysis.dette_nette, 0))}) "
        f"= <font color='#166534'>{_fmt(analysis.valeur_titres)}</font></b>",
        ParagraphStyle(
            "passage",
            fontSize=9.5,
            fontName="Helvetica-Bold",
            textColor=COLOR_NAVY,
            alignment=TA_CENTER,
            backColor=COLOR_LIGHT_BLUE,
            borderPad=5,
            spaceAfter=6,
            leading=14,
        ),
    )
    items.append(passage)
    return items


# ---------------------------------------------------------------------------
# Investment Case (Pros / Cons)
# ---------------------------------------------------------------------------

def _investment_case(analysis: CompanyAnalysis, styles: dict) -> list:
    items = []

    # PROS
    items.append(Paragraph("✔ Arguments « Bonne Affaire »", styles["h3"]))
    for item in analysis.pros:
        items.append(Paragraph(f"• {item}", styles["bullet"]))
    items.append(Spacer(1, 3 * mm))

    # CONS
    items.append(Paragraph("✘ Points de Vigilance / Risques", styles["h3"]))
    for item in analysis.cons:
        items.append(Paragraph(f"• {item}", styles["bullet"]))
    items.append(Spacer(1, 3 * mm))
    return items


# ---------------------------------------------------------------------------
# Questions au vendeur
# ---------------------------------------------------------------------------

def _questions_section(questions: list[str], styles: dict) -> list:
    items = []
    for i, q in enumerate(questions, 1):
        items.append(Paragraph(f"<b>{i}.</b> {q}", styles["bullet"]))
    return items


# ---------------------------------------------------------------------------
# Leviers de négociation
# ---------------------------------------------------------------------------

def _leviers_section(leviers: list[str], styles: dict) -> list:
    items = []
    for item in leviers:
        items.append(Paragraph(f"▸ {item}", styles["bullet"]))
    return items


# ---------------------------------------------------------------------------
# Synthèse consolidée
# ---------------------------------------------------------------------------

def _synthese_consolidee(consol: dict, ana3: CompanyAnalysis, anal: CompanyAnalysis,
                         styles: dict) -> list:
    items = []

    ca_total = consol["ca_total"]
    ebitda_total = consol["ebitda_total"]
    ve_low, ve_high = consol["ve_fourchette"]
    vt_low, vt_high = consol["valeur_titres_totale"]

    data = [
        ["Indicateur consolidé", "ARCH'ANGE3", "LAVANGE", "Total"],
        [
            "Chiffre d'affaires",
            _fmt(ana3.company.sorted_years[0].chiffre_affaires),
            _fmt(next(
                (y.chiffre_affaires for y in anal.company.sorted_years
                 if y.chiffre_affaires > 0 and y.year != "2024"),
                0,
            )),
            _fmt(ca_total),
        ],
        [
            "EBE normatif",
            _fmt(ana3.ebitda_normalise),
            _fmt(anal.ebitda_normalise),
            _fmt(ebitda_total),
        ],
        [
            "Valeur des Titres",
            _fmt(ana3.valeur_titres),
            _fmt(anal.valeur_titres),
            f"{_fmt(vt_low)} – {_fmt(vt_high)}",
        ],
    ]

    col_widths = [5 * cm, 3.8 * cm, 3.8 * cm, 4 * cm]
    table = Table(data, colWidths=col_widths)
    table.setStyle(TABLE_STYLE_BASE)
    items.append(table)
    items.append(Spacer(1, 3 * mm))
    items.append(Paragraph(
        "Note : L'acquisition simultanée peut générer des synergies opérationnelles estimées à "
        "+5-10% de l'EBE combiné (mutualisation RH, achats groupés). Elle double cependant "
        "la dépendance à la franchise ANGE.",
        ParagraphStyle(
            "note",
            fontSize=8.5,
            fontName="Helvetica-Oblique",
            textColor=COLOR_MID_GRAY,
            leading=12,
        ),
    ))
    return items


# ---------------------------------------------------------------------------
# Conclusion stratégique
# ---------------------------------------------------------------------------

def _conclusion(ana3: CompanyAnalysis, anal: CompanyAnalysis,
                consol: dict, styles: dict) -> list:
    items = []
    vt_low, _ = consol["valeur_titres_totale"]

    items.append(Paragraph(
        "L'acquisition des franchises ANGE de Cesson-Sévigné et Laval constitue une "
        "<b>opportunité de marché intéressante</b> dans un secteur résilient, portée par une "
        "enseigne bien positionnée.",
        styles["body"],
    ))
    items.append(Spacer(1, 2 * mm))

    items.append(Paragraph("<b>Points forts décisifs</b>", styles["h3"]))
    items.append(Paragraph(
        "Résultats positifs sur 3 exercices, CA en croissance à Laval, potentiel de "
        "développement identifié, marque ANGE reconnue et primée (meilleure franchise "
        "alimentaire France 2023).",
        styles["body"],
    ))

    items.append(Paragraph("<b>Points de vigilance</b>", styles["h3"]))
    items.append(Paragraph(
        "Baisse du CA et du résultat à Cesson en 2024, dépendance structurelle à la franchise "
        "ANGE, sites uniques, besoin de capex de rénovation (120-150K€ à Cesson).",
        styles["body"],
    ))

    items.append(Paragraph("<b>Recommandations</b>", styles["h3"]))
    reco_items = [
        "Procéder à une due diligence approfondie (audit comptable, juridique, social et fiscal).",
        f"Valorisation cible ARCH'ANGE3 : {_fmt(ana3.valeur_titres)} (valeur des titres, après dette nette).",
        f"Valorisation cible LAVANGE : {_fmt(anal.valeur_titres)} (valeur des titres, après dette nette).",
        "Prévoir une garantie de passif de 18-24 mois couvrant les risques fiscaux, sociaux "
        "et liés au contrat de franchise.",
        f"En cas d'acquisition simultanée, viser un prix total inférieur à {_fmt(vt_low)} "
        "avec earn-out conditionnel aux objectifs 2025-2026.",
        "Négocier les conditions de transfert du bail commercial de Cesson (SCI du vendeur).",
    ]
    for reco in reco_items:
        items.append(Paragraph(f"▸ {reco}", styles["bullet"]))

    items.append(Spacer(1, 6 * mm))
    items.append(Paragraph(
        "Ce rapport est établi sur la base des documents fournis. Les informations financières "
        "sont indicatives et devront être confirmées lors de la phase de due diligence. "
        "Tout investissement comporte des risques.",
        styles["disclaimer"],
    ))
    return items


# ---------------------------------------------------------------------------
# En-tête et pied de page
# ---------------------------------------------------------------------------

class _PageTemplate:
    """Callback pour en-tête / pied de page via SimpleDocTemplate."""

    def __init__(self, today: str) -> None:
        self.today = today
        self._page_num = 0

    def on_first_page(self, canvas, doc) -> None:
        canvas.saveState()
        canvas.restoreState()

    def on_later_pages(self, canvas, doc) -> None:
        canvas.saveState()
        w, h = A4

        # En-tête
        canvas.setFillColor(COLOR_NAVY)
        canvas.rect(0, h - 1.5 * cm, w, 1.5 * cm, fill=True, stroke=False)
        canvas.setFillColor(COLOR_WHITE)
        canvas.setFont("Helvetica-Bold", 8)
        canvas.drawString(1.5 * cm, h - 0.9 * cm, "RAPPORT M&A CONFIDENTIEL — Mandat n°1326")
        canvas.setFont("Helvetica", 8)
        canvas.drawRightString(w - 1.5 * cm, h - 0.9 * cm,
                               "ARCH'ANGE3 & LAVANGE — Franchises ANGE")

        # Trait doré sous en-tête
        canvas.setStrokeColor(COLOR_GOLD)
        canvas.setLineWidth(1.5)
        canvas.line(1.5 * cm, h - 1.5 * cm, w - 1.5 * cm, h - 1.5 * cm)

        # Pied de page
        canvas.setStrokeColor(COLOR_NAVY)
        canvas.setLineWidth(0.5)
        canvas.line(1.5 * cm, 1.3 * cm, w - 1.5 * cm, 1.3 * cm)
        canvas.setFillColor(COLOR_MID_GRAY)
        canvas.setFont("Helvetica", 7)
        canvas.drawString(1.5 * cm, 0.8 * cm, f"Date : {self.today}")
        canvas.drawCentredString(w / 2, 0.8 * cm,
                                 "Axe Avenir — Conseil en Haut de Bilan | CNCEF n°05/917")
        canvas.drawRightString(w - 1.5 * cm, 0.8 * cm, f"Page {doc.page}")

        canvas.restoreState()


# ---------------------------------------------------------------------------
# Fonction principale
# ---------------------------------------------------------------------------

def generate_pdf(archange3: CompanyData, lavange: CompanyData,
                 output_path: str | Path) -> Path:
    """
    Génère le rapport M&A au format PDF professionnel (10-15 pages).

    Args:
        archange3: Données financières de SAS ARCH'ANGE3.
        lavange: Données financières de SAS LAVANGE.
        output_path: Chemin de destination du fichier PDF.

    Returns:
        Path du fichier PDF généré.
    """
    output_path = Path(output_path)
    results = analyze_consolidated(archange3, lavange)
    ana3 = results["archange3"]
    anal = results["lavange"]
    consol = results["consolide"]

    today = date.today().strftime("%d/%m/%Y")
    styles = _build_styles()
    pt = _PageTemplate(today)

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=1.8 * cm,
        title="Rapport Diagnostic M&A — Mandat 1326",
        author="Axe Avenir Conseil en Haut de Bilan",
        subject="Diagnostic 360 franchises ANGE — ARCH'ANGE3 & LAVANGE",
    )

    story: list = []

    # ── PAGE 1 : COUVERTURE ──────────────────────────────────────────────────
    _cover_page(story, styles, today)

    # ── SECTION 1 : FICHES D'IDENTITÉ ──────────────────────────────────────
    story.extend(_section_title("1. Fiches d'Identité", styles))
    story.append(_subsection_title("1.1 SAS ARCH'ANGE3 — Cesson-Sévigné (35)", styles))
    story.extend(_fiche_identite(archange3, styles))
    story.append(_subsection_title("1.2 SAS LAVANGE — Laval (53)", styles))
    story.extend(_fiche_identite(lavange, styles))

    # ── SECTION 2 : TABLEAUX SYNOPTIQUES ───────────────────────────────────
    story.extend(_section_title("2. Tableaux Synoptiques Financiers (3 exercices)", styles))
    story.append(_subsection_title("2.1 SAS ARCH'ANGE3", styles))
    story.extend(_tableau_synoptique(archange3, styles))
    story.append(_subsection_title("2.2 SAS LAVANGE", styles))
    story.extend(_tableau_synoptique(lavange, styles))

    # ── SECTION 3 : RATIOS ──────────────────────────────────────────────────
    story.extend(_section_title("3. Ratios Financiers Clés", styles))
    story.append(_subsection_title("3.1 SAS ARCH'ANGE3", styles))
    story.extend(_ratios_table(ana3, styles))
    story.append(_subsection_title("3.2 SAS LAVANGE", styles))
    story.extend(_ratios_table(anal, styles))

    # ── SECTION 4 : CONTEXTE SECTORIEL ─────────────────────────────────────
    story.extend(_section_title("4. Contexte Sectoriel et Stratégique", styles))
    sector_text = [
        ("<b>Secteur</b> : Boulangerie-pâtisserie artisanale (NAF 10.71C) — "
         "marché estimé à 11 Md€ en France (2023)."),
        ("<b>Tendances positives :</b> Résilience de la consommation (produit du quotidien), "
         "montée en gamme (bio, snacking premium), digitalisation (click & collect, Deliveroo), "
         "marque ANGE primée meilleure franchise alimentaire France 2023."),
        ("<b>Tendances négatives / risques :</b> Pression inflationniste sur matières premières "
         "(blé, beurre, énergie), concurrence des GMS et chaînes (Paul, Marie Blachère), "
         "difficultés de recrutement de boulangers qualifiés."),
        ("<b>Géographie :</b> Cesson-Sévigné (35) — commune dynamique de l'agglomération rennaise, "
         "fort pouvoir d'achat, croissance démographique. Laval (53) — préfecture de la Mayenne, "
         "bassin de chalandise limité mais concurrence ANGE directe quasi-nulle."),
        ("<b>Barrières à l'entrée :</b> Investissement initial 300-500K€, savoir-faire technique, "
         "exclusivité territoriale de franchise, durée d'apprentissage des équipes."),
    ]
    for para in sector_text:
        story.append(Paragraph(para, styles["body"]))
        story.append(Spacer(1, 2 * mm))

    # ── SECTION 5 : VALORISATION ────────────────────────────────────────────
    story.extend(_section_title("5. Analyse de Valorisation", styles))
    story.append(_subsection_title("5.1 SAS ARCH'ANGE3 — Cesson-Sévigné", styles))
    story.extend(_valorisation_section(ana3, styles))
    story.append(_subsection_title("5.2 SAS LAVANGE — Laval", styles))
    story.extend(_valorisation_section(anal, styles))
    story.append(_subsection_title("5.3 Vision Consolidée (Acquisition des 2 sites)", styles))
    story.extend(_synthese_consolidee(consol, ana3, anal, styles))

    # ── SECTION 6 : DIAGNOSTIC D'INVESTISSEMENT ────────────────────────────
    story.extend(_section_title("6. Diagnostic d'Investissement (Investment Case)", styles))
    story.append(_subsection_title("6.1 SAS ARCH'ANGE3", styles))
    story.extend(_investment_case(ana3, styles))
    story.append(_subsection_title("6.2 SAS LAVANGE", styles))
    story.extend(_investment_case(anal, styles))

    # ── SECTION 7 : QUESTIONS AU VENDEUR ───────────────────────────────────
    story.extend(_section_title("7. Questions Clés au Vendeur (Due Diligence)", styles))
    story.extend(_questions_section(ana3.questions_vendeur, styles))

    # ── SECTION 8 : LEVIERS DE NÉGOCIATION ─────────────────────────────────
    story.extend(_section_title("8. Leviers de Négociation pour l'Acheteur", styles))
    story.append(Paragraph(
        "Objectif : obtenir le prix le plus bas possible tout en sécurisant l'opération.",
        ParagraphStyle(
            "obj",
            fontSize=9,
            fontName="Helvetica-Oblique",
            textColor=COLOR_MID_GRAY,
            spaceAfter=4,
        ),
    ))
    story.extend(_leviers_section(ana3.leviers_negociation, styles))

    # ── SECTION 9 : CONCLUSION STRATÉGIQUE ─────────────────────────────────
    story.extend(_section_title("9. Conclusion Stratégique", styles))
    story.extend(_conclusion(ana3, anal, consol, styles))

    # ── GÉNÉRATION DU PDF ───────────────────────────────────────────────────
    doc.build(
        story,
        onFirstPage=pt.on_first_page,
        onLaterPages=pt.on_later_pages,
    )

    return output_path

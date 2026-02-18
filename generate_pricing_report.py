"""
Script pour générer le rapport d'estimation des coûts Gemini API
pour le projet "Corrige Moi".
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm, mm
from reportlab.lib.colors import HexColor, white, black
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from datetime import datetime
import os


# Couleurs du thème
PRIMARY = HexColor('#1a73e8')
PRIMARY_DARK = HexColor('#0d47a1')
PRIMARY_LIGHT = HexColor('#e8f0fe')
SECONDARY = HexColor('#34a853')
ACCENT = HexColor('#ea4335')
TEXT_DARK = HexColor('#202124')
TEXT_GRAY = HexColor('#5f6368')
BG_LIGHT = HexColor('#f8f9fa')
BORDER = HexColor('#dadce0')
ROW_ALT = HexColor('#f1f3f4')


def create_styles():
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        'DocTitle',
        parent=styles['Title'],
        fontSize=26,
        leading=32,
        textColor=PRIMARY_DARK,
        spaceAfter=6,
        alignment=TA_LEFT,
        fontName='Helvetica-Bold',
    ))

    styles.add(ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontSize=13,
        leading=18,
        textColor=TEXT_GRAY,
        spaceAfter=20,
        fontName='Helvetica',
    ))

    styles.add(ParagraphStyle(
        'SectionTitle',
        parent=styles['Heading1'],
        fontSize=16,
        leading=22,
        textColor=PRIMARY_DARK,
        spaceBefore=24,
        spaceAfter=10,
        fontName='Helvetica-Bold',
        borderPadding=(0, 0, 4, 0),
    ))

    styles.add(ParagraphStyle(
        'SubSection',
        parent=styles['Heading2'],
        fontSize=12,
        leading=16,
        textColor=TEXT_DARK,
        spaceBefore=14,
        spaceAfter=6,
        fontName='Helvetica-Bold',
    ))

    styles.add(ParagraphStyle(
        'BodyText2',
        parent=styles['Normal'],
        fontSize=10,
        leading=14,
        textColor=TEXT_DARK,
        spaceAfter=6,
        fontName='Helvetica',
    ))

    styles.add(ParagraphStyle(
        'Highlight',
        parent=styles['Normal'],
        fontSize=11,
        leading=15,
        textColor=PRIMARY_DARK,
        fontName='Helvetica-Bold',
        spaceAfter=4,
    ))

    styles.add(ParagraphStyle(
        'SmallNote',
        parent=styles['Normal'],
        fontSize=8,
        leading=11,
        textColor=TEXT_GRAY,
        fontName='Helvetica',
    ))

    styles.add(ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontSize=9,
        leading=12,
        textColor=white,
        fontName='Helvetica-Bold',
        alignment=TA_CENTER,
    ))

    styles.add(ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontSize=9,
        leading=12,
        textColor=TEXT_DARK,
        fontName='Helvetica',
        alignment=TA_CENTER,
    ))

    styles.add(ParagraphStyle(
        'TableCellLeft',
        parent=styles['Normal'],
        fontSize=9,
        leading=12,
        textColor=TEXT_DARK,
        fontName='Helvetica',
        alignment=TA_LEFT,
    ))

    styles.add(ParagraphStyle(
        'BulletItem',
        parent=styles['Normal'],
        fontSize=10,
        leading=14,
        textColor=TEXT_DARK,
        fontName='Helvetica',
        leftIndent=16,
        spaceAfter=4,
    ))

    styles.add(ParagraphStyle(
        'BigNumber',
        parent=styles['Normal'],
        fontSize=22,
        leading=28,
        textColor=PRIMARY,
        fontName='Helvetica-Bold',
        alignment=TA_CENTER,
    ))

    styles.add(ParagraphStyle(
        'BigNumberLabel',
        parent=styles['Normal'],
        fontSize=9,
        leading=12,
        textColor=TEXT_GRAY,
        fontName='Helvetica',
        alignment=TA_CENTER,
    ))

    return styles


def make_table(headers, rows, col_widths=None):
    """Crée un tableau stylisé."""
    s = create_styles()

    header_cells = [Paragraph(h, s['TableHeader']) for h in headers]
    data = [header_cells]

    for row in rows:
        cells = []
        for i, cell in enumerate(row):
            style = s['TableCellLeft'] if i == 0 else s['TableCell']
            cells.append(Paragraph(str(cell), style))
        data.append(cells)

    t = Table(data, colWidths=col_widths, repeatRows=1)

    style_commands = [
        ('BACKGROUND', (0, 0), (-1, 0), PRIMARY),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 0), (-1, 0), 8),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
        ('TOPPADDING', (0, 1), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, BORDER),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]

    # Alternate row colors
    for i in range(1, len(data)):
        if i % 2 == 0:
            style_commands.append(('BACKGROUND', (0, i), (-1, i), ROW_ALT))

    t.setStyle(TableStyle(style_commands))
    return t


def make_highlight_box(text, styles):
    """Crée une boîte mise en évidence."""
    data = [[Paragraph(text, styles['Highlight'])]]
    t = Table(data, colWidths=[16 * cm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), PRIMARY_LIGHT),
        ('BORDER', (0, 0), (-1, -1), 1, PRIMARY),
        ('LEFTPADDING', (0, 0), (-1, -1), 12),
        ('RIGHTPADDING', (0, 0), (-1, -1), 12),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('ROUNDEDCORNERS', [4, 4, 4, 4]),
    ]))
    return t


def make_stat_cards(cards_data, styles):
    """Crée des cartes de statistiques côte à côte."""
    cells = []
    for value, label in cards_data:
        cell_content = [
            Paragraph(value, styles['BigNumber']),
            Paragraph(label, styles['BigNumberLabel']),
        ]
        inner = Table([[c] for c in cell_content], colWidths=[4.5 * cm])
        inner.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))
        cells.append(inner)

    t = Table([cells], colWidths=[5 * cm] * len(cells))
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), BG_LIGHT),
        ('GRID', (0, 0), (-1, -1), 0.5, BORDER),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    return t


def build_pdf(output_path):
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
    )

    styles = create_styles()
    story = []

    # === EN-TÊTE ===
    story.append(Paragraph("Corrige Moi", styles['DocTitle']))
    story.append(Paragraph(
        f"Estimation des coûts API Google Gemini — {datetime.now().strftime('%d/%m/%Y')}",
        styles['DocSubtitle']
    ))
    story.append(HRFlowable(
        width="100%", thickness=2, color=PRIMARY,
        spaceAfter=16, spaceBefore=4
    ))

    # === RÉSUMÉ RAPIDE ===
    story.append(Paragraph("Résumé rapide", styles['SectionTitle']))

    story.append(make_stat_cards([
        ("$0.003", "Par correction"),
        ("$0.0008", "Par message chat"),
        ("~$27/mois", "500 utilisateurs"),
    ], styles))
    story.append(Spacer(1, 12))

    story.append(make_highlight_box(
        "Gemini 2.5 Flash est un modèle très économique. "
        "Même avec 2 000 utilisateurs actifs, le coût API reste inférieur à $110/mois (~66 000 FCFA).",
        styles
    ))
    story.append(Spacer(1, 8))

    # === SECTION 1 : TARIFS ===
    story.append(Paragraph("1. Tarifs Gemini 2.5 Flash", styles['SectionTitle']))
    story.append(Paragraph(
        "Modèle utilisé dans l'application : <b>gemini-2.5-flash</b> (le plus économique avec de bonnes capacités).",
        styles['BodyText2']
    ))

    story.append(make_table(
        ["Modèle", "Input / 1M tokens", "Output / 1M tokens"],
        [
            ["Gemini 2.5 Flash", "$0.15", "$0.60"],
            ["Gemini 2.5 Flash (Thinking)", "$0.15", "$3.50"],
            ["Gemini 2.5 Flash-Lite", "$0.10", "$0.40"],
            ["Gemini 2.5 Pro (comparaison)", "$1.25", "$10.00"],
        ],
        col_widths=[6 * cm, 5 * cm, 5 * cm]
    ))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "Source : ai.google.dev/gemini-api/docs/pricing (février 2026)",
        styles['SmallNote']
    ))

    # === SECTION 2 : CONSOMMATION PAR ACTION ===
    story.append(Paragraph("2. Consommation par action", styles['SectionTitle']))

    story.append(Paragraph("Correction d'image (3 appels API)", styles['SubSection']))
    story.append(Paragraph(
        "Chaque correction d'image nécessite 3 appels successifs à Gemini :",
        styles['BodyText2']
    ))

    story.append(make_table(
        ["Appel API", "Input estimé", "Output estimé", "Rôle"],
        [
            ["1. Extraction texte", "~1 200 tokens", "~500 tokens", "OCR depuis l'image"],
            ["2. Détection branche", "~1 200 tokens", "~200 tokens", "Scientifique ou littéraire"],
            ["3. Correction principale", "~1 500 tokens", "~3 000 tokens", "Correction détaillée + étapes"],
            ["TOTAL", "~3 900 tokens", "~3 700 tokens", "—"],
        ],
        col_widths=[4 * cm, 3 * cm, 3 * cm, 5.5 * cm]
    ))

    story.append(Spacer(1, 6))
    story.append(make_highlight_box(
        "Coût par correction d'image : ~$0.003 (environ 2 FCFA)",
        styles
    ))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Message chat (1-2 appels API)", styles['SubSection']))
    story.append(Paragraph(
        "Chaque message de chat nécessite 1 appel + optionnellement 1 appel pour la génération du titre de session :",
        styles['BodyText2']
    ))

    story.append(make_table(
        ["Appel API", "Input estimé", "Output estimé", "Rôle"],
        [
            ["1. Réponse chat", "~1 500 tokens", "~1 000 tokens", "Réponse pédagogique"],
            ["2. Titre (1er msg)", "~200 tokens", "~50 tokens", "Titre de session auto"],
            ["TOTAL (moyen)", "~1 500 tokens", "~1 000 tokens", "—"],
        ],
        col_widths=[4 * cm, 3 * cm, 3 * cm, 5.5 * cm]
    ))

    story.append(Spacer(1, 6))
    story.append(make_highlight_box(
        "Coût par message chat : ~$0.0008 (environ 0.5 FCFA)",
        styles
    ))

    # === SECTION 3 : ESTIMATION MENSUELLE ===
    story.append(Paragraph("3. Estimation mensuelle par volume", styles['SectionTitle']))
    story.append(Paragraph(
        "Hypothèses : chaque utilisateur actif fait en moyenne 10 corrections et 30 messages chat par mois.",
        styles['BodyText2']
    ))

    story.append(make_table(
        ["Scénario", "Utilisateurs", "Corrections", "Messages chat", "Coût mensuel", "En FCFA"],
        [
            ["Lancement", "100", "1 000", "3 000", "$5.40", "~3 300 FCFA"],
            ["Croissance", "500", "5 000", "15 000", "$27", "~16 500 FCFA"],
            ["Établi", "2 000", "20 000", "60 000", "$108", "~66 000 FCFA"],
            ["Grande échelle", "10 000", "100 000", "300 000", "$540", "~330 000 FCFA"],
        ],
        col_widths=[2.8 * cm, 2.5 * cm, 2.5 * cm, 2.7 * cm, 2.7 * cm, 2.8 * cm]
    ))

    story.append(Spacer(1, 10))

    # === SECTION 4 : OPTIMISATIONS ===
    story.append(Paragraph("4. Pistes d'optimisation des coûts", styles['SectionTitle']))

    optimisations = [
        ("<b>Tier gratuit Google AI Studio</b> — Accès gratuit avec limites de débit, parfait pour le développement et les tests.",
        ),
        ("<b>Context Caching</b> — Mettez en cache vos prompts système pour réduire les tokens d'input répétitifs "
         "(coût de lecture du cache = 10% du prix normal).",
        ),
        ("<b>Gemini 2.5 Flash-Lite</b> — Alternative encore moins chère ($0.10/$0.40 par 1M tokens) "
         "pour les appels simples comme la détection de branche.",
        ),
        ("<b>Réduire à 2 appels par correction</b> — Combiner l'extraction de texte et la détection de branche "
         "en un seul appel pourrait réduire les coûts de ~30%.",
        ),
        ("<b>Batch Processing</b> — -50% de réduction pour les traitements différés (pas adapté au temps réel, "
         "mais utile pour des analyses en lot).",
        ),
    ]

    for opt in optimisations:
        story.append(Paragraph(f"• {opt[0]}", styles['BulletItem']))
    story.append(Spacer(1, 8))

    # === SECTION 5 : COMPARAISON AVEC AUTRES COÛTS ===
    story.append(Paragraph("5. Comparaison avec les autres coûts du projet", styles['SectionTitle']))
    story.append(Paragraph(
        "Pour mettre en perspective, voici une comparaison des coûts mensuels typiques :",
        styles['BodyText2']
    ))

    story.append(make_table(
        ["Poste de dépense", "Coût estimé/mois", "Commentaire"],
        [
            ["Hébergement Render (Starter)", "$7 - $25", "Serveur web + base de données"],
            ["API Gemini (500 users)", "~$27", "Très économique"],
            ["API Gemini (2000 users)", "~$108", "Reste abordable"],
            ["Nom de domaine", "$1 - $2", "Annualisé"],
            ["Firebase (notifications)", "Gratuit", "Tier gratuit suffisant"],
        ],
        col_widths=[5 * cm, 3.5 * cm, 7 * cm]
    ))

    story.append(Spacer(1, 12))

    # === CONCLUSION ===
    story.append(Paragraph("Conclusion", styles['SectionTitle']))
    story.append(HRFlowable(
        width="100%", thickness=1, color=SECONDARY,
        spaceAfter=8, spaceBefore=2
    ))

    story.append(make_highlight_box(
        "L'utilisation de Gemini 2.5 Flash est un choix optimal pour Corrige Moi. "
        "Les coûts API sont négligeables par rapport aux revenus potentiels des abonnements. "
        "Avec un abonnement utilisateur à ~1 000 FCFA/mois, il suffit de 2-3 utilisateurs payants "
        "pour couvrir les frais API de 100 utilisateurs actifs.",
        styles
    ))

    story.append(Spacer(1, 16))
    story.append(Paragraph(
        f"Document généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')} — Corrige Moi",
        styles['SmallNote']
    ))

    doc.build(story)
    return output_path


if __name__ == "__main__":
    output = os.path.join(os.path.dirname(__file__), "Estimation_Couts_Gemini_CorrigeMoi.pdf")
    build_pdf(output)
    print(f"PDF généré avec succès : {output}")

"""
Générateurs PDF — Factures, Contrats de concession, Documents d'exhumation
Utilise ReportLab pour une génération native sans dépendances système lourdes.
"""

import io
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm, mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
)

# ─── Palette couleurs (cohérente avec le code couleur de la carte) ────────────
COULEUR_PRIMAIRE = colors.HexColor("#2d6a4f")
COULEUR_SECONDAIRE = colors.HexColor("#1b4332")
COULEUR_GRIS_CLAIR = colors.HexColor("#f1f5f9")
COULEUR_TEXTE = colors.HexColor("#1f2937")


def _styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="TitrePrincipal", fontSize=18, leading=22,
        textColor=COULEUR_PRIMAIRE, fontName="Helvetica-Bold",
        alignment=TA_LEFT, spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        name="SousTitre", fontSize=10, leading=14,
        textColor=colors.grey, alignment=TA_LEFT,
    ))
    styles.add(ParagraphStyle(
        name="SectionTitre", fontSize=12, leading=16,
        textColor=COULEUR_SECONDAIRE, fontName="Helvetica-Bold",
        spaceBefore=12, spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        name="CorpsTexte", fontSize=10, leading=15,
        textColor=COULEUR_TEXTE, alignment=TA_JUSTIFY,
    ))
    styles.add(ParagraphStyle(
        name="PiedPage", fontSize=8, leading=11,
        textColor=colors.grey, alignment=TA_CENTER,
    ))
    return styles


def _header_table(titre_doc, numero, date_str):
    """En-tête commun à tous les documents."""
    data = [
        [Paragraph("<b>ADMINISTRATION DU CIMETIÈRE</b>", _styles()["TitrePrincipal"]),
         Paragraph(f"<b>{titre_doc}</b><br/>N° {numero}<br/>{date_str}", _styles()["SousTitre"])],
    ]
    t = Table(data, colWidths=[10 * cm, 7 * cm])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
    ]))
    return t


def _footer_canvas(canvas, doc):
    """Pied de page sur chaque page du PDF."""
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.grey)
    canvas.drawCentredString(
        A4[0] / 2, 1.2 * cm,
        "Document généré automatiquement — Application de Gestion de Cimetière"
    )
    canvas.drawCentredString(
        A4[0] / 2, 0.8 * cm,
        f"Page {doc.page}"
    )
    canvas.restoreState()


# ─── FACTURE ───────────────────────────────────────────────────────────────────

def generer_pdf_facture(facture) -> bytes:
    """Génère le PDF d'une facture avec ses lignes et le récapitulatif."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=2 * cm, bottomMargin=2 * cm,
        leftMargin=2 * cm, rightMargin=2 * cm,
    )
    styles = _styles()
    elements = []

    elements.append(_header_table(
        "FACTURE", facture.numero_facture,
        facture.date_emission.strftime("%d/%m/%Y")
    ))
    elements.append(Spacer(1, 0.5 * cm))
    elements.append(HRFlowable(width="100%", color=COULEUR_PRIMAIRE, thickness=1.5))
    elements.append(Spacer(1, 0.5 * cm))

    # Informations client
    elements.append(Paragraph("Facturé à :", styles["SectionTitre"]))
    elements.append(Paragraph(
        f"{facture.client.nom_complet}<br/>{facture.client.email}"
        + (f"<br/>{facture.client.telephone}" if facture.client.telephone else ""),
        styles["CorpsTexte"]
    ))

    if facture.reservation:
        elements.append(Spacer(1, 0.2 * cm))
        elements.append(Paragraph(
            f"<b>Réf. dossier :</b> {facture.reservation.numero_dossier} — "
            f"Caveau : {facture.reservation.caveau.reference_complete}",
            styles["CorpsTexte"]
        ))

    elements.append(Spacer(1, 0.6 * cm))

    # Tableau des lignes
    data = [["Description", "Qté", "Prix unitaire (FCFA)", "Montant (FCFA)"]]
    for ligne in facture.lignes.all():
        data.append([
            ligne.description,
            str(ligne.quantite),
            f"{ligne.prix_unitaire:,.0f}",
            f"{ligne.montant_total:,.0f}",
        ])

    table = Table(data, colWidths=[8.5 * cm, 1.5 * cm, 3.5 * cm, 3.5 * cm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), COULEUR_PRIMAIRE),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, COULEUR_GRIS_CLAIR]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 0.4 * cm))

    # Récapitulatif des totaux
    totaux_data = [["Sous-total", f"{facture.sous_total:,.0f} FCFA"]]
    if facture.tva_pct > 0:
        totaux_data.append([f"TVA ({facture.tva_pct}%)", f"{facture.montant_tva:,.0f} FCFA"])
    totaux_data.append(["TOTAL", f"{facture.montant_total:,.0f} FCFA"])
    if facture.montant_paye > 0:
        totaux_data.append(["Déjà payé", f"{facture.montant_paye:,.0f} FCFA"])
        totaux_data.append(["Solde restant", f"{facture.solde_restant:,.0f} FCFA"])

    totaux_table = Table(totaux_data, colWidths=[10.5 * cm, 6.5 * cm])
    style_totaux = [
        ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    # Mettre en gras la ligne TOTAL
    for i, row in enumerate(totaux_data):
        if row[0] == "TOTAL":
            style_totaux += [
                ("FONTNAME", (0, i), (-1, i), "Helvetica-Bold"),
                ("FONTSIZE", (0, i), (-1, i), 12),
                ("LINEABOVE", (0, i), (-1, i), 1, COULEUR_PRIMAIRE),
                ("LINEBELOW", (0, i), (-1, i), 1, COULEUR_PRIMAIRE),
                ("TEXTCOLOR", (0, i), (-1, i), COULEUR_PRIMAIRE),
            ]
    totaux_table.setStyle(TableStyle(style_totaux))
    elements.append(totaux_table)

    elements.append(Spacer(1, 1 * cm))

    # Échéance et statut
    if facture.date_echeance:
        elements.append(Paragraph(
            f"<b>Date d'échéance :</b> {facture.date_echeance.strftime('%d/%m/%Y')}",
            styles["CorpsTexte"]
        ))

    elements.append(Spacer(1, 0.4 * cm))
    elements.append(Paragraph(
        "<b>Moyens de paiement acceptés :</b> Mobile Money, Airtel Money, "
        "espèces, virement bancaire.",
        styles["CorpsTexte"]
    ))

    doc.build(elements, onFirstPage=_footer_canvas, onLaterPages=_footer_canvas)
    buffer.seek(0)
    return buffer.read()


# ─── CONTRAT DE CONCESSION ──────────────────────────────────────────────────────

def generer_pdf_contrat_concession(concession) -> bytes:
    """Génère le PDF du contrat de concession funéraire."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=2 * cm, bottomMargin=2 * cm,
        leftMargin=2 * cm, rightMargin=2 * cm,
    )
    styles = _styles()
    elements = []

    elements.append(_header_table(
        "CONTRAT DE CONCESSION FUNÉRAIRE", concession.numero_contrat,
        concession.date_signature.strftime("%d/%m/%Y")
    ))
    elements.append(Spacer(1, 0.5 * cm))
    elements.append(HRFlowable(width="100%", color=COULEUR_PRIMAIRE, thickness=1.5))
    elements.append(Spacer(1, 0.6 * cm))

    elements.append(Paragraph("Titulaire de la concession", styles["SectionTitre"]))
    elements.append(Paragraph(
        f"Nom : {concession.titulaire.nom_complet}<br/>"
        f"Email : {concession.titulaire.email}<br/>"
        f"Téléphone : {concession.titulaire.telephone or 'Non renseigné'}",
        styles["CorpsTexte"]
    ))

    elements.append(Paragraph("Emplacement concédé", styles["SectionTitre"]))
    caveau = concession.reservation.caveau
    elements.append(Paragraph(
        f"Référence : {caveau.reference_complete}<br/>"
        f"Zone : {caveau.bloc.zone.nom} ({caveau.bloc.zone.code})<br/>"
        f"Bloc : {caveau.bloc.nom} ({caveau.bloc.code})<br/>"
        f"Numéro de caveau : {caveau.numero}",
        styles["CorpsTexte"]
    ))

    elements.append(Paragraph("Conditions de la concession", styles["SectionTitre"]))
    duree_texte = (
        "Concession perpétuelle (sans date d'expiration)"
        if concession.est_perpetuelle
        else f"Du {concession.date_debut.strftime('%d/%m/%Y')} "
             f"au {concession.date_fin.strftime('%d/%m/%Y')}"
    )
    elements.append(Paragraph(
        f"Type de concession : {concession.get_type_concession_display()}<br/>"
        f"Durée : {duree_texte}<br/>"
        f"Date de signature : {concession.date_signature.strftime('%d/%m/%Y')}",
        styles["CorpsTexte"]
    ))

    elements.append(Spacer(1, 0.8 * cm))
    elements.append(Paragraph("Article 1 — Objet", styles["SectionTitre"]))
    elements.append(Paragraph(
        "La présente concession accorde au titulaire désigné ci-dessus le droit "
        "d'usage de l'emplacement funéraire décrit, dans les conditions et pour "
        "la durée précisées ci-dessus, conformément au règlement intérieur du "
        "cimetière et aux dispositions légales en vigueur.",
        styles["CorpsTexte"]
    ))

    elements.append(Paragraph("Article 2 — Obligations du titulaire", styles["SectionTitre"]))
    elements.append(Paragraph(
        "Le titulaire s'engage à entretenir l'emplacement concédé et à respecter "
        "le règlement intérieur du cimetière. Toute modification de l'aménagement "
        "doit faire l'objet d'une autorisation préalable de l'administration.",
        styles["CorpsTexte"]
    ))

    if not concession.est_perpetuelle:
        elements.append(Paragraph("Article 3 — Renouvellement", styles["SectionTitre"]))
        elements.append(Paragraph(
            "À l'échéance de la présente concession, le titulaire sera informé "
            "par voie électronique de la possibilité de renouvellement, au moins "
            "90 jours avant la date d'expiration. À défaut de renouvellement, "
            "l'emplacement pourra être repris par l'administration conformément "
            "à la réglementation funéraire en vigueur.",
            styles["CorpsTexte"]
        ))

    elements.append(Spacer(1, 1.5 * cm))
    sig_data = [["Signature du titulaire", "Signature de l'administration"]]
    sig_table = Table(sig_data, colWidths=[8.5 * cm, 8.5 * cm])
    sig_table.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 40),
        ("LINEABOVE", (0, 0), (0, 0), 0.5, colors.grey),
        ("LINEABOVE", (1, 0), (1, 0), 0.5, colors.grey),
    ]))
    elements.append(sig_table)

    doc.build(elements, onFirstPage=_footer_canvas, onLaterPages=_footer_canvas)
    buffer.seek(0)
    return buffer.read()


# ─── AUTORISATION D'EXHUMATION ──────────────────────────────────────────────────

def generer_pdf_autorisation_exhumation(exhumation) -> bytes:
    """Génère le PDF d'autorisation d'exhumation."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=2 * cm, bottomMargin=2 * cm,
        leftMargin=2 * cm, rightMargin=2 * cm,
    )
    styles = _styles()
    elements = []

    date_str = (
        exhumation.date_autorisation.strftime("%d/%m/%Y")
        if exhumation.date_autorisation else "—"
    )

    elements.append(_header_table(
        "AUTORISATION D'EXHUMATION", exhumation.numero_demande, date_str
    ))
    elements.append(Spacer(1, 0.5 * cm))
    elements.append(HRFlowable(width="100%", color=COULEUR_PRIMAIRE, thickness=1.5))
    elements.append(Spacer(1, 0.6 * cm))

    caveau = exhumation.concession.reservation.caveau

    elements.append(Paragraph(
        "L'administration du cimetière, après instruction de la demande "
        f"référencée <b>{exhumation.numero_demande}</b>, autorise par la "
        "présente l'exhumation des restes mortels inhumés à l'emplacement "
        "suivant :",
        styles["CorpsTexte"]
    ))

    elements.append(Spacer(1, 0.4 * cm))
    elements.append(Paragraph(
        f"<b>Emplacement :</b> {caveau.reference_complete}<br/>"
        f"<b>Concession :</b> {exhumation.concession.numero_contrat}<br/>"
        f"<b>Demandeur :</b> {exhumation.demandeur.nom_complet}<br/>"
        f"<b>Motif de la demande :</b> {exhumation.motif}",
        styles["CorpsTexte"]
    ))

    if exhumation.destination_restes:
        elements.append(Spacer(1, 0.2 * cm))
        elements.append(Paragraph(
            f"<b>Destination des restes mortels :</b> {exhumation.destination_restes}",
            styles["CorpsTexte"]
        ))

    elements.append(Spacer(1, 0.6 * cm))
    elements.append(Paragraph(
        "Cette autorisation est délivrée sous réserve du strict respect des "
        "dispositions légales et réglementaires applicables aux opérations "
        "d'exhumation, notamment en matière d'hygiène et de salubrité publique. "
        "L'opération devra être réalisée en présence d'un représentant de "
        "l'administration et donnera lieu à l'établissement d'un procès-verbal.",
        styles["CorpsTexte"]
    ))

    elements.append(Spacer(1, 1.5 * cm))
    elements.append(Paragraph(
        f"Autorisé par : {exhumation.autorisee_par.nom_complet if exhumation.autorisee_par else '—'}",
        styles["CorpsTexte"]
    ))
    elements.append(Spacer(1, 1.2 * cm))
    elements.append(Paragraph("Signature et cachet de l'administration", styles["CorpsTexte"]))

    doc.build(elements, onFirstPage=_footer_canvas, onLaterPages=_footer_canvas)
    buffer.seek(0)
    return buffer.read()


def generer_pdf_pv_exhumation(exhumation) -> bytes:
    """Génère le PDF du procès-verbal d'exhumation (à compléter sur le terrain)."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=2 * cm, bottomMargin=2 * cm,
        leftMargin=2 * cm, rightMargin=2 * cm,
    )
    styles = _styles()
    elements = []

    elements.append(_header_table(
        "PROCÈS-VERBAL D'EXHUMATION", exhumation.numero_demande,
        datetime.now().strftime("%d/%m/%Y")
    ))
    elements.append(Spacer(1, 0.5 * cm))
    elements.append(HRFlowable(width="100%", color=COULEUR_PRIMAIRE, thickness=1.5))
    elements.append(Spacer(1, 0.6 * cm))

    caveau = exhumation.concession.reservation.caveau

    elements.append(Paragraph(
        f"Référence de l'autorisation : <b>{exhumation.numero_demande}</b><br/>"
        f"Emplacement concerné : <b>{caveau.reference_complete}</b><br/>"
        f"Concession : {exhumation.concession.numero_contrat}",
        styles["CorpsTexte"]
    ))

    elements.append(Spacer(1, 0.6 * cm))
    elements.append(Paragraph(
        "Le présent procès-verbal constate le déroulement de l'opération "
        "d'exhumation à la date et dans les conditions ci-après :",
        styles["CorpsTexte"]
    ))

    elements.append(Spacer(1, 0.4 * cm))
    champs_data = [
        ["Date de réalisation :", "________________________"],
        ["Heure de début :", "________________________"],
        ["Heure de fin :", "________________________"],
        ["Représentant de l'administration :", "________________________"],
        ["Observations :", ""],
    ]
    champs_table = Table(champs_data, colWidths=[6 * cm, 11 * cm])
    champs_table.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LINEBELOW", (1, 0), (1, 2), 0.5, colors.grey),
        ("LINEBELOW", (1, 3), (1, 3), 0.5, colors.grey),
    ]))
    elements.append(champs_table)

    elements.append(Spacer(1, 1 * cm))
    elements.append(Paragraph(
        "Espace réservé aux observations complémentaires :",
        styles["CorpsTexte"]
    ))
    elements.append(Spacer(1, 3 * cm))
    elements.append(HRFlowable(width="100%", color=colors.grey, thickness=0.5))

    elements.append(Spacer(1, 1.5 * cm))
    sig_data = [["Signature du représentant", "Signature du demandeur"]]
    sig_table = Table(sig_data, colWidths=[8.5 * cm, 8.5 * cm])
    sig_table.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 40),
        ("LINEABOVE", (0, 0), (0, 0), 0.5, colors.grey),
        ("LINEABOVE", (1, 0), (1, 0), 0.5, colors.grey),
    ]))
    elements.append(sig_table)

    doc.build(elements, onFirstPage=_footer_canvas, onLaterPages=_footer_canvas)
    buffer.seek(0)
    return buffer.read()

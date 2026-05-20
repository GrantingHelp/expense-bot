import os
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    Image, HRFlowable
)
from reportlab.lib.enums import TA_CENTER


def generate_pdf(trip: dict, output_path: str) -> str:
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch
    )

    styles = getSampleStyleSheet()

    style_title = ParagraphStyle(
        "TripTitle",
        fontSize=18,
        fontName="Helvetica-Bold",
        textColor=colors.HexColor("#111111"),
        spaceAfter=4
    )
    style_subtitle = ParagraphStyle(
        "SubTitle",
        fontSize=11,
        fontName="Helvetica",
        textColor=colors.HexColor("#555555"),
        spaceAfter=2
    )
    style_section = ParagraphStyle(
        "Section",
        fontSize=13,
        fontName="Helvetica-Bold",
        textColor=colors.HexColor("#222222"),
        spaceBefore=6,
        spaceAfter=4
    )
    style_field_label = ParagraphStyle(
        "FieldLabel",
        fontSize=9,
        fontName="Helvetica-Bold",
        textColor=colors.HexColor("#888888"),
        spaceAfter=1
    )
    style_field_value = ParagraphStyle(
        "FieldValue",
        fontSize=11,
        fontName="Helvetica",
        textColor=colors.HexColor("#111111"),
        spaceAfter=5
    )
    style_footer = ParagraphStyle(
        "Footer",
        fontSize=9,
        fontName="Helvetica",
        textColor=colors.HexColor("#999999"),
        alignment=TA_CENTER
    )

    story = []
    printed = datetime.now().strftime("%B %d, %Y")
    trip_name = trip.get("name", "Unknown Trip")
    started = trip.get("started", "")
    receipts = sorted(
        trip.get("receipts", []),
        key=lambda r: r.get("logged_at", "")
    )

    try:
        date_str = datetime.fromisoformat(started).strftime("%B %d, %Y")
    except Exception:
        date_str = "Unknown date"

    # Header
    story.append(Paragraph("Expense Report", style_subtitle))
    story.append(Paragraph(trip_name, style_title))
    story.append(Paragraph(f"Trip date: {date_str}", style_subtitle))
    story.append(Paragraph(f"Printed: {printed}", style_subtitle))
    story.append(Paragraph(
        f"Total receipts: {len(receipts)}", style_subtitle
    ))
    story.append(Spacer(1, 0.15 * inch))
    story.append(HRFlowable(
        width="100%", thickness=1,
        color=colors.HexColor("#cccccc")
    ))
    story.append(Spacer(1, 0.15 * inch))

    # Fixed image dimensions for consistency
    IMAGE_WIDTH = 2.6 * inch
    IMAGE_HEIGHT = 2.6 * inch

    # Receipts two per row
    receipt_pairs = [
        receipts[i:i + 2]
        for i in range(0, len(receipts), 2)
    ]

    for pair in receipt_pairs:
        row_content = []

        for receipt in pair:
            vendor = receipt.get("VENDOR", "Unknown")
            date = receipt.get("DATE", "Unknown")
            amount = receipt.get("AMOUNT", "Unknown")
            category = receipt.get("CATEGORY", "Unknown")
            description = receipt.get("DESCRIPTION", "")
            sites = receipt.get("SITES", [])
            site_str = ", ".join(sites) if sites else "{SITE ID NEEDED}"
            photo_path = receipt.get("photo_path")

            cell = []
            cell.append(Paragraph(vendor, style_section))
            cell.append(HRFlowable(
                width="100%", thickness=0.5,
                color=colors.HexColor("#eeeeee")
            ))
            cell.append(Spacer(1, 0.04 * inch))

            cell.append(Paragraph("DATE", style_field_label))
            cell.append(Paragraph(date, style_field_value))

            cell.append(Paragraph("AMOUNT", style_field_label))
            cell.append(Paragraph(f"${amount}", style_field_value))

            cell.append(Paragraph("CATEGORY", style_field_label))
            cell.append(Paragraph(category, style_field_value))

            cell.append(Paragraph("FINANCE", style_field_label))
            cell.append(Paragraph(site_str, style_field_value))

            if description:
                cell.append(Paragraph("DESCRIPTION", style_field_label))
                cell.append(Paragraph(description, style_field_value))

            if photo_path and os.path.exists(photo_path):
                cell.append(Spacer(1, 0.06 * inch))
                cell.append(Paragraph("RECEIPT IMAGE", style_field_label))
                cell.append(Spacer(1, 0.04 * inch))
                try:
                    img = Image(photo_path)
                    img.drawWidth = IMAGE_WIDTH
                    img.drawHeight = IMAGE_HEIGHT
                    cell.append(img)
                except Exception:
                    cell.append(Paragraph(
                        "Image unavailable", style_field_value
                    ))
            else:
                # Placeholder to keep column heights consistent
                cell.append(Spacer(1, IMAGE_HEIGHT))

            row_content.append(cell)

        # Pad to two columns if only one receipt in pair
        if len(row_content) == 1:
            row_content.append([Spacer(1, 0.1 * inch)])

        table = Table(
            [row_content],
            colWidths=[3.4 * inch, 3.4 * inch],
            hAlign="LEFT"
        )
        table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("BOX", (0, 0), (0, 0), 0.5, colors.HexColor("#dddddd")),
            ("BOX", (1, 0), (1, 0), 0.5, colors.HexColor("#dddddd")),
        ]))
        story.append(table)
        story.append(Spacer(1, 0.15 * inch))

    # Footer
    story.append(HRFlowable(
        width="100%", thickness=0.5,
        color=colors.HexColor("#cccccc")
    ))
    story.append(Spacer(1, 0.08 * inch))
    story.append(Paragraph(
        f"Confidential expense report · {trip_name} · {printed}",
        style_footer
    ))

    doc.build(story)
    return output_path
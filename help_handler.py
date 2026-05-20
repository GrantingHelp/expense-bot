import anthropic
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
from reportlab.lib.enums import TA_CENTER
from dotenv import load_dotenv

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
DEV_EMAIL = "erhardt.belle@gmail.com"
DEV_EMAIL_SUBJECT = "CLAUDE BOT CHANGE RQ - David"

FEATURE_GUIDE = """
Here's what I can do and how to use each one:

📸 *Log a receipt*
Just send me a photo of your receipt. I'll read it and ask which site it's for.

📍 *Save a site code*
Forward any message or link that contains an L- code and I'll save it automatically.

✈️ *Start a trip*
Say something like "starting a trip" or "heading out today". I'll ask what you want to call it.

🏁 *End a trip*
Say "I'm done" or "heading home" and I'll wrap up the trip.

✏️ *Rename a trip*
Say "rename this trip" or "call this trip Portland Run" and I'll update the name.

🔄 *Assign unassigned receipts*
Say "let's reconcile" and I'll walk you through assigning any receipts that don't have a site yet.

🔁 *Update already assigned receipts*
Say "review assigned" and I'll go through your assigned receipts so you can make changes.

📋 *See what you've logged*
Say "show my summary" or "what do I have so far" anytime.

📧 *Email your report*
Say "email me" or "send my report" and I'll send a summary with your receipt images to your email.

Does any of that cover what you were trying to do?
"""


def generate_transcript_pdf(transcript: list, output_path: str) -> str:
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
        "Title",
        fontSize=16,
        fontName="Helvetica-Bold",
        textColor=colors.HexColor("#111111"),
        spaceAfter=4
    )
    style_subtitle = ParagraphStyle(
        "SubTitle",
        fontSize=11,
        fontName="Helvetica",
        textColor=colors.HexColor("#555555"),
        spaceAfter=12
    )
    style_david = ParagraphStyle(
        "David",
        fontSize=11,
        fontName="Helvetica-Bold",
        textColor=colors.HexColor("#1a1a1a"),
        spaceBefore=8,
        spaceAfter=2
    )
    style_bot = ParagraphStyle(
        "Bot",
        fontSize=11,
        fontName="Helvetica",
        textColor=colors.HexColor("#444444"),
        spaceBefore=8,
        spaceAfter=2,
        leftIndent=20
    )
    style_footer = ParagraphStyle(
        "Footer",
        fontSize=9,
        fontName="Helvetica",
        textColor=colors.HexColor("#999999"),
        alignment=TA_CENTER
    )

    printed = datetime.now().strftime("%B %d, %Y %I:%M %p")
    story = []

    story.append(Paragraph("Change Request Transcript", style_title))
    story.append(Paragraph(f"Generated: {printed}", style_subtitle))
    story.append(HRFlowable(
        width="100%", thickness=1,
        color=colors.HexColor("#cccccc")
    ))
    story.append(Spacer(1, 0.15 * inch))

    for entry in transcript:
        role = entry.get("role", "")
        message = entry.get("message", "")
        if role == "david":
            story.append(Paragraph(f"David: {message}", style_david))
        else:
            story.append(Paragraph(f"Bot: {message}", style_bot))

    story.append(Spacer(1, 0.2 * inch))
    story.append(HRFlowable(
        width="100%", thickness=0.5,
        color=colors.HexColor("#cccccc")
    ))
    story.append(Spacer(1, 0.08 * inch))
    story.append(Paragraph(
        f"Claude Bot Change Request · {printed}",
        style_footer
    ))

    doc.build(story)
    return output_path


def summarize_change_request(transcript: list) -> str:
    conversation = "\n".join([
        f"{'David' if e['role'] == 'david' else 'Bot'}: {e['message']}"
        for e in transcript
    ])

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=500,
        messages=[
            {
                "role": "user",
                "content": f"""You are summarizing a change request for a developer.
A field worker named David was using a Telegram expense tracking bot and identified 
something he needs that the bot doesn't currently support.

Here is the conversation transcript:

{conversation}

Write a concise change request summary for the developer. Include:
1. What David was trying to do
2. Why the current bot doesn't meet his need
3. What the new feature or change should do
4. How often he expects to use it if mentioned

Write it clearly and technically — this is for a developer to act on.
Keep it under 200 words."""
            }
        ]
    )
    return response.content[0].text.strip()


def needs_clarification(transcript: list) -> tuple[bool, str]:
    conversation = "\n".join([
        f"{'David' if e['role'] == 'david' else 'Bot'}: {e['message']}"
        for e in transcript
        if e.get("role") == "david"
    ])

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=100,
        messages=[
            {
                "role": "user",
                "content": f"""A field worker named David is describing a feature he needs 
for his expense tracking bot. Based on what he said, do you have enough information 
to write a clear change request, or do you need one more clarifying question?

What David said: "{conversation}"

If you need clarification, reply with:
CLARIFY: <one short natural question to ask him>

If you have enough information, reply with:
ENOUGH

Reply with only one of those two formats."""
            }
        ]
    )

    result = response.content[0].text.strip()
    if result.startswith("CLARIFY:"):
        question = result.replace("CLARIFY:", "").strip()
        return True, question
    return False, ""


def send_change_request_email(summary: str, transcript_pdf_path: str) -> bool:
    try:
        msg = MIMEMultipart()
        msg["From"] = GMAIL_ADDRESS
        msg["To"] = DEV_EMAIL
        msg["Subject"] = DEV_EMAIL_SUBJECT

        body = (
            f"Hi Belle,\n\n"
            f"David submitted a change request via the expense bot. "
            f"Here's a summary of what he needs:\n\n"
            f"{'=' * 40}\n\n"
            f"{summary}\n\n"
            f"{'=' * 40}\n\n"
            f"Full conversation transcript is attached as a PDF.\n\n"
            f"This was generated automatically by the expense bot."
        )

        msg.attach(MIMEText(body, "plain"))

        with open(transcript_pdf_path, "rb") as f:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header(
                "Content-Disposition",
                f"attachment; filename={os.path.basename(transcript_pdf_path)}"
            )
            msg.attach(part)

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_ADDRESS, DEV_EMAIL, msg.as_string())

        return True

    except Exception as e:
        import logging
        logging.error(f"Change request email error: {e}")
        return False
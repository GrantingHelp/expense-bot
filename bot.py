import logging
import os
import re
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from receipt_processor import process_receipt
from trip_log import (
    add_receipt, start_trip, get_current_trip, add_site_code,
    get_trip_summary, end_trip, update_receipt_sites,
    get_unassigned_receipts, get_assigned_receipts, update_trip_name,
    get_last_trip
)
from reconciliation import (
    format_trip_summary, start_reconciliation,
    start_review_assigned, build_next_prompt
)
from pdf_generator import generate_pdf
from help_handler import (
    FEATURE_GUIDE, needs_clarification, summarize_change_request,
    generate_transcript_pdf, send_change_request_email
)

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
RECIPIENT_EMAIL = "derhardt@tepgroup.net"

import anthropic
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)


def extract_site_code(text: str) -> str | None:
    match = re.search(r'L-\w+', text)
    return match.group(0) if match else None


def parse_sites_from_input(text: str) -> list:
    parts = [s.strip() for s in re.split(r'[,\n]', text) if s.strip()]
    cleaned = []
    for part in parts:
        match = re.search(r'L-\w+', part)
        if match:
            cleaned.append(match.group(0))
        else:
            cleaned.append(part)
    return cleaned


def interpret_intent(text: str) -> str:
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=50,
        messages=[
            {
                "role": "user",
                "content": f"""You are interpreting a message from a field worker to his expense tracking bot.
Classify this message into exactly one of these intents:
- START_TRIP: he is starting a new trip or heading out for the day
- END_TRIP: he is done for the day or finishing a trip
- SUMMARY: he wants to see what he has logged so far
- EMAIL: he wants the summary emailed to him
- RECONCILE: he wants to sort or assign unassigned receipts
- REVIEW_ASSIGNED: he wants to review and update already assigned receipts
- RENAME_TRIP: he wants to name or rename the current trip
- HELP: he is confused, lost, needs help, or doesn't know what to do
- SITE_CODE: he is providing or referencing a site code
- UNKNOWN: none of the above

Message: "{text}"

Reply with only the intent label, nothing else."""
            }
        ]
    )
    return response.content[0].text.strip()


def send_email(trip: dict, pdf_path: str) -> bool:
    try:
        summary_text = format_trip_summary(trip)

        msg = MIMEMultipart()
        msg["From"] = GMAIL_ADDRESS
        msg["To"] = RECIPIENT_EMAIL
        msg["Subject"] = f"Expense Report — {trip.get('name', 'Trip')}"

        body = (
            f"Hi David,\n\n"
            f"Please find your expense report summary below, "
            f"with receipt images attached as a PDF.\n\n"
            f"{'=' * 40}\n\n"
            f"{summary_text}\n\n"
            f"{'=' * 40}\n\n"
            f"This report was generated automatically by your expense bot."
        )

        msg.attach(MIMEText(body, "plain"))

        with open(pdf_path, "rb") as f:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header(
                "Content-Disposition",
                f"attachment; filename={os.path.basename(pdf_path)}"
            )
            msg.attach(part)

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_ADDRESS, RECIPIENT_EMAIL, msg.as_string())

        return True

    except Exception as e:
        logging.error(f"Email error: {e}")
        return False


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hi! I'm your expense bot.\n\n"
        "Here's what I can do:\n"
        "📸 Send me a receipt photo and I'll log it\n"
        "📍 Forward a site link and I'll save the code\n"
        "🗓 Tell me you're starting a trip and I'll track it\n"
        "📋 Ask me for a summary anytime\n"
        "🔄 Say 'let's reconcile' to assign unassigned receipts\n"
        "📧 Say 'email me' when you're ready to send your report\n"
        "❓ Say 'help' if you're lost or need something new"
    )


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Got your receipt, processing it now...")

    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)

    photo_path = f"temp_photos/{photo.file_id}.jpg"
    logging.info(f"Attempting to download photo to: {photo_path}")
    await file.download_to_drive(photo_path)
    logging.info(f"Photo downloaded successfully to: {photo_path}")
    context.user_data['pending_photo_path'] = photo_path

    try:
        receipt_data = process_receipt(photo_path)
        context.user_data['pending_receipt'] = receipt_data

        if not get_current_trip():
            start_trip()
            context.user_data['awaiting_trip_name'] = True
            context.user_data['awaiting_site_after_name'] = True
            await update.message.reply_text(
                "No active trip found so I started one automatically. "
                "What would you like to call this trip?"
            )
            return

        response = (
            f"✅ Receipt processed:\n\n"
            f"🏪 Vendor: {receipt_data.get('VENDOR', 'Unknown')}\n"
            f"📅 Date: {receipt_data.get('DATE', 'Unknown')}\n"
            f"💵 Amount: ${receipt_data.get('AMOUNT', 'Unknown')}\n"
            f"🏷 Category: {receipt_data.get('CATEGORY', 'Unknown')}\n"
            f"📝 Description: {receipt_data.get('DESCRIPTION', 'Unknown')}\n\n"
            f"Which site(s) is this for? You can reply with a site code, "
            f"a description like 'first stop', multiple sites separated by commas, "
            f"or say 'skip' to sort it out later."
        )

        await update.message.reply_text(response)
        context.user_data['awaiting_site'] = True

    except Exception as e:
        await update.message.reply_text(
            "Sorry, I had trouble processing that receipt. Please try again."
        )
        logging.error(f"Receipt processing error: {e}")

    finally:
        pass


async def wrap_up_change_request(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
):
    transcript = context.user_data.get('help_transcript', [])

    await update.message.reply_text(
        "Got it — let me put that together and send it to Belle."
    )

    summary = summarize_change_request(transcript)
    pdf_path = f"change_request_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"

    try:
        generate_transcript_pdf(transcript, pdf_path)
        success = send_change_request_email(summary, pdf_path)

        if success:
            await update.message.reply_text(
                "✅ Done — Belle has been notified with a summary "
                "of what you need. She'll be in touch."
            )
        else:
            await update.message.reply_text(
                "I had trouble sending the email. Please let Belle know directly."
            )
    except Exception as e:
        logging.error(f"Change request error: {e}")
        await update.message.reply_text(
            "Something went wrong. Please let Belle know directly."
        )

    context.user_data['help_mode'] = False
    context.user_data['help_stage'] = None
    context.user_data['help_transcript'] = []


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    # --- Awaiting trip name ---
    if context.user_data.get('awaiting_trip_name'):
        trip_id = get_current_trip()
        if trip_id:
            update_trip_name(trip_id, text)
            await update.message.reply_text(
                f"✅ Trip named '{text}'."
            )
        context.user_data['awaiting_trip_name'] = False

        # If a receipt is waiting for site assignment, ask now
        if context.user_data.get('awaiting_site_after_name'):
            context.user_data['awaiting_site_after_name'] = False
            context.user_data['awaiting_site'] = True
            receipt_data = context.user_data.get('pending_receipt', {})
            await update.message.reply_text(
                f"Got it. Now — which site is this receipt for?\n\n"
                f"🏪 {receipt_data.get('VENDOR', 'Unknown')} "
                f"${receipt_data.get('AMOUNT', 'Unknown')} — "
                f"{receipt_data.get('CATEGORY', 'Unknown')}\n\n"
                f"Reply with a site code, a description like 'first stop', "
                f"multiple sites separated by commas, or say 'skip'."
            )
        return

    # --- Help mode ---
    if context.user_data.get('help_mode'):
        stage = context.user_data.get('help_stage')
        transcript = context.user_data.get('help_transcript', [])

        if stage == 'features_shown':
            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=50,
                messages=[
                    {
                        "role": "user",
                        "content": f"""A user was shown a feature guide and replied: "{text}"
Did they indicate that their question was answered and they no longer need help?
Reply with only YES or NO."""
                    }
                ]
            )
            resolved = response.content[0].text.strip() == "YES"

            if resolved:
                context.user_data['help_mode'] = False
                context.user_data['help_stage'] = None
                context.user_data['help_transcript'] = []
                await update.message.reply_text(
                    "Great! Let me know if you need anything else."
                )
            else:
                context.user_data['help_stage'] = 'gathering'
                context.user_data['help_transcript'] = []
                await update.message.reply_text(
                    "No problem — just tell me what you were trying to do "
                    "and what happened instead. Explain it however feels natural."
                )
            return

        elif stage == 'gathering':
            transcript.append({"role": "david", "message": text})
            context.user_data['help_transcript'] = transcript

            clarify_needed, question = needs_clarification(transcript)

            if clarify_needed:
                context.user_data['help_stage'] = 'clarifying'
                transcript.append({"role": "bot", "message": question})
                context.user_data['help_transcript'] = transcript
                await update.message.reply_text(question)
            else:
                await wrap_up_change_request(update, context)
            return

        elif stage == 'clarifying':
            transcript.append({"role": "david", "message": text})
            context.user_data['help_transcript'] = transcript
            await wrap_up_change_request(update, context)
            return

    # --- Awaiting site assignment after a receipt photo ---
    if context.user_data.get('awaiting_site'):
        receipt_data = context.user_data.get('pending_receipt', {})
        photo_path = context.user_data.get('pending_photo_path')

        if text.lower() == 'skip':
            sites = []
            await update.message.reply_text(
                "No problem — receipt saved as unassigned. "
                "You can sort it out during reconciliation."
            )
        else:
            sites = parse_sites_from_input(text)
            site_display = ", ".join(sites)
            await update.message.reply_text(
                f"Got it — receipt tied to {site_display}."
            )

        add_receipt(receipt_data, sites, photo_path)
        context.user_data['awaiting_site'] = False
        context.user_data['pending_receipt'] = None
        context.user_data['pending_photo_path'] = None
        return

    # --- Reconciliation in progress ---
    if context.user_data.get('reconciling'):
        await handle_reconciliation_reply(update, context, text)
        return

    # --- Review assigned in progress ---
    if context.user_data.get('reviewing_assigned'):
        await handle_review_reply(update, context, text)
        return

    # --- Check for site code in message ---
    site_code = extract_site_code(text)
    if site_code:
        add_site_code(site_code)
        await update.message.reply_text(
            f"📍 Site code saved: {site_code}"
        )
        return

    # --- Interpret intent via Claude ---
    intent = interpret_intent(text)
    logging.info(f"Detected intent: {intent} for message: {text}")

    if intent == "START_TRIP":
        context.user_data['awaiting_trip_name'] = True
        start_trip()
        await update.message.reply_text(
            "✈️ Trip started! What would you like to call this trip?"
        )

    elif intent == "RENAME_TRIP":
        trip_id = get_current_trip()
        if not trip_id:
            await update.message.reply_text("No active trip found.")
            return
        context.user_data['awaiting_trip_name'] = True
        await update.message.reply_text(
            "What would you like to call this trip?"
        )

    elif intent == "END_TRIP":
        trip = get_trip_summary()
        if not trip:
            await update.message.reply_text("No active trip found.")
            return
        receipts = trip.get("receipts", [])
        unassigned = [r for r in receipts if not r.get("SITES")]
        end_trip()
        msg = (
            f"✅ Trip ended.\n\n"
            f"🧾 Total receipts: {len(receipts)}\n"
        )
        if unassigned:
            msg += (
                f"⚠️ {len(unassigned)} unassigned receipt"
                f"{'s' if len(unassigned) != 1 else ''}.\n"
                f"Say 'let's reconcile' to sort them out."
            )
        else:
            msg += "All receipts are assigned.\n"
        msg += "\nSay 'email me' when you're ready to send your report."
        await update.message.reply_text(msg)

    elif intent == "SUMMARY":
        trip = get_trip_summary()
        if not trip:
            await update.message.reply_text(
                "No active trip. Just start sending receipts and "
                "I'll track everything."
            )
            return
        await update.message.reply_text(format_trip_summary(trip))

    elif intent == "RECONCILE":
        trip_id = get_current_trip()
        if not trip_id:
            await update.message.reply_text(
                "No active trip found. Start a trip first."
            )
            return
        unassigned, msg = start_reconciliation(trip_id)
        if not unassigned:
            await update.message.reply_text(msg)
            return
        context.user_data['reconciling'] = True
        context.user_data['reconcile_queue'] = unassigned
        context.user_data['reconcile_index'] = 0
        context.user_data['reconcile_trip_id'] = trip_id
        await update.message.reply_text(msg)

    elif intent == "REVIEW_ASSIGNED":
        trip_id = get_current_trip()
        if not trip_id:
            await update.message.reply_text("No active trip found.")
            return
        assigned, msg = start_review_assigned(trip_id)
        if not assigned:
            await update.message.reply_text(msg)
            return
        context.user_data['reviewing_assigned'] = True
        context.user_data['review_queue'] = assigned
        context.user_data['review_index'] = 0
        context.user_data['review_trip_id'] = trip_id
        await update.message.reply_text(msg)

    elif intent == "HELP":
        context.user_data['help_mode'] = True
        context.user_data['help_stage'] = 'features_shown'
        context.user_data['help_transcript'] = []
        await update.message.reply_text(FEATURE_GUIDE)
        return

    elif intent == "EMAIL":
        trip = get_trip_summary()
        if not trip:
            last_id = get_last_trip()
            if last_id:
                trip = get_trip_summary(last_id)
            if not trip:
                await update.message.reply_text(
                    "No trip found to report on."
                )
                return
        await update.message.reply_text(
            "Generating your report, one moment..."
        )
        trip_name = trip.get("name", "trip").replace(" ", "_")
        pdf_path = f"{trip_name}_expense_report.pdf"
        try:
            generate_pdf(trip, pdf_path)
            success = send_email(trip, pdf_path)
            if success:
                await update.message.reply_text(
                    f"📧 Report sent to {RECIPIENT_EMAIL}.\n"
                    f"Summary and PDF receipt images are included."
                )
            else:
                await update.message.reply_text(
                    "Sorry, I had trouble sending the email. "
                    "Please check the email settings and try again."
                )
        except Exception as e:
            logging.error(f"Report generation error: {e}")
            await update.message.reply_text(
                "Sorry, I had trouble generating the report. Please try again."
            )

    else:
        await update.message.reply_text(
            "I'm not sure what you need. You can:\n"
            "📸 Send a receipt photo\n"
            "📍 Forward a site link\n"
            "📋 Ask for a summary\n"
            "🔄 Say 'let's reconcile' to assign receipts\n"
            "✈️ Tell me you're starting or finishing a trip\n"
            "📧 Say 'email me' to send your report\n"
            "❓ Say 'help' if you're lost or need something new"
        )


async def handle_reconciliation_reply(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        text: str
):
    queue = context.user_data.get('reconcile_queue', [])
    index = context.user_data.get('reconcile_index', 0)
    trip_id = context.user_data.get('reconcile_trip_id')
    current = queue[index]

    if text.lower() == 'skip':
        sites = []
        await update.message.reply_text("Skipped — left unassigned.")
    else:
        sites = parse_sites_from_input(text)
        site_display = ", ".join(sites)
        await update.message.reply_text(f"✅ Assigned to {site_display}.")

    if sites:
        update_receipt_sites(
            trip_id,
            current.get("receipt_index"),
            sites
        )

    next_index = index + 1
    if next_index >= len(queue):
        context.user_data['reconciling'] = False
        context.user_data['reconcile_queue'] = []
        context.user_data['reconcile_index'] = 0
        await update.message.reply_text(
            "✅ Reconciliation complete.\n\n"
            "Say 'summary' to review your trip or "
            "'email me' to send your report."
        )
    else:
        context.user_data['reconcile_index'] = next_index
        next_receipt = queue[next_index]
        remaining = len(queue) - next_index - 1
        await update.message.reply_text(
            build_next_prompt(next_receipt, remaining, mode="reconcile")
        )


async def handle_review_reply(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        text: str
):
    queue = context.user_data.get('review_queue', [])
    index = context.user_data.get('review_index', 0)
    trip_id = context.user_data.get('review_trip_id')
    current = queue[index]

    if text.lower() == 'keep':
        await update.message.reply_text("Kept as is.")
    else:
        sites = parse_sites_from_input(text)
        site_display = ", ".join(sites)
        update_receipt_sites(
            trip_id,
            current.get("receipt_index"),
            sites
        )
        await update.message.reply_text(f"✅ Updated to {site_display}.")

    next_index = index + 1
    if next_index >= len(queue):
        context.user_data['reviewing_assigned'] = False
        context.user_data['review_queue'] = []
        context.user_data['review_index'] = 0
        await update.message.reply_text(
            "✅ Review complete.\n\n"
            "Say 'summary' to review your trip or "
            "'email me' to send your report."
        )
    else:
        context.user_data['review_index'] = next_index
        next_receipt = queue[next_index]
        remaining = len(queue) - next_index - 1
        await update.message.reply_text(
            build_next_prompt(next_receipt, remaining, mode="review")
        )


def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND, handle_message
    ))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    print("Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
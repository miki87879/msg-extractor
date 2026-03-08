from flask import Flask, request, jsonify, Response
import tempfile
import os
import re
import extract_msg

app = Flask(__name__)

@app.route("/")
def home():
    return {"status": "ok", "message": "MSG extractor is running"}

@app.route("/extract-pdf", methods=["POST"])
def extract_pdf():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    uploaded_file = request.files["file"]

    if uploaded_file.filename == "":
        return jsonify({"error": "Empty filename"}), 400

    with tempfile.NamedTemporaryFile(delete=False, suffix=".msg") as temp_file:
        uploaded_file.save(temp_file.name)
        temp_path = temp_file.name

    try:
        msg = extract_msg.Message(temp_path)

        attachment_list = []
        body_text = msg.body or ""
        subject = msg.subject or ""
        sender = msg.sender or ""
        msg_date = str(msg.date) if msg.date else ""

        for attachment in msg.attachments:
            filename = getattr(attachment, "longFilename", None) or getattr(attachment, "shortFilename", None) or "attachment.bin"
            data = getattr(attachment, "data", None)

            attachment_list.append({
                "filename": filename,
                "has_data": data is not None
            })

            if filename and filename.lower().endswith(".pdf") and data:
                return Response(
                    data,
                    mimetype="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'}
                )

        urls = re.findall(r'https?://[^\s<>"\']+', body_text)

        filtered_urls = []
        for url in urls:
            lowered = url.lower()

            # לדלג על תמונות וקבצים לא רלוונטיים
            if any(lowered.endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"]):
                continue

            # עדיפות גבוהה לקישורי חשבונית
            if any(keyword in lowered for keyword in [
                "p_print",
                "invoice",
                "receipt",
                "docemail",
                "icount",
                "hash",
                "print"
            ]):
                filtered_urls.append(url)

        invoice_url = filtered_urls[0] if filtered_urls else None

        return jsonify({
            "error": "No PDF found inside MSG",
            "subject": subject,
            "sender": sender,
            "date": msg_date,
            "body_preview": body_text[:2000],
            "attachments": attachment_list,
            "pdf_found": False,
            "invoice_url": invoice_url,
            "all_urls": urls[:20],
            "filtered_urls": filtered_urls[:20]
        }), 404

    finally:
        os.remove(temp_path)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)            filename = getattr(attachment, "longFilename", None) or getattr(attachment, "shortFilename", None) or "attachment.bin"
            data = getattr(attachment, "data", None)

            attachment_list.append({
                "filename": filename,
                "has_data": data is not None
            })

            if filename and filename.lower().endswith(".pdf") and data:
                return Response(
                    data,
                    mimetype="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'}
                )

        # אם אין PDF - מחפשים קישור לחשבונית בתוך גוף המייל
        urls = re.findall(r'https?://[^\s<>"\']+', body_text)

        invoice_url = None
        for url in urls:
            lowered = url.lower()
            if any(keyword in lowered for keyword in [
                "icount",
                "invoice",
                "receipt",
                "print",
                "docemail",
                "p_print",
                "greeninvoice",
                "morning",
                "rivhit",
                "meshulam"
            ]):
                invoice_url = url
                break

        return jsonify({
            "error": "No PDF found inside MSG",
            "subject": subject,
            "sender": sender,
            "date": msg_date,
            "body_preview": body_text[:2000],
            "attachments": attachment_list,
            "pdf_found": False,
            "invoice_url": invoice_url,
            "all_urls": urls[:20]
        }), 404

    finally:
        os.remove(temp_path)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)

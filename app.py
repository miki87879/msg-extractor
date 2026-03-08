from flask import Flask, request, jsonify, Response
import tempfile
import os
import re
import extract_msg

app = Flask(__name__)


@app.route("/")
def home():
    return jsonify({
        "status": "ok",
        "message": "MSG extractor is running"
    })


@app.route("/extract-pdf", methods=["POST"])
def extract_pdf():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    uploaded_file = request.files["file"]

    if uploaded_file.filename == "":
        return jsonify({"error": "Empty filename"}), 400

    temp_path = None

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".msg") as temp_file:
            uploaded_file.save(temp_file.name)
            temp_path = temp_file.name

        msg = extract_msg.Message(temp_path)

        attachment_list = []
        body_text = msg.body or ""
        subject = msg.subject or ""
        sender = msg.sender or ""
        msg_date = str(msg.date) if msg.date else ""

        for attachment in msg.attachments:
            long_name = getattr(attachment, "longFilename", None)
            short_name = getattr(attachment, "shortFilename", None)
            filename = long_name or short_name or "attachment.bin"
            data = getattr(attachment, "data", None)

            attachment_list.append({
                "filename": filename,
                "has_data": data is not None
            })

            if filename.lower().endswith(".pdf") and data:
                return Response(
                    data,
                    mimetype="application/pdf",
                    headers={
                        "Content-Disposition": f'attachment; filename="{filename}"'
                    }
                )

        urls = re.findall(r'https?://[^\s<>"\']+', body_text)

        filtered_urls = []
        blocked_extensions = [".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"]

        for url in urls:
            lowered = url.lower()

            if any(lowered.endswith(ext) for ext in blocked_extensions):
                continue

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
            "status": "link_found",
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
        })

    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)

from flask import Flask, request, jsonify, Response
import tempfile
import os
import re
import extract_msg

app = Flask(__name__)


def extract_urls_from_text(body_text: str):
    urls = re.findall(r'https?://[^\s<>"\']+', body_text or "")
    blocked_extensions = [".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"]

    filtered_urls = []
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
    return urls[:20], filtered_urls[:20], invoice_url


def inspect_msg_file(msg_path: str, depth: int = 0):
    msg = extract_msg.Message(msg_path)

    body_text = msg.body or ""
    subject = msg.subject or ""
    sender = msg.sender or ""
    msg_date = str(msg.date) if msg.date else ""

    attachment_list = []

    # 1. קודם מחפשים PDF ישיר
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
            return {
                "type": "pdf",
                "filename": filename,
                "data": data
            }

    # 2. מחפשים URL לחשבונית בגוף ההודעה
    all_urls, filtered_urls, invoice_url = extract_urls_from_text(body_text)
    if invoice_url:
        return {
            "type": "link",
            "subject": subject,
            "sender": sender,
            "date": msg_date,
            "body_preview": body_text[:2000],
            "attachments": attachment_list,
            "pdf_found": False,
            "invoice_url": invoice_url,
            "all_urls": all_urls,
            "filtered_urls": filtered_urls
        }

    # 3. אם אין PDF ואין לינק - מחפשים MSG פנימי
    if depth < 2:
        for attachment in msg.attachments:
            long_name = getattr(attachment, "longFilename", None)
            short_name = getattr(attachment, "shortFilename", None)
            filename = long_name or short_name or "attachment.bin"
            data = getattr(attachment, "data", None)

            if not data:
                continue

            if filename.lower().endswith(".msg"):
                nested_temp_path = None
                try:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".msg") as nested_file:
                        nested_file.write(data)
                        nested_temp_path = nested_file.name

                    nested_result = inspect_msg_file(nested_temp_path, depth + 1)
                    if nested_result:
                        nested_result["nested_from"] = filename
                        return nested_result

                finally:
                    if nested_temp_path and os.path.exists(nested_temp_path):
                        os.remove(nested_temp_path)

    # 4. אם לא מצאנו כלום
    return {
        "type": "none",
        "subject": subject,
        "sender": sender,
        "date": msg_date,
        "body_preview": body_text[:2000],
        "attachments": attachment_list,
        "pdf_found": False,
        "invoice_url": None,
        "all_urls": [],
        "filtered_urls": []
    }


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

        result = inspect_msg_file(temp_path)

        if result["type"] == "pdf":
            return Response(
                result["data"],
                mimetype="application/pdf",
                headers={
                    "Content-Disposition": f'attachment; filename="{result["filename"]}"'
                }
            )

        if result["type"] == "link":
            return jsonify({
                "status": "link_found",
                "error": "No PDF found inside MSG",
                "subject": result.get("subject"),
                "sender": result.get("sender"),
                "date": result.get("date"),
                "body_preview": result.get("body_preview"),
                "attachments": result.get("attachments"),
                "pdf_found": False,
                "invoice_url": result.get("invoice_url"),
                "all_urls": result.get("all_urls"),
                "filtered_urls": result.get("filtered_urls"),
                "nested_from": result.get("nested_from")
            })

        return jsonify({
            "status": "no_invoice_found",
            "error": "No PDF or invoice link found inside MSG",
            "subject": result.get("subject"),
            "sender": result.get("sender"),
            "date": result.get("date"),
            "body_preview": result.get("body_preview"),
            "attachments": result.get("attachments"),
            "pdf_found": False,
            "invoice_url": None,
            "all_urls": result.get("all_urls"),
            "filtered_urls": result.get("filtered_urls"),
            "nested_from": result.get("nested_from")
        })

    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)

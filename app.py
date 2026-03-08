from flask import Flask, request, jsonify, Response
import tempfile
import os
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
        pdf_found = False

        for attachment in msg.attachments:
            filename = getattr(attachment, "longFilename", None) or getattr(attachment, "shortFilename", None) or "attachment.bin"
            data = getattr(attachment, "data", None)

            attachment_list.append({
                "filename": filename,
                "has_data": data is not None
            })

            if filename and filename.lower().endswith(".pdf") and data:
                pdf_found = True
                return Response(
                    data,
                    mimetype="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'}
                )

        return jsonify({
            "error": "No PDF found inside MSG",
            "subject": msg.subject,
            "sender": msg.sender,
            "date": str(msg.date),
            "body_preview": (msg.body[:1000] if msg.body else ""),
            "attachments": attachment_list,
            "pdf_found": pdf_found
        }), 404

    finally:
        os.remove(temp_path)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)

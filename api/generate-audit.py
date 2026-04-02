"""
Vercel Serverless Function — POST /api/generate-audit
Receives lead data from GHL webhook, generates a branded Missed Call Audit PDF,
uploads it to Vercel Blob storage, and returns the public URL.

Expected POST body (JSON):
{
    "company_name": "Bluewave Plumbing",
    "first_name": "Mike",
    "email": "mike@bluewave.com",        // optional, for future use
    "phone": "6195551234",                // optional, for future use
    "zip_code": "92101",
    "service_type": "Plumbing",
    "monthly_calls": "100-200"
}

Returns:
{
    "success": true,
    "pdf_url": "https://xxxxxxx.public.blob.vercel-storage.com/audit-bluewave-plumbing-xxxx.pdf",
    "company_name": "Bluewave Plumbing",
    "annual_loss": "$84,240"
}
"""

from http.server import BaseHTTPRequestHandler
import json
import os
import sys
import urllib.request
import time
import hashlib

# Add project root to path so we can import lib/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib.pdf_generator import generate_audit_pdf, calculate_metrics, fmt_currency, MONTHLY_CALL_MAP, AVG_JOB_VALUES


def upload_to_vercel_blob(pdf_bytes, filename):
    """Upload PDF bytes to Vercel Blob and return the public URL."""
    blob_token = os.environ.get("BLOB_READ_WRITE_TOKEN")
    if not blob_token:
        raise ValueError("BLOB_READ_WRITE_TOKEN environment variable not set")

    url = f"https://blob.vercel-storage.com/{filename}"
    req = urllib.request.Request(
        url,
        data=pdf_bytes,
        method="PUT",
        headers={
            "Authorization": f"Bearer {blob_token}",
            "Content-Type": "application/pdf",
            "x-api-version": "7",
            "x-content-type": "application/pdf",
        },
    )

    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read().decode())
        return result.get("url", "")


def slugify(text):
    """Simple slugify for filenames."""
    return text.lower().replace(" ", "-").replace("'", "").replace("&", "and")[:50]


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            # Parse request body
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            data = json.loads(body.decode("utf-8"))

            # Extract fields
            company_name = data.get("company_name", "").strip()
            first_name = data.get("first_name", "").strip()
            zip_code = data.get("zip_code", "").strip()
            service_type = data.get("service_type", "Plumbing").strip()
            monthly_calls = data.get("monthly_calls", "100-200").strip()

            # Validate required fields
            if not company_name:
                self._send_error(400, "company_name is required")
                return

            if not zip_code:
                self._send_error(400, "zip_code is required")
                return

            if service_type not in AVG_JOB_VALUES:
                self._send_error(400, f"Invalid service_type. Must be one of: {', '.join(AVG_JOB_VALUES.keys())}")
                return

            # Generate PDF as bytes
            pdf_bytes = generate_audit_pdf(
                output_path=None,  # return bytes
                company_name=company_name,
                first_name=first_name,
                zip_code=zip_code,
                monthly_calls_label=monthly_calls,
                service_type=service_type,
            )

            # Generate unique filename
            ts = str(int(time.time()))
            slug = slugify(company_name)
            hash_suffix = hashlib.md5(f"{company_name}{ts}".encode()).hexdigest()[:8]
            filename = f"audits/audit-{slug}-{hash_suffix}.pdf"

            # Upload to Vercel Blob
            pdf_url = upload_to_vercel_blob(pdf_bytes, filename)

            # Calculate metrics for response
            metrics = calculate_metrics(monthly_calls, service_type)

            # Return success response
            self._send_json(200, {
                "success": True,
                "pdf_url": pdf_url,
                "company_name": company_name,
                "annual_loss": fmt_currency(metrics["annual_loss"]),
                "monthly_loss": fmt_currency(metrics["monthly_loss"]),
            })

        except json.JSONDecodeError:
            self._send_error(400, "Invalid JSON body")
        except ValueError as e:
            self._send_error(500, str(e))
        except Exception as e:
            self._send_error(500, f"Internal error: {str(e)}")

    def do_GET(self):
        """Health check endpoint."""
        self._send_json(200, {
            "status": "ok",
            "service": "Neighborly Voice AI — Audit PDF Generator",
            "valid_service_types": list(AVG_JOB_VALUES.keys()),
            "valid_monthly_calls": list(MONTHLY_CALL_MAP.keys()),
        })

    def _send_json(self, status_code, data):
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def _send_error(self, status_code, message):
        self._send_json(status_code, {"success": False, "error": message})

    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

"""
Vercel Serverless Function — POST /api/generate-audit
Receives lead data from GHL webhook, generates a branded Missed Call Audit PDF,
uploads it to Vercel Blob storage, writes the PDF URL back to the GHL contact,
and returns the public URL.

GHL webhook sends standard contact data automatically. Custom Data keys map
the fields we need. The contact_id comes in the standard payload.

Returns:
{
    "success": true,
    "pdf_url": "https://xxxxxxx.public.blob.vercel-storage.com/audit-bluewave-plumbing-xxxx.pdf",
    "company_name": "Bluewave Plumbing",
    "annual_loss": "$84,240",
    "ghl_updated": true
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

# GHL config
GHL_CUSTOM_FIELD_KEY = "contact.audit_pdf_url"


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


def update_ghl_contact(contact_id, pdf_url):
    """Write the PDF URL back to the GHL contact's custom field via GHL API v2."""
    api_key = os.environ.get("GHL_API_KEY")
    if not api_key:
        return {"error": "GHL_API_KEY not set"}

    url = f"https://services.leadconnectorhq.com/contacts/{contact_id}"

    payload = json.dumps({
        "customFields": [
            {
                "key": GHL_CUSTOM_FIELD_KEY,
                "value": pdf_url,
            }
        ]
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        method="PUT",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Version": "2021-07-28",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode() if e.fp else ""
        return {"error": f"GHL API {e.code}: {error_body}"}
    except Exception as e:
        return {"error": str(e)}


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

            # Extract fields — from GHL Custom Data key/value pairs
            company_name = data.get("company_name", "").strip()
            first_name = data.get("first_name", "").strip()
            zip_code = (data.get("zip_code") or data.get("postal_code") or "").strip()
            service_type = data.get("service_type", "Plumbing").strip()
            monthly_calls = data.get("monthly_calls", "100-200").strip()

            # GHL standard payload includes contact_id
            contact_id = data.get("contact_id", "").strip()

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

            # Write PDF URL back to GHL contact
            ghl_updated = False
            ghl_result = None
            if contact_id:
                ghl_result = update_ghl_contact(contact_id, pdf_url)
                ghl_updated = "error" not in ghl_result

            # Calculate metrics for response
            metrics = calculate_metrics(monthly_calls, service_type)

            # Return success response
            response = {
                "success": True,
                "pdf_url": pdf_url,
                "company_name": company_name,
                "annual_loss": fmt_currency(metrics["annual_loss"]),
                "monthly_loss": fmt_currency(metrics["monthly_loss"]),
                "ghl_updated": ghl_updated,
            }

            # Include GHL error info if update failed (for debugging)
            if not ghl_updated and contact_id:
                response["ghl_error"] = ghl_result

            self._send_json(200, response)

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

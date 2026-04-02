# Neighborly Voice AI — Missed Call Audit PDF Generator

Serverless API that generates personalized "Missed Call Audit" PDFs for home service business leads. Built for the GHL → Vercel → email delivery pipeline.

## Architecture

```
GHL Form Submit → GHL Workflow → Webhook POST → Vercel Serverless (Python)
  → Generate branded PDF → Upload to Vercel Blob → Return public URL
  → GHL saves URL to custom field → GHL emails lead with PDF link
```

## Project Structure

```
neighborly-audit-pdf/
├── api/
│   └── generate-audit.py    ← Vercel serverless endpoint
├── lib/
│   ├── __init__.py
│   └── pdf_generator.py     ← PDF generation logic (ReportLab)
├── assets/
│   └── logo.png             ← Branded logo (charcoal background)
├── requirements.txt          ← Python dependencies
├── vercel.json               ← Vercel route + runtime config
└── README.md
```

## Setup

### 1. Create GitHub Repo

```bash
git init
git add .
git commit -m "Initial commit — audit PDF generator"
git remote add origin https://github.com/YOUR_USERNAME/neighborly-audit-pdf.git
git push -u origin main
```

### 2. Deploy to Vercel

1. Go to [vercel.com/new](https://vercel.com/new) and import the GitHub repo
2. Framework Preset: **Other**
3. Deploy

### 3. Add Vercel Blob Storage

1. In your Vercel project dashboard → **Storage** → **Create Database** → **Blob**
2. This auto-creates the `BLOB_READ_WRITE_TOKEN` environment variable
3. Redeploy after adding storage

### 4. Test the Endpoint

**Health check (GET):**
```bash
curl https://your-project.vercel.app/api/generate-audit
```

**Generate a PDF (POST):**
```bash
curl -X POST https://your-project.vercel.app/api/generate-audit \
  -H "Content-Type: application/json" \
  -d '{
    "company_name": "Bluewave Plumbing",
    "first_name": "Mike",
    "zip_code": "92101",
    "service_type": "Plumbing",
    "monthly_calls": "100-200"
  }'
```

**Response:**
```json
{
  "success": true,
  "pdf_url": "https://xxxxxxx.public.blob.vercel-storage.com/audits/audit-bluewave-plumbing-abc12345.pdf",
  "company_name": "Bluewave Plumbing",
  "annual_loss": "$84,240",
  "monthly_loss": "$7,020"
}
```

## GHL Integration

### Webhook Setup

In your GHL workflow (triggered by form submission):

1. **Add Webhook action** → POST to `https://your-project.vercel.app/api/generate-audit`
2. **Body (JSON):**
```json
{
  "company_name": "{{contact.company_name}}",
  "first_name": "{{contact.first_name}}",
  "zip_code": "{{contact.postal_code}}",
  "service_type": "{{contact.service_type}}",
  "monthly_calls": "{{contact.estimated_monthly_calls}}"
}
```
3. **Save webhook response** → Map `pdf_url` from response to a custom contact field (e.g., `audit_pdf_url`)
4. **Send email** → Include `{{contact.audit_pdf_url}}` as the link to their personalized report

### Form Field Mapping

| GHL Form Field | Webhook Key | PDF Usage |
|---|---|---|
| First Name | `first_name` | Future personalization |
| Company Name | `company_name` | Hero text, footer |
| Email | — | Not sent to PDF endpoint |
| Phone | — | Not sent to PDF endpoint |
| Zip Code | `zip_code` | Resolved to "City, ST" via API |
| Service Type | `service_type` | Avg job value, copy |
| Estimated Monthly Calls | `monthly_calls` | All revenue calculations |

### Valid Input Values

**service_type:** Plumbing, HVAC, Electrical, Garage Door Repair, Pest Control, Other home services

**monthly_calls:** Under 50, 50-100, 100-200, 200-300, 300+

## Revenue Calculation

```
missed_calls = monthly_calls × 32% miss rate
convertible  = missed_calls × 45% conversion rate
monthly_loss = convertible × avg_job_value
annual_loss  = monthly_loss × 12
```

| Service Type | Avg Job Value |
|---|---|
| Plumbing | $325 |
| HVAC | $400 |
| Electrical | $275 |
| Garage Door Repair | $300 |
| Pest Control | $225 |
| Other home services | $300 |

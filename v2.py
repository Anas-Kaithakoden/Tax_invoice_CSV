import os
import json
import csv
import re
import pdfplumber
from groq import Groq
from dotenv import load_dotenv

# Load API key
load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

PDF_FOLDER = "invoices"
OUTPUT_CSV = "output.csv"

FIELDS = [
    "Invoice_no",
    "Date",
    "Buyer_Name",
    "Buyer_GSTIN",
    "Buyer_State",
    "Taxable_Value",
    "CGST",
    "SGST",
    "IGST",
    "Total_Value"
]

# ---------------------------
# REGEX FALLBACK PATTERNS
# ---------------------------
def extract_gstin_with_regex(text):
    """
    Extract GSTIN using regex patterns.
    GSTIN format: 2 digits + 10 alphanumeric + 1 letter + 1 digit + 1 letter + 1 alphanumeric
    Example: 27AAPFU0939F1ZV
    """
    # Pattern for GSTIN: exactly 15 characters
    # Format: \d{2}[A-Z]{5}\d{4}[A-Z]{1}[A-Z\d]{1}[Z]{1}[A-Z\d]{1}
    # Simplified: 15 alphanumeric characters starting with 2 digits
    
    patterns = [
        # Look for "GSTIN:" or "GSTIN :" or "GST No:" followed by 15 chars
        r'(?:GSTIN|GST\s*No|GST\s*IN|PAN)[\s:]+([0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[A-Z0-9]{1}[Z]{1}[A-Z0-9]{1})',
        # Look for standalone 15-char GSTIN (must start with 2 digits)
        r'\b([0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[A-Z0-9]{1}[Z]{1}[A-Z0-9]{1})\b',
        # More lenient: any 15 alphanumeric starting with 2 digits
        r'\b([0-9]{2}[A-Z0-9]{13})\b'
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            # Return first valid-looking GSTIN
            for match in matches:
                gstin = match.upper()
                # Basic validation: starts with 2 digits, length 15
                if len(gstin) == 15 and gstin[:2].isdigit():
                    return gstin
    
    return None

def extract_invoice_number_with_regex(text):
    """Extract invoice number using common patterns"""
    patterns = [
        r'(?:Invoice\s*(?:No|Number|#)[\s:]+)([A-Z0-9\-/]+)',
        r'(?:Bill\s*(?:No|Number)[\s:]+)([A-Z0-9\-/]+)',
        r'(?:Tax\s*Invoice[\s:]+)([A-Z0-9\-/]+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    
    return None

def extract_date_with_regex(text):
    """Extract date using common patterns"""
    patterns = [
        r'(?:Date[\s:]+)(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})',
        r'(?:Invoice\s*Date[\s:]+)(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})',
        r'\b(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})\b',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    
    return None

def extract_buyer_gstin_with_regex(text):
    """
    Extract buyer's GSTIN specifically from 'Bill To' or 'Buyer' section.
    Returns the GSTIN found in buyer section, not seller section.
    """
    # Try to isolate the buyer section
    buyer_section_patterns = [
        r'(?:Bill\s*To|Buyer|Consignee|Ship\s*To)[\s\S]{0,500}?([0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[A-Z0-9]{1}[Z]{1}[A-Z0-9]{1})',
    ]
    
    for pattern in buyer_section_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).upper()
    
    # If no buyer section found, get all GSTINs and return the second one (first is usually seller)
    all_gstins = re.findall(r'\b([0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[A-Z0-9]{1}[Z]{1}[A-Z0-9]{1})\b', text)
    
    if len(all_gstins) >= 2:
        return all_gstins[1].upper()  # Second GSTIN is usually buyer
    elif len(all_gstins) == 1:
        return all_gstins[0].upper()  # Only one GSTIN found
    
    return None

# ---------------------------
# PDF TEXT EXTRACTION
# ---------------------------
def extract_text_from_pdf(pdf_path):
    """Extract text with better table handling"""
    full_text = []
    
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            full_text.append(f"\n--- PAGE {i} ---\n")
            
            # Extract regular text
            page_text = page.extract_text(
                x_tolerance=2,
                y_tolerance=3,
                layout=True
            )
            if page_text:
                full_text.append(page_text)
            
            # Also extract tables explicitly
            tables = page.extract_tables()
            if tables:
                full_text.append("\n[TABLES ON THIS PAGE]")
                for t_idx, table in enumerate(tables, start=1):
                    full_text.append(f"\nTable {t_idx}:")
                    for row in table:
                        cleaned_row = [str(cell).strip() if cell else "" for cell in row]
                        full_text.append(" | ".join(cleaned_row))
    
    return "\n".join(full_text)

# ---------------------------
# SAFE JSON PARSER
# ---------------------------
def safe_json_extract(raw):
    """Extract JSON from LLM response"""
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        return None
    
    try:
        return json.loads(match.group())
    except json.JSONDecodeError:
        return None

# ---------------------------
# TAX VALIDATION & FIXING
# ---------------------------
def validate_and_fix_taxes(data):
    """Validate tax fields and fix common issues"""
    # Handle string "null" values
    for key in ["CGST", "SGST", "IGST"]:
        if isinstance(data.get(key), str):
            if data[key].lower() in ["null", "none", "n/a", ""]:
                data[key] = None
            else:
                # Remove currency symbols and clean
                data[key] = re.sub(r'[₹$,\s]', '', data[key])
    
    # Get numeric values
    cgst = data.get("CGST")
    sgst = data.get("SGST")
    igst = data.get("IGST")
    
    # Convert to float for checking
    def is_valid_amount(val):
        if val is None:
            return False
        try:
            return float(val) > 0
        except:
            return False
    
    has_cgst_sgst = is_valid_amount(cgst) or is_valid_amount(sgst)
    has_igst = is_valid_amount(igst)
    
    # Apply mutual exclusivity rule
    if has_cgst_sgst and has_igst:
        cgst_sgst_total = float(cgst or 0) + float(sgst or 0)
        igst_val = float(igst or 0)
        
        if cgst_sgst_total > igst_val:
            data["IGST"] = None
        else:
            data["CGST"] = None
            data["SGST"] = None
    
    return data

# ---------------------------
# ENHANCED LLM EXTRACTION WITH FALLBACK
# ---------------------------
def extract_invoice_data_llama(text):
    """Extract invoice data with improved prompting and regex fallback"""
    
    prompt = f"""You are an expert GST invoice data extraction system. 

CRITICAL INSTRUCTIONS:
1. Tax amounts are MONETARY VALUES (e.g., "1800", "₹450.50"), NOT percentages
2. Look for tax amounts in tables and summary sections
3. TAX RULES:
   - Intra-state: Use CGST + SGST (IGST must be null)
   - Inter-state: Use IGST (CGST and SGST must be null)
4. Buyer details come from "Bill To" or "Buyer" section (NOT seller section)
5. Buyer GSTIN is the GSTIN in the buyer section (usually the second GSTIN in the invoice)
6. GSTIN is exactly 15 alphanumeric characters

Return ONLY valid JSON:

{{
  "Invoice_no": "invoice number",
  "Date": "invoice date",
  "Buyer_Name": "buyer company name",
  "Buyer_GSTIN": "15-char buyer GSTIN (from Bill To section)",
  "Buyer_State": "state name",
  "Taxable_Value": "taxable amount",
  "CGST": null,
  "SGST": null,
  "IGST": null,
  "Total_Value": "total invoice amount"
}}

Invoice Text:
{text}

Return ONLY the JSON object."""

    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        
        raw = response.choices[0].message.content.strip()
        data = safe_json_extract(raw)
        
        if data:
            # Validate and fix tax fields
            data = validate_and_fix_taxes(data)
            
            # FALLBACK: Use regex if LLM missed critical fields
            if not data.get("Buyer_GSTIN") or len(str(data.get("Buyer_GSTIN", ""))) != 15:
                regex_gstin = extract_buyer_gstin_with_regex(text)
                if regex_gstin:
                    print(f"   🔧 Regex fallback: Found GSTIN = {regex_gstin}")
                    data["Buyer_GSTIN"] = regex_gstin
            
            if not data.get("Invoice_no"):
                regex_invoice = extract_invoice_number_with_regex(text)
                if regex_invoice:
                    print(f"   🔧 Regex fallback: Found Invoice# = {regex_invoice}")
                    data["Invoice_no"] = regex_invoice
            
            if not data.get("Date"):
                regex_date = extract_date_with_regex(text)
                if regex_date:
                    print(f"   🔧 Regex fallback: Found Date = {regex_date}")
                    data["Date"] = regex_date
        
        return data
        
    except Exception as e:
        print(f"❌ LLM Error: {e}")
        return None

# ---------------------------
# MAIN LOOP
# ---------------------------
def main():
    rows = []
    
    if not os.path.exists(PDF_FOLDER):
        print(f"❌ Folder '{PDF_FOLDER}' not found!")
        return
    
    pdf_files = [f for f in os.listdir(PDF_FOLDER) if f.lower().endswith(".pdf")]
    
    if not pdf_files:
        print(f"❌ No PDF files found in '{PDF_FOLDER}'")
        return
    
    print(f"\n🔍 Found {len(pdf_files)} PDF file(s)\n")
    
    for filename in pdf_files:
        pdf_path = os.path.join(PDF_FOLDER, filename)
        
        print("\n" + "=" * 80)
        print(f"📄 Processing: {filename}")
        print("=" * 80)
        
        # Extract text
        text = extract_text_from_pdf(pdf_path)
        
        # Truncate if too long
        if len(text) > 15000:
            print(f"⚠️  Text truncated ({len(text)} → 15000 chars)")
            text = text[:15000]
        
        # Extract data
        data = extract_invoice_data_llama(text)
        
        if data:
            data["File_Name"] = filename
            rows.append(data)
            
            print("✅ Extracted:")
            for k in FIELDS:
                val = data.get(k)
                print(f"   {k:20s}: {val}")
            
            # Tax validation summary
            cgst = data.get("CGST")
            sgst = data.get("SGST")
            igst = data.get("IGST")
            
            if cgst or sgst:
                print(f"\n   📊 Tax Type: CGST/SGST (Intra-state)")
            elif igst:
                print(f"\n   📊 Tax Type: IGST (Inter-state)")
            else:
                print(f"\n   ⚠️  No tax values extracted")
        else:
            print("❌ Extraction failed - check PDF format or API response")
    
    # Save results
    if rows:
        with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f, 
                fieldnames=["File_Name"] + FIELDS
            )
            writer.writeheader()
            writer.writerows(rows)
        
        print(f"\n{'='*80}")
        print(f"✅ SUCCESS: Extracted {len(rows)} invoice(s)")
        print(f"📁 Data saved to: {OUTPUT_CSV}")
        print(f"{'='*80}\n")
    else:
        print("\n⚠️  No data extracted from any PDF\n")

if __name__ == "__main__":
    main()
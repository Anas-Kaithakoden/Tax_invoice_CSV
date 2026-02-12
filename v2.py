import os
import json
import csv
import re
import pdfplumber
from groq import Groq
from dotenv import load_dotenv
from PIL import Image
import pytesseract
from pdf2image import convert_from_path

# Load API key
load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# Model configuration - you can change this to use different models
# Available Groq models: "llama-3.1-8b-instant", "llama-3.1-70b-versatile", "mixtral-8x7b-32768"
AI_MODEL = "llama-3.3-70b-versatile"  # More powerful model for better reasoning

PDF_FOLDER = "invoices"
OUTPUT_CSV = "output.csv"
DEBUG_MODE = True  # Set to True to save extracted text for debugging

# Supported image formats
IMAGE_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.tif')

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
# OCR FUNCTIONS
# ---------------------------
def extract_text_from_image(image_path):
    """
    Extract text from image using Tesseract OCR.
    
    Args:
        image_path: Path to image file
    
    Returns:
        Extracted text string
    """
    try:
        print(f"   🔍 Running OCR on image...")
        
        # Open image
        img = Image.open(image_path)
        
        # Optional: Preprocess image for better OCR
        # Convert to grayscale
        img = img.convert('L')
        
        # Apply OCR with custom config for better accuracy
        custom_config = r'--oem 3 --psm 6'
        text = pytesseract.image_to_string(img, config=custom_config)
        
        print(f"   ✅ OCR completed: {len(text)} characters extracted")
        return text
        
    except Exception as e:
        print(f"   ❌ OCR Error: {e}")
        return ""

def is_scanned_pdf(pdf_path):
    """
    Check if PDF is scanned (image-based) or text-based.
    
    Args:
        pdf_path: Path to PDF file
    
    Returns:
        True if scanned/image-based, False if text-based
    """
    try:
        with pdfplumber.open(pdf_path) as pdf:
            # Check first page
            first_page = pdf.pages[0]
            text = first_page.extract_text()
            
            # If very little text extracted, it's likely scanned
            if not text or len(text.strip()) < 50:
                return True
            
            # Check if page has images (scanned PDFs are essentially images)
            images = first_page.images
            if len(images) > 0 and len(text.strip()) < 200:
                return True
            
        return False
        
    except Exception as e:
        print(f"   ⚠️  Error checking PDF type: {e}")
        return False

def extract_text_from_scanned_pdf(pdf_path):
    """
    Extract text from scanned PDF using OCR.
    
    Args:
        pdf_path: Path to scanned PDF file
    
    Returns:
        Extracted text string
    """
    try:
        print(f"   🔍 Converting PDF to images for OCR...")
        
        # Convert PDF pages to images
        images = convert_from_path(pdf_path, dpi=300)
        
        print(f"   📄 Processing {len(images)} page(s)...")
        
        full_text = []
        
        for i, image in enumerate(images, start=1):
            print(f"   📖 OCR on page {i}/{len(images)}...")
            
            full_text.append(f"\n--- PAGE {i} ---\n")
            
            # Convert to grayscale for better OCR
            image = image.convert('L')
            
            # Extract text with Tesseract
            custom_config = r'--oem 3 --psm 6'
            page_text = pytesseract.image_to_string(image, config=custom_config)
            
            full_text.append(page_text)
        
        result = "\n".join(full_text)
        print(f"   ✅ OCR completed: {len(result)} characters extracted")
        
        return result
        
    except Exception as e:
        print(f"   ❌ OCR Error: {e}")
        return ""

# ---------------------------
# REGEX FALLBACK PATTERNS
# ---------------------------
def extract_gstin_with_regex(text):
    """
    Extract GSTIN using regex patterns.
    GSTIN format: 2 digits + 10 alphanumeric + 1 letter + 1 digit + 1 letter + 1 alphanumeric
    Example: 27AAPFU0939F1ZV
    """
    patterns = [
        r'(?:GSTIN|GST\s*No|GST\s*IN|PAN)[\s:]+([0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[A-Z0-9]{1}[Z]{1}[A-Z0-9]{1})',
        r'\b([0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[A-Z0-9]{1}[Z]{1}[A-Z0-9]{1})\b',
        r'\b([0-9]{2}[A-Z0-9]{13})\b'
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            for match in matches:
                gstin = match.upper()
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
    buyer_section_patterns = [
        r'(?:Bill\s*To|Buyer|Consignee|Ship\s*To)[\s\S]{0,500}?([0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[A-Z0-9]{1}[Z]{1}[A-Z0-9]{1})',
    ]
    
    for pattern in buyer_section_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).upper()
    
    all_gstins = re.findall(r'\b([0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[A-Z0-9]{1}[Z]{1}[A-Z0-9]{1})\b', text)
    
    if len(all_gstins) >= 2:
        return all_gstins[1].upper()
    elif len(all_gstins) == 1:
        return all_gstins[0].upper()
    
    return None

# ---------------------------
# PDF TEXT EXTRACTION
# ---------------------------
def extract_text_from_pdf(pdf_path):
    """
    Extract text from PDF. Automatically detects if PDF is scanned and uses OCR.
    
    Args:
        pdf_path: Path to PDF file
    
    Returns:
        Extracted text string
    """
    # Check if PDF is scanned
    if is_scanned_pdf(pdf_path):
        print(f"   📸 Detected scanned PDF - using OCR")
        return extract_text_from_scanned_pdf(pdf_path)
    
    # Regular text extraction for text-based PDFs
    print(f"   📝 Detected text-based PDF - using pdfplumber")
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
    for key in ["CGST", "SGST", "IGST"]:
        if isinstance(data.get(key), str):
            if data[key].lower() in ["null", "none", "n/a", ""]:
                data[key] = None
            else:
                data[key] = re.sub(r'[₹$,\s]', '', data[key])
    
    cgst = data.get("CGST")
    sgst = data.get("SGST")
    igst = data.get("IGST")
    
    def is_valid_amount(val):
        if val is None:
            return False
        try:
            return float(val) > 0
        except:
            return False
    
    has_cgst_sgst = is_valid_amount(cgst) or is_valid_amount(sgst)
    has_igst = is_valid_amount(igst)
    
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
    
    prompt = f"""You are an expert GST invoice data extraction system. Analyze the invoice carefully and extract accurate data.

STEP-BY-STEP ANALYSIS REQUIRED:

1. **IDENTIFY SECTIONS**: First locate these sections in the invoice:
   - Header: Invoice number, date
   - Seller/Supplier section (top, has "From" or supplier details)
   - Buyer section (has "Bill To", "Ship To", "Buyer", "Consignee")
   - Items/Products table (line items with rates and quantities)
   - Tax Summary section (bottom, shows tax breakdown)
   - Grand Total section (final amount to pay)

2. **EXTRACT BUYER DETAILS** (NOT seller):
   - Buyer_Name: Company name in "Bill To" or "Buyer" section
   - Buyer_GSTIN: 15-digit GSTIN in buyer section (NOT the seller's GSTIN)
   - Buyer_State: State mentioned in buyer address

3. **EXTRACT FINANCIAL VALUES** (be careful with totals):
   - Taxable_Value: Sum of all taxable amounts BEFORE tax (look for "Taxable Amount", "Taxable Value", or sum of item amounts)
   - CGST: Central GST amount in RUPEES (₹), NOT percentage (look in tax summary)
   - SGST: State GST amount in RUPEES (₹), NOT percentage (look in tax summary)
   - IGST: Integrated GST amount in RUPEES (₹), NOT percentage (look in tax summary)
   - Total_Value: Final grand total AFTER all taxes (look for "Total", "Grand Total", "Amount Payable")

4. **TAX LOGIC** (apply strictly):
   - If invoice has CGST AND SGST → set IGST to null (intra-state transaction)
   - If invoice has IGST → set both CGST and SGST to null (inter-state transaction)
   - Tax amounts are ALWAYS in rupees/currency, NEVER percentages

5. **COMMON MISTAKES TO AVOID**:
   - Don't confuse tax rate (%) with tax amount (₹)
   - Don't use seller's GSTIN as buyer's GSTIN
   - Don't use item-level totals as invoice total
   - Taxable Value ≠ Total Value (taxable is before tax, total is after tax)
   - Make sure Taxable_Value + taxes ≈ Total_Value

Return ONLY valid JSON (no explanation):

{{
  "Invoice_no": "invoice number",
  "Date": "DD-MMM-YYYY format",
  "Buyer_Name": "buyer company name from Bill To section",
  "Buyer_GSTIN": "15-char GSTIN from buyer section only",
  "Buyer_State": "state name",
  "Taxable_Value": "total taxable amount before tax",
  "CGST": null,
  "SGST": null,
  "IGST": null,
  "Total_Value": "final grand total after all taxes"
}}

Invoice Text:
{text}

Think step-by-step, then return ONLY the JSON object."""

    try:
        response = client.chat.completions.create(
            model=AI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        
        raw = response.choices[0].message.content.strip()
        
        # Debug: Show AI's raw response
        print(f"\n   🤖 AI Response Preview:")
        preview = raw[:300] + "..." if len(raw) > 300 else raw
        print(f"   {preview}\n")
        
        data = safe_json_extract(raw)
        
        if data:
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
    
    # Get all supported files (PDFs and images)
    all_files = os.listdir(PDF_FOLDER)
    supported_files = [
        f for f in all_files 
        if f.lower().endswith('.pdf') or f.lower().endswith(IMAGE_EXTENSIONS)
    ]
    
    if not supported_files:
        print(f"❌ No supported files found in '{PDF_FOLDER}'")
        print(f"   Supported: PDF, PNG, JPG, JPEG, BMP, TIFF")
        return
    
    print(f"\n🔍 Found {len(supported_files)} supported file(s)\n")
    
    for filename in supported_files:
        file_path = os.path.join(PDF_FOLDER, filename)
        
        print("\n" + "=" * 80)
        print(f"📄 Processing: {filename}")
        print("=" * 80)
        
        # Determine file type and extract text accordingly
        if filename.lower().endswith('.pdf'):
            text = extract_text_from_pdf(file_path)
        elif filename.lower().endswith(IMAGE_EXTENSIONS):
            text = extract_text_from_image(file_path)
        else:
            print(f"⚠️  Unsupported file type, skipping...")
            continue
        
        if not text or len(text.strip()) < 20:
            print(f"⚠️  Very little text extracted - file may be blank or unreadable")
            continue
        
        # Debug: Save extracted text
        if DEBUG_MODE:
            debug_file = f"debug_{filename}.txt"
            with open(debug_file, "w", encoding="utf-8") as f:
                f.write(text)
            print(f"   💾 Debug: Extracted text saved to {debug_file}")
        
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
            
            # Validation check
            print("\n   🔍 Validation Check:")
            taxable = data.get("Taxable_Value")
            cgst = data.get("CGST")
            sgst = data.get("SGST")
            igst = data.get("IGST")
            total = data.get("Total_Value")
            
            # Convert to float for checking
            def to_float(val):
                if val is None:
                    return 0.0
                try:
                    # Remove common currency symbols and commas
                    cleaned = str(val).replace('₹', '').replace(',', '').replace('$', '').strip()
                    return float(cleaned)
                except:
                    return 0.0
            
            taxable_f = to_float(taxable)
            cgst_f = to_float(cgst)
            sgst_f = to_float(sgst)
            igst_f = to_float(igst)
            total_f = to_float(total)
            
            # Calculate expected total
            expected_total = taxable_f + cgst_f + sgst_f + igst_f
            
            print(f"   Taxable: ₹{taxable_f:,.2f}")
            print(f"   + CGST: ₹{cgst_f:,.2f}")
            print(f"   + SGST: ₹{sgst_f:,.2f}")
            print(f"   + IGST: ₹{igst_f:,.2f}")
            print(f"   = Expected: ₹{expected_total:,.2f}")
            print(f"   Actual Total: ₹{total_f:,.2f}")
            
            # Check if values make sense
            diff = abs(expected_total - total_f)
            if diff > 1.0:  # Allow ₹1 rounding difference
                print(f"   ⚠️  WARNING: Math doesn't add up! Difference: ₹{diff:,.2f}")
                print(f"   Please verify the extracted values manually.")
            else:
                print(f"   ✅ Math checks out! (Diff: ₹{diff:.2f})")
            
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
            print("❌ Extraction failed - check file format or API response")
    
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
        print("\n⚠️  No data extracted from any file\n")

if __name__ == "__main__":
    main()
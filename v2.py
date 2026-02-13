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

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

AI_MODEL = "llama-3.3-70b-versatile"
PDF_FOLDER = "invoices"
OUTPUT_CSV = "output.csv"
DEBUG_MODE = True

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
    try:
        print(f"   🔍 Running OCR on image...")
        img = Image.open(image_path).convert('L')
        custom_config = r'--oem 3 --psm 6'
        text = pytesseract.image_to_string(img, config=custom_config)
        print(f"   ✅ OCR completed: {len(text)} characters extracted")
        return text
    except Exception as e:
        print(f"   ❌ OCR Error: {e}")
        return ""

def is_scanned_pdf(pdf_path):
    try:
        with pdfplumber.open(pdf_path) as pdf:
            first_page = pdf.pages[0]
            text = first_page.extract_text()
            if not text or len(text.strip()) < 50:
                return True
            images = first_page.images
            if len(images) > 0 and len(text.strip()) < 200:
                return True
        return False
    except Exception as e:
        print(f"   ⚠️  Error checking PDF type: {e}")
        return False

def extract_text_from_scanned_pdf(pdf_path):
    try:
        print(f"   🔍 Converting PDF to images for OCR...")
        images = convert_from_path(pdf_path, dpi=300)
        print(f"   📄 Processing {len(images)} page(s)...")
        
        full_text = []
        for i, image in enumerate(images, start=1):
            print(f"   📖 OCR on page {i}/{len(images)}...")
            full_text.append(f"\n--- PAGE {i} ---\n")
            image = image.convert('L')
            custom_config = r'--oem 3 --psm 6'
            page_text = pytesseract.image_to_string(image, config=custom_config)
            full_text.append(page_text)
        
        result = "\n".join(full_text)
        print(f"   ✅ OCR completed: {len(result)} characters extracted")
        return result
    except Exception as e:
        print(f"   ❌ OCR Error: {e}")
        return ""

def extract_text_from_pdf(pdf_path):
    if is_scanned_pdf(pdf_path):
        print(f"   📸 Detected scanned PDF - using OCR")
        return extract_text_from_scanned_pdf(pdf_path)
    
    print(f"   📝 Detected text-based PDF - using pdfplumber")
    full_text = []
    
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            full_text.append(f"\n--- PAGE {i} ---\n")
            page_text = page.extract_text(x_tolerance=2, y_tolerance=3, layout=True)
            if page_text:
                full_text.append(page_text)
            
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
# AI EXTRACTION (SIMPLE)
# ---------------------------
def extract_invoice_data_ai(text):
    """
    Send everything to AI and let it figure it out.
    No regex, no complex rules, just AI doing its thing.
    """
    
    prompt = f"""You are a GST invoice data extraction expert. Extract fields from this OCR text that contains errors.

CRITICAL: OCR ERRORS ARE PRESENT!
- Lines may be garbled (e.g., "rata) 208 00] sao] 288920]" instead of "Total 2NOS 3,805.00 684.90 4,489.90")
- Words may be misspelled (e.g., "Toas" instead of "Total Tax")
- Numbers may have extra digits (e.g., "24,490.00" instead of "4,490.00")

CURRENCY HANDLING:
- Keep currency symbols/codes in the values (₹, $, RS, SAR, USD, etc.)
- Format: "₹3,805.00" or "$1,234.56" or "SAR 500.00"
- If no currency symbol visible, use numeric value only

TAX TYPES (VERY IMPORTANT):
- INTER-STATE invoices have ONLY "IGST" or "Total Tax" → extract as IGST, set CGST and SGST to null
- INTRA-STATE invoices have "CGST" AND "SGST" separately → extract both, set IGST to null
- NEVER calculate IGST from CGST+SGST or vice versa
- NEVER combine tax values - extract exactly as shown in the invoice
- If invoice shows "CGST: 342.45" and "SGST: 342.45", keep them separate, don't make IGST = 684.90

HOW TO EXTRACT CORRECTLY:

1. FIND THE LINE ITEMS TABLE (lines 18-21):
   - Line 18: Item 1 with amounts
   - Line 20: Item 2 with amounts  
   - Line 21: TOTALS ROW (may be garbled like "rata) 208 00] sao] 288920]")

2. PARSE THE TOTALS ROW (line 21):
   Pattern: [quantity] [taxable_total] [tax_total] [grand_total]
   
   Look for 3-4 numbers in sequence. The LAST 3 numbers are:
   - Third-last number = Taxable Value (before tax)
   - Second-last number = Tax amount (IGST or CGST+SGST combined)
   - Last number = Grand Total (after tax)

3. VERIFY WITH "TOTAL IN WORDS":
   Find the line that says "Total in words : FOUR THOUSAND FOUR HUNDRED AND NINETY RUPEES"
   This tells you the GRAND TOTAL = 4,490 (not 24,490 or 20,800)
   Convert words to number and use this as Total_Value

4. IDENTIFY TAX TYPE:
   - Look for "CGST" keyword → if found, this is INTRA-STATE (extract CGST and SGST separately)
   - Look for "IGST" or only "Total Tax" → if found, this is INTER-STATE (extract as IGST only)
   - Check the line items table headers or tax summary section

5. EXTRACT TAX VALUES:
   - If INTRA-STATE: Find "CGST Amount" and "SGST Amount" (usually equal amounts)
   - If INTER-STATE: Use the total tax amount from totals row as IGST
   - Do NOT calculate one from the other

6. CALCULATE TAXABLE VALUE:
   Taxable_Value = Total_Value - (IGST or CGST+SGST)
   Example: 4,490 - 684.90 = 3,805.10

7. DOUBLE-CHECK:
   Taxable_Value + tax amounts should equal Total_Value
   Example: 3,805 + 684.90 ≈ 4,490 ✓

FIELDS TO EXTRACT:
- Invoice_no: From line with "Invoice No."
- Date: From line with "Invoice Date" (DD-MMM-YYYY format)
- Buyer_Name: Company after "M/S" (NOT the seller at top)
- Buyer_GSTIN: 15-char GSTIN after "M/S" line (second GSTIN, NOT first)
- Buyer_State: From "Place of Supply" or buyer address
- Taxable_Value: With currency symbol if present (e.g., "₹3,805.00")
- CGST: With currency if present, or null if inter-state
- SGST: With currency if present, or null if inter-state
- IGST: With currency if present, or null if intra-state
- Total_Value: With currency symbol (e.g., "₹4,490.00")

Return ONLY JSON (no markdown):

{{
  "Invoice_no": "value",
  "Date": "value",
  "Buyer_Name": "value",
  "Buyer_GSTIN": "value",
  "Buyer_State": "value",
  "Taxable_Value": "value with currency",
  "CGST": null,
  "SGST": null,
  "IGST": "value with currency",
  "Total_Value": "value with currency"
}}

INVOICE TEXT:
{text}"""

    try:
        print(f"\n   🤖 Sending to AI ({AI_MODEL})...")
        
        response = client.chat.completions.create(
            model=AI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        
        raw = response.choices[0].message.content.strip()
        
        # Show preview
        print(f"\n   📝 AI Response Preview:")
        preview = raw[:400] + "..." if len(raw) > 400 else raw
        print(f"   {preview}\n")
        
        # Extract JSON
        raw = re.sub(r'```json\s*', '', raw)
        raw = re.sub(r'```\s*', '', raw)
        
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            data = json.loads(match.group())
            
            # Keep currency symbols in the data - don't clean them
            # Just ensure numeric fields are present
            
            # Apply tax logic: IGST XOR (CGST+SGST) - never combine them
            cgst = data.get("CGST")
            sgst = data.get("SGST")
            igst = data.get("IGST")
            
            # Convert to float for comparison (strip currency symbols)
            def to_float(val):
                if val is None:
                    return 0.0
                try:
                    cleaned = re.sub(r'[₹$,\s]', '', str(val))
                    cleaned = re.sub(r'(RS|SAR|USD|AED|INR|EUR|GBP)', '', cleaned, flags=re.IGNORECASE)
                    return float(cleaned.strip())
                except:
                    return 0.0
            
            cgst_f = to_float(cgst)
            sgst_f = to_float(sgst)
            igst_f = to_float(igst)
            
            # If AI mistakenly extracted both types, fix it based on which is larger
            # But NEVER calculate IGST from CGST+SGST or vice versa
            if igst_f > 0 and (cgst_f > 0 or sgst_f > 0):
                total_cgst_sgst = cgst_f + sgst_f
                if igst_f > total_cgst_sgst:
                    print(f"   ⚠️  AI extracted both IGST and CGST/SGST - keeping IGST, removing others")
                    data["CGST"] = None
                    data["SGST"] = None
                else:
                    print(f"   ⚠️  AI extracted both IGST and CGST/SGST - keeping CGST/SGST, removing IGST")
                    data["IGST"] = None
            
            return data
        else:
            print(f"   ❌ Could not find JSON in AI response")
            return None
            
    except Exception as e:
        print(f"   ❌ AI Error: {e}")
        return None

# ---------------------------
# MAIN LOOP
# ---------------------------
def main():
    rows = []
    
    if not os.path.exists(PDF_FOLDER):
        print(f"❌ Folder '{PDF_FOLDER}' not found!")
        return
    
    all_files = os.listdir(PDF_FOLDER)
    supported_files = [
        f for f in all_files 
        if f.lower().endswith('.pdf') or f.lower().endswith(IMAGE_EXTENSIONS)
    ]
    
    if not supported_files:
        print(f"❌ No supported files found in '{PDF_FOLDER}'")
        return
    
    print(f"\n🔍 Found {len(supported_files)} file(s)\n")
    
    for filename in supported_files:
        file_path = os.path.join(PDF_FOLDER, filename)
        
        print("\n" + "=" * 80)
        print(f"📄 Processing: {filename}")
        print("=" * 80)
        
        # Extract text
        if filename.lower().endswith('.pdf'):
            text = extract_text_from_pdf(file_path)
        elif filename.lower().endswith(IMAGE_EXTENSIONS):
            text = extract_text_from_image(file_path)
        else:
            continue
        
        if not text or len(text.strip()) < 20:
            print(f"⚠️  Very little text extracted")
            continue
        
        # Let AI handle everything
        data = extract_invoice_data_ai(text)
        
        if data:
            data["File_Name"] = filename
            rows.append(data)
            
            print("\n" + "=" * 80)
            print("✅ EXTRACTED DATA:")
            print("=" * 80)
            for k in FIELDS:
                val = data.get(k)
                print(f"   {k:20s}: {val}")
            
            # Validation
            print("\n" + "=" * 80)
            print("🔍 VALIDATION:")
            print("=" * 80)
            
            # Extract numeric values for validation (remove currency symbols temporarily)
            def extract_number(val):
                if val is None:
                    return 0.0
                try:
                    # Remove currency symbols and commas for calculation
                    cleaned = re.sub(r'[₹$,\s]', '', str(val))
                    # Remove currency codes like RS, SAR, USD, AED
                    cleaned = re.sub(r'(RS|SAR|USD|AED|INR|EUR|GBP)', '', cleaned, flags=re.IGNORECASE)
                    return float(cleaned.strip())
                except:
                    return 0.0
            
            taxable = extract_number(data.get("Taxable_Value"))
            cgst = extract_number(data.get("CGST"))
            sgst = extract_number(data.get("SGST"))
            igst = extract_number(data.get("IGST"))
            total = extract_number(data.get("Total_Value"))
            
            expected = taxable + cgst + sgst + igst
            
            print(f"   Taxable Value: {data.get('Taxable_Value')}")
            print(f"   + CGST:        {data.get('CGST')}")
            print(f"   + SGST:        {data.get('SGST')}")
            print(f"   + IGST:        {data.get('IGST')}")
            print(f"   {'─' * 40}")
            print(f"   = Expected:    {expected:,.2f}")
            print(f"   Actual Total:  {data.get('Total_Value')}")
            
            diff = abs(expected - total)
            if diff < 1.0:
                print(f"\n   ✅ PASS: Math checks out! (diff: {diff:.2f})")
            else:
                print(f"\n   ⚠️  WARNING: Difference of {diff:,.2f}")
                print(f"      This may be due to OCR errors or rounding")
            
            # Tax type
            if igst > 0:
                print(f"\n   📊 Tax Type: IGST (Inter-state)")
            elif cgst > 0 or sgst > 0:
                print(f"\n   📊 Tax Type: CGST/SGST (Intra-state)")
            
            print("=" * 80)
        else:
            print("\n❌ Extraction failed - check AI response above")
    
    # Save results
    if rows:
        with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["File_Name"] + FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        
        print(f"\n{'='*80}")
        print(f"✅ SUCCESS: Extracted {len(rows)} invoice(s)")
        print(f"📁 Data saved to: {OUTPUT_CSV}")
        print(f"{'='*80}\n")
    else:
        print("\n⚠️  No data extracted from any files\n")

if __name__ == "__main__":
    main()
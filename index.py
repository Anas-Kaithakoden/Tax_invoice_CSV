import pdfplumber

# --------------------------------------------------
# LABEL CONFIGURATION
# --------------------------------------------------
# Mapping of internal field names -> labels as they appear in the PDF

LABELS = {
    "Invoice_No": "Invoice No",
    "Bill_From": "Bill From",
    "Bill_To" : "Bill To",
    "Invoice_Date" :"Invoice Date",
    "CGST":"CGST",
    "SGST":"SGST",
    "Total" :"Total"

}

# * Used to prevent accidentally extracting one label as the value of another
ALL_LABELS = {v.lower() for v in LABELS.values()} # Lowercase version of all labels



COLUMN_TABLE_FIELDS = {
    "CGST",
    "SGST",
    "Total"
}

# --------------------------------------------------
# HELPER FUNCTIONS
# --------------------------------------------------
def clean(text):
    if not text:
        return ""
    return " ".join(text.split())

# POST-PROCESSING / NORMALIZATION
def normalize_bill_data(value, mode):
    if not value:
        return value

    if mode == "bill":
        return " ".join(value.split()[:2])
    elif mode =="total":
        if "₹" not in value and any(c.isdigit() for c in value):
                return f"₹ {value}"
        return value
    
    return value

# --------------------------------------------------
# ! Text-based (non-scanned) PDF ---------------------------------------------------
# --------------------------------------------------
def text_based_pdf(file):
    with pdfplumber.open(file) as pdf:
            page = pdf.pages[0]
            words = page.extract_words()

            for key, label in LABELS.items():
                value = extract_value(page, words, label)
                if label in {"Bill From", "Bill To"}:
                    value = normalize_bill_data(value, "bill")
                if label in {"Total"}:
                    value = normalize_bill_data(value, "total")

                print(f"{key}: {value}")

# --------------------------------------------------
# LABEL DETECTION
# --------------------------------------------------
def find_label(words, label_text):
    label_words = label_text.split()

    for i in range(len(words) - len(label_words)):
        if all(words[i + j]["text"] == label_words[j]
               for j in range(len(label_words))):
            return words[i:i + len(label_words)]

    return None


# --------------------------------------------------
# EXTRACTION STRATEGIES
# --------------------------------------------------
def extract_right_of_label(page, label_words, max_width=200):
    last = label_words[-1]

    x0 = last["x1"] + 5
    top = last["top"]

    x1 = min(x0 + max_width, page.width)
    bottom = last["bottom"]

    box = (x0, top, x1, bottom)
    return clean(page.crop(box).extract_text())

def extract_below_label(page, label_words, height=40):
    first = label_words[0]

    x0 = first["x0"]
    top = first["bottom"] + 5

    x1 = min(x0 + 200, page.width)
    bottom = min(top + height, page.height)

    box = (x0, top, x1, bottom)
    return clean(page.crop(box).extract_text())

def extract_same_column_below_words(words, label_words, y_gap=5, max_height=60):
    """
    Extract words directly below the label,
    whose horizontal CENTER aligns with the label column.
    """

    col_left = min(w["x0"] for w in label_words)
    col_right = max(w["x1"] for w in label_words)
    label_bottom = max(w["bottom"] for w in label_words)

    candidates = []

    for w in words:
        # Must be below the label
        if not (label_bottom + y_gap < w["top"] < label_bottom + max_height):
            continue

        # Word center must align with column center
        word_center = (w["x0"] + w["x1"]) / 2

        if col_left - 10 <= word_center <= col_right + 10:
            candidates.append(w)

    # Sort left → right (₹ first, then number)
    candidates.sort(key=lambda w: w["x0"])

    return clean(" ".join(w["text"] for w in candidates))


# --------------------------------------------------
# FIELD EXTRACTION ORCHESTRATOR
# --------------------------------------------------
def extract_value(page, words, label_text):
    label_words = find_label(words, label_text)
    if not label_words:
        return ""

    # 1️⃣ Column-table logic (CGST / SGST / Total)
    if label_text in COLUMN_TABLE_FIELDS:
        value = extract_same_column_below_words(words, label_words)
        if value:
            return value

    # 2️⃣ Right-of-label logic
    right = extract_right_of_label(page, label_words)
    if right:
        right_lower = right.lower()
        if right_lower not in ALL_LABELS and any(c.isdigit() for c in right):
            return right

    # 3️⃣ Below-label logic
    below = extract_below_label(page, label_words)
    if below:
        return below

    return ""

# ! End of Text-based (non-scanned) PDF


# --------------------------------------------------
# * Find Data Type(PDF)
# --------------------------------------------------
def detect_pdf_type(pdf_path):
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text and text.strip():
                return "text_pdf"   # non-scanned
    return "scanned_pdf"            # image-only




# ---------------- MAIN ----------------

def main():
    file = "invoice1.pdf"
    pdf_type = detect_pdf_type(file)
    if pdf_type == "text_pdf":
        print("Text-based PDF → direct extraction")
        text_based_pdf(file)
    else:
        print("Scanned PDF → OCR required")

    
    

if __name__ == "__main__":
    main()
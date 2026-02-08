# Invoice Extractor Desktop UI

A PySide6 desktop application for extracting data from invoice PDFs.

## Project Structure

```
.
├── ui.py              # UI layout and components (PySide6 widgets)
├── logic.py           # Business logic layer (connects to PDF extraction)
├── main.py            # Application entry point (connects UI + logic)
├── extract_invoice.py # Your PDF extraction code (rename your document to this)
└── README.md          # This file
```

## Setup

1. **Install dependencies:**
   ```bash
   pip install PySide6 pdfplumber --break-system-packages
   ```

2. **Run the application:**
   ```bash
   python main.py
   ```

## Usage

1. **Select Invoice Folder**: Click to choose a folder containing PDF invoices
2. **Process**: Click to extract data from all PDFs in the selected folder
3. **Export to CSV**: Save the extracted data to a CSV file of your choice

## Features

- ✅ Clean separation of UI and business logic
- ✅ Background processing (UI remains responsive)
- ✅ Real-time logging of processing status
- ✅ Interactive data table with extracted invoice information
- ✅ CSV export functionality with custom save location
- ✅ Error handling and user feedback

## Notes

- The application processes only text-based PDFs (skips scanned PDFs)
- Processing happens in a background thread to keep the UI responsive
- All logs are displayed in real-time in the log area
- The table is read-only to prevent accidental data modification
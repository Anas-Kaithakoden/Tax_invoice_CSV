import os
import csv
from datetime import datetime


class InvoiceExtractorLogic:
    def __init__(self):
        self.current_folder = ""
        self.extracted_data = []
    
    def set_folder(self, folder_path):
        """Set the folder path for invoice processing"""
        self.current_folder = folder_path
    
    def process_invoices(self, log_callback=None):
        """Process all PDF invoices in the selected folder
        
        Args:
            log_callback: Function to call for logging messages
            
        Returns:
            List of dictionaries containing extracted data
        """
        # Import your PDF extraction module here
        import extract_invoice
        
        self.extracted_data = []
        
        if not os.path.exists(self.current_folder):
            if log_callback:
                log_callback(f"Error: Folder does not exist: {self.current_folder}")
            return []
        
        pdf_files = [f for f in os.listdir(self.current_folder) if f.lower().endswith(".pdf")]
        
        if not pdf_files:
            if log_callback:
                log_callback("No PDF files found in selected folder.")
            return []
        
        if log_callback:
            log_callback(f"Found {len(pdf_files)} PDF file(s)")
            log_callback("-" * 50)
        
        processed_count = 0
        skipped_count = 0
        
        for filename in pdf_files:
            file_path = os.path.join(self.current_folder, filename)
            
            try:
                # Detect PDF type
                pdf_type = extract_invoice.detect_pdf_type(file_path)
                
                if pdf_type != "text_pdf":
                    if log_callback:
                        log_callback(f"⚠ Skipping scanned PDF: {filename}")
                    skipped_count += 1
                    continue
                
                # Extract data
                row = extract_invoice.text_based_pdf(file_path)
                row["File_Name"] = filename
                self.extracted_data.append(row)
                
                processed_count += 1
                if log_callback:
                    log_callback(f"✓ Processed: {filename}")
                
            except Exception as e:
                if log_callback:
                    log_callback(f"✗ Error processing {filename}: {str(e)}")
                skipped_count += 1
        
        if log_callback:
            log_callback("-" * 50)
            log_callback(f"Processing complete: {processed_count} processed, {skipped_count} skipped")
        
        return self.extracted_data
    
    def export_to_csv(self, output_path, log_callback=None):
        """Export extracted data to CSV file
        
        Args:
            output_path: Path where CSV should be saved
            log_callback: Function to call for logging messages
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.extracted_data:
            if log_callback:
                log_callback("No data to export")
            return False
        
        try:
            # Import labels from your extraction module
            import extract_invoice
            
            fieldnames = ["File_Name"] + list(extract_invoice.LABELS.keys())
            
            with open(output_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(self.extracted_data)
            
            if log_callback:
                log_callback(f"✓ CSV exported successfully: {output_path}")
            
            return True
            
        except Exception as e:
            if log_callback:
                log_callback(f"✗ Error exporting CSV: {str(e)}")
            return False
    
    def get_data(self):
        """Get the extracted data"""
        return self.extracted_data
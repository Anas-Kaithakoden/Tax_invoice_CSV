import sys
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox
from PySide6.QtCore import QThread, Signal
from ui import InvoiceExtractorUI
from logic import InvoiceExtractorLogic


class ProcessingThread(QThread):
    """Background thread for processing invoices"""
    log_message = Signal(str)
    processing_complete = Signal(list)
    
    def __init__(self, logic):
        super().__init__()
        self.logic = logic
    
    def run(self):
        """Run the processing in background"""
        data = self.logic.process_invoices(log_callback=self.emit_log)
        self.processing_complete.emit(data)
    
    def emit_log(self, message):
        """Emit log message to UI"""
        self.log_message.emit(message)


class InvoiceExtractorApp:
    def __init__(self):
        self.ui = InvoiceExtractorUI()
        self.logic = InvoiceExtractorLogic()
        self.processing_thread = None
        
        self.connect_signals()
    
    def connect_signals(self):
        """Connect UI signals to logic handlers"""
        self.ui.folder_selected.connect(self.on_folder_selected)
        self.ui.process_clicked.connect(self.on_process_clicked)
        self.ui.export_clicked.connect(self.on_export_clicked)
    
    def on_folder_selected(self, folder_path):
        """Handle folder selection"""
        self.logic.set_folder(folder_path)
        self.ui.clear_logs()
        self.ui.add_log(f"Folder selected: {folder_path}")
    
    def on_process_clicked(self):
        """Handle process button click"""
        self.ui.clear_logs()
        self.ui.add_log("Starting invoice processing...")
        self.ui.set_processing_state(True)
        
        # Create and start processing thread
        self.processing_thread = ProcessingThread(self.logic)
        self.processing_thread.log_message.connect(self.ui.add_log)
        self.processing_thread.processing_complete.connect(self.on_processing_complete)
        self.processing_thread.start()
    
    def on_processing_complete(self, data):
        """Handle completion of processing"""
        self.ui.set_processing_state(False)
        
        if data:
            self.ui.populate_table(data)
            self.ui.add_log(f"\n✓ Successfully extracted data from {len(data)} invoice(s)")
        else:
            self.ui.add_log("\n⚠ No data extracted")
            QMessageBox.warning(
                self.ui,
                "No Data",
                "No invoices were successfully processed. Check the logs for details."
            )
    
    def on_export_clicked(self):
        """Handle export button click"""
        # Get save file path from user
        file_path, _ = QFileDialog.getSaveFileName(
            self.ui,
            "Save CSV File",
            "invoices_export.csv",
            "CSV Files (*.csv);;All Files (*)"
        )
        
        if file_path:
            success = self.logic.export_to_csv(file_path, log_callback=self.ui.add_log)
            
            if success:
                QMessageBox.information(
                    self.ui,
                    "Export Successful",
                    f"Data exported successfully to:\n{file_path}"
                )
            else:
                QMessageBox.warning(
                    self.ui,
                    "Export Failed",
                    "Failed to export CSV file. Check the logs for details."
                )
    
    def run(self):
        """Show the UI and start the application"""
        self.ui.show()
        return app.exec()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Set application style
    app.setStyle("Fusion")
    
    invoice_app = InvoiceExtractorApp()
    sys.exit(invoice_app.run())
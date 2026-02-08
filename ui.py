from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTableWidget, QTableWidgetItem,
    QTextEdit, QLabel, QFileDialog, QHeaderView, QFrame, QScrollArea
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont


class InvoiceExtractorUI(QMainWindow):
    # Signals for communication with logic layer
    folder_selected = Signal(str)
    process_clicked = Signal()
    export_clicked = Signal()
    
    def __init__(self):
        super().__init__()
        self.selected_folder = ""
        self.init_ui()
        self.apply_global_stylesheet()
    
    def init_ui(self):
        self.setWindowTitle("Invoice Extractor Pro")
        self.setMinimumSize(1200, 800)
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Header Section
        header_frame = self.create_header()
        main_layout.addWidget(header_frame)
        
        # Scroll Area for content
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        # Content Area
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(24)
        content_layout.setContentsMargins(40, 30, 40, 40)
        
        # Action Cards Section
        action_frame = self.create_action_section()
        content_layout.addWidget(action_frame)
        
        # Folder Selection Display
        self.folder_display_frame = self.create_folder_display()
        content_layout.addWidget(self.folder_display_frame)
        
        # Results table
        table_container = self.create_table_section()
        content_layout.addWidget(table_container, stretch=3)
        
        # Logs section
        log_container = self.create_log_section()
        content_layout.addWidget(log_container, stretch=1)
        
        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area)
    
    def create_header(self):
        """Create the application header with gradient background"""
        header_frame = QFrame()
        header_frame.setObjectName("headerFrame")
        header_layout = QVBoxLayout(header_frame)
        header_layout.setContentsMargins(40, 30, 40, 30)
        
        # Title
        title_label = QLabel("Invoice Extractor Pro")
        title_label.setObjectName("mainTitle")
        header_layout.addWidget(title_label)
        
        # Subtitle
        subtitle_label = QLabel("Automated PDF invoice data extraction & CSV export")
        subtitle_label.setObjectName("subtitle")
        header_layout.addWidget(subtitle_label)
        
        return header_frame
    
    def create_action_section(self):
        """Create action buttons as cards"""
        action_frame = QFrame()
        action_layout = QHBoxLayout(action_frame)
        action_layout.setSpacing(20)
        
        # Select Folder Card
        select_card = self.create_action_card(
            "📁", "Select Folder", 
            "Choose invoice PDFs"
        )
        select_card.setObjectName("selectCard")
        self.select_folder_btn = select_card.button
        self.select_folder_btn.setObjectName("selectBtn")
        self.select_folder_btn.clicked.connect(self.on_select_folder)
        action_layout.addWidget(select_card)
        
        # Process Card
        process_card = self.create_action_card(
            "⚡", "Process", 
            "Extract data"
        )
        process_card.setObjectName("processCard")
        self.process_btn = process_card.button
        self.process_btn.setObjectName("processBtn")
        self.process_btn.setEnabled(False)
        self.process_btn.clicked.connect(self.on_process)
        action_layout.addWidget(process_card)
        
        # Export Card
        export_card = self.create_action_card(
            "💾", "Export", 
            "Download CSV"
        )
        export_card.setObjectName("exportCard")
        self.export_btn = export_card.button
        self.export_btn.setObjectName("exportBtn")
        self.export_btn.setEnabled(False)
        self.export_btn.clicked.connect(self.on_export)
        action_layout.addWidget(export_card)
        
        return action_frame
    
    def create_action_card(self, icon, title, subtitle):
        """Create a styled action button card"""
        # Create a container widget instead of putting layout in button
        container = QWidget()
        container.setObjectName("cardContainer")
        container.setMinimumHeight(120)
        container.setCursor(Qt.CursorShape.PointingHandCursor)
        
        # Create the actual button
        btn = QPushButton(container)
        btn.setGeometry(0, 0, 1000, 120)  # Will be resized by parent
        btn.setObjectName("cardButton")
        
        # Create layout for labels
        layout = QVBoxLayout(container)
        layout.setSpacing(5)
        layout.setContentsMargins(10, 20, 10, 20)
        
        # Icon
        icon_label = QLabel(icon)
        icon_label.setObjectName("cardIcon")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(icon_label)
        
        # Title
        title_label = QLabel(title)
        title_label.setObjectName("cardTitle")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(title_label)
        
        # Subtitle
        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("cardSubtitle")
        subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(subtitle_label)
        
        # Store the button reference so we can connect signals
        container.button = btn
        
        return container
    
    def create_folder_display(self):
        """Create folder selection display area"""
        folder_frame = QFrame()
        folder_frame.setObjectName("folderDisplay")
        folder_layout = QVBoxLayout(folder_frame)
        folder_layout.setContentsMargins(20, 15, 20, 15)
        
        label_header = QLabel("📂 Selected Folder")
        label_header.setObjectName("folderHeader")
        folder_layout.addWidget(label_header)
        
        self.folder_label = QLabel("No folder selected")
        self.folder_label.setObjectName("folderPath")
        self.folder_label.setWordWrap(True)
        folder_layout.addWidget(self.folder_label)
        
        return folder_frame
    
    def create_table_section(self):
        """Create the data table with header"""
        container = QFrame()
        container.setObjectName("tableContainer")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(15)
        
        # Header
        header_layout = QHBoxLayout()
        table_label = QLabel("📊 Extracted Invoice Data")
        table_label.setObjectName("sectionHeader")
        header_layout.addWidget(table_label)
        header_layout.addStretch()
        
        self.record_count_label = QLabel("0 records")
        self.record_count_label.setObjectName("recordCount")
        header_layout.addWidget(self.record_count_label)
        
        layout.addLayout(header_layout)
        
        # Table
        self.table = QTableWidget()
        self.table.setObjectName("dataTable")
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table)
        
        return container
    
    def create_log_section(self):
        """Create the log display area"""
        container = QFrame()
        container.setObjectName("logContainer")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        
        log_label = QLabel("📝 Processing Logs")
        log_label.setObjectName("sectionHeader")
        layout.addWidget(log_label)
        
        self.log_text = QTextEdit()
        self.log_text.setObjectName("logText")
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(180)
        layout.addWidget(self.log_text)
        
        return container
    
    def apply_global_stylesheet(self):
        """Apply comprehensive stylesheet to the application"""
        self.setStyleSheet("""
            /* Main Window */
            QMainWindow {
                background-color: #f8f9fa;
            }
            
            /* Header Section */
            #headerFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #667eea, stop:1 #764ba2);
                border: none;
            }
            
            #mainTitle {
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 32px;
                font-weight: 700;
                color: white;
                letter-spacing: -0.5px;
            }
            
            #subtitle {
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 15px;
                color: rgba(255, 255, 255, 0.9);
                margin-top: 5px;
                font-weight: 400;
            }
            
            /* Action Cards */
            #cardContainer {
                background: white;
                border: 2px solid #e3e8ef;
                border-radius: 12px;
            }
            
            #selectCard:hover {
                border: 2px solid #667eea;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #f0f3ff, stop:1 #faf5ff);
            }
            
            #processCard:hover {
                border: 2px solid #f5576c;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #fff5f7, stop:1 #fff0f3);
            }
            
            #exportCard:hover {
                border: 2px solid #00f2fe;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #f0fdff, stop:1 #f0fcff);
            }
            
            #cardButton {
                background: transparent;
                border: none;
            }
            
            #cardIcon {
                font-size: 36px;
                background: transparent;
                border: none;
            }
            
            #cardTitle {
                font-size: 16px;
                font-weight: 700;
                color: #1e293b;
                background: transparent;
                border: none;
            }
            
            #cardSubtitle {
                font-size: 12px;
                color: #64748b;
                background: transparent;
                border: none;
            }
            
            /* Folder Display */
            #folderDisplay {
                background-color: white;
                border: 2px solid #e3e8ef;
                border-radius: 10px;
                padding: 5px;
            }
            
            #folderHeader {
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 13px;
                font-weight: 600;
                color: #6366f1;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }
            
            #folderPath {
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 13px;
                color: #1e293b;
                padding: 5px 0;
            }
            
            /* Section Headers */
            #sectionHeader {
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 18px;
                font-weight: 700;
                color: #1e293b;
                padding: 10px 0;
            }
            
            #recordCount {
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 13px;
                font-weight: 600;
                color: #6366f1;
                background-color: #eef2ff;
                padding: 6px 14px;
                border-radius: 20px;
            }
            
            /* Table Styling */
            #dataTable {
                background-color: white;
                border: 2px solid #e3e8ef;
                border-radius: 10px;
                gridline-color: #f1f5f9;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 13px;
                selection-background-color: #eef2ff;
                selection-color: #1e293b;
            }
            
            #dataTable::item {
                padding: 12px 8px;
                border: none;
            }
            
            #dataTable::item:alternate {
                background-color: #f8fafc;
            }
            
            #dataTable::item:selected {
                background-color: #eef2ff;
                color: #1e293b;
            }
            
            QHeaderView::section {
                background-color: #f1f5f9;
                color: #475569;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 12px;
                font-weight: 700;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                padding: 14px 8px;
                border: none;
                border-bottom: 2px solid #cbd5e1;
            }
            
            QHeaderView::section:first {
                border-top-left-radius: 8px;
            }
            
            QHeaderView::section:last {
                border-top-right-radius: 8px;
            }
            
            /* Log Container */
            #logContainer {
                background-color: white;
                border: 2px solid #e3e8ef;
                border-radius: 10px;
                padding: 15px;
            }
            
            #logText {
                background-color: #0f172a;
                color: #e2e8f0;
                border: none;
                border-radius: 8px;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 12px;
                padding: 12px;
                line-height: 1.6;
            }
            
            /* Scrollbars */
            QScrollBar:vertical {
                background: #f1f5f9;
                width: 12px;
                border-radius: 6px;
                margin: 0px;
            }
            
            QScrollBar::handle:vertical {
                background: #cbd5e1;
                border-radius: 6px;
                min-height: 30px;
            }
            
            QScrollBar::handle:vertical:hover {
                background: #94a3b8;
            }
            
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            
            QScrollBar:horizontal {
                background: #f1f5f9;
                height: 12px;
                border-radius: 6px;
                margin: 0px;
            }
            
            QScrollBar::handle:horizontal {
                background: #cbd5e1;
                border-radius: 6px;
                min-width: 30px;
            }
            
            QScrollBar::handle:horizontal:hover {
                background: #94a3b8;
            }
            
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
            }
        """)
    
    def on_select_folder(self):
        """Handle folder selection"""
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Invoice Folder",
            "",
            QFileDialog.Option.ShowDirsOnly
        )
        
        if folder:
            self.selected_folder = folder
            self.folder_label.setText(folder)
            self.folder_display_frame.setStyleSheet("""
                #folderDisplay {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 #ecfdf5, stop:1 #d1fae5);
                    border: 2px solid #10b981;
                    border-radius: 10px;
                    padding: 5px;
                }
            """)
            self.process_btn.setEnabled(True)
            self.folder_selected.emit(folder)
    
    def on_process(self):
        """Handle process button click"""
        self.process_clicked.emit()
    
    def on_export(self):
        """Handle export button click"""
        self.export_clicked.emit()
    
    def populate_table(self, data):
        """Populate table with extracted data
        
        Args:
            data: List of dictionaries containing invoice data
        """
        if not data:
            self.table.setRowCount(0)
            self.table.setColumnCount(0)
            self.record_count_label.setText("0 records")
            return
        
        # Get headers from first row
        headers = list(data[0].keys())
        
        self.table.setRowCount(len(data))
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        
        # Populate cells
        for row_idx, row_data in enumerate(data):
            for col_idx, header in enumerate(headers):
                value = str(row_data.get(header, ""))
                item = QTableWidgetItem(value)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row_idx, col_idx, item)
        
        # Resize columns to content
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        
        # Update record count
        self.record_count_label.setText(f"{len(data)} records")
        
        # Enable export button
        self.export_btn.setEnabled(True)
    
    def add_log(self, message):
        """Add a log message to the log text area"""
        self.log_text.append(message)
    
    def clear_logs(self):
        """Clear all log messages"""
        self.log_text.clear()
    
    def set_processing_state(self, is_processing):
        """Enable/disable buttons during processing"""
        self.select_folder_btn.setEnabled(not is_processing)
        self.process_btn.setEnabled(not is_processing and bool(self.selected_folder))
        self.export_btn.setEnabled(not is_processing and self.table.rowCount() > 0)
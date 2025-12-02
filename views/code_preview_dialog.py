"""
Code Preview Dialog.

Provides a text editor with Python syntax highlighting for
previewing and editing generated ns-3 scripts before running.
"""

from typing import Optional
from PyQt6.QtCore import Qt, QRegularExpression
from PyQt6.QtGui import (
    QFont, QColor, QTextCharFormat, QSyntaxHighlighter,
    QTextDocument, QKeySequence, QShortcut
)
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QPlainTextEdit, QLabel, QWidget, QSplitter,
    QFrame, QMessageBox
)


class PythonHighlighter(QSyntaxHighlighter):
    """Syntax highlighter for Python code."""
    
    def __init__(self, document: QTextDocument):
        super().__init__(document)
        self._highlighting_rules = []
        
        # Keywords
        keyword_format = QTextCharFormat()
        keyword_format.setForeground(QColor("#CF222E"))  # Red
        keyword_format.setFontWeight(QFont.Weight.Bold)
        keywords = [
            "and", "as", "assert", "async", "await", "break", "class",
            "continue", "def", "del", "elif", "else", "except", "finally",
            "for", "from", "global", "if", "import", "in", "is", "lambda",
            "nonlocal", "not", "or", "pass", "raise", "return", "try",
            "while", "with", "yield", "True", "False", "None"
        ]
        for word in keywords:
            pattern = QRegularExpression(rf"\b{word}\b")
            self._highlighting_rules.append((pattern, keyword_format))
        
        # Built-in functions
        builtin_format = QTextCharFormat()
        builtin_format.setForeground(QColor("#8250DF"))  # Purple
        builtins = [
            "print", "len", "range", "str", "int", "float", "list",
            "dict", "set", "tuple", "type", "isinstance", "hasattr",
            "getattr", "setattr", "open", "input", "sorted", "reversed",
            "enumerate", "zip", "map", "filter", "sum", "min", "max"
        ]
        for word in builtins:
            pattern = QRegularExpression(rf"\b{word}\b")
            self._highlighting_rules.append((pattern, builtin_format))
        
        # ns-3 specific classes and helpers
        ns3_format = QTextCharFormat()
        ns3_format.setForeground(QColor("#0550AE"))  # Blue
        ns3_format.setFontWeight(QFont.Weight.Bold)
        ns3_classes = [
            "NodeContainer", "NetDeviceContainer", "Ipv4InterfaceContainer",
            "PointToPointHelper", "CsmaHelper", "WifiHelper", "InternetStackHelper",
            "Ipv4AddressHelper", "UdpEchoServerHelper", "UdpEchoClientHelper",
            "OnOffHelper", "PacketSinkHelper", "ApplicationContainer",
            "Simulator", "GlobalValue", "Config", "LogComponentEnable",
            "MobilityHelper", "YansWifiChannelHelper", "YansWifiPhyHelper",
            "WifiMacHelper", "SsidValue", "StringValue", "TimeValue",
            "UintegerValue", "BooleanValue", "DoubleValue", "Seconds",
            "MilliSeconds", "MicroSeconds", "NanoSeconds", "InetSocketAddress",
            "Ipv4Address", "Ipv4GlobalRoutingHelper", "AsciiTraceHelper",
            "FlowMonitorHelper", "AnimationInterface"
        ]
        for word in ns3_classes:
            pattern = QRegularExpression(rf"\b{word}\b")
            self._highlighting_rules.append((pattern, ns3_format))
        
        # ns module reference
        ns_module_format = QTextCharFormat()
        ns_module_format.setForeground(QColor("#0550AE"))  # Blue
        pattern = QRegularExpression(r"\bns\.[a-zA-Z_][a-zA-Z0-9_]*")
        self._highlighting_rules.append((pattern, ns_module_format))
        
        # Numbers
        number_format = QTextCharFormat()
        number_format.setForeground(QColor("#0550AE"))  # Blue
        pattern = QRegularExpression(r"\b[0-9]+\.?[0-9]*\b")
        self._highlighting_rules.append((pattern, number_format))
        
        # Strings (double quotes)
        string_format = QTextCharFormat()
        string_format.setForeground(QColor("#0A3069"))  # Dark blue
        pattern = QRegularExpression(r'"[^"\\]*(\\.[^"\\]*)*"')
        self._highlighting_rules.append((pattern, string_format))
        
        # Strings (single quotes)
        pattern = QRegularExpression(r"'[^'\\]*(\\.[^'\\]*)*'")
        self._highlighting_rules.append((pattern, string_format))
        
        # Comments
        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor("#6E7781"))  # Gray
        comment_format.setFontItalic(True)
        pattern = QRegularExpression(r"#[^\n]*")
        self._highlighting_rules.append((pattern, comment_format))
        
        # Function definitions
        func_format = QTextCharFormat()
        func_format.setForeground(QColor("#8250DF"))  # Purple
        func_format.setFontWeight(QFont.Weight.Bold)
        pattern = QRegularExpression(r"\bdef\s+([a-zA-Z_][a-zA-Z0-9_]*)")
        self._highlighting_rules.append((pattern, func_format))
        
        # Class definitions
        class_format = QTextCharFormat()
        class_format.setForeground(QColor("#953800"))  # Orange
        class_format.setFontWeight(QFont.Weight.Bold)
        pattern = QRegularExpression(r"\bclass\s+([a-zA-Z_][a-zA-Z0-9_]*)")
        self._highlighting_rules.append((pattern, class_format))
        
        # Decorators
        decorator_format = QTextCharFormat()
        decorator_format.setForeground(QColor("#8250DF"))  # Purple
        pattern = QRegularExpression(r"@[a-zA-Z_][a-zA-Z0-9_]*")
        self._highlighting_rules.append((pattern, decorator_format))
    
    def highlightBlock(self, text: str):
        """Apply syntax highlighting to a block of text."""
        for pattern, fmt in self._highlighting_rules:
            match_iterator = pattern.globalMatch(text)
            while match_iterator.hasNext():
                match = match_iterator.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), fmt)


class CodeEditor(QPlainTextEdit):
    """
    Plain text editor with line numbers and Python highlighting.
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Setup font - use a safe fallback
        font = QFont("Monospace", 11)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.setFont(font)
        
        # Setup tab width (4 spaces)
        try:
            self.setTabStopDistance(self.fontMetrics().horizontalAdvance(' ') * 4)
        except Exception:
            pass  # Older Qt versions might not have this
        
        # Line number area
        self._line_number_area = LineNumberArea(self)
        
        # Syntax highlighting
        self._highlighter = PythonHighlighter(self.document())
        
        # Styling
        self.setStyleSheet("""
            QPlainTextEdit {
                background: #FFFFFF;
                color: #24292F;
                border: 1px solid #D0D7DE;
                border-radius: 6px;
                padding: 8px;
                selection-background-color: #0969DA;
                selection-color: white;
            }
        """)
        
        # Connect signals for line numbers
        self.blockCountChanged.connect(self._update_line_number_area_width)
        self.updateRequest.connect(self._update_line_number_area)
        self.cursorPositionChanged.connect(self._highlight_current_line)
        
        self._update_line_number_area_width(0)
        self._highlight_current_line()
    
    def line_number_area_width(self) -> int:
        """Calculate width needed for line numbers."""
        digits = len(str(max(1, self.blockCount())))
        space = 10 + self.fontMetrics().horizontalAdvance('9') * digits
        return space
    
    def _update_line_number_area_width(self, _):
        """Update the margin to accommodate line numbers."""
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)
    
    def _update_line_number_area(self, rect, dy):
        """Update line number area on scroll."""
        if dy:
            self._line_number_area.scroll(0, dy)
        else:
            self._line_number_area.update(0, rect.y(), 
                                          self._line_number_area.width(), rect.height())
        
        if rect.contains(self.viewport().rect()):
            self._update_line_number_area_width(0)
    
    def resizeEvent(self, event):
        """Handle resize to update line number area."""
        super().resizeEvent(event)
        cr = self.contentsRect()
        self._line_number_area.setGeometry(
            cr.left(), cr.top(), 
            self.line_number_area_width(), cr.height()
        )
    
    def _highlight_current_line(self):
        """Highlight the current line."""
        extra_selections = []
        
        if not self.isReadOnly():
            # In PyQt6, ExtraSelection is a nested class or we create it differently
            from PyQt6.QtWidgets import QTextEdit
            selection = QTextEdit.ExtraSelection()
            line_color = QColor("#F6F8FA")
            selection.format.setBackground(line_color)
            selection.format.setProperty(
                QTextCharFormat.Property.FullWidthSelection, True
            )
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extra_selections.append(selection)
        
        self.setExtraSelections(extra_selections)
    
    def line_number_area_paint_event(self, event):
        """Paint the line numbers."""
        from PyQt6.QtGui import QPainter
        painter = QPainter(self._line_number_area)
        painter.fillRect(event.rect(), QColor("#F6F8FA"))
        
        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = round(self.blockBoundingGeometry(block).translated(
            self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())
        
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)
                painter.setPen(QColor("#8C959F"))
                painter.drawText(
                    0, top,
                    self._line_number_area.width() - 5,
                    self.fontMetrics().height(),
                    Qt.AlignmentFlag.AlignRight, number
                )
            
            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            block_number += 1


class LineNumberArea(QWidget):
    """Widget displaying line numbers for CodeEditor."""
    
    def __init__(self, editor: CodeEditor):
        super().__init__(editor)
        self._editor = editor
    
    def sizeHint(self):
        from PyQt6.QtCore import QSize
        return QSize(self._editor.line_number_area_width(), 0)
    
    def paintEvent(self, event):
        self._editor.line_number_area_paint_event(event)


class CodePreviewDialog(QDialog):
    """
    Dialog for previewing and editing generated ns-3 Python scripts.
    
    Features:
    - Python syntax highlighting
    - Line numbers
    - Edit capability
    - Run or Cancel options
    """
    
    def __init__(self, code: str, script_name: str = "simulation.py", parent=None):
        super().__init__(parent)
        self._original_code = code
        self._script_name = script_name
        self._accepted_code: Optional[str] = None
        
        self.setWindowTitle(f"Preview: {script_name}")
        self.setModal(True)
        self.resize(900, 700)
        
        self._setup_ui()
        self._editor.setPlainText(code)
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # Header
        header_layout = QHBoxLayout()
        
        title_label = QLabel(f"📝 {self._script_name}")
        title_label.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: 600;
                color: #24292F;
            }
        """)
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()
        
        # Info label
        info_label = QLabel("Review and edit the generated script before running")
        info_label.setStyleSheet("color: #57606A; font-size: 12px;")
        header_layout.addWidget(info_label)
        
        layout.addLayout(header_layout)
        
        # Code editor
        self._editor = CodeEditor()
        layout.addWidget(self._editor, 1)
        
        # Status bar
        status_layout = QHBoxLayout()
        
        self._line_col_label = QLabel("Line 1, Column 1")
        self._line_col_label.setStyleSheet("color: #57606A; font-size: 11px;")
        status_layout.addWidget(self._line_col_label)
        
        status_layout.addStretch()
        
        self._modified_label = QLabel("")
        self._modified_label.setStyleSheet("color: #CF222E; font-size: 11px;")
        status_layout.addWidget(self._modified_label)
        
        layout.addLayout(status_layout)
        
        # Button bar
        button_layout = QHBoxLayout()
        
        # Reset button
        reset_btn = QPushButton("Reset to Original")
        reset_btn.setStyleSheet("""
            QPushButton {
                background: white;
                color: #57606A;
                border: 1px solid #D0D7DE;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 13px;
            }
            QPushButton:hover {
                background: #F6F8FA;
            }
        """)
        reset_btn.clicked.connect(self._on_reset)
        button_layout.addWidget(reset_btn)
        
        button_layout.addStretch()
        
        # Cancel button
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet("""
            QPushButton {
                background: white;
                color: #24292F;
                border: 1px solid #D0D7DE;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 13px;
            }
            QPushButton:hover {
                background: #F6F8FA;
            }
        """)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        # Run button
        run_btn = QPushButton("▶ Run Simulation")
        run_btn.setStyleSheet("""
            QPushButton {
                background: #2DA44E;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 20px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #2C974B;
            }
        """)
        run_btn.clicked.connect(self._on_run)
        button_layout.addWidget(run_btn)
        
        layout.addLayout(button_layout)
        
        # Connect signals
        self._editor.cursorPositionChanged.connect(self._update_cursor_position)
        self._editor.textChanged.connect(self._update_modified_status)
        
        # Keyboard shortcuts
        QShortcut(QKeySequence("Ctrl+Return"), self, self._on_run)
        QShortcut(QKeySequence("Escape"), self, self.reject)
    
    def _update_cursor_position(self):
        """Update line/column display."""
        cursor = self._editor.textCursor()
        line = cursor.blockNumber() + 1
        col = cursor.columnNumber() + 1
        self._line_col_label.setText(f"Line {line}, Column {col}")
    
    def _update_modified_status(self):
        """Update modified indicator."""
        if self._editor.toPlainText() != self._original_code:
            self._modified_label.setText("● Modified")
        else:
            self._modified_label.setText("")
    
    def _on_reset(self):
        """Reset to original code."""
        if self._editor.toPlainText() != self._original_code:
            reply = QMessageBox.question(
                self, "Reset Code",
                "Discard all changes and reset to original?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._editor.setPlainText(self._original_code)
    
    def _on_run(self):
        """Accept and return the edited code."""
        self._accepted_code = self._editor.toPlainText()
        self.accept()
    
    def get_code(self) -> Optional[str]:
        """Get the edited code (or None if cancelled)."""
        return self._accepted_code
    
    @staticmethod
    def preview_code(code: str, script_name: str = "simulation.py", 
                     parent=None) -> Optional[str]:
        """
        Show preview dialog and return edited code.
        
        Returns the (possibly edited) code if Run was clicked,
        or None if cancelled.
        """
        dialog = CodePreviewDialog(code, script_name, parent)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return dialog.get_code()
        return None

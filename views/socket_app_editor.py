"""
Socket Application Script Editor.

Provides a code editor for customizing socket application behavior
including payload generation, send logic, and receive callbacks.
"""

import os
import re
from typing import Optional
from PyQt6.QtCore import Qt, pyqtSignal, QRegularExpression
from PyQt6.QtGui import (
    QFont, QColor, QTextCharFormat, QSyntaxHighlighter,
    QKeySequence, QShortcut, QTextCursor
)
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QPlainTextEdit, QWidget, QSplitter, QFrame, QMessageBox,
    QFileDialog, QStatusBar, QToolBar, QSizePolicy
)

from models import NodeModel, NodeType


class PythonHighlighter(QSyntaxHighlighter):
    """Syntax highlighter for Python code."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._highlighting_rules = []
        
        # Keywords
        keyword_format = QTextCharFormat()
        keyword_format.setForeground(QColor("#C678DD"))  # Purple
        keyword_format.setFontWeight(QFont.Weight.Bold)
        keywords = [
            "and", "as", "assert", "async", "await", "break", "class",
            "continue", "def", "del", "elif", "else", "except", "False",
            "finally", "for", "from", "global", "if", "import", "in",
            "is", "lambda", "None", "nonlocal", "not", "or", "pass",
            "raise", "return", "True", "try", "while", "with", "yield"
        ]
        for word in keywords:
            pattern = QRegularExpression(rf"\b{word}\b")
            self._highlighting_rules.append((pattern, keyword_format))
        
        # Built-in functions
        builtin_format = QTextCharFormat()
        builtin_format.setForeground(QColor("#61AFEF"))  # Blue
        builtins = [
            "abs", "all", "any", "bin", "bool", "bytes", "callable",
            "chr", "dict", "dir", "enumerate", "eval", "exec", "filter",
            "float", "format", "getattr", "globals", "hasattr", "hash",
            "hex", "id", "input", "int", "isinstance", "iter", "len",
            "list", "locals", "map", "max", "min", "next", "object",
            "oct", "open", "ord", "pow", "print", "range", "repr",
            "reversed", "round", "set", "setattr", "slice", "sorted",
            "str", "sum", "super", "tuple", "type", "vars", "zip"
        ]
        for word in builtins:
            pattern = QRegularExpression(rf"\b{word}\b")
            self._highlighting_rules.append((pattern, builtin_format))
        
        # ns-3 specific
        ns3_format = QTextCharFormat()
        ns3_format.setForeground(QColor("#98C379"))  # Green
        ns3_keywords = [
            "ns", "Packet", "Socket", "Simulator", "Seconds", "MilliSeconds",
            "UdpSocketFactory", "TcpSocketFactory", "InetSocketAddress",
            "Ipv4Address", "NodeContainer", "GetTypeId", "Schedule"
        ]
        for word in ns3_keywords:
            pattern = QRegularExpression(rf"\b{word}\b")
            self._highlighting_rules.append((pattern, ns3_format))
        
        # Self
        self_format = QTextCharFormat()
        self_format.setForeground(QColor("#E06C75"))  # Red
        self_format.setFontItalic(True)
        self._highlighting_rules.append(
            (QRegularExpression(r"\bself\b"), self_format)
        )
        
        # Numbers
        number_format = QTextCharFormat()
        number_format.setForeground(QColor("#D19A66"))  # Orange
        self._highlighting_rules.append(
            (QRegularExpression(r"\b[0-9]+\.?[0-9]*\b"), number_format)
        )
        self._highlighting_rules.append(
            (QRegularExpression(r"\b0x[0-9A-Fa-f]+\b"), number_format)
        )
        
        # Strings (single and double quotes)
        string_format = QTextCharFormat()
        string_format.setForeground(QColor("#98C379"))  # Green
        self._highlighting_rules.append(
            (QRegularExpression(r'"[^"\\]*(\\.[^"\\]*)*"'), string_format)
        )
        self._highlighting_rules.append(
            (QRegularExpression(r"'[^'\\]*(\\.[^'\\]*)*'"), string_format)
        )
        
        # Triple-quoted strings
        self._highlighting_rules.append(
            (QRegularExpression(r'""".*?"""', QRegularExpression.PatternOption.DotMatchesEverythingOption), string_format)
        )
        self._highlighting_rules.append(
            (QRegularExpression(r"'''.*?'''", QRegularExpression.PatternOption.DotMatchesEverythingOption), string_format)
        )
        
        # Comments
        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor("#5C6370"))  # Gray
        comment_format.setFontItalic(True)
        self._highlighting_rules.append(
            (QRegularExpression(r"#[^\n]*"), comment_format)
        )
        
        # Decorators
        decorator_format = QTextCharFormat()
        decorator_format.setForeground(QColor("#C678DD"))  # Purple
        self._highlighting_rules.append(
            (QRegularExpression(r"@\w+"), decorator_format)
        )
        
        # Function definitions
        function_format = QTextCharFormat()
        function_format.setForeground(QColor("#61AFEF"))  # Blue
        function_format.setFontWeight(QFont.Weight.Bold)
        self._highlighting_rules.append(
            (QRegularExpression(r"\bdef\s+(\w+)"), function_format)
        )
        
        # Class definitions
        class_format = QTextCharFormat()
        class_format.setForeground(QColor("#E5C07B"))  # Yellow
        class_format.setFontWeight(QFont.Weight.Bold)
        self._highlighting_rules.append(
            (QRegularExpression(r"\bclass\s+(\w+)"), class_format)
        )
    
    def highlightBlock(self, text: str):
        for pattern, fmt in self._highlighting_rules:
            iterator = pattern.globalMatch(text)
            while iterator.hasNext():
                match = iterator.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), fmt)


class LineNumberArea(QWidget):
    """Line number display area for code editor."""
    
    def __init__(self, editor):
        super().__init__(editor)
        self._editor = editor
    
    def sizeHint(self):
        return self._editor.line_number_area_size()
    
    def paintEvent(self, event):
        self._editor.line_number_area_paint_event(event)


class CodeEditor(QPlainTextEdit):
    """Enhanced code editor with line numbers and syntax highlighting."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Set monospace font
        font = QFont("Consolas", 11)
        if not font.exactMatch():
            font = QFont("Monaco", 11)
        if not font.exactMatch():
            font = QFont("Courier New", 11)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.setFont(font)
        
        # Dark theme colors
        self.setStyleSheet("""
            QPlainTextEdit {
                background-color: #282C34;
                color: #ABB2BF;
                border: none;
                selection-background-color: #3E4451;
            }
        """)
        
        # Line number area
        self._line_number_area = LineNumberArea(self)
        
        # Connect signals
        self.blockCountChanged.connect(self._update_line_number_area_width)
        self.updateRequest.connect(self._update_line_number_area)
        self.cursorPositionChanged.connect(self._highlight_current_line)
        
        # Syntax highlighter
        self._highlighter = PythonHighlighter(self.document())
        
        # Initial setup
        self._update_line_number_area_width(0)
        self._highlight_current_line()
        
        # Tab settings
        self.setTabStopDistance(self.fontMetrics().horizontalAdvance(' ') * 4)
    
    def line_number_area_width(self) -> int:
        digits = 1
        max_num = max(1, self.blockCount())
        while max_num >= 10:
            max_num //= 10
            digits += 1
        space = 10 + self.fontMetrics().horizontalAdvance('9') * digits
        return space
    
    def line_number_area_size(self):
        from PyQt6.QtCore import QSize
        return QSize(self.line_number_area_width(), 0)
    
    def _update_line_number_area_width(self, _):
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)
    
    def _update_line_number_area(self, rect, dy):
        if dy:
            self._line_number_area.scroll(0, dy)
        else:
            self._line_number_area.update(0, rect.y(), 
                                          self._line_number_area.width(), 
                                          rect.height())
        
        if rect.contains(self.viewport().rect()):
            self._update_line_number_area_width(0)
    
    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self._line_number_area.setGeometry(
            cr.left(), cr.top(),
            self.line_number_area_width(), cr.height()
        )
    
    def _highlight_current_line(self):
        extra_selections = []
        
        if not self.isReadOnly():
            from PyQt6.QtWidgets import QTextEdit
            selection = QTextEdit.ExtraSelection()
            line_color = QColor("#2C313A")
            selection.format.setBackground(line_color)
            selection.format.setProperty(
                QTextCharFormat.Property.FullWidthSelection, True
            )
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extra_selections.append(selection)
        
        self.setExtraSelections(extra_selections)
    
    def line_number_area_paint_event(self, event):
        from PyQt6.QtGui import QPainter
        painter = QPainter(self._line_number_area)
        painter.fillRect(event.rect(), QColor("#21252B"))
        
        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = round(self.blockBoundingGeometry(block).translated(
            self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())
        
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)
                painter.setPen(QColor("#636D83"))
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
    
    def keyPressEvent(self, event):
        # Auto-indent on Enter
        if event.key() == Qt.Key.Key_Return:
            cursor = self.textCursor()
            block = cursor.block()
            text = block.text()
            
            # Get current indentation
            indent = ""
            for char in text:
                if char in " \t":
                    indent += char
                else:
                    break
            
            # Add extra indent after colon
            if text.rstrip().endswith(":"):
                indent += "    "
            
            super().keyPressEvent(event)
            self.insertPlainText(indent)
            return
        
        # Handle Tab for indentation
        if event.key() == Qt.Key.Key_Tab:
            cursor = self.textCursor()
            if cursor.hasSelection():
                # Indent selected lines
                start = cursor.selectionStart()
                end = cursor.selectionEnd()
                cursor.setPosition(start)
                cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
                cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
                cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock, 
                                   QTextCursor.MoveMode.KeepAnchor)
                text = cursor.selectedText()
                lines = text.split('\u2029')  # QTextCursor paragraph separator
                indented = ['    ' + line for line in lines]
                cursor.insertText('\n'.join(indented))
            else:
                self.insertPlainText("    ")
            return
        
        # Handle Shift+Tab for dedent
        if event.key() == Qt.Key.Key_Backtab:
            cursor = self.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
            cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock,
                               QTextCursor.MoveMode.KeepAnchor)
            text = cursor.selectedText()
            if text.startswith("    "):
                cursor.insertText(text[4:])
            elif text.startswith("\t"):
                cursor.insertText(text[1:])
            return
        
        super().keyPressEvent(event)


class SocketAppEditorDialog(QDialog):
    """
    Dialog for editing Socket Application custom scripts.
    
    Provides a code editor with:
    - Syntax highlighting
    - Line numbers
    - Template generation
    - ApplicationBase class integration
    
    Double-click any node to open this editor.
    The script is stored in node.app_script.
    """
    
    scriptSaved = pyqtSignal(str, str)  # node_id, script_content
    
    def __init__(self, node: NodeModel, parent=None):
        super().__init__(parent)
        self._node = node
        self._modified = False
        
        self._setup_ui()
        self._load_or_generate_script()
        self._connect_signals()
    
    def _sanitize_name(self, name: str) -> str:
        """Sanitize node name for use as filename."""
        # Replace spaces and special chars with underscores
        sanitized = re.sub(r'[^\w\-]', '_', name)
        # Ensure it doesn't start with a number
        if sanitized and sanitized[0].isdigit():
            sanitized = f"app_{sanitized}"
        return sanitized or "socket_app"
    
    def _setup_ui(self):
        self.setWindowTitle(f"Socket Application Editor - {self._node.name}")
        self.setMinimumSize(800, 600)
        self.resize(1000, 800)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Compact toolbar with all actions
        toolbar = QToolBar()
        toolbar.setStyleSheet("""
            QToolBar {
                background: #21252B;
                border-bottom: 1px solid #181A1F;
                padding: 2px 4px;
                spacing: 2px;
            }
            QToolButton {
                background: transparent;
                border: none;
                border-radius: 3px;
                padding: 4px 8px;
                color: #ABB2BF;
                font-size: 11px;
            }
            QToolButton:hover {
                background: #2C313A;
            }
        """)
        
        # Node name label (left side)
        self._path_label = QLabel(f"📝 {self._node.name}.py")
        self._path_label.setStyleSheet("color: #ABB2BF; padding: 0 8px; font-weight: bold;")
        toolbar.addWidget(self._path_label)
        
        toolbar.addSeparator()
        
        # Toolbar actions - compact buttons
        save_btn = QPushButton("💾 Save")
        save_btn.setStyleSheet(self._compact_button_style("#3B82F6"))
        save_btn.clicked.connect(self._save_script)
        toolbar.addWidget(save_btn)
        
        validate_btn = QPushButton("✓ Validate")
        validate_btn.setStyleSheet(self._compact_button_style("#10B981"))
        validate_btn.clicked.connect(self._validate_script)
        toolbar.addWidget(validate_btn)
        
        reset_btn = QPushButton("🔄 Reset")
        reset_btn.setStyleSheet(self._compact_button_style("#6B7280"))
        reset_btn.clicked.connect(self._reset_to_template)
        toolbar.addWidget(reset_btn)
        
        # Spacer
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(spacer)
        
        # Help toggle button
        self._help_btn = QPushButton("? Help")
        self._help_btn.setCheckable(True)
        self._help_btn.setStyleSheet(self._compact_button_style("#6B7280"))
        self._help_btn.clicked.connect(self._toggle_help)
        toolbar.addWidget(self._help_btn)
        
        toolbar.addSeparator()
        
        # Cancel and Save & Close buttons in toolbar (right side)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(self._compact_button_style("#6B7280"))
        cancel_btn.clicked.connect(self._on_cancel)
        toolbar.addWidget(cancel_btn)
        
        save_close_btn = QPushButton("Save && Close")
        save_close_btn.setStyleSheet(self._compact_button_style("#3B82F6"))
        save_close_btn.clicked.connect(self._on_save_and_close)
        toolbar.addWidget(save_close_btn)
        
        layout.addWidget(toolbar)
        
        # Main content area - editor with optional help panel
        self._content_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._content_splitter.setStyleSheet("""
            QSplitter::handle {
                background: #181A1F;
                width: 2px;
            }
        """)
        
        # Code editor (takes full space)
        self._editor = CodeEditor()
        self._content_splitter.addWidget(self._editor)
        
        # Help panel (hidden by default)
        self._help_panel = self._create_help_panel()
        self._help_panel.hide()
        self._content_splitter.addWidget(self._help_panel)
        
        self._content_splitter.setSizes([1000, 0])
        layout.addWidget(self._content_splitter, 1)  # stretch factor 1 to expand
        
        # Minimal status bar
        self._status_bar = QStatusBar()
        self._status_bar.setStyleSheet("""
            QStatusBar {
                background: #21252B;
                color: #636D83;
                border-top: 1px solid #181A1F;
                padding: 2px;
                font-size: 11px;
            }
            QStatusBar::item {
                border: none;
            }
        """)
        self._status_bar.setMaximumHeight(22)
        self._update_status("Ready")
        layout.addWidget(self._status_bar)
    
    def _toggle_help(self):
        """Toggle the help panel visibility."""
        if self._help_panel.isVisible():
            self._help_panel.hide()
            self._content_splitter.setSizes([1000, 0])
            self._help_btn.setChecked(False)
        else:
            self._help_panel.show()
            self._content_splitter.setSizes([700, 300])
            self._help_btn.setChecked(True)
    
    def _compact_button_style(self, color: str) -> str:
        return f"""
            QPushButton {{
                background: {color};
                color: white;
                border: none;
                border-radius: 3px;
                padding: 2px 4px;
                font-size: 11px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: {color}DD;
            }}
            QPushButton:pressed {{
                background: {color}BB;
            }}
            QPushButton:checked {{
                background: {color}AA;
            }}
        """
    
    def _create_help_panel(self) -> QWidget:
        """Create the help/reference panel."""
        panel = QWidget()
        panel.setStyleSheet("background: #1E2127;")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Header
        header = QLabel("  📖 API Reference")
        header.setStyleSheet("""
            background: #21252B;
            color: #ABB2BF;
            padding: 8px;
            font-weight: bold;
            border-bottom: 1px solid #181A1F;
        """)
        layout.addWidget(header)
        
        # Help content
        from PyQt6.QtWidgets import QTextBrowser
        help_browser = QTextBrowser()
        help_browser.setStyleSheet("""
            QTextBrowser {
                background: #1E2127;
                color: #ABB2BF;
                border: none;
                padding: 10px;
            }
        """)
        help_browser.setOpenExternalLinks(True)
        help_browser.setHtml(self._get_help_content())
        layout.addWidget(help_browser)
        
        return panel
    
    def _get_help_content(self) -> str:
        return """
        <style>
            body { font-family: -apple-system, sans-serif; font-size: 12px; line-height: 1.5; }
            h3 { color: #61AFEF; margin-top: 2px; margin-bottom: 2px; }
            code { background: #2C313A; padding: 1px 2px; border-radius: 3px; color: #98C379; }
            .func { color: #C678DD; }
            .note { background: #3E4451; padding: 8px; border-radius: 4px; margin: 8px 0; }
            pre { background: #2C313A; padding: 8px; border-radius: 4px; overflow-x: auto; }
        </style>
        
        <h3>Override Methods</h3>
        <p>Your script can override these methods:</p>
        
        <p><code><span class="func">create_payload</span>(self)</code> → bytes<br>
        Returns the packet payload data to send</p>
        
        <p><code><span class="func">on_packet_sent</span>(self, sequence, payload)</code><br>
        Called after each packet is sent<br>
        <i>sequence</i>: packet number (1-indexed)<br>
        <i>payload</i>: the bytes that were sent</p>
        
        <p><code><span class="func">on_packet_received</span>(self, sequence, payload)</code><br>
        Called when a packet is received<br>
        <i>sequence</i>: receive count (1-indexed)<br>
        <i>payload</i>: received bytes</p>
        
        <div class="note">
        <b>Example on_packet_received:</b>
        <pre>def on_packet_received(self, sequence, payload):
    self.log(f"Received #{sequence}: {len(payload)} bytes")
    try:
        text = payload.decode('utf-8')
        self.log(f"  Content: {text}")
    except UnicodeDecodeError:
        self.log(f"  Hex: {payload.hex()}")</pre>
        </div>
        
        <h3>Available Methods</h3>
        <p><code>self.log(message)</code> - Print to console<br>
        <code>self.get_stats()</code> - Get packet stats</p>
        
        <h3>Available Variables</h3>
        <p><code>self.target_address</code> - Target IP<br>
        <code>self.target_port</code> - Target port<br>
        <code>self.packets_sent</code> - Send count<br>
        <code>self.bytes_sent</code> - Bytes sent<br>
        <code>self.packets_received</code> - Receive count</p>
        
        <h3>Payload Examples</h3>
        <p><b>String:</b> <code>b'Hello World'</code></p>
        <p><b>Hex:</b> <code>bytes.fromhex('DEADBEEF')</code></p>
        <p><b>JSON:</b> <code>json.dumps({'temp': 23.5}).encode()</code></p>
        <p><b>Struct:</b> <code>struct.pack('!HI', 1, 12345)</code></p>
        
        <div class="note">
        <b>💡 Tip:</b> Use <code>self.log()</code> for debug output.
        It will appear in the simulation console.
        </div>
        """
    
    def _connect_signals(self):
        self._editor.textChanged.connect(self._on_text_changed)
    
    def _on_text_changed(self):
        if not self._modified:
            self._modified = True
            self.setWindowTitle(f"Socket Application Editor - {self._node.name} *")
    
    def _update_status(self, message: str, is_error: bool = False):
        color = "#EF4444" if is_error else "#636D83"
        self._status_bar.setStyleSheet(f"""
            QStatusBar {{
                background: #21252B;
                color: {color};
                border-top: 1px solid #181A1F;
            }}
        """)
        self._status_bar.showMessage(message)
    
    def _load_or_generate_script(self):
        """Load existing script from node or generate from template."""
        if self._node.app_script:
            self._editor.setPlainText(self._node.app_script)
            self._update_status(f"Loaded script for {self._node.name}")
            self._modified = False
        else:
            self._generate_template()
            self._update_status("Generated new template - edit and save to attach to node")
    
    def _sanitize_class_name(self, name: str) -> str:
        """Convert a name to a valid Python class name."""
        import re
        # Replace non-alphanumeric with underscore
        clean = re.sub(r'[^a-zA-Z0-9]', '_', name)
        # Split and capitalize each part
        parts = clean.split('_')
        return ''.join(part.capitalize() for part in parts if part)
    
    def _generate_template(self):
        """Generate script template based on node type."""
        # Generate a simple template that extends ApplicationBase
        template = self._generate_sender_template(
            protocol='UDP',
            remote_addr='10.1.1.2',
            port=9000,
            payload_size=512,
            payload_type='pattern',
            payload_data='',
            send_count=10,
            send_interval=1.0
        )
        
        self._editor.setPlainText(template)
        self._modified = True
    
    def _generate_sender_template(
        self, protocol: str, remote_addr: str, port: int,
        payload_size: int, payload_type: str, payload_data: str,
        send_count: int, send_interval: float
    ) -> str:
        # Generate class name from node name
        class_name = self._sanitize_class_name(self._node.name) + "App"
        node_name = self._node.name
        
        return f'''"""
Socket Application: {node_name}
Protocol: UDP
Target: (configured at runtime)

This class extends ApplicationBase to implement custom traffic generation.
Override create_payload() to customize what data is sent in each packet.

The ApplicationBase handles:
- Socket creation and connection
- Scheduled packet transmission at send_interval
- Start/stop timing

You just need to define what payload to send!
"""

from app_base import ApplicationBase


class {class_name}(ApplicationBase):
    """
    Custom socket application for {node_name}.
    """
    
    def on_setup(self):
        """Called during setup. Initialize your state here."""
        self.message_counter = 0
    
    def create_payload(self) -> bytes:
        """
        Generate the payload for each packet.
        
        This is called before each packet is sent.
        Return the bytes you want to transmit.
        """
        self.message_counter += 1
        
        # Simple "Hello World" message with counter
        message = f"Hello World #{{self.message_counter}} from {node_name}"
        return message.encode('utf-8')
    
    def on_packet_sent(self, sequence: int, payload: bytes):
        """Called after each packet is sent. Good for logging."""
        self.log(f"Sent packet #{{sequence}}: {{len(payload)}} bytes")
    
    def on_packet_received(self, sequence: int, payload: bytes):
        """
        Called when a packet is received.
        
        Args:
            sequence: Receive sequence number (1-indexed)
            payload: The received data as bytes
        """
        # Log the received data to the simulation console
        self.log(f"Received packet #{{sequence}}: {{len(payload)}} bytes")
        
        # Try to decode as UTF-8 text
        try:
            text = payload.decode('utf-8')
            self.log(f"  Content: {{text}}")
        except UnicodeDecodeError:
            # Binary data - show as hex
            self.log(f"  Hex: {{payload.hex()}}")
    
    def on_stop(self):
        """Called when application stops. Print final stats."""
        self.log(f"Finished! Sent {{self.packets_sent}} packets, {{self.bytes_sent}} bytes")
'''
    
    def _generate_receiver_template(self, protocol: str, port: int) -> str:
        # Generate class name from node name  
        class_name = self._sanitize_class_name(self._node.name) + "App"
        
        return f'''"""
Socket Application: {self._node.name}
Role: Receiver
Protocol: {protocol}
Listen Port: {port}

This class extends ApplicationBase to implement custom packet receiving.
Note: Receivers typically use ns-3's PacketSink helper, but you can
extend this to implement custom response logic.
"""

from app_base import ApplicationBase
import json


class {class_name}(ApplicationBase):
    """
    Custom receiver application for {self._node.name}.
    
    Extends ApplicationBase to provide custom receive handling.
    Note: This template is for reference - receivers are usually
    implemented using ns-3's PacketSink helper in the generated code.
    """
    
    def on_setup(self):
        """Initialize receiver state."""
        self.log("Receiver initialized")
    
    def on_start(self):
        """Called when the receiver starts."""
        self.log(f"Receiver started on port {{self.target_port}}")
    
    def on_stop(self):
        """Called when the receiver stops."""
        stats = self.get_stats()
        self.log(f"Receiver stopped - received {{stats['packets_received']}} packets")
    
    def create_payload(self) -> bytes:
        """
        Receivers typically don't send packets.
        This returns empty for compatibility.
        """
        return b''
    
    def on_packet_received(self, sequence: int, payload: bytes):
        """
        Process a received packet.
        
        Args:
            sequence: Receive sequence number (1-indexed)
            payload: The received data
        """
        self.log(f"Received packet #{{sequence}}: {{len(payload)}} bytes")
        
        # Example: Parse JSON payload
        try:
            data = json.loads(payload.decode('utf-8'))
            self.log(f"  Parsed JSON: {{data}}")
            
            # Example: Process sensor reading
            if 'seq' in data:
                self.log(f"  Sequence: {{data['seq']}}")
                
            # Check for alerts
            self.process_data(data)
        except json.JSONDecodeError:
            # Not JSON, try to decode as string
            try:
                text = payload.decode('utf-8')
                self.log(f"  Text: {{text[:50]}}...")
            except:
                # Binary data
                self.log(f"  Binary: {{payload[:20].hex()}}...")
    
    # =========================================================================
    # Custom processing methods
    # =========================================================================
    
    def process_data(self, data: dict):
        """Process received data and check thresholds."""
        temp = data.get('temperature', 0)
        if temp > 30:
            self.log(f"  ⚠️ High temperature alert: {{temp}}°C")
'''
    
    def _reset_to_template(self):
        """Reset editor to fresh template."""
        reply = QMessageBox.question(
            self, "Reset Template",
            "This will replace all code with a fresh template.\n\nContinue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self._generate_template()
            self._update_status("Template reset")
    
    def _validate_script(self):
        """Validate the Python script for syntax errors."""
        code = self._editor.toPlainText()
        
        try:
            compile(code, f"{self._node.name}_app.py", 'exec')
            
            # Check for required class/methods
            if 'class ' not in code or 'ApplicationBase' not in code:
                self._update_status(
                    "Warning: Script should define a class extending ApplicationBase", 
                    is_error=True
                )
                QMessageBox.warning(
                    self, "Validation Warning",
                    "Script should define a class that extends ApplicationBase.\n\n"
                    "Example:\n"
                    "class MyApp(ApplicationBase):\n"
                    "    def create_payload(self) -> bytes:\n"
                    "        return b'Hello'"
                )
            elif 'def create_payload' not in code:
                self._update_status(
                    "Warning: Missing create_payload() method", 
                    is_error=True
                )
                QMessageBox.warning(
                    self, "Validation Warning",
                    "Script should include a create_payload() method.\n\n"
                    "This method returns the bytes to send for each packet."
                )
            else:
                self._update_status("✓ Script is valid")
                QMessageBox.information(
                    self, "Validation Passed",
                    "Script is valid and contains the expected structure."
                )
                
        except SyntaxError as e:
            self._update_status(f"Syntax error: {e}", is_error=True)
            QMessageBox.critical(
                self, "Syntax Error",
                f"Line {e.lineno}: {e.msg}\n\n{e.text}"
            )
    
    def _save_script(self) -> bool:
        """Save the script to node.app_script."""
        code = self._editor.toPlainText()
        
        try:
            # Validate syntax first
            compile(code, f"{self._node.name}_app.py", 'exec')
            
            # Save to node
            self._node.app_script = code
            
            self._modified = False
            self.setWindowTitle(f"Socket Application Editor - {self._node.name}")
            self._update_status(f"Saved script for {self._node.name}")
            
            # Emit signal with script content
            self.scriptSaved.emit(self._node.id, code)
            
            return True
            
        except SyntaxError as e:
            self._update_status(f"Syntax error - not saved: {e}", is_error=True)
            QMessageBox.critical(
                self, "Cannot Save",
                f"Script has syntax errors:\n\nLine {e.lineno}: {e.msg}"
            )
            return False
        except Exception as e:
            self._update_status(f"Save error: {e}", is_error=True)
            QMessageBox.critical(self, "Save Error", str(e))
            return False
    
    def _on_cancel(self):
        """Handle cancel button."""
        if self._modified:
            reply = QMessageBox.question(
                self, "Unsaved Changes",
                "You have unsaved changes. Discard them?",
                QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel
            )
            if reply != QMessageBox.StandardButton.Discard:
                return
        
        self.reject()
    
    def _on_save_and_close(self):
        """Save and close dialog."""
        if self._save_script():
            self.accept()
    
    def closeEvent(self, event):
        """Handle window close."""
        if self._modified:
            reply = QMessageBox.question(
                self, "Unsaved Changes",
                "Save changes before closing?",
                QMessageBox.StandardButton.Save | 
                QMessageBox.StandardButton.Discard | 
                QMessageBox.StandardButton.Cancel
            )
            
            if reply == QMessageBox.StandardButton.Save:
                if self._save_script():
                    event.accept()
                else:
                    event.ignore()
            elif reply == QMessageBox.StandardButton.Discard:
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()
    
    @property
    def script_path(self) -> str:
        """Get the script file path."""
        return self._script_path

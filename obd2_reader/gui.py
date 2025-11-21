"""Main GUI application for OBD2 reader."""

import sys
import time
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTreeWidget, QTreeWidgetItem, QTreeWidgetItemIterator,
    QTextEdit, QSplitter, QGroupBox, QComboBox, QLineEdit
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject
from typing import Dict, Set, Optional

from .obd2_interface import OBD2Interface
from .pid_definitions import get_all_pids, get_pid_by_id, decode_pid


class OBD2SignalEmitter(QObject):
    """Qt signal emitter for OBD2 messages (thread-safe communication)."""
    data_received = pyqtSignal(str, str)


class PIDMetadata:
    """Store metadata about received PID data."""
    def __init__(self):
        self.last_timestamp: float = 0
        self.count: int = 0
        self.decoded_value: Optional[str] = None


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self):
        super().__init__()
        self.obd2_interface = OBD2Interface()
        self.signal_emitter = OBD2SignalEmitter()
        self.selected_pid_ids: Set[str] = set()
        self.pid_metadata: Dict[str, PIDMetadata] = {}
        self.all_pids = list(get_all_pids().values())

        self.init_ui()
        self.setup_connections()

        # Update timer for GUI refresh
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_live_data_display)
        self.update_timer.setInterval(100)  # Update every 100ms

    def init_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle("OBD2 Reader")
        self.setGeometry(100, 100, 1200, 800)

        # Central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        # Splitter for left panel and data display
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left side: Control panel + PID list
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)

        control_panel = self.create_control_panel()
        left_layout.addWidget(control_panel)

        pid_list_group = self.create_pid_list_panel()
        left_layout.addWidget(pid_list_group)

        splitter.addWidget(left_panel)

        # Right: Live data display
        data_display_group = self.create_data_display_panel()
        splitter.addWidget(data_display_group)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        main_layout.addWidget(splitter)

        # Status bar
        self.statusBar().showMessage("Ready - Select COM port to begin")

    def create_control_panel(self) -> QGroupBox:
        """Create the control panel."""
        group = QGroupBox("Configuration")
        layout = QVBoxLayout()

        # COM port selection
        port_layout = QHBoxLayout()
        port_layout.addWidget(QLabel("COM Port:"))
        self.port_combo = QComboBox()
        self.refresh_ports()
        port_layout.addWidget(self.port_combo, 1)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh_ports)
        port_layout.addWidget(refresh_btn)
        layout.addLayout(port_layout)

        # Baudrate selection
        baudrate_layout = QHBoxLayout()
        baudrate_layout.addWidget(QLabel("Baudrate:"))
        self.baudrate_combo = QComboBox()
        self.baudrate_combo.addItems([
            "9600", "19200", "38400", "57600", "115200", "230400"
        ])
        self.baudrate_combo.setCurrentText("38400")
        baudrate_layout.addWidget(self.baudrate_combo, 1)
        layout.addLayout(baudrate_layout)

        # Connect/Disconnect button
        self.connect_button = QPushButton("Connect")
        self.connect_button.clicked.connect(self.toggle_connection)
        layout.addWidget(self.connect_button)

        group.setLayout(layout)
        return group

    def create_pid_list_panel(self) -> QGroupBox:
        """Create the PID list panel with checkboxes."""
        group = QGroupBox("Available PIDs")
        layout = QVBoxLayout()

        # Search bar
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Search:"))
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Filter PIDs by ID or name...")
        self.search_box.textChanged.connect(self.filter_pids)
        search_layout.addWidget(self.search_box)
        layout.addLayout(search_layout)

        self.pid_tree = QTreeWidget()
        self.pid_tree.setHeaderLabels(["PID", "Description"])
        self.pid_tree.setColumnWidth(0, 100)
        self.pid_tree.itemChanged.connect(self.on_pid_selection_changed)
        layout.addWidget(self.pid_tree)

        # Populate PID tree
        self.populate_pid_list()

        # Select all/none buttons
        button_layout = QHBoxLayout()
        select_all_btn = QPushButton("Select All")
        select_all_btn.clicked.connect(self.select_all_pids)
        select_none_btn = QPushButton("Select None")
        select_none_btn.clicked.connect(self.select_no_pids)
        button_layout.addWidget(select_all_btn)
        button_layout.addWidget(select_none_btn)
        layout.addLayout(button_layout)

        group.setLayout(layout)
        return group

    def create_data_display_panel(self) -> QGroupBox:
        """Create the live data display panel."""
        group = QGroupBox("Live Data")
        layout = QVBoxLayout()

        self.data_display = QTextEdit()
        self.data_display.setReadOnly(True)
        self.data_display.setFontFamily("Courier New")
        layout.addWidget(self.data_display)

        # Clear button
        clear_btn = QPushButton("Clear Display")
        clear_btn.clicked.connect(self.data_display.clear)
        layout.addWidget(clear_btn)

        group.setLayout(layout)
        return group

    def setup_connections(self):
        """Setup signal/slot connections."""
        self.signal_emitter.data_received.connect(self.on_obd2_data_received)

    def refresh_ports(self):
        """Refresh the list of available COM ports."""
        current_text = self.port_combo.currentText()
        self.port_combo.clear()

        ports = OBD2Interface.get_available_ports()
        if ports:
            self.port_combo.addItems(ports)
            # Try to restore previous selection
            index = self.port_combo.findText(current_text)
            if index >= 0:
                self.port_combo.setCurrentIndex(index)
        else:
            self.port_combo.addItem("No ports found")

    def populate_pid_list(self):
        """Populate the PID tree with available PIDs organized by service."""
        self.filter_pids()

    def filter_pids(self):
        """Filter the PID tree based on search text."""
        search_text = self.search_box.text().lower() if hasattr(self, 'search_box') else ""

        # Temporarily disconnect the itemChanged signal
        self.pid_tree.itemChanged.disconnect(self.on_pid_selection_changed)

        self.pid_tree.clear()

        # Create "Service 01" category for Show Current Data PIDs
        service_01_item = QTreeWidgetItem(self.pid_tree, ["Service 01", "Show Current Data"])
        service_01_item.setFlags(service_01_item.flags() | Qt.ItemFlag.ItemIsAutoTristate | Qt.ItemFlag.ItemIsUserCheckable)

        # Group PIDs by service
        service_01_pids = [pid for pid in self.all_pids if pid.mode == "01"]

        # Add PIDs under the category
        for pid_def in sorted(service_01_pids, key=lambda p: p.pid):
            # Filter by PID ID or name
            pid_id_str = pid_def.full_id.lower()
            pid_name = pid_def.name.lower()

            if search_text in pid_id_str or search_text in pid_name or not search_text:
                item = QTreeWidgetItem(service_01_item, [pid_def.full_id, pid_def.name])
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)

                # Preserve checked state if this PID was previously selected
                if pid_def.full_id in self.selected_pid_ids:
                    item.setCheckState(0, Qt.CheckState.Checked)
                else:
                    item.setCheckState(0, Qt.CheckState.Unchecked)

                item.setData(0, Qt.ItemDataRole.UserRole, pid_def.full_id)

        # Expand the category by default
        service_01_item.setExpanded(True)

        # Reconnect the signal
        self.pid_tree.itemChanged.connect(self.on_pid_selection_changed)

    def select_all_pids(self):
        """Select all PIDs in the tree."""
        iterator = QTreeWidgetItemIterator(self.pid_tree)
        while iterator.value():
            item = iterator.value()
            # Only check items that have PID data (not category headers)
            if item.data(0, Qt.ItemDataRole.UserRole):
                item.setCheckState(0, Qt.CheckState.Checked)
            iterator += 1

    def select_no_pids(self):
        """Deselect all PIDs in the tree."""
        iterator = QTreeWidgetItemIterator(self.pid_tree)
        while iterator.value():
            item = iterator.value()
            # Only uncheck items that have PID data (not category headers)
            if item.data(0, Qt.ItemDataRole.UserRole):
                item.setCheckState(0, Qt.CheckState.Unchecked)
            iterator += 1

    def on_pid_selection_changed(self, item: QTreeWidgetItem, column: int):
        """Handle PID checkbox state changes."""
        pid_id = item.data(0, Qt.ItemDataRole.UserRole)

        # Skip category items (they don't have PID data)
        if not pid_id:
            return

        if item.checkState(0) == Qt.CheckState.Checked:
            self.selected_pid_ids.add(pid_id)
        else:
            self.selected_pid_ids.discard(pid_id)

    def toggle_connection(self):
        """Connect or disconnect from OBD2 adapter."""
        if not self.obd2_interface.is_connected:
            port = self.port_combo.currentText()

            if port == "No ports found":
                self.statusBar().showMessage("No COM ports available")
                return

            baudrate = int(self.baudrate_combo.currentText())

            if self.obd2_interface.connect(port, baudrate):
                self.connect_button.setText("Disconnect")
                self.port_combo.setEnabled(False)
                self.baudrate_combo.setEnabled(False)

                # Build list of PIDs to monitor
                pids_to_monitor = []
                for pid_id in self.selected_pid_ids:
                    pid_def = get_pid_by_id(pid_id)
                    if pid_def:
                        pids_to_monitor.append((pid_def.mode, pid_def.pid, pid_def.name))

                if pids_to_monitor:
                    self.obd2_interface.start_receiving(self.obd2_data_callback, pids_to_monitor)
                    self.update_timer.start()
                    self.statusBar().showMessage(f"Connected to {port} at {baudrate} bps - Monitoring {len(pids_to_monitor)} PIDs")
                else:
                    self.statusBar().showMessage(f"Connected to {port} - No PIDs selected for monitoring")
            else:
                self.statusBar().showMessage("Failed to connect to OBD2 adapter")
        else:
            self.obd2_interface.disconnect()
            self.update_timer.stop()
            self.connect_button.setText("Connect")
            self.port_combo.setEnabled(True)
            self.baudrate_combo.setEnabled(True)
            self.statusBar().showMessage("Disconnected")

    def obd2_data_callback(self, pid_id: str, raw_data: str):
        """Callback for received OBD2 data (called from OBD2 thread)."""
        # Emit signal to handle in GUI thread
        self.signal_emitter.data_received.emit(pid_id, raw_data)

    def on_obd2_data_received(self, pid_id: str, raw_data: str):
        """Handle received OBD2 data in GUI thread."""
        # Only process PIDs that are selected
        if pid_id not in self.selected_pid_ids:
            return

        # Create metadata entry if it doesn't exist
        if pid_id not in self.pid_metadata:
            self.pid_metadata[pid_id] = PIDMetadata()

        # Update metadata
        metadata = self.pid_metadata[pid_id]
        metadata.last_timestamp = time.time()
        metadata.count += 1

        # Decode the PID data
        decoded = decode_pid(pid_id, raw_data)
        if decoded:
            metadata.decoded_value = decoded

    def update_live_data_display(self):
        """Update the live data display with cached PID data."""
        if not self.pid_metadata:
            return

        current_time = time.time()
        output_lines = []

        for pid_id in sorted(self.selected_pid_ids):
            if pid_id in self.pid_metadata:
                metadata = self.pid_metadata[pid_id]
                pid_def = get_pid_by_id(pid_id)

                if pid_def and metadata.decoded_value is not None:
                    # Calculate time since last update
                    time_since = current_time - metadata.last_timestamp

                    # Header with PID info
                    output_lines.append(f"=== {pid_def.full_id} - {pid_def.name} ===")
                    output_lines.append(f"  Count: {metadata.count} | Last: {time_since:.2f}s ago")

                    # Decoded value with unit
                    output_lines.append(f"  Value: {metadata.decoded_value} {pid_def.unit}")
                    output_lines.append("")

        # Save current scroll position
        scrollbar = self.data_display.verticalScrollBar()
        current_scroll_position = scrollbar.value()
        is_at_bottom = current_scroll_position >= scrollbar.maximum() - 10

        # Update content
        self.data_display.setPlainText("\n".join(output_lines))

        # Restore scroll position (or stick to bottom if user was at bottom)
        if is_at_bottom:
            scrollbar.setValue(scrollbar.maximum())
        else:
            scrollbar.setValue(current_scroll_position)

    def closeEvent(self, event):
        """Handle application close."""
        if self.obd2_interface.is_connected:
            self.obd2_interface.disconnect()
        event.accept()


def main():
    """Main entry point for the GUI application."""
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

"""Main GUI application for OBD2 reader."""

import sys
import time
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTreeWidget, QTreeWidgetItem, QTreeWidgetItemIterator,
    QTextEdit, QSplitter, QGroupBox, QComboBox, QLineEdit, QMessageBox, QDialog,
    QFormLayout, QDialogButtonBox, QStackedWidget, QProgressDialog
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject, QThread
from typing import Dict, Set, Optional, List
from collections import deque
import pyqtgraph as pg

from .obd2_interface import OBD2Interface
from .pid_definitions import get_all_pids, get_pid_by_id, decode_pid

# ============================================================================
# DEBUG MODE
# Set DEBUG = True to enable detailed print statements to the terminal
# Set DEBUG = False to disable all terminal output (default)
# ============================================================================
DEBUG = False


class ConnectionWorker(QThread):
    """Worker thread for connecting to OBD2 adapter."""
    progress = pyqtSignal(str)  # Progress messages
    finished = pyqtSignal(bool)  # Success/failure

    def __init__(self, obd2_interface, port: str, baudrate: int):
        super().__init__()
        self.obd2_interface = obd2_interface
        self.port = port
        self.baudrate = baudrate

    def run(self):
        """Run the connection process in background thread."""
        try:
            import serial

            self.progress.emit(f"Opening serial port {self.port} at {self.baudrate} bps...")

            # Open serial port
            self.obd2_interface.serial_port = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=1,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                bytesize=serial.EIGHTBITS
            )

            self.progress.emit("Port opened successfully. Waiting for adapter initialization...")
            time.sleep(2)

            # Reset adapter (ATZ)
            self.progress.emit("Sending ATZ (Reset adapter)...")
            response = self._send_command_with_progress("ATZ")
            if response:
                self.progress.emit(f"ATZ Response: {response}")
            time.sleep(1)

            # Disable echo (ATE0)
            self.progress.emit("Sending ATE0 (Disable echo)...")
            response = self._send_command_with_progress("ATE0")
            if response:
                self.progress.emit(f"ATE0 Response: {response}")

            # Set protocol to auto (ATSP0)
            self.progress.emit("Sending ATSP0 (Set protocol to auto)...")
            response = self._send_command_with_progress("ATSP0")
            if response:
                self.progress.emit(f"ATSP0 Response: {response}")

            self.obd2_interface.is_connected = True
            self.progress.emit("Connection successful!")
            self.finished.emit(True)

        except Exception as e:
            self.progress.emit(f"Connection failed: {e}")
            if self.obd2_interface.serial_port and self.obd2_interface.serial_port.is_open:
                self.obd2_interface.serial_port.close()
            self.finished.emit(False)

    def _send_command_with_progress(self, command: str) -> str:
        """Send command and return response."""
        if not self.obd2_interface.serial_port or not self.obd2_interface.serial_port.is_open:
            return ""

        try:
            # Clear input buffer
            self.obd2_interface.serial_port.reset_input_buffer()

            # Send command
            self.obd2_interface.serial_port.write((command + "\r").encode())

            # Read response
            response = ""
            start_time = time.time()
            timeout = 5.0

            while time.time() - start_time < timeout:
                if self.obd2_interface.serial_port.in_waiting > 0:
                    chunk = self.obd2_interface.serial_port.read(
                        self.obd2_interface.serial_port.in_waiting
                    ).decode('utf-8', errors='ignore')
                    response += chunk
                    if ">" in response:
                        break
                time.sleep(0.01)

            # Clean up response: remove echo, prompt character, and extra whitespace
            response = response.replace(command, "").replace(">", "").strip()
            # Remove any line breaks and consolidate whitespace
            response = " ".join(response.split())

            return response
        except Exception as e:
            return f"Error: {e}"


class ScanWorker(QThread):
    """Worker thread for scanning vehicle PIDs."""
    progress = pyqtSignal(str)  # Progress messages
    finished = pyqtSignal(list)  # List of supported PIDs

    def __init__(self, obd2_interface, services: List[str]):
        super().__init__()
        self.obd2_interface = obd2_interface
        self.services = services

    def run(self):
        """Run the scan process in background thread."""
        try:
            supported_pids = self.obd2_interface.scan_supported_pids(
                services=self.services,
                progress_callback=self.progress.emit
            )
            self.finished.emit(supported_pids)
        except Exception as e:
            self.progress.emit(f"Scan error: {e}")
            self.finished.emit([])


class OBD2SignalEmitter(QObject):
    """Qt signal emitter for OBD2 messages (thread-safe communication)."""
    data_received = pyqtSignal(str, str)


class PIDMetadata:
    """Store metadata about received PID data."""
    def __init__(self):
        self.last_timestamp: float = 0
        self.count: int = 0
        self.decoded_value: Optional[str] = None
        self.value_history: deque = deque(maxlen=300)  # 30 seconds at 10Hz
        self.time_history: deque = deque(maxlen=300)  # Corresponding timestamps (absolute time.time())
        self.start_time: Optional[float] = None  # Time of first data point


class GraphSelectionDialog(QDialog):
    """Dialog for selecting PIDs to graph (1-8 PIDs)."""

    def __init__(self, parent=None, available_pids=None, currently_selected=None):
        super().__init__(parent)
        self.setWindowTitle("Select PIDs to Graph")
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)

        self.available_pids = available_pids or []
        self.selected_pids = set(currently_selected or [])

        self.init_ui()

    def init_ui(self):
        """Initialize the graph selection dialog UI."""
        layout = QVBoxLayout(self)

        # Instructions
        instruction_label = QLabel("Select 1-8 PIDs to graph:")
        instruction_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(instruction_label)

        # PID list with checkboxes
        self.pid_tree = QTreeWidget()
        self.pid_tree.setHeaderLabels(["PID", "Description"])
        self.pid_tree.setColumnWidth(0, 100)
        self.pid_tree.itemChanged.connect(self.on_selection_changed)

        # Sort PIDs by their ID (e.g., 0104, 0105, etc.) in ascending order
        sorted_pids = sorted(self.available_pids, key=lambda p: p.full_id)

        # Populate with available PIDs in sorted order
        for pid_def in sorted_pids:
            item = QTreeWidgetItem(self.pid_tree, [pid_def.full_id, pid_def.name])
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            if pid_def.full_id in self.selected_pids:
                item.setCheckState(0, Qt.CheckState.Checked)
            else:
                item.setCheckState(0, Qt.CheckState.Unchecked)
            item.setData(0, Qt.ItemDataRole.UserRole, pid_def.full_id)

        layout.addWidget(self.pid_tree)

        # Selection count label
        self.count_label = QLabel(f"Selected: {len(self.selected_pids)}/8")
        layout.addWidget(self.count_label)

        # Dialog buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self.update_count_label()

    def on_selection_changed(self, item, _column):
        """Handle PID selection changes."""
        pid_id = item.data(0, Qt.ItemDataRole.UserRole)

        if item.checkState(0) == Qt.CheckState.Checked:
            if len(self.selected_pids) < 8:
                self.selected_pids.add(pid_id)
            else:
                # Prevent checking more than 8
                item.setCheckState(0, Qt.CheckState.Unchecked)
                QMessageBox.warning(self, "Maximum Reached", "You can only select up to 8 PIDs for graphing.")
        else:
            self.selected_pids.discard(pid_id)

        self.update_count_label()

    def update_count_label(self):
        """Update the selection count label."""
        self.count_label.setText(f"Selected: {len(self.selected_pids)}/8")

    def get_selected_pids(self):
        """Get the list of selected PID IDs."""
        return list(self.selected_pids)


class GraphWindow(QMainWindow):
    """Separate window for displaying graphs in 4x2 grid layout."""

    def __init__(self, parent=None, selected_pids=None):
        super().__init__(parent)
        self.setWindowTitle("OBD2 Live Graphs")
        self.setGeometry(150, 150, 1400, 900)

        self.selected_pids = selected_pids or []
        self.graph_plots: Dict[str, pg.PlotDataItem] = {}

        self.init_ui()

    def init_ui(self):
        """Initialize the graph window UI."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Create graph widget with grid layout
        self.graph_widget = pg.GraphicsLayoutWidget()
        self.graph_widget.setBackground('w')
        layout.addWidget(self.graph_widget)

        # Setup graphs in 4x2 grid (4 columns, 2 rows)
        self.setup_graphs()

    def setup_graphs(self):
        """Setup graph plots in 4x2 grid layout."""
        self.graph_widget.clear()
        self.graph_plots.clear()

        # Calculate grid positions for up to 8 graphs
        # Layout: 4 columns x 2 rows
        for i, pid_id in enumerate(self.selected_pids[:8]):  # Max 8 graphs
            row = i // 4  # 0 or 1
            col = i % 4   # 0, 1, 2, or 3

            pid_def = get_pid_by_id(pid_id)
            if not pid_def:
                continue

            # Create plot at grid position
            plot = self.graph_widget.addPlot(row=row, col=col)
            plot.setLabel('left', pid_def.name, units=pid_def.unit)
            plot.setLabel('bottom', 'Time', units='s')
            plot.showGrid(x=True, y=True)
            plot.setTitle(f"{pid_def.full_id} - {pid_def.name}")

            # Disable mouse interaction - lock the view
            plot.setMouseEnabled(x=False, y=False)  # Disable panning and zooming
            plot.setMenuEnabled(False)  # Disable right-click menu

            # Disable auto-range on X-axis, enable on Y-axis
            plot.enableAutoRange(axis='x', enable=False)
            plot.enableAutoRange(axis='y', enable=True)

            # Set strict X-axis range with no padding
            plot.setXRange(-30, 0, padding=0)
            plot.getViewBox().setLimits(xMin=-30, xMax=0)  # Hard limits

            # Create plot data item
            curve = plot.plot(pen=pg.mkPen(color='b', width=2))
            self.graph_plots[pid_id] = curve

    def update_graphs(self, pid_metadata):
        """Update all graphs with latest data."""
        # Find the most recent timestamp across all PIDs for synchronization
        reference_time = None
        for pid_id in self.selected_pids:
            if pid_id in pid_metadata:
                metadata = pid_metadata[pid_id]
                if metadata.time_history:
                    latest = metadata.time_history[-1]
                    if reference_time is None or latest > reference_time:
                        reference_time = latest

        if reference_time is None:
            return

        # Update all graphs using the common reference time
        for pid_id in self.selected_pids:
            if pid_id not in pid_metadata:
                if DEBUG:
                    print(f"[GraphWindow] No metadata for {pid_id}")
                continue

            if pid_id not in self.graph_plots:
                if DEBUG:
                    print(f"[GraphWindow] No plot for {pid_id}")
                continue

            metadata = pid_metadata[pid_id]
            if not metadata.time_history or not metadata.value_history or metadata.start_time is None:
                if DEBUG:
                    print(f"[GraphWindow] No history data for {pid_id} (time: {len(metadata.time_history)}, values: {len(metadata.value_history)})")
                continue

            # Convert deques to lists for plotting
            absolute_times = list(metadata.time_history)
            values = list(metadata.value_history)

            # Calculate relative times from the COMMON reference time
            # This synchronizes all graphs to show data at the same time alignment
            if absolute_times:
                # Convert absolute times to relative times using common reference
                relative_times = [t - reference_time for t in absolute_times]

                # Update plot data
                curve = self.graph_plots[pid_id]
                curve.setData(relative_times, values)
                if DEBUG:
                    print(f"[GraphWindow] Updated {pid_id}: {len(values)} points, latest value: {values[-1]}")


class SettingsDialog(QDialog):
    """Settings dialog for unit preferences."""

    def __init__(self, parent=None, current_settings=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(400)

        # Default settings
        self.settings = current_settings or {
            'speed_unit': 'mph',
            'temperature_unit': 'f',
            'pressure_unit': 'psi',
            'distance_unit': 'miles',
            'fuel_unit': 'mpg'
        }

        self.init_ui()

    def init_ui(self):
        """Initialize the settings dialog UI."""
        layout = QVBoxLayout(self)

        # Create form layout for settings
        form_layout = QFormLayout()

        # Speed unit
        self.speed_combo = QComboBox()
        self.speed_combo.addItems(["MPH", "KPH"])
        self.speed_combo.setCurrentText(self.settings['speed_unit'].upper())
        form_layout.addRow("Speed Unit:", self.speed_combo)

        # Temperature unit
        self.temp_combo = QComboBox()
        self.temp_combo.addItems(["F (Fahrenheit)", "C (Celsius)"])
        current_temp = "F (Fahrenheit)" if self.settings['temperature_unit'] == 'f' else "C (Celsius)"
        self.temp_combo.setCurrentText(current_temp)
        form_layout.addRow("Temperature Unit:", self.temp_combo)

        # Pressure unit
        self.pressure_combo = QComboBox()
        self.pressure_combo.addItems(["PSI", "kPa", "bar"])
        self.pressure_combo.setCurrentText(self.settings['pressure_unit'].upper())
        form_layout.addRow("Pressure Unit:", self.pressure_combo)

        # Distance unit
        self.distance_combo = QComboBox()
        self.distance_combo.addItems(["Miles", "Kilometers"])
        self.distance_combo.setCurrentText(self.settings['distance_unit'].capitalize())
        form_layout.addRow("Distance Unit:", self.distance_combo)

        # Fuel economy unit
        self.fuel_combo = QComboBox()
        self.fuel_combo.addItems(["MPG (US)", "MPG (UK)", "L/100km"])
        if self.settings['fuel_unit'] == 'mpg':
            self.fuel_combo.setCurrentText("MPG (US)")
        elif self.settings['fuel_unit'] == 'mpg_uk':
            self.fuel_combo.setCurrentText("MPG (UK)")
        else:
            self.fuel_combo.setCurrentText("L/100km")
        form_layout.addRow("Fuel Economy Unit:", self.fuel_combo)

        layout.addLayout(form_layout)

        # Dialog buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def get_settings(self):
        """Get the current settings from the dialog."""
        settings = {
            'speed_unit': self.speed_combo.currentText().lower(),
            'temperature_unit': 'f' if 'F' in self.temp_combo.currentText() else 'c',
            'pressure_unit': self.pressure_combo.currentText().lower(),
            'distance_unit': self.distance_combo.currentText().lower(),
            'fuel_unit': 'mpg' if 'US' in self.fuel_combo.currentText() else
                        'mpg_uk' if 'UK' in self.fuel_combo.currentText() else 'l100km'
        }
        return settings


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self):
        super().__init__()
        self.obd2_interface = OBD2Interface()
        self.signal_emitter = OBD2SignalEmitter()
        self.selected_pid_ids: Set[str] = set()
        self.pid_metadata: Dict[str, PIDMetadata] = {}
        self.all_pids = list(get_all_pids().values())
        self.supported_pid_ids: Optional[Set[str]] = None  # None = show nothing, Set = show only supported

        # Unit settings
        self.unit_settings = {
            'speed_unit': 'mph',
            'temperature_unit': 'f',
            'pressure_unit': 'psi',
            'distance_unit': 'miles',
            'fuel_unit': 'mpg'
        }

        # View mode: 'raw', 'graph', or 'dashboard'
        self.current_view_mode = 'raw'
        self.graph_plots: Dict[str, pg.PlotDataItem] = {}  # PID ID -> plot item
        self.graph_window: Optional[GraphWindow] = None  # Separate graph window
        self.graphed_pids: List[str] = []  # PIDs selected for graphing

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

        # Create menu bar
        self.create_menu_bar()

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

    def create_menu_bar(self):
        """Create the menu bar with Connection, Diagnostics, Data, Display, and Help menus."""
        menu_bar = self.menuBar()

        # Connection menu
        connection_menu = menu_bar.addMenu("&Connection")

        # Connect to Vehicle
        connect_action = connection_menu.addAction("Connect to &Vehicle")
        connect_action.setStatusTip("Connect to OBD2 adapter")
        connect_action.triggered.connect(lambda: self.toggle_connection() if not self.obd2_interface.is_connected else None)

        # Disconnect
        disconnect_action = connection_menu.addAction("&Disconnect")
        disconnect_action.setStatusTip("Disconnect from OBD2 adapter")
        disconnect_action.triggered.connect(lambda: self.toggle_connection() if self.obd2_interface.is_connected else None)

        connection_menu.addSeparator()

        # Connection Settings
        settings_action = connection_menu.addAction("Connection &Settings...")
        settings_action.setStatusTip("Configure connection settings")
        settings_action.triggered.connect(self.show_connection_settings)

        # Diagnostics menu
        diagnostics_menu = menu_bar.addMenu("&Diagnostics")

        # Scan Supported PIDs
        scan_pids_action = diagnostics_menu.addAction("&Scan Supported PIDs")
        scan_pids_action.setStatusTip("Scan vehicle for supported PIDs")
        scan_pids_action.triggered.connect(self.scan_vehicle)

        # Read Codes
        read_codes_action = diagnostics_menu.addAction("&Read Codes")
        read_codes_action.setStatusTip("Read diagnostic trouble codes")
        read_codes_action.triggered.connect(self.read_codes)

        # Clear Codes
        clear_codes_action = diagnostics_menu.addAction("&Clear Codes")
        clear_codes_action.setStatusTip("Clear diagnostic trouble codes")
        clear_codes_action.triggered.connect(self.clear_codes)

        # View Freeze Frame
        freeze_frame_action = diagnostics_menu.addAction("View &Freeze Frame")
        freeze_frame_action.setStatusTip("View freeze frame data")
        freeze_frame_action.triggered.connect(self.view_freeze_frame)

        # Readiness Monitors
        readiness_action = diagnostics_menu.addAction("Readiness &Monitors")
        readiness_action.setStatusTip("View readiness monitor status")
        readiness_action.triggered.connect(self.view_readiness_monitors)

        # Data menu
        data_menu = menu_bar.addMenu("D&ata")

        # Live Data Stream
        live_data_action = data_menu.addAction("&Live Data Stream")
        live_data_action.setStatusTip("View live data stream")
        live_data_action.triggered.connect(self.show_live_data)

        data_menu.addSeparator()

        # Start/Stop Recording
        self.recording_action = data_menu.addAction("Start &Recording")
        self.recording_action.setStatusTip("Start recording live data")
        self.recording_action.triggered.connect(self.toggle_recording)

        # View Recordings
        view_recordings_action = data_menu.addAction("&View Recordings...")
        view_recordings_action.setStatusTip("View recorded data sessions")
        view_recordings_action.triggered.connect(self.view_recordings)

        # Export Data
        export_data_action = data_menu.addAction("&Export Data...")
        export_data_action.setStatusTip("Export data to file")
        export_data_action.triggered.connect(self.export_data)

        # Display menu
        display_menu = menu_bar.addMenu("D&isplay")

        # Graph View
        graph_view_action = display_menu.addAction("&Graph View")
        graph_view_action.setStatusTip("Display data as graphs")
        graph_view_action.triggered.connect(self.show_graph_view)

        # Table View
        table_view_action = display_menu.addAction("&Table View")
        table_view_action.setStatusTip("Display data as table")
        table_view_action.triggered.connect(self.show_table_view)

        # Dashboard View
        dashboard_view_action = display_menu.addAction("&Dashboard View")
        dashboard_view_action.setStatusTip("Display data with gauge-style displays")
        dashboard_view_action.triggered.connect(self.show_dashboard_view)

        # Help menu
        help_menu = menu_bar.addMenu("&Help")

        # About action
        about_action = help_menu.addAction("&About")
        about_action.setStatusTip("About OBD2 Reader")
        about_action.triggered.connect(self.show_about)

    def show_connection_settings(self):
        """Show connection settings dialog."""
        dialog = SettingsDialog(self, self.unit_settings)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Update settings
            self.unit_settings = dialog.get_settings()
            if DEBUG:
                print(f"[GUI] Settings updated: {self.unit_settings}")
            self.statusBar().showMessage("Settings updated successfully", 3000)

    def read_codes(self):
        """Read diagnostic trouble codes (placeholder)."""
        QMessageBox.information(self, "Read Codes", "Read diagnostic trouble codes functionality coming soon!")

    def clear_codes(self):
        """Clear diagnostic trouble codes (placeholder)."""
        QMessageBox.information(self, "Clear Codes", "Clear diagnostic trouble codes functionality coming soon!")

    def view_freeze_frame(self):
        """View freeze frame data (placeholder)."""
        QMessageBox.information(self, "Freeze Frame", "View freeze frame functionality coming soon!")

    def view_readiness_monitors(self):
        """View readiness monitor status (placeholder)."""
        QMessageBox.information(self, "Readiness Monitors", "Readiness monitors functionality coming soon!")

    def show_live_data(self):
        """Show live data stream (placeholder)."""
        QMessageBox.information(self, "Live Data Stream", "This is the current view - live data stream is already active!")

    def toggle_recording(self):
        """Toggle data recording on/off (placeholder)."""
        if self.recording_action.text() == "Start &Recording":
            self.recording_action.setText("Stop &Recording")
            self.recording_action.setStatusTip("Stop recording live data")
            QMessageBox.information(self, "Recording", "Data recording started!")
        else:
            self.recording_action.setText("Start &Recording")
            self.recording_action.setStatusTip("Start recording live data")
            QMessageBox.information(self, "Recording", "Data recording stopped!")

    def view_recordings(self):
        """View recorded data sessions (placeholder)."""
        QMessageBox.information(self, "View Recordings", "View recordings functionality coming soon!")

    def export_data(self):
        """Export data to file (placeholder)."""
        QMessageBox.information(self, "Export Data", "Export data functionality coming soon!")

    def show_graph_view(self):
        """Show graph view - opens separate window with currently selected PIDs."""
        # Check if any PIDs are selected in the main window
        if not self.selected_pid_ids:
            QMessageBox.warning(self, "No PIDs Selected",
                              "Please select at least one PID from the Available PIDs list to graph.")
            return

        # Use the currently selected PIDs (up to 8)
        selected_pids = list(self.selected_pid_ids)[:8]

        # Close existing graph window if open
        if self.graph_window:
            self.graph_window.close()

        # Create and show new graph window
        self.graph_window = GraphWindow(self, selected_pids)
        self.graph_window.show()

        if DEBUG:
            print(f"[GUI] Opened graph window with {len(selected_pids)} PIDs: {selected_pids}")

    def show_table_view(self):
        """Show table view (placeholder - same as raw for now)."""
        self.switch_view('raw')

    def show_dashboard_view(self):
        """Show dashboard view with gauges."""
        self.switch_view('dashboard')

    def show_about(self):
        """Show about dialog."""
        about_text = """<h2>OBD2 Reader</h2>
        <p>Version 1.0</p>
        <p>A PyQt6-based GUI application for reading live OBD2 data using ELM327-compatible adapters.</p>
        <p><b>Features:</b></p>
        <ul>
        <li>Real-time OBD2 data monitoring</li>
        <li>Vehicle PID scanning</li>
        <li>Multi-service support (Services 01, 02, 09)</li>
        <li>Dynamic PID selection</li>
        </ul>
        <p>MIT License</p>"""
        QMessageBox.about(self, "About OBD2 Reader", about_text)

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
        self.baudrate_combo.setCurrentText("115200")
        baudrate_layout.addWidget(self.baudrate_combo, 1)
        layout.addLayout(baudrate_layout)

        # Connect/Disconnect button
        self.connect_button = QPushButton("Connect")
        self.connect_button.clicked.connect(self.toggle_connection)
        layout.addWidget(self.connect_button)

        # Scan Vehicle button
        self.scan_button = QPushButton("Scan Vehicle")
        self.scan_button.clicked.connect(self.scan_vehicle)
        self.scan_button.setEnabled(False)  # Disabled until connected
        layout.addWidget(self.scan_button)

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
        self.pid_tree.setColumnWidth(0, 130)
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
        """Create the live data display panel with view switching."""
        group = QGroupBox("Live Data")
        layout = QVBoxLayout()

        # View selector buttons
        view_button_layout = QHBoxLayout()
        self.raw_view_btn = QPushButton("Raw")
        self.graph_view_btn = QPushButton("Graph")
        self.dashboard_view_btn = QPushButton("Dashboard")

        self.raw_view_btn.clicked.connect(lambda: self.switch_view('raw'))
        self.graph_view_btn.clicked.connect(lambda: self.switch_view('graph'))
        self.dashboard_view_btn.clicked.connect(lambda: self.switch_view('dashboard'))

        # Set initial button states
        self.raw_view_btn.setStyleSheet("font-weight: bold;")

        view_button_layout.addWidget(self.raw_view_btn)
        view_button_layout.addWidget(self.graph_view_btn)
        view_button_layout.addWidget(self.dashboard_view_btn)
        view_button_layout.addStretch()
        layout.addLayout(view_button_layout)

        # Stacked widget to hold different views
        self.view_stack = QStackedWidget()

        # Raw text view
        self.data_display = QTextEdit()
        self.data_display.setReadOnly(True)
        self.data_display.setFontFamily("Courier New")
        self.view_stack.addWidget(self.data_display)

        # Graph view
        self.graph_widget = pg.GraphicsLayoutWidget()
        self.graph_widget.setBackground('w')
        self.view_stack.addWidget(self.graph_widget)

        # Dashboard view (placeholder for now)
        self.dashboard_widget = QWidget()
        dashboard_layout = QVBoxLayout(self.dashboard_widget)
        dashboard_label = QLabel("Dashboard view with gauges - Coming soon!")
        dashboard_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dashboard_layout.addWidget(dashboard_label)
        self.view_stack.addWidget(self.dashboard_widget)

        layout.addWidget(self.view_stack)

        # Clear button
        clear_btn = QPushButton("Clear Display")
        clear_btn.clicked.connect(self.clear_display_data)
        layout.addWidget(clear_btn)

        group.setLayout(layout)
        return group

    def switch_view(self, view_mode: str):
        """Switch between different view modes."""
        self.current_view_mode = view_mode

        # Update button styles
        self.raw_view_btn.setStyleSheet("")
        self.graph_view_btn.setStyleSheet("")
        self.dashboard_view_btn.setStyleSheet("")

        if view_mode == 'raw':
            self.view_stack.setCurrentIndex(0)
            self.raw_view_btn.setStyleSheet("font-weight: bold;")
        elif view_mode == 'graph':
            self.view_stack.setCurrentIndex(1)
            self.graph_view_btn.setStyleSheet("font-weight: bold;")
            self.setup_graphs()
        elif view_mode == 'dashboard':
            self.view_stack.setCurrentIndex(2)
            self.dashboard_view_btn.setStyleSheet("font-weight: bold;")

        if DEBUG:
            print(f"[GUI] Switched to {view_mode} view")

    def setup_graphs(self):
        """Setup graph plots for currently selected PIDs."""
        # Clear existing plots
        self.graph_widget.clear()
        self.graph_plots.clear()

        if not self.selected_pid_ids:
            return

        # Create a plot for each selected PID
        for i, pid_id in enumerate(sorted(self.selected_pid_ids)):
            pid_def = get_pid_by_id(pid_id)
            if not pid_def:
                continue

            # Create plot
            plot = self.graph_widget.addPlot(row=i, col=0)
            plot.setLabel('left', pid_def.name, units=pid_def.unit)
            plot.setLabel('bottom', 'Time', units='s')
            plot.showGrid(x=True, y=True)

            # Disable mouse interaction - lock the view
            plot.setMouseEnabled(x=False, y=False)  # Disable panning and zooming
            plot.setMenuEnabled(False)  # Disable right-click menu

            # Disable auto-range on X-axis, enable on Y-axis
            plot.enableAutoRange(axis='x', enable=False)
            plot.enableAutoRange(axis='y', enable=True)

            # Set strict X-axis range with no padding
            plot.setXRange(-30, 0, padding=0)
            plot.getViewBox().setLimits(xMin=-30, xMax=0)  # Hard limits

            # Create plot data item
            curve = plot.plot(pen=pg.mkPen(color='b', width=2))
            self.graph_plots[pid_id] = curve

    def clear_display_data(self):
        """Clear all display data."""
        if self.current_view_mode == 'raw':
            self.data_display.clear()
        elif self.current_view_mode == 'graph':
            # Clear graph data
            for metadata in self.pid_metadata.values():
                metadata.value_history.clear()
                metadata.time_history.clear()
            self.setup_graphs()

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
        """Filter the PID tree based on search text and supported PIDs."""
        search_text = self.search_box.text().lower() if hasattr(self, 'search_box') else ""

        # Temporarily disconnect the itemChanged signal
        self.pid_tree.itemChanged.disconnect(self.on_pid_selection_changed)

        self.pid_tree.clear()

        # If no scan has been performed yet, show nothing
        if self.supported_pid_ids is None:
            self.pid_tree.itemChanged.connect(self.on_pid_selection_changed)
            return

        # Create "Service 01" category for Show Current Data PIDs
        service_01_item = QTreeWidgetItem(self.pid_tree, ["Service 01", "Show Current Data"])
        service_01_item.setFlags(service_01_item.flags() | Qt.ItemFlag.ItemIsAutoTristate | Qt.ItemFlag.ItemIsUserCheckable)

        # Group PIDs by service
        service_01_pids = [pid for pid in self.all_pids if pid.mode == "01"]

        # Add PIDs under the category
        for pid_def in sorted(service_01_pids, key=lambda p: p.pid):
            # Only show PIDs that are in the supported list
            if pid_def.full_id not in self.supported_pid_ids:
                continue

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
            if DEBUG:
                print(f"[GUI] PID {pid_id} selected")
        else:
            self.selected_pid_ids.discard(pid_id)
            if DEBUG:
                print(f"[GUI] PID {pid_id} deselected")

        # If in graph view mode, update the graphs to reflect the new selection
        if self.current_view_mode == 'graph':
            self.setup_graphs()

        # If already connected, restart monitoring with updated PID list
        if self.obd2_interface.is_connected:
            if DEBUG:
                print("[GUI] Already connected - restarting monitoring with updated PID list")
            self.restart_monitoring()

    def restart_monitoring(self):
        """Restart monitoring with the current selected PIDs."""
        # Stop current monitoring
        if self.obd2_interface.running:
            if DEBUG:
                print("[GUI] Stopping current monitoring...")
            self.obd2_interface.running = False
            if self.obd2_interface.receive_thread:
                self.obd2_interface.receive_thread.join(timeout=1)

        # Build list of PIDs to monitor
        pids_to_monitor = []
        for pid_id in self.selected_pid_ids:
            pid_def = get_pid_by_id(pid_id)
            if pid_def:
                pids_to_monitor.append((pid_def.mode, pid_def.pid, pid_def.name))

        # Start monitoring if we have PIDs selected
        if pids_to_monitor:
            if DEBUG:
                print(f"[GUI] Starting monitoring for {len(pids_to_monitor)} PIDs")
            self.obd2_interface.start_receiving(self.obd2_data_callback, pids_to_monitor)
            if not self.update_timer.isActive():
                self.update_timer.start()
            self.statusBar().showMessage(f"Monitoring {len(pids_to_monitor)} PIDs")
        else:
            if DEBUG:
                print("[GUI] No PIDs selected - stopping monitoring")
            self.update_timer.stop()
            self.statusBar().showMessage("Connected - No PIDs selected for monitoring")

    def toggle_connection(self):
        """Connect or disconnect from OBD2 adapter."""
        if not self.obd2_interface.is_connected:
            port = self.port_combo.currentText()

            if port == "No ports found":
                self.statusBar().showMessage("No COM ports available")
                return

            baudrate = int(self.baudrate_combo.currentText())

            # Create progress dialog
            progress = QProgressDialog("Connecting to OBD2 adapter...", "Cancel", 0, 0, self)
            progress.setWindowTitle("Connecting")
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.setMinimumDuration(0)
            progress.setCancelButton(None)  # No cancel button
            progress.setAutoClose(False)
            progress.setAutoReset(False)

            # Create worker thread
            self.connection_worker = ConnectionWorker(self.obd2_interface, port, baudrate)

            # Connect signals
            self.connection_worker.progress.connect(lambda msg: progress.setLabelText(msg))
            self.connection_worker.finished.connect(lambda success: self.on_connection_finished(success, progress, port, baudrate))

            # Start connection
            self.connection_worker.start()
            progress.show()

        else:
            self.obd2_interface.disconnect()
            self.update_timer.stop()
            self.connect_button.setText("Connect")
            self.port_combo.setEnabled(True)
            self.baudrate_combo.setEnabled(True)
            self.scan_button.setEnabled(False)
            self.statusBar().showMessage("Disconnected")

    def on_connection_finished(self, success: bool, progress: QProgressDialog, port: str, baudrate: int):
        """Handle connection completion."""
        progress.close()

        if success:
            self.connect_button.setText("Disconnect")
            self.port_combo.setEnabled(False)
            self.baudrate_combo.setEnabled(False)
            self.scan_button.setEnabled(True)

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

    def scan_vehicle(self):
        """Scan the vehicle for supported PIDs and filter the PID list."""
        if DEBUG:
            print("\n[GUI] Scan Vehicle button clicked")

        if not self.obd2_interface.is_connected:
            if DEBUG:
                print("[GUI] Not connected - aborting scan")
            self.statusBar().showMessage("Must be connected to scan vehicle")
            return

        if DEBUG:
            print("[GUI] Connection verified, starting scan...")

        # Disable scan button during scan
        self.scan_button.setEnabled(False)

        # Create progress dialog
        progress = QProgressDialog("Scanning vehicle for supported PIDs...", "Cancel", 0, 0, self)
        progress.setWindowTitle("Scanning Vehicle")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.setCancelButton(None)  # No cancel button
        progress.setAutoClose(False)
        progress.setAutoReset(False)

        # Create worker thread
        services_to_scan = ["01", "02", "09"]
        self.scan_worker = ScanWorker(self.obd2_interface, services_to_scan)

        # Connect signals
        self.scan_worker.progress.connect(lambda msg: progress.setLabelText(msg))
        self.scan_worker.finished.connect(lambda pids: self.on_scan_finished(pids, progress))

        # Start scan
        self.scan_worker.start()
        progress.show()

    def on_scan_finished(self, supported_pids: list, progress: QProgressDialog):
        """Handle scan completion."""
        progress.close()
        self.scan_button.setEnabled(True)

        if supported_pids:
            # Store supported PIDs
            self.supported_pid_ids = set(supported_pids)
            if DEBUG:
                print(f"[GUI] Stored {len(self.supported_pid_ids)} supported PIDs")

            # Rebuild PID tree with filtered list
            if DEBUG:
                print("[GUI] Rebuilding PID tree...")
            self.filter_pids()

            msg = f"Scan complete - Found {len(supported_pids)} supported PIDs"
            if DEBUG:
                print(f"[GUI] {msg}")
            self.statusBar().showMessage(msg)
        else:
            msg = "Scan failed - No supported PIDs found"
            if DEBUG:
                print(f"[GUI] {msg}")
            self.statusBar().showMessage(msg)

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
        current_time = time.time()
        metadata.last_timestamp = current_time
        metadata.count += 1

        # Decode the PID data
        decoded = decode_pid(pid_id, raw_data)
        if decoded:
            metadata.decoded_value = decoded

            # Extract numeric value for graphing
            try:
                # The decoded value is typically just a number string (e.g., "45.2" or "1234")
                # Try to convert it directly to float
                numeric_value = float(decoded.strip())

                # Store absolute timestamp for proper time tracking
                if metadata.start_time is None:
                    # First data point - set the reference time
                    metadata.start_time = current_time

                # Store absolute timestamp (will calculate relative time during display)
                metadata.time_history.append(current_time)
                metadata.value_history.append(numeric_value)

                if DEBUG:
                    print(f"[GUI] Stored value for {pid_id}: {numeric_value} (history size: {len(metadata.value_history)})")
            except (ValueError, TypeError) as e:
                # Not a numeric value, skip graphing
                if DEBUG:
                    print(f"[GUI] Could not extract numeric value from '{decoded}' for {pid_id}: {e}")

    def update_live_data_display(self):
        """Update the live data display with cached PID data."""
        if not self.pid_metadata:
            return

        if self.current_view_mode == 'raw':
            self.update_raw_view()
        elif self.current_view_mode == 'graph':
            self.update_graph_view()

        # Also update the separate graph window if it's open
        if self.graph_window and self.graph_window.isVisible():
            self.graph_window.update_graphs(self.pid_metadata)

    def update_raw_view(self):
        """Update the raw text view."""
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

    def update_graph_view(self):
        """Update the graph view with scrolling 30-second window."""
        # Find the most recent timestamp across all PIDs for synchronization
        reference_time = None
        for pid_id in self.selected_pid_ids:
            if pid_id in self.pid_metadata:
                metadata = self.pid_metadata[pid_id]
                if metadata.time_history:
                    latest = metadata.time_history[-1]
                    if reference_time is None or latest > reference_time:
                        reference_time = latest

        if reference_time is None:
            return

        # Update all graphs using the common reference time
        for pid_id in sorted(self.selected_pid_ids):
            if pid_id not in self.pid_metadata or pid_id not in self.graph_plots:
                continue

            metadata = self.pid_metadata[pid_id]
            if not metadata.time_history or not metadata.value_history or metadata.start_time is None:
                continue

            # Convert deques to lists for plotting
            absolute_times = list(metadata.time_history)
            values = list(metadata.value_history)

            # Calculate relative times from the COMMON reference time
            # This synchronizes all graphs to show data at the same time alignment
            if absolute_times:
                # Convert absolute times to relative times using common reference
                relative_times = [t - reference_time for t in absolute_times]

                # Update plot data
                curve = self.graph_plots[pid_id]
                curve.setData(relative_times, values)

    def closeEvent(self, event):
        """Handle application close."""
        if self.obd2_interface.is_connected:
            self.obd2_interface.disconnect()
        event.accept()


def main():
    """Main entry point for the GUI application."""
    app = QApplication(sys.argv)
    app.setApplicationName("OBD2 Reader")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

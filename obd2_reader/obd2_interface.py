"""OBD2 Interface for communicating with ELM327 adapters."""

import serial
import serial.tools.list_ports
import threading
import time
from typing import Optional, Callable, List

# ============================================================================
# DEBUG MODE
# Set DEBUG = True to enable detailed print statements to the terminal
# Set DEBUG = False to disable all terminal output (default)
# ============================================================================
DEBUG = False


class OBD2Interface:
    """Interface for ELM327 OBD2 adapter communication."""

    def __init__(self):
        self.serial_port: Optional[serial.Serial] = None
        self.is_connected: bool = False
        self.receive_thread: Optional[threading.Thread] = None
        self.running: bool = False
        self.message_callback: Optional[Callable[[str, str], None]] = None

    @staticmethod
    def get_available_ports() -> List[str]:
        """Get list of available COM ports."""
        ports = serial.tools.list_ports.comports()
        return [port.device for port in ports]

    def connect(self, port: str, baudrate: int = 38400) -> bool:
        """
        Connect to the ELM327 adapter.

        Args:
            port: COM port name (e.g., 'COM3')
            baudrate: Baud rate for serial communication (default: 38400)

        Returns:
            True if connection successful, False otherwise
        """
        try:
            self.serial_port = serial.Serial(
                port=port,
                baudrate=baudrate,
                timeout=1,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                bytesize=serial.EIGHTBITS
            )

            # Wait for adapter to initialize
            time.sleep(2)

            # Reset adapter
            self._send_command("ATZ")
            time.sleep(1)

            # Disable echo
            self._send_command("ATE0")

            # Set protocol to auto
            self._send_command("ATSP0")

            self.is_connected = True
            return True

        except Exception as e:
            if DEBUG:
                print(f"Failed to connect: {e}")
            if self.serial_port and self.serial_port.is_open:
                self.serial_port.close()
            return False

    def disconnect(self):
        """Disconnect from the ELM327 adapter."""
        self.running = False

        if self.receive_thread:
            self.receive_thread.join(timeout=2)
            self.receive_thread = None

        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()

        self.is_connected = False

    def _send_command(self, command: str) -> str:
        """
        Send a command to the ELM327 adapter.

        Args:
            command: AT or OBD command string

        Returns:
            Response from adapter
        """
        if not self.serial_port or not self.serial_port.is_open:
            if DEBUG:
                print(f"[OBD2] Cannot send '{command}' - port not open")
            return ""

        try:
            # Clear input buffer
            self.serial_port.reset_input_buffer()

            # Send command
            if DEBUG:
                print(f"[OBD2] Sending: {command}")
            self.serial_port.write((command + "\r").encode())

            # Read response
            response = ""
            start_time = time.time()
            timeout = 5.0  # 5 second timeout to handle SEARCHING...

            while time.time() - start_time < timeout:
                if self.serial_port.in_waiting > 0:
                    chunk = self.serial_port.read(self.serial_port.in_waiting).decode('utf-8', errors='ignore')
                    response += chunk
                    if ">" in response:  # Prompt character indicates end of response
                        break
                time.sleep(0.01)

            elapsed = time.time() - start_time
            if DEBUG:
                print(f"[OBD2] Received ({elapsed:.2f}s): {repr(response.strip())}")
            return response.strip()

        except Exception as e:
            if DEBUG:
                print(f"[OBD2] Command error: {e}")
            return ""

    def query_pid(self, mode: str, pid: str) -> Optional[str]:
        """
        Query an OBD2 PID.

        Args:
            mode: OBD2 mode (e.g., '01' for current data)
            pid: PID code (e.g., '0C' for engine RPM)

        Returns:
            Raw response data or None if error
        """
        command = f"{mode}{pid}"
        response = self._send_command(command)

        # Parse response (remove echo, prompt, SEARCHING..., and whitespace)
        response = response.replace(command, "").replace(">", "").replace("SEARCHING...", "").strip()
        # Remove any line breaks and extra spaces
        response = " ".join(response.split())

        if response and "NO DATA" not in response and "ERROR" not in response:
            return response
        return None

    def start_receiving(self, callback: Callable[[str, str], None], pids: List[tuple]):
        """
        Start continuous PID monitoring.

        Args:
            callback: Function to call with (pid_name, value) when data received
            pids: List of (mode, pid, name) tuples to monitor
        """
        self.message_callback = callback
        self.running = True

        self.receive_thread = threading.Thread(
            target=self._receive_loop,
            args=(pids,),
            daemon=True
        )
        self.receive_thread.start()

    def _receive_loop(self, pids: List[tuple]):
        """Continuously query PIDs and call callback with results."""
        while self.running:
            for mode, pid, name in pids:
                if not self.running:
                    break

                response = self.query_pid(mode, pid)
                if response and self.message_callback:
                    self.message_callback(f"{mode}{pid}", response)

                # Small delay between queries
                time.sleep(0.05)

    def scan_supported_pids(self, services: List[str] = None, progress_callback: Optional[Callable[[str], None]] = None) -> List[str]:
        """
        Scan the vehicle for all supported PIDs across specified services.

        Args:
            services: List of service modes to scan (e.g., ["01", "02", "09"]).
                     If None, scans Service 01 only for backwards compatibility.
            progress_callback: Optional callback function for progress updates.

        Queries PIDs 00, 20, 40, 60, 80, A0, C0, E0 which return bitmaps
        indicating which PIDs in their respective ranges are supported.

        Returns:
            List of supported PID IDs in format "MMXX" (e.g., ["010C", "020D", "0902"])
        """
        if services is None:
            services = ["01"]

        if DEBUG:
            print(f"\n=== Starting PID Scan for Services: {', '.join(services)} ===")
        if progress_callback:
            progress_callback(f"Starting PID Scan for Services: {', '.join(services)}")

        supported_pids = []

        # Support PIDs follow a pattern: 00, 20, 40, 60, 80, A0, C0, E0
        # Each returns a 4-byte bitmap for PIDs 01-20, 21-40, 41-60, etc.
        support_pids = ["00", "20", "40", "60", "80", "A0", "C0", "E0"]

        for service in services:
            if DEBUG:
                print(f"\n--- Scanning Service {service} ---")
            if progress_callback:
                progress_callback(f"Scanning Service {service}...")

            for support_pid in support_pids:
                if DEBUG:
                    print(f"\nQuerying support PID {service}{support_pid}...")
                if progress_callback:
                    progress_callback(f"Querying PID {service}{support_pid}...")

                response = self.query_pid(service, support_pid)

                if not response:
                    if DEBUG:
                        print(f"  No response for PID {service}{support_pid} - stopping scan for this service")
                    if progress_callback:
                        progress_callback(f"No response for PID {service}{support_pid}")
                    break

                if DEBUG:
                    print(f"  Response: {response}")
                if progress_callback:
                    progress_callback(f"Response: {response}")

                # Parse the response to extract supported PIDs
                try:
                    # Response format: "4X XX A B C D" where 4X is service response (41, 42, 49, etc.)
                    parts = response.split()
                    # Response code should be (0x40 + service_mode)
                    expected_response = f"{int(service, 16) + 0x40:02X}"

                    if len(parts) >= 6 and parts[0] == expected_response:
                        # Combine the 4 data bytes into a 32-bit bitmap
                        data_bytes = parts[2:6]
                        bitmap = 0
                        for byte_str in data_bytes:
                            bitmap = (bitmap << 8) | int(byte_str, 16)

                        if DEBUG:
                            print(f"  Bitmap: 0x{bitmap:08X}")

                        # Calculate the starting PID number for this range
                        base_pid = int(support_pid, 16) + 1

                        # Check each bit (bit 31 = PID base+0, bit 30 = PID base+1, etc.)
                        pids_in_range = []
                        for bit_pos in range(32):
                            if bitmap & (1 << (31 - bit_pos)):
                                pid_num = base_pid + bit_pos
                                pid_id = f"{service}{pid_num:02X}"
                                supported_pids.append(pid_id)
                                pids_in_range.append(pid_id)

                        if DEBUG:
                            print(f"  Found {len(pids_in_range)} PIDs: {', '.join(pids_in_range)}")
                        if progress_callback:
                            progress_callback(f"Found {len(pids_in_range)} PIDs: {', '.join(pids_in_range)}")
                    else:
                        if DEBUG:
                            expected_len = len(parts)
                            print(f"  Invalid response format (expected {expected_response} XX ... with 6+ parts, got {expected_len} parts)")

                except (ValueError, IndexError) as e:
                    if DEBUG:
                        print(f"  Error parsing support PID {support_pid}: {e}")
                    continue

        if DEBUG:
            print(f"\n=== Scan Complete: Found {len(supported_pids)} total PIDs ===")
            print(f"Supported PIDs: {', '.join(supported_pids)}\n")
        if progress_callback:
            progress_callback(f"Scan Complete: Found {len(supported_pids)} total PIDs")

        return supported_pids

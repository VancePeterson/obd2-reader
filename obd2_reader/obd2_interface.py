"""OBD2 Interface for communicating with ELM327 adapters."""

import serial
import serial.tools.list_ports
import threading
import time
from typing import Optional, Callable, List


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
            return ""

        try:
            # Clear input buffer
            self.serial_port.reset_input_buffer()

            # Send command
            self.serial_port.write((command + "\r").encode())

            # Read response
            response = ""
            start_time = time.time()
            while time.time() - start_time < 1:  # 1 second timeout
                if self.serial_port.in_waiting > 0:
                    chunk = self.serial_port.read(self.serial_port.in_waiting).decode('utf-8', errors='ignore')
                    response += chunk
                    if ">" in response:  # Prompt character indicates end of response
                        break
                time.sleep(0.01)

            return response.strip()

        except Exception as e:
            print(f"Command error: {e}")
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

        # Parse response (remove echo, prompt, and whitespace)
        response = response.replace(command, "").replace(">", "").strip()

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

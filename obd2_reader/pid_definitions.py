"""Standard OBD2 PID definitions and decoding functions."""

from typing import Dict, Optional, Callable


class PIDDefinition:
    """Definition of an OBD2 PID parameter."""

    def __init__(self, mode: str, pid: str, name: str, description: str,
                 decoder: Callable[[str], Optional[str]], unit: str = ""):
        self.mode = mode
        self.pid = pid
        self.name = name
        self.description = description
        self.decoder = decoder
        self.unit = unit

    @property
    def full_id(self) -> str:
        """Get the full PID identifier (mode + pid)."""
        return f"{self.mode}{self.pid}"


# Decoder functions for Service 01 PIDs

def decode_calculated_load(data: str) -> Optional[str]:
    """Decode calculated engine load (PID 04)."""
    try:
        parts = data.split()
        if len(parts) >= 3 and parts[0] == "41" and parts[1] == "04":
            load = int(parts[2], 16) * 100 / 255
            return f"{load:.1f}"
    except:
        pass
    return None


def decode_coolant_temp(data: str) -> Optional[str]:
    """Decode engine coolant temperature (PID 05)."""
    try:
        parts = data.split()
        if len(parts) >= 3 and parts[0] == "41" and parts[1] == "05":
            temp = int(parts[2], 16) - 40
            return f"{temp}"
    except:
        pass
    return None


def decode_short_fuel_trim_1(data: str) -> Optional[str]:
    """Decode short term fuel trim - Bank 1 (PID 06)."""
    try:
        parts = data.split()
        if len(parts) >= 3 and parts[0] == "41" and parts[1] == "06":
            trim = (int(parts[2], 16) - 128) * 100 / 128
            return f"{trim:.1f}"
    except:
        pass
    return None


def decode_long_fuel_trim_1(data: str) -> Optional[str]:
    """Decode long term fuel trim - Bank 1 (PID 07)."""
    try:
        parts = data.split()
        if len(parts) >= 3 and parts[0] == "41" and parts[1] == "07":
            trim = (int(parts[2], 16) - 128) * 100 / 128
            return f"{trim:.1f}"
    except:
        pass
    return None


def decode_short_fuel_trim_2(data: str) -> Optional[str]:
    """Decode short term fuel trim - Bank 2 (PID 08)."""
    try:
        parts = data.split()
        if len(parts) >= 3 and parts[0] == "41" and parts[1] == "08":
            trim = (int(parts[2], 16) - 128) * 100 / 128
            return f"{trim:.1f}"
    except:
        pass
    return None


def decode_long_fuel_trim_2(data: str) -> Optional[str]:
    """Decode long term fuel trim - Bank 2 (PID 09)."""
    try:
        parts = data.split()
        if len(parts) >= 3 and parts[0] == "41" and parts[1] == "09":
            trim = (int(parts[2], 16) - 128) * 100 / 128
            return f"{trim:.1f}"
    except:
        pass
    return None


def decode_fuel_pressure(data: str) -> Optional[str]:
    """Decode fuel pressure (PID 0A)."""
    try:
        parts = data.split()
        if len(parts) >= 3 and parts[0] == "41" and parts[1] == "0A":
            pressure = int(parts[2], 16) * 3
            return f"{pressure}"
    except:
        pass
    return None


def decode_intake_pressure(data: str) -> Optional[str]:
    """Decode intake manifold pressure (PID 0B)."""
    try:
        parts = data.split()
        if len(parts) >= 3 and parts[0] == "41" and parts[1] == "0B":
            pressure = int(parts[2], 16)
            return f"{pressure}"
    except:
        pass
    return None


def decode_rpm(data: str) -> Optional[str]:
    """Decode engine RPM (PID 0C)."""
    try:
        parts = data.split()
        if len(parts) >= 4 and parts[0] == "41" and parts[1] == "0C":
            a = int(parts[2], 16)
            b = int(parts[3], 16)
            rpm = ((a * 256) + b) / 4
            return f"{rpm:.0f}"
    except:
        pass
    return None


def decode_speed(data: str) -> Optional[str]:
    """Decode vehicle speed (PID 0D)."""
    try:
        parts = data.split()
        if len(parts) >= 3 and parts[0] == "41" and parts[1] == "0D":
            speed = int(parts[2], 16)
            return f"{speed}"
    except:
        pass
    return None


def decode_timing_advance(data: str) -> Optional[str]:
    """Decode timing advance (PID 0E)."""
    try:
        parts = data.split()
        if len(parts) >= 3 and parts[0] == "41" and parts[1] == "0E":
            timing = int(parts[2], 16) / 2 - 64
            return f"{timing:.1f}"
    except:
        pass
    return None


def decode_intake_temp(data: str) -> Optional[str]:
    """Decode intake air temperature (PID 0F)."""
    try:
        parts = data.split()
        if len(parts) >= 3 and parts[0] == "41" and parts[1] == "0F":
            temp = int(parts[2], 16) - 40
            return f"{temp}"
    except:
        pass
    return None


def decode_maf(data: str) -> Optional[str]:
    """Decode mass air flow rate (PID 10)."""
    try:
        parts = data.split()
        if len(parts) >= 4 and parts[0] == "41" and parts[1] == "10":
            a = int(parts[2], 16)
            b = int(parts[3], 16)
            maf = ((a * 256) + b) / 100
            return f"{maf:.2f}"
    except:
        pass
    return None


def decode_throttle(data: str) -> Optional[str]:
    """Decode throttle position (PID 11)."""
    try:
        parts = data.split()
        if len(parts) >= 3 and parts[0] == "41" and parts[1] == "11":
            throttle = int(parts[2], 16) * 100 / 255
            return f"{throttle:.1f}"
    except:
        pass
    return None


def decode_runtime(data: str) -> Optional[str]:
    """Decode run time since engine start (PID 1F)."""
    try:
        parts = data.split()
        if len(parts) >= 4 and parts[0] == "41" and parts[1] == "1F":
            a = int(parts[2], 16)
            b = int(parts[3], 16)
            seconds = (a * 256) + b
            return f"{seconds}"
    except:
        pass
    return None


def decode_distance_mil(data: str) -> Optional[str]:
    """Decode distance traveled with MIL on (PID 21)."""
    try:
        parts = data.split()
        if len(parts) >= 4 and parts[0] == "41" and parts[1] == "21":
            a = int(parts[2], 16)
            b = int(parts[3], 16)
            distance = (a * 256) + b
            return f"{distance}"
    except:
        pass
    return None


def decode_fuel_rail_pressure_rel(data: str) -> Optional[str]:
    """Decode fuel rail pressure relative (PID 22)."""
    try:
        parts = data.split()
        if len(parts) >= 4 and parts[0] == "41" and parts[1] == "22":
            a = int(parts[2], 16)
            b = int(parts[3], 16)
            pressure = ((a * 256) + b) * 0.079
            return f"{pressure:.2f}"
    except:
        pass
    return None


def decode_fuel_rail_pressure_abs(data: str) -> Optional[str]:
    """Decode fuel rail pressure absolute (PID 23)."""
    try:
        parts = data.split()
        if len(parts) >= 4 and parts[0] == "41" and parts[1] == "23":
            a = int(parts[2], 16)
            b = int(parts[3], 16)
            pressure = ((a * 256) + b) * 10
            return f"{pressure}"
    except:
        pass
    return None


def decode_commanded_egr(data: str) -> Optional[str]:
    """Decode commanded EGR (PID 2C)."""
    try:
        parts = data.split()
        if len(parts) >= 3 and parts[0] == "41" and parts[1] == "2C":
            egr = int(parts[2], 16) * 100 / 255
            return f"{egr:.1f}"
    except:
        pass
    return None


def decode_egr_error(data: str) -> Optional[str]:
    """Decode EGR error (PID 2D)."""
    try:
        parts = data.split()
        if len(parts) >= 3 and parts[0] == "41" and parts[1] == "2D":
            error = (int(parts[2], 16) - 128) * 100 / 128
            return f"{error:.1f}"
    except:
        pass
    return None


def decode_evap_purge(data: str) -> Optional[str]:
    """Decode commanded evaporative purge (PID 2E)."""
    try:
        parts = data.split()
        if len(parts) >= 3 and parts[0] == "41" and parts[1] == "2E":
            purge = int(parts[2], 16) * 100 / 255
            return f"{purge:.1f}"
    except:
        pass
    return None


def decode_fuel_level(data: str) -> Optional[str]:
    """Decode fuel tank level (PID 2F)."""
    try:
        parts = data.split()
        if len(parts) >= 3 and parts[0] == "41" and parts[1] == "2F":
            level = int(parts[2], 16) * 100 / 255
            return f"{level:.1f}"
    except:
        pass
    return None


def decode_warmups(data: str) -> Optional[str]:
    """Decode warm-ups since codes cleared (PID 30)."""
    try:
        parts = data.split()
        if len(parts) >= 3 and parts[0] == "41" and parts[1] == "30":
            warmups = int(parts[2], 16)
            return f"{warmups}"
    except:
        pass
    return None


def decode_distance_cleared(data: str) -> Optional[str]:
    """Decode distance since codes cleared (PID 31)."""
    try:
        parts = data.split()
        if len(parts) >= 4 and parts[0] == "41" and parts[1] == "31":
            a = int(parts[2], 16)
            b = int(parts[3], 16)
            distance = (a * 256) + b
            return f"{distance}"
    except:
        pass
    return None


def decode_barometric_pressure(data: str) -> Optional[str]:
    """Decode barometric pressure (PID 33)."""
    try:
        parts = data.split()
        if len(parts) >= 3 and parts[0] == "41" and parts[1] == "33":
            pressure = int(parts[2], 16)
            return f"{pressure}"
    except:
        pass
    return None


def decode_catalyst_temp_b1s1(data: str) -> Optional[str]:
    """Decode catalyst temperature Bank 1 Sensor 1 (PID 3C)."""
    try:
        parts = data.split()
        if len(parts) >= 4 and parts[0] == "41" and parts[1] == "3C":
            a = int(parts[2], 16)
            b = int(parts[3], 16)
            temp = ((a * 256) + b) / 10 - 40
            return f"{temp:.1f}"
    except:
        pass
    return None


def decode_catalyst_temp_b2s1(data: str) -> Optional[str]:
    """Decode catalyst temperature Bank 2 Sensor 1 (PID 3D)."""
    try:
        parts = data.split()
        if len(parts) >= 4 and parts[0] == "41" and parts[1] == "3D":
            a = int(parts[2], 16)
            b = int(parts[3], 16)
            temp = ((a * 256) + b) / 10 - 40
            return f"{temp:.1f}"
    except:
        pass
    return None


def decode_catalyst_temp_b1s2(data: str) -> Optional[str]:
    """Decode catalyst temperature Bank 1 Sensor 2 (PID 3E)."""
    try:
        parts = data.split()
        if len(parts) >= 4 and parts[0] == "41" and parts[1] == "3E":
            a = int(parts[2], 16)
            b = int(parts[3], 16)
            temp = ((a * 256) + b) / 10 - 40
            return f"{temp:.1f}"
    except:
        pass
    return None


def decode_catalyst_temp_b2s2(data: str) -> Optional[str]:
    """Decode catalyst temperature Bank 2 Sensor 2 (PID 3F)."""
    try:
        parts = data.split()
        if len(parts) >= 4 and parts[0] == "41" and parts[1] == "3F":
            a = int(parts[2], 16)
            b = int(parts[3], 16)
            temp = ((a * 256) + b) / 10 - 40
            return f"{temp:.1f}"
    except:
        pass
    return None


def decode_control_module_voltage(data: str) -> Optional[str]:
    """Decode control module voltage (PID 42)."""
    try:
        parts = data.split()
        if len(parts) >= 4 and parts[0] == "41" and parts[1] == "42":
            a = int(parts[2], 16)
            b = int(parts[3], 16)
            voltage = ((a * 256) + b) / 1000
            return f"{voltage:.3f}"
    except:
        pass
    return None


def decode_absolute_load(data: str) -> Optional[str]:
    """Decode absolute load value (PID 43)."""
    try:
        parts = data.split()
        if len(parts) >= 4 and parts[0] == "41" and parts[1] == "43":
            a = int(parts[2], 16)
            b = int(parts[3], 16)
            load = ((a * 256) + b) * 100 / 255
            return f"{load:.1f}"
    except:
        pass
    return None


def decode_relative_throttle(data: str) -> Optional[str]:
    """Decode relative throttle position (PID 45)."""
    try:
        parts = data.split()
        if len(parts) >= 3 and parts[0] == "41" and parts[1] == "45":
            throttle = int(parts[2], 16) * 100 / 255
            return f"{throttle:.1f}"
    except:
        pass
    return None


def decode_ambient_temp(data: str) -> Optional[str]:
    """Decode ambient air temperature (PID 46)."""
    try:
        parts = data.split()
        if len(parts) >= 3 and parts[0] == "41" and parts[1] == "46":
            temp = int(parts[2], 16) - 40
            return f"{temp}"
    except:
        pass
    return None


def decode_throttle_b(data: str) -> Optional[str]:
    """Decode absolute throttle position B (PID 47)."""
    try:
        parts = data.split()
        if len(parts) >= 3 and parts[0] == "41" and parts[1] == "47":
            throttle = int(parts[2], 16) * 100 / 255
            return f"{throttle:.1f}"
    except:
        pass
    return None


def decode_throttle_c(data: str) -> Optional[str]:
    """Decode absolute throttle position C (PID 48)."""
    try:
        parts = data.split()
        if len(parts) >= 3 and parts[0] == "41" and parts[1] == "48":
            throttle = int(parts[2], 16) * 100 / 255
            return f"{throttle:.1f}"
    except:
        pass
    return None


def decode_accelerator_d(data: str) -> Optional[str]:
    """Decode accelerator pedal position D (PID 49)."""
    try:
        parts = data.split()
        if len(parts) >= 3 and parts[0] == "41" and parts[1] == "49":
            position = int(parts[2], 16) * 100 / 255
            return f"{position:.1f}"
    except:
        pass
    return None


def decode_accelerator_e(data: str) -> Optional[str]:
    """Decode accelerator pedal position E (PID 4A)."""
    try:
        parts = data.split()
        if len(parts) >= 3 and parts[0] == "41" and parts[1] == "4A":
            position = int(parts[2], 16) * 100 / 255
            return f"{position:.1f}"
    except:
        pass
    return None


def decode_accelerator_f(data: str) -> Optional[str]:
    """Decode accelerator pedal position F (PID 4B)."""
    try:
        parts = data.split()
        if len(parts) >= 3 and parts[0] == "41" and parts[1] == "4B":
            position = int(parts[2], 16) * 100 / 255
            return f"{position:.1f}"
    except:
        pass
    return None


def decode_throttle_actuator(data: str) -> Optional[str]:
    """Decode commanded throttle actuator (PID 4C)."""
    try:
        parts = data.split()
        if len(parts) >= 3 and parts[0] == "41" and parts[1] == "4C":
            position = int(parts[2], 16) * 100 / 255
            return f"{position:.1f}"
    except:
        pass
    return None


def decode_time_mil(data: str) -> Optional[str]:
    """Decode time run with MIL on (PID 4D)."""
    try:
        parts = data.split()
        if len(parts) >= 4 and parts[0] == "41" and parts[1] == "4D":
            a = int(parts[2], 16)
            b = int(parts[3], 16)
            minutes = (a * 256) + b
            return f"{minutes}"
    except:
        pass
    return None


def decode_time_cleared(data: str) -> Optional[str]:
    """Decode time since codes cleared (PID 4E)."""
    try:
        parts = data.split()
        if len(parts) >= 4 and parts[0] == "41" and parts[1] == "4E":
            a = int(parts[2], 16)
            b = int(parts[3], 16)
            minutes = (a * 256) + b
            return f"{minutes}"
    except:
        pass
    return None


def decode_ethanol_percent(data: str) -> Optional[str]:
    """Decode ethanol fuel percentage (PID 52)."""
    try:
        parts = data.split()
        if len(parts) >= 3 and parts[0] == "41" and parts[1] == "52":
            percent = int(parts[2], 16) * 100 / 255
            return f"{percent:.1f}"
    except:
        pass
    return None


def decode_fuel_rail_pressure_abs2(data: str) -> Optional[str]:
    """Decode fuel rail pressure absolute (PID 59)."""
    try:
        parts = data.split()
        if len(parts) >= 4 and parts[0] == "41" and parts[1] == "59":
            a = int(parts[2], 16)
            b = int(parts[3], 16)
            pressure = ((a * 256) + b) * 10
            return f"{pressure}"
    except:
        pass
    return None


def decode_relative_accel_pos(data: str) -> Optional[str]:
    """Decode relative accelerator pedal position (PID 5A)."""
    try:
        parts = data.split()
        if len(parts) >= 3 and parts[0] == "41" and parts[1] == "5A":
            position = int(parts[2], 16) * 100 / 255
            return f"{position:.1f}"
    except:
        pass
    return None


def decode_hybrid_battery(data: str) -> Optional[str]:
    """Decode hybrid battery pack remaining life (PID 5B)."""
    try:
        parts = data.split()
        if len(parts) >= 3 and parts[0] == "41" and parts[1] == "5B":
            percent = int(parts[2], 16) * 100 / 255
            return f"{percent:.1f}"
    except:
        pass
    return None


def decode_oil_temp(data: str) -> Optional[str]:
    """Decode engine oil temperature (PID 5C)."""
    try:
        parts = data.split()
        if len(parts) >= 3 and parts[0] == "41" and parts[1] == "5C":
            temp = int(parts[2], 16) - 40
            return f"{temp}"
    except:
        pass
    return None


def decode_fuel_injection_timing(data: str) -> Optional[str]:
    """Decode fuel injection timing (PID 5D)."""
    try:
        parts = data.split()
        if len(parts) >= 4 and parts[0] == "41" and parts[1] == "5D":
            a = int(parts[2], 16)
            b = int(parts[3], 16)
            timing = (((a * 256) + b) - 26880) / 128
            return f"{timing:.2f}"
    except:
        pass
    return None


def decode_fuel_rate(data: str) -> Optional[str]:
    """Decode engine fuel rate (PID 5E)."""
    try:
        parts = data.split()
        if len(parts) >= 4 and parts[0] == "41" and parts[1] == "5E":
            a = int(parts[2], 16)
            b = int(parts[3], 16)
            rate = ((a * 256) + b) / 20
            return f"{rate:.2f}"
    except:
        pass
    return None


# Standard Mode 01 PIDs - Comprehensive list
STANDARD_PIDS: Dict[str, PIDDefinition] = {
    "0104": PIDDefinition("01", "04", "Calculated Engine Load", "Calculated engine load value", decode_calculated_load, "%"),
    "0105": PIDDefinition("01", "05", "Coolant Temperature", "Engine coolant temperature", decode_coolant_temp, "°C"),
    "0106": PIDDefinition("01", "06", "Short Fuel Trim Bank 1", "Short term fuel trim - Bank 1", decode_short_fuel_trim_1, "%"),
    "0107": PIDDefinition("01", "07", "Long Fuel Trim Bank 1", "Long term fuel trim - Bank 1", decode_long_fuel_trim_1, "%"),
    "0108": PIDDefinition("01", "08", "Short Fuel Trim Bank 2", "Short term fuel trim - Bank 2", decode_short_fuel_trim_2, "%"),
    "0109": PIDDefinition("01", "09", "Long Fuel Trim Bank 2", "Long term fuel trim - Bank 2", decode_long_fuel_trim_2, "%"),
    "010A": PIDDefinition("01", "0A", "Fuel Pressure", "Fuel pressure (gauge pressure)", decode_fuel_pressure, "kPa"),
    "010B": PIDDefinition("01", "0B", "Intake Manifold Pressure", "Intake manifold absolute pressure", decode_intake_pressure, "kPa"),
    "010C": PIDDefinition("01", "0C", "Engine RPM", "Engine speed", decode_rpm, "RPM"),
    "010D": PIDDefinition("01", "0D", "Vehicle Speed", "Vehicle speed", decode_speed, "km/h"),
    "010E": PIDDefinition("01", "0E", "Timing Advance", "Timing advance", decode_timing_advance, "° before TDC"),
    "010F": PIDDefinition("01", "0F", "Intake Air Temperature", "Intake air temperature", decode_intake_temp, "°C"),
    "0110": PIDDefinition("01", "10", "MAF Air Flow Rate", "Mass air flow sensor rate", decode_maf, "g/s"),
    "0111": PIDDefinition("01", "11", "Throttle Position", "Throttle position", decode_throttle, "%"),
    "011F": PIDDefinition("01", "1F", "Run Time", "Run time since engine start", decode_runtime, "sec"),
    "0121": PIDDefinition("01", "21", "Distance with MIL", "Distance traveled with MIL on", decode_distance_mil, "km"),
    "0122": PIDDefinition("01", "22", "Fuel Rail Pressure (relative)", "Fuel rail pressure relative to manifold vacuum", decode_fuel_rail_pressure_rel, "kPa"),
    "0123": PIDDefinition("01", "23", "Fuel Rail Pressure (absolute)", "Fuel rail pressure (diesel/direct inject)", decode_fuel_rail_pressure_abs, "kPa"),
    "012C": PIDDefinition("01", "2C", "Commanded EGR", "Commanded EGR", decode_commanded_egr, "%"),
    "012D": PIDDefinition("01", "2D", "EGR Error", "EGR error", decode_egr_error, "%"),
    "012E": PIDDefinition("01", "2E", "Commanded Evap Purge", "Commanded evaporative purge", decode_evap_purge, "%"),
    "012F": PIDDefinition("01", "2F", "Fuel Level", "Fuel tank level input", decode_fuel_level, "%"),
    "0130": PIDDefinition("01", "30", "Warm-ups Since Codes Cleared", "Number of warm-ups since codes cleared", decode_warmups, "count"),
    "0131": PIDDefinition("01", "31", "Distance Since Codes Cleared", "Distance traveled since codes cleared", decode_distance_cleared, "km"),
    "0133": PIDDefinition("01", "33", "Barometric Pressure", "Absolute barometric pressure", decode_barometric_pressure, "kPa"),
    "013C": PIDDefinition("01", "3C", "Catalyst Temp Bank 1 Sensor 1", "Catalyst temperature Bank 1, Sensor 1", decode_catalyst_temp_b1s1, "°C"),
    "013D": PIDDefinition("01", "3D", "Catalyst Temp Bank 2 Sensor 1", "Catalyst temperature Bank 2, Sensor 1", decode_catalyst_temp_b2s1, "°C"),
    "013E": PIDDefinition("01", "3E", "Catalyst Temp Bank 1 Sensor 2", "Catalyst temperature Bank 1, Sensor 2", decode_catalyst_temp_b1s2, "°C"),
    "013F": PIDDefinition("01", "3F", "Catalyst Temp Bank 2 Sensor 2", "Catalyst temperature Bank 2, Sensor 2", decode_catalyst_temp_b2s2, "°C"),
    "0142": PIDDefinition("01", "42", "Control Module Voltage", "Control module voltage", decode_control_module_voltage, "V"),
    "0143": PIDDefinition("01", "43", "Absolute Load Value", "Absolute load value", decode_absolute_load, "%"),
    "0145": PIDDefinition("01", "45", "Relative Throttle Position", "Relative throttle position", decode_relative_throttle, "%"),
    "0146": PIDDefinition("01", "46", "Ambient Temperature", "Ambient air temperature", decode_ambient_temp, "°C"),
    "0147": PIDDefinition("01", "47", "Absolute Throttle Position B", "Absolute throttle position B", decode_throttle_b, "%"),
    "0148": PIDDefinition("01", "48", "Absolute Throttle Position C", "Absolute throttle position C", decode_throttle_c, "%"),
    "0149": PIDDefinition("01", "49", "Accelerator Pedal Position D", "Accelerator pedal position D", decode_accelerator_d, "%"),
    "014A": PIDDefinition("01", "4A", "Accelerator Pedal Position E", "Accelerator pedal position E", decode_accelerator_e, "%"),
    "014B": PIDDefinition("01", "4B", "Accelerator Pedal Position F", "Accelerator pedal position F", decode_accelerator_f, "%"),
    "014C": PIDDefinition("01", "4C", "Commanded Throttle Actuator", "Commanded throttle actuator", decode_throttle_actuator, "%"),
    "014D": PIDDefinition("01", "4D", "Time with MIL On", "Time run with MIL on", decode_time_mil, "min"),
    "014E": PIDDefinition("01", "4E", "Time Since Codes Cleared", "Time since trouble codes cleared", decode_time_cleared, "min"),
    "0152": PIDDefinition("01", "52", "Ethanol Fuel Percent", "Ethanol fuel percentage", decode_ethanol_percent, "%"),
    "0159": PIDDefinition("01", "59", "Fuel Rail Pressure (absolute)", "Fuel rail absolute pressure", decode_fuel_rail_pressure_abs2, "kPa"),
    "015A": PIDDefinition("01", "5A", "Relative Accel Pedal Position", "Relative accelerator pedal position", decode_relative_accel_pos, "%"),
    "015B": PIDDefinition("01", "5B", "Hybrid Battery Life", "Hybrid battery pack remaining life", decode_hybrid_battery, "%"),
    "015C": PIDDefinition("01", "5C", "Oil Temperature", "Engine oil temperature", decode_oil_temp, "°C"),
    "015D": PIDDefinition("01", "5D", "Fuel Injection Timing", "Fuel injection timing", decode_fuel_injection_timing, "°"),
    "015E": PIDDefinition("01", "5E", "Engine Fuel Rate", "Engine fuel rate", decode_fuel_rate, "L/h"),
}


def get_all_pids() -> Dict[str, PIDDefinition]:
    """Get all available PID definitions."""
    return STANDARD_PIDS


def get_pid_by_id(pid_id: str) -> Optional[PIDDefinition]:
    """Get a PID definition by its full ID (mode + pid)."""
    return STANDARD_PIDS.get(pid_id)


def decode_pid(pid_id: str, raw_data: str) -> Optional[str]:
    """Decode raw PID data using the appropriate decoder."""
    pid_def = get_pid_by_id(pid_id)
    if pid_def:
        return pid_def.decoder(raw_data)
    return None

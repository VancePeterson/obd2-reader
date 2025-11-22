# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a PyQt6-based GUI application for reading live OBD2 data from vehicles using ELM327-compatible adapters over serial communication. The application provides real-time monitoring of vehicle parameters (PIDs) with a split-panel interface.

## Development Commands

### Running the Application
```bash
# Using uv (preferred)
uv run main.py

# Using Python directly
python main.py
```

### Dependency Management
```bash
# Install/sync dependencies
uv sync
```

## Architecture

### Three-Layer Architecture

1. **GUI Layer** ([gui.py](obd2_reader/gui.py))
   - PyQt6-based main window with split-panel layout
   - Left panel: Configuration (COM port, baudrate) + checkable PID tree
   - Right panel: Live data display showing decoded values with units
   - Uses Qt signals (`OBD2SignalEmitter`) for thread-safe communication between OBD2 interface and GUI
   - Maintains `PIDMetadata` dictionary tracking count, timestamp, and decoded values for each monitored PID
   - `QTimer` updates display every 100ms for smooth refresh

2. **Communication Layer** ([obd2_interface.py](obd2_reader/obd2_interface.py))
   - `OBD2Interface` class handles serial communication with ELM327 adapter
   - Implements ELM327 initialization sequence: ATZ (reset), ATE0 (echo off), ATSP0 (auto protocol)
   - Runs continuous PID polling loop in background thread (`_receive_loop`)
   - Callback-based design: calls GUI callback for each received PID response
   - Response parsing: strips echo and prompt characters, validates for "NO DATA" and "ERROR"

3. **Data Layer** ([pid_definitions.py](obd2_reader/pid_definitions.py))
   - `PIDDefinition` class encapsulates PID metadata (mode, pid, name, decoder function, unit)
   - Extensive decoder functions for Service 01 PIDs (mode "01" = Show Current Data)
   - Each decoder parses hex response format (e.g., "41 0C A1 B2" for RPM) and applies OBD2 conversion formulas
   - `STANDARD_PIDS` dictionary maps full PID IDs (e.g., "010C") to definitions

### Threading Model

- **Main thread**: PyQt6 GUI event loop
- **Background thread**: OBD2 receive loop queries PIDs sequentially, 50ms delay between queries
- **Communication**: Background thread emits Qt signals to update GUI thread safely

### Data Flow

1. User selects PIDs from tree and clicks Connect
2. `OBD2Interface.connect()` initializes serial port and ELM327
3. `start_receiving()` spawns background thread with list of (mode, pid, name) tuples
4. Background thread continuously queries each PID via `query_pid()`
5. Raw responses trigger callback → Qt signal → `on_obd2_data_received()`
6. GUI decodes using `decode_pid()` and stores in `PIDMetadata`
7. Timer-driven `update_live_data_display()` renders all tracked PIDs

### PID Response Format

ELM327 returns responses like:
```
41 0C 1A F8    # Response to "010C" (RPM query)
```
Where:
- `41` = Service 01 response header
- `0C` = PID identifier
- `1A F8` = Data bytes (decoded by PID-specific decoder)

Decoders parse this format and apply formulas (e.g., RPM = ((A * 256) + B) / 4)

## Key Implementation Details

- **PID tree organization**: Uses `QTreeWidget` with "Service 01" parent item, individual PIDs as children with checkboxes
- **Search/filter**: `filter_pids()` rebuilds tree while preserving checked state in `selected_pid_ids` set
- **Scroll preservation**: Live data display maintains scroll position unless user is at bottom (auto-scrolls)
- **Error handling**: Serial errors printed to console, graceful disconnect on window close
- **No persistence**: Selected PIDs and settings are not saved between sessions

## Common Development Patterns

When adding new PIDs:
1. Write decoder function following existing pattern in [pid_definitions.py](obd2_reader/pid_definitions.py)
2. Add `PIDDefinition` entry to `STANDARD_PIDS` dictionary
3. No GUI changes needed - tree automatically populated from `get_all_pids()`

When modifying serial communication:
- All serial operations must happen on background thread
- Use Qt signals to communicate results back to GUI
- Maintain thread safety for `running` flag and `message_callback`

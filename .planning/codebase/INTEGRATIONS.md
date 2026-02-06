# Integrations

## External APIs
None. All current projects are offline, terminal-only applications.

## Databases
None.

## Auth Providers
None.

## File I/O
None. No file read/write operations — all state is in-memory.

## Terminal Integration
- ANSI escape codes for rendering (colors, cursor control, screen clear)
- Raw terminal mode via `tty`/`termios` for keyboard input
- `shutil.get_terminal_size()` for responsive layout
- Non-blocking input via `select` module (aquarium.py)

## Notes
The installed-but-unused packages (yfinance, httpx) indicate planned future work requiring network/API integration.

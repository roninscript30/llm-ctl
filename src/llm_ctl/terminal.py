"""
Robust terminal handling: non-blocking key reader, ANSI styling, and safe terminal restore.
"""

import sys
import os
import tty
import termios
import select
import atexit

_ORIGINAL_SETTINGS = None
_RAW_ACTIVE = False

def init_terminal_cleanup():
    """Registers cleanup handlers so the terminal is NEVER left in a broken state."""
    global _ORIGINAL_SETTINGS
    if sys.stdin.isatty():
        try:
            _ORIGINAL_SETTINGS = termios.tcgetattr(sys.stdin.fileno())
        except Exception:
            pass

    def _cleanup():
        restore_terminal()
        sys.stdout.write("\033[?25h\033[0m")
        sys.stdout.flush()

    atexit.register(_cleanup)

def set_raw_mode():
    """Sets terminal to raw mode safely."""
    global _RAW_ACTIVE
    if not sys.stdin.isatty():
        return
    try:
        tty.setraw(sys.stdin.fileno())
        _RAW_ACTIVE = True
    except Exception:
        pass

def restore_terminal():
    """Restores original terminal settings."""
    global _RAW_ACTIVE, _ORIGINAL_SETTINGS
    if _RAW_ACTIVE and _ORIGINAL_SETTINGS and sys.stdin.isatty():
        try:
            termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, _ORIGINAL_SETTINGS)
            _RAW_ACTIVE = False
        except Exception:
            pass

def read_key() -> str:
    """
    Reads a single keypress or escape sequence with non-blocking polling.
    Properly parses xterm/kitty arrow keys (\x1b[A, \x1bOA, etc.).
    Returns: 'UP', 'DOWN', 'LEFT', 'RIGHT', 'ENTER', 'SPACE', 'ESC', 'BACKSPACE',
             'CTRL_C', 'CTRL_D', or the raw single character.
    """
    if not sys.stdin.isatty():
        return sys.stdin.read(1)

    set_raw_mode()
    try:
        ch = sys.stdin.read(1)
        if ch == '\x03':  # Ctrl+C
            return 'CTRL_C'
        elif ch == '\x04':  # Ctrl+D
            return 'CTRL_D'
        elif ch in ('\r', '\n'):
            return 'ENTER'
        elif ch == ' ':
            return 'SPACE'
        elif ch in ('\x7f', '\x08'):
            return 'BACKSPACE'
        elif ch == '\x1b':
            # Check for trailing escape characters within 40ms
            r, _, _ = select.select([sys.stdin], [], [], 0.04)
            if not r:
                return 'ESC'

            seq1 = sys.stdin.read(1)
            if seq1 in ('[', 'O'):
                r2, _, _ = select.select([sys.stdin], [], [], 0.04)
                if r2:
                    code = sys.stdin.read(1)
                    # Drain any remaining bytes in multi-byte sequence (e.g. \x1b[1;2A)
                    while True:
                        r_more, _, _ = select.select([sys.stdin], [], [], 0.01)
                        if r_more:
                            sys.stdin.read(1)
                        else:
                            break

                    if code in ('A',): return 'UP'
                    if code in ('B',): return 'DOWN'
                    if code in ('C',): return 'RIGHT'
                    if code in ('D',): return 'LEFT'
                    if code in ('H',): return 'HOME'
                    if code in ('F',): return 'END'
            return 'ESC'
        return ch
    finally:
        restore_terminal()

# ANSI Color & Formatting Constants
CYAN = "\033[36m"
BRIGHT_CYAN = "\033[96m"
GREEN = "\033[32m"
BRIGHT_GREEN = "\033[92m"
YELLOW = "\033[33m"
BRIGHT_YELLOW = "\033[93m"
RED = "\033[31m"
BRIGHT_RED = "\033[91m"
MAGENTA = "\033[35m"
BLUE = "\033[34m"
WHITE = "\033[37m"
BRIGHT_WHITE = "\033[97m"
BOLD = "\033[1m"
DIM = "\033[2m"
ITALIC = "\033[3m"
RESET = "\033[0m"

def clear_screen():
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()

def hide_cursor():
    sys.stdout.write("\033[?25l")
    sys.stdout.flush()

def show_cursor():
    sys.stdout.write("\033[?25h")
    sys.stdout.flush()

init_terminal_cleanup()

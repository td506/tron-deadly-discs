"""Right stick -> TRON throw keys, one clean keypad press per flick.

jzIntv's own stick handling never releases a direction when the stick slides
into the next one, so keypad keys pile up (and 1+9 together pauses the game).
This reads the Xbox right stick through XInput and sends jzIntv's keyboard keys
1-9 (right controller keypad) instead: a key goes down when the stick leaves
the centre, stays the same key until the stick returns, then goes up.

    py tools/right_stick.py <jzintv pid>

Keys are only sent while that jzIntv window has focus; the helper exits when
jzIntv does.  Started automatically by tron_build.run() and trace_session.py.
"""
import ctypes
import ctypes.wintypes as W
import math
import sys
import time

PUSH = 0.60         # fraction of full deflection that counts as a throw
RELEASE = 0.30      # back below this = stick centred, key released
POLL = 0.004        # seconds

# Direction sector (0 = E, counter-clockwise in 45-degree steps) -> key '1'-'9'
SECTOR_KEY = ["6", "3", "2", "1", "4", "7", "8", "9"]
SCANCODE = {str(n): 0x01 + n for n in range(1, 10)}     # main-row digits


class XINPUT_GAMEPAD(ctypes.Structure):
    _fields_ = [("wButtons", W.WORD), ("bLeftTrigger", W.BYTE), ("bRightTrigger", W.BYTE),
                ("sThumbLX", W.SHORT), ("sThumbLY", W.SHORT),
                ("sThumbRX", W.SHORT), ("sThumbRY", W.SHORT)]


class XINPUT_STATE(ctypes.Structure):
    _fields_ = [("dwPacketNumber", W.DWORD), ("Gamepad", XINPUT_GAMEPAD)]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", W.WORD), ("wScan", W.WORD), ("dwFlags", W.DWORD),
                ("time", W.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class INPUT(ctypes.Structure):
    class _U(ctypes.Union):
        _fields_ = [("ki", KEYBDINPUT), ("pad", ctypes.c_byte * 32)]
    _anonymous_ = ("u",)
    _fields_ = [("type", W.DWORD), ("u", _U)]


user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
xinput = ctypes.windll.xinput1_4


def send_key(key, up):
    flags = 0x0008 | (0x0002 if up else 0)          # KEYEVENTF_SCANCODE [| KEYUP]
    inp = INPUT(type=1)
    inp.ki = KEYBDINPUT(0, SCANCODE[key], flags, 0, 0)
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))


def focused_pid():
    pid = W.DWORD()
    user32.GetWindowThreadProcessId(user32.GetForegroundWindow(), ctypes.byref(pid))
    return pid.value


def read_stick():
    """Right stick as (x, y) in -1..1, y up; None if no controller."""
    state = XINPUT_STATE()
    for pad in range(4):
        if xinput.XInputGetState(pad, ctypes.byref(state)) == 0:
            g = state.Gamepad
            return g.sThumbRX / 32767.0, g.sThumbRY / 32767.0
    return None


def main():
    pid = int(sys.argv[1])
    proc = kernel32.OpenProcess(0x00100000, False, pid)     # SYNCHRONIZE
    held = None
    try:
        while kernel32.WaitForSingleObject(proc, 0) != 0:    # until jzIntv exits
            stick = read_stick() if focused_pid() == pid else None
            mag = math.hypot(*stick) if stick else 0.0
            if held and mag < RELEASE:
                send_key(held, up=True)
                held = None
            elif not held and mag > PUSH:
                angle = math.degrees(math.atan2(stick[1], stick[0])) % 360
                held = SECTOR_KEY[int((angle + 22.5) // 45) % 8]
                send_key(held, up=False)
            time.sleep(POLL)
    finally:
        if held:
            send_key(held, up=True)


if __name__ == "__main__":
    main()

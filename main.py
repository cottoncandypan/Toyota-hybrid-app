"""
ToyotaScan Android — v2
Pastel UI · Toyota Prius · Veepeak Bluetooth OBD2
"""

import threading
import time
import queue
import math
import random
from datetime import datetime

from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen, SlideTransition
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.widget import Widget
from kivy.uix.popup import Popup
from kivy.uix.textinput import TextInput
from kivy.graphics import Color, RoundedRectangle, Rectangle
from kivy.clock import Clock, mainthread
from kivy.core.window import Window
from kivy.metrics import dp, sp
from kivy.properties import ListProperty
from kivy.utils import get_color_from_hex as hex_c

# ── Bluetooth (Android only, graceful fallback) ──────────────────────────────
try:
    from jnius import autoclass
    from android.permissions import request_permissions, Permission
    BluetoothAdapter = autoclass('android.bluetooth.BluetoothAdapter')
    BluetoothDevice  = autoclass('android.bluetooth.BluetoothDevice')
    BluetoothSocket  = autoclass('android.bluetooth.BluetoothSocket')
    UUID             = autoclass('java.util.UUID')
    BLUETOOTH_AVAILABLE = True
except Exception:
    BLUETOOTH_AVAILABLE = False

SPP_UUID = "00001101-0000-1000-8000-00805F9B34FB"

# ── Pastel palette ────────────────────────────────────────────────────────────
C = {
    # backgrounds
    "bg":       hex_c("F7F0F5"),   # very light pinkish white
    "surface":  hex_c("EEE5F0"),   # soft lavender-pink
    "panel":    hex_c("FFFFFF"),   # white cards
    "panel2":   hex_c("F0EAF6"),   # slightly tinted panel
    "border":   hex_c("D9C8E3"),   # muted lavender border

    # accents
    "pink":     hex_c("F4A7C0"),   # pastel pink
    "pink2":    hex_c("E87DAA"),   # deeper pink for active states
    "blue":     hex_c("8EC5E6"),   # pastel blue
    "blue2":    hex_c("5BAAD4"),   # deeper pastel blue
    "mint":     hex_c("85D4C8"),   # pastel teal/mint
    "mint2":    hex_c("4BBDAF"),   # deeper mint
    "lavender": hex_c("B8A9E3"),   # pastel purple
    "peach":    hex_c("F4C49A"),   # pastel amber/peach
    "sage":     hex_c("A8D5A2"),   # pastel green

    # text
    "text":     hex_c("2D2438"),   # dark plum — readable on white
    "muted":    hex_c("8A7A9B"),   # medium muted purple-grey
    "muted2":   hex_c("6B5D7A"),   # slightly darker muted

    # status colours (kept vivid enough to be meaningful)
    "warn":     hex_c("E8703D"),   # orange for warnings
    "danger":   hex_c("D94F6B"),   # rose-red for errors
    "ok":       hex_c("5CBF8A"),   # green for OK
}

# ── PID definitions ───────────────────────────────────────────────────────────
# (name, mode, pid, unit, formula, min, max)
STANDARD_PIDS = [
    ("Engine RPM",         "01", "0C", "rpm",  "rpm",       0,    8000),
    ("Vehicle Speed",      "01", "0D", "km/h", "speed",     0,    250),
    ("Coolant Temp",       "01", "05", "°C",   "temp",     -40,   130),
    ("Intake Air Temp",    "01", "0F", "°C",   "temp",     -40,   100),
    ("Throttle Position",  "01", "11", "%",    "pct",       0,    100),
    ("Engine Load",        "01", "04", "%",    "pct",       0,    100),
    ("Short Fuel Trim B1", "01", "06", "%",    "fuel_trim",-30,    30),
    ("Long Fuel Trim B1",  "01", "07", "%",    "fuel_trim",-30,    30),
    ("O2 Sensor B1S1",     "01", "14", "V",    "o2",        0,    1.275),
    ("MAF Air Flow",       "01", "10", "g/s",  "maf",       0,    200),
    ("Ignition Timing",    "01", "0E", "°",    "timing",   -10,    60),
    ("Fuel Level",         "01", "2F", "%",    "pct",       0,    100),
]

# Prius Toyota-enhanced PIDs
# (name, mode, pid, unit, decode_fn, min, max)
# decode_fn receives raw byte list and returns float
def _prius_soc(d):
    # Mode 21 PID 10: byte[2] is SOC * 0.5
    return d[2] * 0.5 if len(d) > 2 else 0

def _prius_pack_v(d):
    # Mode 22 F401: bytes [2],[3] big-endian * 0.1
    return ((d[2] << 8) | d[3]) * 0.1 if len(d) > 3 else 0

def _prius_pack_a(d):
    # Signed 16-bit * 0.1
    raw = (d[2] << 8) | d[3]
    if raw > 32767: raw -= 65536
    return raw * 0.1 if len(d) > 3 else 0

def _prius_temp(d):
    return d[2] - 40 if len(d) > 2 else 0

def _prius_mg_speed(d):
    # Signed 16-bit rpm
    raw = (d[2] << 8) | d[3]
    if raw > 32767: raw -= 65536
    return float(raw) if len(d) > 3 else 0

def _prius_torque(d):
    raw = (d[2] << 8) | d[3]
    if raw > 32767: raw -= 65536
    return raw * 0.5 if len(d) > 3 else 0

def _prius_inv_temp(d):
    return ((d[2] << 8) | d[3]) * 0.1 - 40 if len(d) > 3 else 0

def _prius_dcdc(d):
    return ((d[2] << 8) | d[3]) * 0.01 if len(d) > 3 else 0

def _prius_vvt(d):
    return (d[2] - 128) * 0.5 if len(d) > 2 else 0

def _prius_oil(d):
    return d[2] - 40 if len(d) > 2 else 0

def _prius_fan(d):
    return float(d[2]) * 100 if len(d) > 2 else 0

def _prius_soh(d):
    return d[2] * 0.5 if len(d) > 2 else 0

PRIUS_PIDS = [
    # (name, mode, pid_hex, unit, decode_fn, min, max)
    ("HV Battery SOC",     "21", "10",   "%",   _prius_soc,      0,   100),
    ("HV Battery Voltage", "22", "F401", "V",   _prius_pack_v,   0,   300),
    ("HV Battery Current", "22", "F402", "A",   _prius_pack_a, -200,  200),
    ("HV Battery Temp",    "22", "F403", "°C",  _prius_temp,   -40,    80),
    ("MG1 Speed",          "22", "E3",   "rpm", _prius_mg_speed,-10000,10000),
    ("MG2 Speed",          "22", "E4",   "rpm", _prius_mg_speed,-10000,10000),
    ("MG1 Torque",         "22", "E5",   "Nm",  _prius_torque, -300,  300),
    ("MG2 Torque",         "22", "E6",   "Nm",  _prius_torque, -300,  300),
    ("Inverter Temp",      "22", "F405", "°C",  _prius_inv_temp,-40,  200),
    ("DC-DC Output",       "22", "F406", "V",   _prius_dcdc,    0,    20),
    ("VVT Advance B1",     "21", "25",   "°CA", _prius_vvt,   -50,    50),
    ("Oil Temp",           "21", "61",   "°C",  _prius_oil,   -40,   200),
    ("Battery Fan Speed",  "22", "F407", "rpm", _prius_fan,     0,   5000),
    ("HV SOH",             "22", "F408", "%",   _prius_soh,     0,   100),
]

HYBRID_DTCS = {
    "HV ECU": [
        ("P3000", "HV Battery Malfunction — General HV system fault. Check cell voltages and cooling."),
        ("P3009", "HV Voltage Leak — Insulation resistance too low. Inspect all HV wiring."),
        ("P3004", "HV Battery Pack Voltage Low — Below operational threshold."),
    ],
    "Battery ECU": [
        ("P0A80", "Replace Hybrid Battery Pack — State of health below serviceable threshold."),
        ("P0A7F", "Hybrid Battery Pack Deterioration — Capacity degraded."),
        ("P0AC0", "Drive Motor A Temperature Sensor — MG2 temp sensor out of range."),
        ("P0A94", "DC/DC Converter Performance — 12V converter not meeting output."),
    ],
    "Inverter ECU": [
        ("P0B40", "Generator Inverter Performance — MG1 inverter output abnormal."),
        ("P0B41", "Drive Motor Inverter Performance — MG2 inverter output abnormal."),
    ],
}

DTC_DB = {
    "P0100": "Mass Air Flow Circuit Malfunction",
    "P0115": "Engine Coolant Temperature Circuit Malfunction",
    "P0120": "Throttle/Pedal Position Sensor A Circuit",
    "P0130": "O2 Sensor Circuit Malfunction (Bank 1 Sensor 1)",
    "P0171": "System Too Lean (Bank 1)",
    "P0172": "System Too Rich (Bank 1)",
    "P0300": "Random/Multiple Cylinder Misfire",
    "P0301": "Cylinder 1 Misfire Detected",
    "P0302": "Cylinder 2 Misfire Detected",
    "P0325": "Knock Sensor 1 Circuit Malfunction",
    "P0335": "Crankshaft Position Sensor A Circuit",
    "P0420": "Catalyst System Efficiency Below Threshold (Bank 1)",
    "P0440": "Evaporative Emission Control System Malfunction",
    "P0500": "Vehicle Speed Sensor Malfunction",
}


# ════════════════════════════════════════════════════════════════════════════
#  VEEPEAK BLUETOOTH MANAGER
# ════════════════════════════════════════════════════════════════════════════
class VeepeakManager:
    def __init__(self):
        self.socket      = None
        self.in_stream   = None
        self.out_stream  = None
        self.connected   = False
        self.demo_mode   = False
        self._lock       = threading.Lock()
        self.elm_version = ""

    def scan_paired_devices(self):
        if not BLUETOOTH_AVAILABLE:
            return [("VEEPEAK (demo)", "00:11:22:33:44:55")]
        try:
            adapter = BluetoothAdapter.getDefaultAdapter()
            if not adapter: return []
            return [(d.getName(), d.getAddress())
                    for d in adapter.getBondedDevices().toArray()]
        except Exception as e:
            return []

    def connect(self, address, callback):
        threading.Thread(target=self._connect_thread,
                         args=(address, callback), daemon=True).start()

    def _connect_thread(self, address, callback):
        if self.demo_mode:
            time.sleep(1.0)
            self.connected = True
            callback(True, "Demo mode active")
            return
        if not BLUETOOTH_AVAILABLE:
            self.connected = True
            callback(True, "Connected (dev build)")
            return
        try:
            adapter = BluetoothAdapter.getDefaultAdapter()
            device  = adapter.getRemoteDevice(address)
            uuid    = UUID.fromString(SPP_UUID)
            # Try insecure socket first (works without PIN re-prompt)
            try:
                sock = device.createInsecureRfcommSocketToServiceRecord(uuid)
            except Exception:
                sock = device.createRfcommSocketToServiceRecord(uuid)
            adapter.cancelDiscovery()
            sock.connect()
            self.socket     = sock
            self.in_stream  = sock.getInputStream()
            self.out_stream = sock.getOutputStream()
            self.connected  = True
            self._init_elm()
            callback(True, f"Connected to {device.getName()}")
        except Exception as e:
            self.connected = False
            callback(False, str(e))

    def disconnect(self):
        self.connected = False
        try:
            if self.socket: self.socket.close()
        except Exception:
            pass
        self.socket = self.in_stream = self.out_stream = None

    def _init_elm(self):
        """Send ELM327 initialisation sequence."""
        cmds = ["ATZ", "ATE0", "ATL0", "ATS0", "ATH1", "ATSP0"]
        for cmd in cmds:
            self._send_raw(cmd)
            time.sleep(0.2)
        resp = self._send_raw("ATI")
        self.elm_version = resp.strip()

    def _send_raw(self, cmd):
        """Send command, return raw string response."""
        if self.demo_mode or not BLUETOOTH_AVAILABLE:
            return self._demo_response(cmd)
        if not self.out_stream or not self.in_stream:
            return ""
        with self._lock:
            try:
                # Write command
                for b in (cmd + "\r").encode("ascii"):
                    self.out_stream.write(b)
                self.out_stream.flush()
                # Read until '>' prompt with timeout
                resp  = bytearray()
                start = time.time()
                while time.time() - start < 4.0:
                    if self.in_stream.available() > 0:
                        byte = self.in_stream.read()
                        resp.append(byte)
                        if byte == ord(">"):
                            break
                    else:
                        time.sleep(0.01)
                return resp.decode("ascii", errors="ignore").replace("\r", "\n")
            except Exception as e:
                return ""

    def query(self, mode, pid):
        """Send OBD query, return parsed byte list or None."""
        raw = self._send_raw(mode + pid)
        return self._parse(raw)

    def _parse(self, raw):
        for line in raw.split("\n"):
            line = line.replace(">", "").strip()
            if not line or line.upper() in ("NO DATA", "ERROR", "?",
                                             "SEARCHING...", "STOPPED"):
                continue
            parts = line.split()
            if len(parts) >= 2:
                try:
                    return [int(b, 16) for b in parts]
                except ValueError:
                    continue
        return None

    def read_dtcs(self):
        raw = self._send_raw("03")
        return self._parse_dtcs(raw)

    def clear_dtcs(self):
        r = self._send_raw("04")
        return "44" in r.upper() or "OK" in r.upper()

    def _parse_dtcs(self, raw):
        dtcs = []
        for line in raw.split("\n"):
            parts = line.replace(">", "").split()
            try:
                data = [int(b, 16) for b in parts]
                i = 1
                while i + 1 < len(data):
                    b1, b2 = data[i], data[i+1]
                    if b1 == 0 and b2 == 0:
                        i += 2; continue
                    prefix = {0:"P",1:"C",2:"B",3:"U"}[(b1>>6)&0x03]
                    dtcs.append(f"{prefix}{((b1&0x3F)<<8)|b2:04X}")
                    i += 2
            except Exception:
                continue
        return dtcs

    def send_custom(self, mode, pid, data=""):
        return self._send_raw(mode + pid + data)

    # ── Demo response simulator ───────────────────────────────────────────────
    def _demo_response(self, cmd):
        t   = time.time()
        c   = cmd.upper().strip()
        soc = int(55 + 15 * math.sin(t * 0.1))
        pv  = int((195 + 2 * math.sin(t * 0.2)) * 10)
        pa  = int(20 * math.sin(t * 0.3) + 128)
        pt  = int(28 + 4 * math.sin(t * 0.04) + 40)
        mg1 = int(1800 + 400 * math.sin(t * 0.4))
        mg2 = int(2500 + 800 * math.sin(t * 0.3))

        table = {
            "ATZ":   "ELM327 v1.5\r\n>",
            "ATI":   "ELM327 v1.5\r\n>",
            "ATDP":  "ISO 15765-4 (CAN 11/500)\r\n>",
            "ATE0":  "OK\r\n>", "ATL0": "OK\r\n>",
            "ATS0":  "OK\r\n>", "ATH1": "OK\r\n>",
            "ATSP0": "OK\r\n>",
            "03":    "43 01 03 00 01 0A 7F 00 00\r\n>",
            "04":    "44\r\n>",
            "010C":  f"41 0C {int((800+1200*abs(math.sin(t*0.3)))*4)//256:02X} {int((800+1200*abs(math.sin(t*0.3)))*4)%256:02X}\r\n>",
            "010D":  f"41 0D {max(0,int(60+30*math.sin(t*0.1))):02X}\r\n>",
            "0105":  f"41 05 {int(88+2*math.sin(t*0.05)+40):02X}\r\n>",
            "010F":  f"41 0F {int(25+3*math.sin(t*0.07)+40):02X}\r\n>",
            "0111":  f"41 11 {int((15+10*abs(math.sin(t*0.4)))*255/100):02X}\r\n>",
            "0104":  f"41 04 {int((30+20*abs(math.sin(t*0.3)))*255/100):02X}\r\n>",
            "0106":  f"41 06 {int((2.3+1.5*math.sin(t*2)+100)*128/100):02X}\r\n>",
            "0107":  f"41 07 {int((1.6+0.5*math.sin(t*0.1)+100)*128/100):02X}\r\n>",
            "0114":  f"41 14 {int((0.45+0.4*math.sin(t))/0.005):02X} FF\r\n>",
            "0110":  f"41 10 {int((5.2+3*abs(math.sin(t*0.3)))*100)//256:02X} {int((5.2+3*abs(math.sin(t*0.3)))*100)%256:02X}\r\n>",
            "010E":  f"41 0E {int((10+5*math.sin(t*0.5))+64)*2:02X}\r\n>",
            "012F":  "41 2F B8\r\n>",
            "2110":  f"61 10 {soc*2:02X}\r\n>",
            "22F401":f"62 F4 01 {pv//256:02X} {pv%256:02X}\r\n>",
            "22F402":f"62 F4 02 {pa:02X} 00\r\n>",
            "22F403":f"62 F4 03 {pt:02X}\r\n>",
            "22E3":  f"62 E3 {mg1//256:02X} {mg1%256:02X}\r\n>",
            "22E4":  f"62 E4 {mg2//256:02X} {mg2%256:02X}\r\n>",
            "22E5":  f"62 E5 {int(50+20*math.sin(t*0.4)+128):02X} 00\r\n>",
            "22E6":  f"62 E6 {int(120+40*math.sin(t*0.3)+128):02X} 00\r\n>",
            "22F405":f"62 F4 05 {int((45+8*math.sin(t*0.05)+40)*10)//256:02X} {int((45+8*math.sin(t*0.05)+40)*10)%256:02X}\r\n>",
            "22F406":f"62 F4 06 {int(14.1*100):02X} 46\r\n>",
            "2125":  f"61 25 {int(15+12*math.sin(t*0.4)+128):02X}\r\n>",
            "2161":  f"61 61 {int(95+3*math.sin(t*0.03)+40):02X}\r\n>",
            "22F407":f"62 F4 07 {int(12):02X}\r\n>",
            "22F408":f"62 F4 08 {int(91*2):02X}\r\n>",
        }
        return table.get(c, "NO DATA\r\n>")


# ════════════════════════════════════════════════════════════════════════════
#  REUSABLE UI COMPONENTS  (pastel theme)
# ════════════════════════════════════════════════════════════════════════════
class PastelButton(Button):
    btn_color = ListProperty(list(hex_c("F4A7C0")))

    def __init__(self, **kw):
        super().__init__(**kw)
        self.background_color  = (0,0,0,0)
        self.background_normal = ""
        self.color             = C["text"]
        self.font_size         = sp(11)
        self.size_hint_y       = None
        self.height            = dp(48)
        self.bold              = True
        self.bind(pos=self._draw, size=self._draw)

    def _draw(self, *_):
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*self.btn_color)
            RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(12)])

    def on_press(self):
        self._orig = list(self.btn_color)
        self.btn_color = [min(1, c * 0.85) for c in self.btn_color[:3]] + [1]

    def on_release(self):
        if hasattr(self, "_orig"):
            self.btn_color = self._orig


class Card(BoxLayout):
    def __init__(self, color=None, border_color=None, **kw):
        super().__init__(**kw)
        self._fill   = color or C["panel"]
        self._border = border_color or C["border"]
        self.bind(pos=self._draw, size=self._draw)

    def _draw(self, *_):
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*self._border)
            RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(14)])
            # inset 1px for border effect
            Color(*self._fill)
            RoundedRectangle(
                pos=(self.x+1, self.y+1),
                size=(self.width-2, self.height-2),
                radius=[dp(13)]
            )


class SectionLabel(Label):
    def __init__(self, **kw):
        kw.setdefault("color", C["muted"])
        kw.setdefault("font_size", sp(9))
        kw.setdefault("size_hint_y", None)
        kw.setdefault("height", dp(26))
        kw.setdefault("halign", "left")
        kw.setdefault("valign", "bottom")
        kw.setdefault("bold", True)
        super().__init__(**kw)
        self.bind(size=lambda *_: setattr(self, "text_size", self.size))


def DarkLabel(**kw):
    kw.setdefault("color", C["text"])
    kw.setdefault("halign", "left")
    kw.setdefault("valign", "center")
    lbl = Label(**kw)
    lbl.bind(size=lambda *_: setattr(lbl, "text_size", lbl.size))
    return lbl

def MutedLabel(**kw):
    kw.setdefault("color", C["muted"])
    kw.setdefault("halign", "left")
    kw.setdefault("valign", "center")
    lbl = Label(**kw)
    lbl.bind(size=lambda *_: setattr(lbl, "text_size", lbl.size))
    return lbl


# ════════════════════════════════════════════════════════════════════════════
#  PID CARD
# ════════════════════════════════════════════════════════════════════════════
class PIDCard(BoxLayout):
    def __init__(self, name, unit, mn, mx, accent, **kw):
        kw.setdefault("orientation", "vertical")
        kw.setdefault("padding",     [dp(10), dp(8)])
        kw.setdefault("spacing",     dp(3))
        kw.setdefault("size_hint_y", None)
        kw.setdefault("height",      dp(90))
        super().__init__(**kw)
        self._mn     = mn
        self._mx     = mx
        self._accent = accent
        self._val    = 0.0

        self._name_lbl = MutedLabel(
            text=name.upper(), font_size=sp(8),
            size_hint_y=None, height=dp(14)
        )
        self._val_lbl = Label(
            text="---", font_size=sp(26), bold=True,
            color=accent, halign="left", valign="center",
            size_hint_y=None, height=dp(34)
        )
        self._val_lbl.bind(size=lambda *_: setattr(s

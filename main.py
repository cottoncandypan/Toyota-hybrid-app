"""
ToyotaScan Android
Toyota/Prius Diagnostic App — Veepeak Bluetooth OBD2
Built with Kivy + python-for-android
"""

import threading
import time
import queue
import math
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
from kivy.graphics import Color, RoundedRectangle, Rectangle, Line, Ellipse
from kivy.clock import Clock, mainthread
from kivy.core.window import Window
from kivy.metrics import dp, sp
from kivy.properties import (StringProperty, NumericProperty,
                               BooleanProperty, ListProperty, ObjectProperty)
from kivy.utils import get_color_from_hex as hex_c

# ── Bluetooth import (Android only, graceful fallback for dev) ──────────────
try:
    from jnius import autoclass, cast
    from android.permissions import request_permissions, Permission
    BluetoothAdapter  = autoclass('android.bluetooth.BluetoothAdapter')
    BluetoothDevice   = autoclass('android.bluetooth.BluetoothDevice')
    BluetoothSocket   = autoclass('android.bluetooth.BluetoothSocket')
    UUID              = autoclass('java.util.UUID')
    BLUETOOTH_AVAILABLE = True
except Exception:
    BLUETOOTH_AVAILABLE = False

# SPP UUID — standard Serial Port Profile, works with all ELM327 adapters
SPP_UUID = "00001101-0000-1000-8000-00805F9B34FB"

# ── Colours ──────────────────────────────────────────────────────────────────
C = {
    "bg":      hex_c("0A0E18"),
    "surface": hex_c("12172A"),
    "panel":   hex_c("1A2035"),
    "panel2":  hex_c("1E2640"),
    "border":  hex_c("252E48"),
    "red":     hex_c("E8003D"),
    "blue":    hex_c("1A8FFF"),
    "green":   hex_c("00D97E"),
    "amber":   hex_c("FFB400"),
    "teal":    hex_c("00C8B4"),
    "text":    hex_c("E2E8F4"),
    "muted":   hex_c("5A6A8A"),
    "muted2":  hex_c("8A9ABB"),
}

# ── PID Definitions ──────────────────────────────────────────────────────────
STANDARD_PIDS = [
    ("Engine RPM",         "01", "0C", "rpm",   "rpm",      0,    8000),
    ("Vehicle Speed",      "01", "0D", "km/h",  "speed",    0,    250),
    ("Coolant Temp",       "01", "05", "°C",    "temp",    -40,   215),
    ("Intake Air Temp",    "01", "0F", "°C",    "temp",    -40,   215),
    ("Throttle Position",  "01", "11", "%",     "pct",      0,    100),
    ("Engine Load",        "01", "04", "%",     "pct",      0,    100),
    ("Short Fuel Trim B1", "01", "06", "%",     "fuel_trim",-100,  99),
    ("Long Fuel Trim B1",  "01", "07", "%",     "fuel_trim",-100,  99),
    ("O2 Sensor B1S1",     "01", "14", "V",     "o2",       0,    1.275),
    ("MAF Air Flow",       "01", "10", "g/s",   "maf",      0,    655),
    ("Ignition Timing",    "01", "0E", "°",     "timing",  -64,   63.5),
    ("Fuel Level",         "01", "2F", "%",     "pct",      0,    100),
]

PRIUS_PIDS = [
    ("HV Battery SOC",     "21", "10", "%",     None,       0,    100),
    ("HV Battery Voltage", "22", "F401","V",    None,       0,    300),
    ("HV Battery Current", "22", "F402","A",    None,      -200,  200),
    ("HV Battery Temp",    "22", "F403","°C",   None,      -40,   80),
    ("MG1 Speed",          "22", "E3",  "rpm",  None,      -10000,10000),
    ("MG2 Speed",          "22", "E4",  "rpm",  None,      -10000,10000),
    ("MG1 Torque",         "22", "E5",  "Nm",   None,      -200,  200),
    ("MG2 Torque",         "22", "E6",  "Nm",   None,      -200,  200),
    ("Inverter Temp",      "22", "F405","°C",   None,      -40,   200),
    ("DC-DC Output",       "22", "F406","V",    None,       0,    20),
    ("VVT Advance B1",     "21", "25",  "°CA",  None,      -50,   50),
    ("Oil Temp",           "21", "61",  "°C",   None,      -40,   200),
    ("Battery Fan Speed",  "22", "F407","rpm",  None,       0,    5000),
    ("HV SOH",             "22", "F408","%",    None,       0,    100),
]

HYBRID_DTCS = {
    "HV ECU": [
        ("P3000", "HV Battery Malfunction — General HV system fault. Check cell block voltages and cooling system."),
        ("P3009", "HV Battery High Voltage Leak — Insulation resistance too low. Inspect all HV wiring."),
        ("P3004", "HV Battery Pack Voltage Low — Pack voltage below operational threshold."),
    ],
    "Battery ECU": [
        ("P0A80", "Replace Hybrid Battery Pack — State of health below serviceable threshold."),
        ("P0A7F", "Hybrid Battery Pack Deterioration — Capacity degraded, trending toward replacement."),
        ("P0AC0", "Drive Motor A Temperature Sensor — MG2 temp sensor out of range."),
        ("P0A94", "DC/DC Converter Performance — 12V converter not meeting output requirements."),
    ],
    "Inverter ECU": [
        ("P0B40", "Generator Inverter Performance — MG1 inverter output abnormal."),
        ("P0B41", "Drive Motor Inverter Performance — MG2 inverter output abnormal."),
    ],
}

DTC_DB = {
    "P0100": "Mass Air Flow Circuit Malfunction",
    "P0115": "Engine Coolant Temperature Circuit Malfunction",
    "P0120": "Throttle Position Sensor A Circuit Malfunction",
    "P0130": "O2 Sensor Circuit Malfunction (Bank 1 Sensor 1)",
    "P0171": "System Too Lean (Bank 1)",
    "P0172": "System Too Rich (Bank 1)",
    "P0300": "Random/Multiple Cylinder Misfire Detected",
    "P0301": "Cylinder 1 Misfire Detected",
    "P0302": "Cylinder 2 Misfire Detected",
    "P0325": "Knock Sensor 1 Circuit Malfunction",
    "P0335": "Crankshaft Position Sensor A Circuit Malfunction",
    "P0420": "Catalyst System Efficiency Below Threshold (Bank 1)",
    "P0440": "Evaporative Emission Control System Malfunction",
    "P0500": "Vehicle Speed Sensor Malfunction",
}


# ════════════════════════════════════════════════════════════════════════════
#  BLUETOOTH / ELM327 MANAGER
# ════════════════════════════════════════════════════════════════════════════
class VeepeakManager:
    """Handles Bluetooth SPP connection and ELM327 protocol for Veepeak adapter."""

    def __init__(self):
        self.socket      = None
        self.in_stream   = None
        self.out_stream  = None
        self.connected   = False
        self.demo_mode   = False
        self._lock       = threading.Lock()
        self.elm_version = ""
        self.log_queue   = queue.Queue()

    # ── Bluetooth scanning ──────────────────────────────────────────────────
    def scan_paired_devices(self):
        """Return list of (name, address) for all paired BT devices."""
        if not BLUETOOTH_AVAILABLE:
            return [("VEEPEAK OBDCheck (demo)", "00:11:22:33:44:55")]
        try:
            adapter = BluetoothAdapter.getDefaultAdapter()
            if adapter is None:
                return []
            paired = adapter.getBondedDevices().toArray()
            return [(d.getName(), d.getAddress()) for d in paired]
        except Exception as e:
            self._log(f"Scan error: {e}")
            return []

    # ── Connect ─────────────────────────────────────────────────────────────
    def connect(self, address, callback):
        """Connect to device in background thread, call callback(ok, msg)."""
        threading.Thread(target=self._connect_thread,
                         args=(address, callback), daemon=True).start()

    def _connect_thread(self, address, callback):
        if self.demo_mode:
            time.sleep(1.2)
            self.connected = True
            callback(True, "DEMO — Veepeak simulated")
            return
        if not BLUETOOTH_AVAILABLE:
            self.connected = True
            callback(True, "Connected (no-BT dev build)")
            return
        try:
            adapter = BluetoothAdapter.getDefaultAdapter()
            device  = adapter.getRemoteDevice(address)
            uuid    = UUID.fromString(SPP_UUID)
            sock    = device.createRfcommSocketToServiceRecord(uuid)
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
            if self.socket:
                self.socket.close()
        except Exception:
            pass
        self.socket = self.in_stream = self.out_stream = None

    # ── ELM327 initialisation ───────────────────────────────────────────────
    def _init_elm(self):
        for cmd in ["ATZ", "ATE0", "ATL0", "ATS0", "ATH1", "ATSP0"]:
            self._send_raw(cmd)
            time.sleep(0.15)
        resp = self._send_raw("ATI")
        self.elm_version = resp.strip()
        self._log(f"ELM: {self.elm_version}")

    # ── Raw serial I/O ──────────────────────────────────────────────────────
    def _send_raw(self, cmd):
        if self.demo_mode or not BLUETOOTH_AVAILABLE:
            return self._demo_response(cmd)
        if not self.out_stream or not self.in_stream:
            return ""
        with self._lock:
            try:
                data = (cmd + "\r").encode("ascii")
                for b in data:
                    self.out_stream.write(b)
                self.out_stream.flush()
                resp, start = bytearray(), time.time()
                while time.time() - start < 3.0:
                    if self.in_stream.available() > 0:
                        resp.append(self.in_stream.read())
                        if resp.endswith(b">"):
                            break
                    else:
                        time.sleep(0.02)
                return resp.decode("ascii", errors="ignore").replace("\r", "\n")
            except Exception as e:
                self._log(f"IO error: {e}")
                return ""

    # ── OBD queries ─────────────────────────────────────────────────────────
    def query(self, mode, pid):
        raw = self._send_raw(mode + pid)
        return self._parse_response(raw)

    def _parse_response(self, raw):
        for line in raw.split("\n"):
            line = line.replace(">", "").strip()
            if not line or line.upper() in ("NO DATA", "ERROR", "?", "SEARCHING..."):
                continue
            parts = line.split()
            if len(parts) >= 3:
                try:
                    return [int(b, 16) for b in parts]
                except ValueError:
                    continue
        return None

    def read_dtcs(self):
        return self._parse_dtcs(self._send_raw("03"))

    def clear_dtcs(self):
        r = self._send_raw("04")
        return "44" in r.upper() or "OK" in r.upper()

    def _parse_dtcs(self, raw):
        dtcs = []
        for line in raw.split("\n"):
            parts = line.replace(">", "").split()
            try:
                data = [int(b, 16) for b in parts if b != ">"]
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

    # ── Demo response simulator ─────────────────────────────────────────────
    _demo_t = 0.0
    def _demo_response(self, cmd):
        t = time.time()
        c = cmd.upper().strip()
        responses = {
            "ATZ":   "ELM327 v1.5\r\n>",
            "ATI":   "ELM327 v1.5\r\n>",
            "ATDP":  "ISO 15765-4 (CAN 11/500)\r\n>",
            "ATE0":  "OK\r\n>", "ATL0": "OK\r\n>",
            "ATS0":  "OK\r\n>", "ATH1": "OK\r\n>",
            "ATSP0": "OK\r\n>",
            "03":    "43 01 03 00 01 0A 7F 00 00\r\n>",
            "04":    "44\r\n>",
            "010C":  f"41 0C {int((800 + 1200*abs(math.sin(t*0.3)))*4)//256:02X} {int((800 + 1200*abs(math.sin(t*0.3)))*4)%256:02X}\r\n>",
            "010D":  f"41 0D {int(60 + 30*math.sin(t*0.1)):02X}\r\n>",
            "0105":  f"41 05 {int(88 + 40):02X}\r\n>",
            "0104":  f"41 04 {int((30 + 20*abs(math.sin(t*0.3)))*255/100):02X}\r\n>",
            "0111":  f"41 11 {int((15 + 10*abs(math.sin(t*0.4)))*255/100):02X}\r\n>",
            "0106":  f"41 06 {int((2.3 + 1.5*math.sin(t*2) + 100)*128/100):02X}\r\n>",
            "0107":  f"41 07 {int((1.6 + 0.5*math.sin(t*0.1) + 100)*128/100):02X}\r\n>",
            "010F":  f"41 0F {int(25 + 3*math.sin(t*0.07) + 40):02X}\r\n>",
            "0114":  f"41 14 {int((0.45 + 0.4*math.sin(t))/0.005):02X} FF\r\n>",
            "0110":  f"41 10 {int((5.2+3*abs(math.sin(t*0.3)))*100)//256:02X} {int((5.2+3*abs(math.sin(t*0.3)))*100)%256:02X}\r\n>",
            "010E":  f"41 0E {int((10+5*math.sin(t*0.5))+64)*2:02X}\r\n>",
            "012F":  "41 2F B8\r\n>",
            # Prius hybrid PIDs
            "2110":  f"61 10 {int(55 + 15*math.sin(t*0.1)):02X} 00 2A\r\n>",
            "22F401":f"62 F4 01 {int((195 + 2*math.sin(t*0.2))*10)//256:02X} {int((195 + 2*math.sin(t*0.2))*10)%256:02X}\r\n>",
            "22F402":f"62 F4 02 {(int(20*math.sin(t*0.3))+128):02X} 00\r\n>",
            "22F403":f"62 F4 03 {int(28 + 4*math.sin(t*0.04) + 40):02X}\r\n>",
            "22E3":  f"62 E3 {int(1800 + 400*math.sin(t*0.4))//256:02X} {int(1800 + 400*math.sin(t*0.4))%256:02X}\r\n>",
            "22E4":  f"62 E4 {int(2500 + 800*math.sin(t*0.3))//256:02X} {int(2500 + 800*math.sin(t*0.3))%256:02X}\r\n>",
            "22F405":f"62 F4 05 {int(45 + 8*math.sin(t*0.05) + 40):02X}\r\n>",
            "22F406":f"62 F4 06 {int((14.1+0.2*math.sin(t*0.3))*10):02X}\r\n>",
            "2125":  f"61 25 {int(15+12*math.sin(t*0.4)+64):02X}\r\n>",
            "2161":  f"61 61 {int(95+3*math.sin(t*0.03)+40):02X}\r\n>",
        }
        return responses.get(c, "NO DATA\r\n>")

    def _log(self, msg):
        self.log_queue.put(msg)


# ════════════════════════════════════════════════════════════════════════════
#  REUSABLE UI WIDGETS
# ════════════════════════════════════════════════════════════════════════════
class StyledButton(Button):
    """Flat styled button with rounded corners."""
    btn_color = ListProperty([0.1, 0.14, 0.25, 1])
    text_color = ListProperty(C["text"])

    def __init__(self, **kw):
        super().__init__(**kw)
        self.background_color  = (0,0,0,0)
        self.background_normal = ""
        self.color             = C["text"]
        self.font_name         = "RobotoMono-Regular"
        self.font_size         = sp(11)
        self.size_hint_y       = None
        self.height            = dp(46)
        self.bind(pos=self._draw, size=self._draw)

    def _draw(self, *_):
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*self.btn_color)
            RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(10)])

    def on_press(self):
        self._orig = list(self.btn_color)
        self.btn_color = [min(1, c * 1.3) for c in self.btn_color[:3]] + [1]

    def on_release(self):
        if hasattr(self, "_orig"):
            self.btn_color = self._orig


class Card(BoxLayout):
    """Rounded panel card."""
    def __init__(self, color=None, **kw):
        super().__init__(**kw)
        self._color = color or C["panel"]
        self.bind(pos=self._draw, size=self._draw)

    def _draw(self, *_):
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*self._color)
            RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(12)])


class SectionLabel(Label):
    def __init__(self, **kw):
        kw.setdefault("color", C["muted"])
        kw.setdefault("font_size", sp(9))
        kw.setdefault("size_hint_y", None)
        kw.setdefault("height", dp(28))
        kw.setdefault("halign", "left")
        kw.setdefault("valign", "bottom")
        super().__init__(**kw)
        self.bind(size=lambda *_: setattr(self, "text_size", self.size))


class Mono(Label):
    """Monospace label shorthand."""
    def __init__(self, **kw):
        kw.setdefault("font_name", "RobotoMono-Regular")
        kw.setdefault("color", C["text"])
        super().__init__(**kw)


class MutedMono(Label):
    def __init__(self, **kw):
        kw.setdefault("font_name", "RobotoMono-Regular")
        kw.setdefault("color", C["muted"])
        super().__init__(**kw)


# ════════════════════════════════════════════════════════════════════════════
#  PID VALUE CARD WIDGET
# ════════════════════════════════════════════════════════════════════════════
class PIDCard(BoxLayout):
    """Live data card: name / value / unit / bar."""

    def __init__(self, name, unit, mn, mx, accent, **kw):
        kw.setdefault("orientation", "vertical")
        kw.setdefault("padding",     [dp(10), dp(8)])
        kw.setdefault("spacing",     dp(2))
        kw.setdefault("size_hint_y", None)
        kw.setdefault("height",      dp(88))
        super().__init__(**kw)

        self._mn     = mn
        self._mx     = mx
        self._accent = accent
        self._val    = 0.0
        self._bar_w  = 0

        self._name_lbl = MutedMono(
            text=name.upper(), font_size=sp(8),
            size_hint_y=None, height=dp(14),
            halign="left", valign="center"
        )
        self._name_lbl.bind(size=lambda *_: setattr(self._name_lbl, "text_size", self._name_lbl.size))

        self._val_lbl = Mono(
            text="---", font_size=sp(26),
            size_hint_y=None, height=dp(34),
            color=accent, halign="left", valign="center"
        )
        self._val_lbl.bind(size=lambda *_: setattr(self._val_lbl, "text_size", self._val_lbl.size))

        self._unit_lbl = MutedMono(
            text=unit, font_size=sp(9),
            size_hint_y=None, height=dp(14),
            halign="left", valign="center"
        )
        self._unit_lbl.bind(size=lambda *_: setattr(self._unit_lbl, "text_size", self._unit_lbl.size))

        self._bar_widget = Widget(size_hint_y=None, height=dp(4))
        self._bar_widget.bind(pos=self._draw_bar, size=self._draw_bar)

        self.add_widget(self._name_lbl)
        self.add_widget(self._val_lbl)
        self.add_widget(self._unit_lbl)
        self.add_widget(self._bar_widget)
        self.bind(pos=self._draw_bg, size=self._draw_bg)

    def _draw_bg(self, *_):
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*C["panel"])
            RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(10)])
            Color(*self._accent[:3], 0.8)
            RoundedRectangle(
                pos=(self.x, self.top - dp(2)),
                size=(self.width, dp(2)),
                radius=[dp(2)]
            )

    def _draw_bar(self, *_):
        w = self._bar_widget
        ratio = max(0, min(1, (self._val - self._mn) / max(self._mx - self._mn, 0.001)))
        color = (self._accent if ratio < 0.75
                 else C["amber"] if ratio < 0.92
                 else C["red"])
        w.canvas.clear()
        with w.canvas:
            Color(*C["border"])
            RoundedRectangle(pos=w.pos, size=w.size, radius=[dp(2)])
            Color(*color)
            RoundedRectangle(
                pos=w.pos,
                size=(w.width * ratio, w.height),
                radius=[dp(2)]
            )

    def update(self, value):
        self._val = value
        dp_val = 0 if abs(value) >= 100 else 1
        self._val_lbl.text = f"{value:.{dp_val}f}"
        ratio = max(0, min(1, (value - self._mn) / max(self._mx - self._mn, 0.001)))
        color = (self._accent if ratio < 0.75
                 else C["amber"] if ratio < 0.92
                 else C["red"])
        self._val_lbl.color = color
        self._draw_bar()


# ════════════════════════════════════════════════════════════════════════════
#  SCREENS
# ════════════════════════════════════════════════════════════════════════════

# ── CONNECT SCREEN ──────────────────────────────────────────────────────────
class ConnectScreen(Screen):
    def __init__(self, manager_ref, **kw):
        super().__init__(**kw)
        self.mgr   = manager_ref
        self._rows = []
        self._build()

    def _build(self):
        root = BoxLayout(orientation="vertical",
                         padding=[dp(16), dp(20)],
                         spacing=dp(12))
        self.add_widget(root)

        # Title
        root.add_widget(Mono(
            text="VEEPEAK BLUETOOTH",
            font_size=sp(18), color=C["teal"],
            size_hint_y=None, height=dp(36),
            halign="center"
        ))
        root.add_widget(MutedMono(
            text="Toyota Prius OBD2 Diagnostic",
            font_size=sp(11), size_hint_y=None, height=dp(24),
            halign="center"
        ))

        # Status box
        self._status = Mono(
            text="Tap SCAN to find your Veepeak adapter",
            font_size=sp(10), color=C["muted2"],
            size_hint_y=None, height=dp(40),
            halign="center", valign="center",
            text_size=(Window.width - dp(32), dp(40))
        )
        root.add_widget(self._status)

        # Scan button
        scan_btn = StyledButton(text="SCAN FOR VEEPEAK",
                                btn_color=list(C["teal"]) + [1])
        scan_btn.color = C["bg"]
        scan_btn.bind(on_press=self._scan)
        root.add_widget(scan_btn)

        # Device list
        self._device_list = BoxLayout(orientation="vertical", spacing=dp(8),
                                       size_hint_y=None)
        self._device_list.bind(minimum_height=self._device_list.setter("height"))
        sv = ScrollView()
        sv.add_widget(self._device_list)
        root.add_widget(sv)

        # Demo mode button
        demo_btn = StyledButton(text="DEMO MODE (no adapter)",
                                btn_color=list(C["border"]) + [1])
        demo_btn.bind(on_press=self._demo)
        root.add_widget(demo_btn)

    def _scan(self, *_):
        self._status.text = "Scanning paired Bluetooth devices..."
        self._device_list.clear_widgets()
        devices = self.mgr.scan_paired_devices()
        if not devices:
            self._status.text = ("No paired devices found.\n"
                                  "Pair Veepeak in Android Bluetooth settings first (PIN: 1234)")
            return
        self._status.text = f"Found {len(devices)} device(s) — tap to connect"
        for name, addr in devices:
            is_veepeak = "VEEP" in name.upper() or "OBD" in name.upper() or "ELM" in name.upper()
            color = list(C["teal"]) + [1] if is_veepeak else list(C["border"]) + [1]
            icon  = "⚡ " if is_veepeak else "🔵 "
            btn   = StyledButton(text=f"{icon}{name}\n{addr}",
                                  btn_color=color)
            btn.bind(on_press=lambda b, a=addr, n=name: self._connect(a, n))
            self._device_list.add_widget(btn)

    def _demo(self, *_):
        self.mgr.demo_mode = True
        self._connect("DEMO", "DEMO")

    def _connect(self, addr, name):
        self._status.text = f"Connecting to {name}..."
        self.mgr.connect(addr, self._on_connect_result)

    @mainthread
    def _on_connect_result(self, ok, msg):
        if ok:
            self._status.text = f"✓ {msg}"
            app = App.get_running_app()
            app.root.current = "main"
        else:
            self._status.text = f"✗ {msg}\n\nCheck Veepeak is powered on and paired."


# ── MAIN APP SCREEN ─────────────────────────────────────────────────────────
class MainScreen(Screen):
    def __init__(self, manager_ref, **kw):
        super().__init__(**kw)
        self.mgr        = manager_ref
        self.live_run   = False
        self.pid_cards  = {}
        self._build()

    def _build(self):
        root = BoxLayout(orientation="vertical")
        self.add_widget(root)

        # ── top bar ──
        topbar = BoxLayout(
            size_hint_y=None, height=dp(52),
            padding=[dp(12), dp(8)], spacing=dp(8)
        )
        with topbar.canvas.before:
            Color(0.025, 0.04, 0.09, 1)
            self._topbar_bg = Rectangle(pos=topbar.pos, size=topbar.size)
        topbar.bind(pos=lambda *_: setattr(self._topbar_bg, "pos", topbar.pos),
                    size=lambda *_: setattr(self._topbar_bg, "size", topbar.size))

        self._conn_dot = Label(text="●", color=C["green"],
                                font_size=sp(14), size_hint_x=None, width=dp(20))
        topbar.add_widget(self._conn_dot)
        topbar.add_widget(Mono(text="TOYOTASCAN", font_size=sp(14),
                                color=C["text"], size_hint_x=1))
        disc_btn = StyledButton(text="DISCONNECT",
                                 size_hint_x=None, width=dp(110),
                                 height=dp(36),
                                 btn_color=list(C["panel"]) + [1])
        disc_btn.font_size = sp(9)
        disc_btn.bind(on_press=self._disconnect)
        topbar.add_widget(disc_btn)
        root.add_widget(topbar)

        # ── tab bar ──
        self._tabs_bar = BoxLayout(size_hint_y=None, height=dp(44))
        with self._tabs_bar.canvas.before:
            Color(*C["surface"])
            Rectangle(pos=self._tabs_bar.pos, size=self._tabs_bar.size)
        self._tabs_bar.bind(
            pos=lambda *_: None, size=lambda *_: None)

        tab_names = ["LIVE", "HYBRID", "DTCs", "TESTS", "CONSOLE"]
        self._tab_btns = {}
        for name in tab_names:
            btn = Button(
                text=name,
                background_color=(0,0,0,0),
                background_normal="",
                color=C["muted"],
                font_name="RobotoMono-Regular",
                font_size=sp(10)
            )
            btn.bind(on_press=lambda b, n=name: self._switch_tab(n))
            self._tabs_bar.add_widget(btn)
            self._tab_btns[name] = btn
        root.add_widget(self._tabs_bar)

        # ── page container ──
        self._pages = {}
        self._page_container = BoxLayout()
        root.add_widget(self._page_container)

        # Build all pages
        self._pages["LIVE"]    = self._build_live_page()
        self._pages["HYBRID"]  = self._build_hybrid_page()
        self._pages["DTCs"]    = self._build_dtc_page()
        self._pages["TESTS"]   = self._build_tests_page()
        self._pages["CONSOLE"] = self._build_console_page()

        self._switch_tab("LIVE")

    def _switch_tab(self, name):
        self._page_container.clear_widgets()
        self._page_container.add_widget(self._pages[name])
        for n, btn in self._tab_btns.items():
            btn.color = C["red"] if n == name else C["muted"]

    def _disconnect(self, *_):
        self.live_run = False
        self.mgr.disconnect()
        App.get_running_app().root.current = "connect"

    # ── LIVE DATA PAGE ──────────────────────────────────────────────────────
    def _build_live_page(self):
        outer = BoxLayout(orientation="vertical")

        # Start/Stop button
        ctrl = BoxLayout(size_hint_y=None, height=dp(54),
                          padding=[dp(10), dp(6)], spacing=dp(8))
        self._live_btn = StyledButton(text="▶  START LIVE DATA",
                                       btn_color=list(C["green"]) + [1])
        self._live_btn.color = C["bg"]
        self._live_btn.bind(on_press=self._toggle_live)
        ctrl.add_widget(self._live_btn)
        outer.add_widget(ctrl)

        sv = ScrollView()
        container = BoxLayout(orientation="vertical",
                               padding=[dp(10), 0],
                               spacing=dp(8),
                               size_hint_y=None)
        container.bind(minimum_height=container.setter("height"))

        # Standard PIDs
        container.add_widget(SectionLabel(text="  STANDARD OBD-II"))
        grid = GridLayout(cols=2, spacing=dp(8), size_hint_y=None)
        grid.bind(minimum_height=grid.setter("height"))
        accents = [C["red"], C["blue"], C["amber"], C["amber"],
                   C["green"], C["green"], C["blue"], C["blue"],
                   C["red"], C["green"], C["muted2"], C["green"]]
        for i, pid in enumerate(STANDARD_PIDS):
            card = PIDCard(pid[0], pid[3], pid[5], pid[6], accents[i % len(accents)])
            grid.add_widget(card)
            self.pid_cards[pid[0]] = card
        container.add_widget(grid)

        # Prius PIDs
        container.add_widget(SectionLabel(text="  ★ PRIUS ENHANCED"))
        pgrid = GridLayout(cols=2, spacing=dp(8), size_hint_y=None)
        pgrid.bind(minimum_height=pgrid.setter("height"))
        for pid in PRIUS_PIDS[:8]:
            card = PIDCard(pid[0], pid[3], pid[5], pid[6], C["teal"])
            pgrid.add_widget(card)
            self.pid_cards[pid[0]] = card
        container.add_widget(pgrid)

        sv.add_widget(container)
        outer.add_widget(sv)
        return outer

    def _toggle_live(self, *_):
        self.live_run = not self.live_run
        if self.live_run:
            self._live_btn.text = "■  STOP"
            self._live_btn.btn_color = list(C["red"]) + [1]
            self._live_btn.color = C["text"]
            threading.Thread(target=self._live_loop, daemon=True).start()
        else:
            self._live_btn.text = "▶  START LIVE DATA"
            self._live_btn.btn_color = list(C["green"]) + [1]
            self._live_btn.color = C["bg"]

    def _live_loop(self):
        while self.live_run:
            t = time.time()
            for pid in STANDARD_PIDS:
                if not self.live_run: break
                val = self._get_demo_value(pid[0], t) if self.mgr.demo_mode else self._query_pid(pid)
                if val is not None:
                    Clock.schedule_once(lambda dt, n=pid[0], v=val:
                        self.pid_cards[n].update(v) if n in self.pid_cards else None)
            for pid in PRIUS_PIDS[:8]:
                if not self.live_run: break
                val = self._get_demo_value(pid[0], t) if self.mgr.demo_mode else self._query_prius_pid(pid)
                if val is not None:
                    Clock.schedule_once(lambda dt, n=pid[0], v=val:
                        self.pid_cards[n].update(v) if n in self.pid_cards else None)
            time.sleep(0.25)

    def _query_pid(self, pid):
        raw = self.mgr.query(pid[1], pid[2])
        return self._decode(raw, pid[4]) if raw else None

    def _query_prius_pid(self, pid):
        raw = self.mgr.query(pid[1], pid[2])
        if not raw or len(raw) < 3: return None
        return float(raw[2])

    def _decode(self, d, formula):
        try:
            A = d[2] if len(d) > 2 else 0
            B = d[3] if len(d) > 3 else 0
            if formula == "rpm":       return ((A*256)+B)/4.0
            if formula == "speed":     return float(A)
            if formula == "temp":      return A - 40
            if formula == "pct":       return A*100.0/255.0
            if formula == "fuel_trim": return (A-128)*100.0/128.0
            if formula == "o2":        return A*0.005
            if formula == "maf":       return ((A*256)+B)/100.0
            if formula == "timing":    return A/2.0 - 64
            return float(A)
        except Exception:
            return None

    def _get_demo_value(self, name, t):
        table = {
            "Engine RPM":         800 + 1200*abs(math.sin(t*0.3)),
            "Vehicle Speed":      max(0, 60 + 30*math.sin(t*0.1)),
            "Coolant Temp":       88 + 2*math.sin(t*0.05),
            "Intake Air Temp":    25 + 3*math.sin(t*0.07),
            "Throttle Position":  15 + 10*abs(math.sin(t*0.4)),
            "Engine Load":        30 + 20*abs(math.sin(t*0.3)),
            "Short Fuel Trim B1": 2.3 + 1.5*math.sin(t*2),
            "Long Fuel Trim B1":  1.6 + 0.5*math.sin(t*0.1),
            "O2 Sensor B1S1":     0.45 + 0.4*math.sin(t),
            "MAF Air Flow":       5.2 + 3*abs(math.sin(t*0.3)),
            "Ignition Timing":    10 + 5*math.sin(t*0.5),
            "Fuel Level":         72.0,
            "HV Battery SOC":     55 + 15*math.sin(t*0.1),
            "HV Battery Voltage": 195 + 5*math.sin(t*0.2),
            "HV Battery Current": 20*math.sin(t*0.3),
            "HV Battery Temp":    28 + 4*math.sin(t*0.04),
            "MG1 Speed":          1800 + 400*math.sin(t*0.4),
            "MG2 Speed":          2500 + 800*math.sin(t*0.3),
            "MG1 Torque":         50 + 20*math.sin(t*0.4),
            "MG2 Torque":         120 + 40*math.sin(t*0.3),
            "Inverter Temp":      45 + 8*math.sin(t*0.05),
            "DC-DC Output":       14.1 + 0.2*math.sin(t*0.3),
            "VVT Advance B1":     15 + 12*math.sin(t*0.4),
            "Oil Temp":           95 + 3*math.sin(t*0.03),
            "Battery Fan Speed":  max(0, 1200 + 300*math.sin(t*0.1)),
            "HV SOH":             91.0,
        }
        return table.get(name, 50 + 10*math.sin(t))

    # ── HYBRID PAGE ─────────────────────────────────────────────────────────
    def _build_hybrid_page(self):
        outer = BoxLayout(orientation="vertical")
        sv    = ScrollView()
        cont  = BoxLayout(orientation="vertical", padding=[dp(10), dp(4)],
                           spacing=dp(10), size_hint_y=None)
        cont.bind(minimum_height=cont.setter("height"))

        # ── Power flow card
        cont.add_widget(SectionLabel(text="  ⚡ POWER FLOW"))
        pf = Card(orientation="horizontal", size_hint_y=None, height=dp(90),
                   padding=[dp(10), dp(8)], spacing=dp(4))
        nodes = [("⚙", "ENGINE",  "pf_eng"),
                 ("→", "",         "pf_a1"),
                 ("🔋", "HV BATT", "pf_batt"),
                 ("→", "",         "pf_a2"),
                 ("⚡", "MG2",     "pf_mg2"),
                 ("→", "",         "pf_a3"),
                 ("🛞", "WHEELS",  "pf_whl")]
        for icon, label, attr in nodes:
            if label == "":
                lbl = Mono(text=icon, font_size=sp(18), color=C["border"],
                            size_hint_x=None, width=dp(24), halign="center")
                setattr(self, attr, lbl)
                pf.add_widget(lbl)
            else:
                box = BoxLayout(orientation="vertical", size_hint_x=1)
                box.add_widget(Mono(text=icon, font_size=sp(20), halign="center"))
                box.add_widget(MutedMono(text=label, font_size=sp(7), halign="center"))
                val = Mono(text="—", font_size=sp(11), color=C["teal"], halign="center")
                setattr(self, attr, val)
                box.add_widget(val)
                pf.add_widget(box)
        cont.add_widget(pf)

        # ── Drive mode
        cont.add_widget(SectionLabel(text="  DRIVE MODE"))
        mode_row = BoxLayout(size_hint_y=None, height=dp(60), spacing=dp(8))
        self._mode_btns = {}
        for m, icon in [("EV","⚡"),("HYBRID","🔄"),("REGEN","♻"),("CHARGE","⚙")]:
            card = BoxLayout(orientation="vertical", padding=[dp(4), dp(4)])
            with card.canvas.before:
                col = Color(*C["panel"])
                rect = RoundedRectangle(pos=card.pos, size=card.size, radius=[dp(8)])
            card.bind(pos=lambda w,p,r=rect: setattr(r,"pos",p),
                      size=lambda w,s,r=rect: setattr(r,"size",s))
            card.add_widget(Mono(text=icon, font_size=sp(16), halign="center"))
            lbl = MutedMono(text=m, font_size=sp(8), halign="center")
            card.add_widget(lbl)
            mode_row.add_widget(card)
            self._mode_btns[m] = (card, col, lbl)
        cont.add_widget(mode_row)

        # ── Battery pack
        cont.add_widget(SectionLabel(text="  HV BATTERY PACK  ·  201.6V NiMH"))
        batt_row = BoxLayout(size_hint_y=None, height=dp(110), spacing=dp(8))

        soc_card = Card(orientation="vertical", size_hint_x=None, width=dp(100),
                         padding=[dp(6), dp(8)], spacing=dp(2))
        self._soc_lbl = Mono(text="—", font_size=sp(32), color=C["teal"], halign="center")
        soc_card.add_widget(self._soc_lbl)
        soc_card.add_widget(MutedMono(text="SOC %", font_size=sp(9), halign="center"))
        self._soc_bar = Widget(size_hint_y=None, height=dp(8))
        self._soc_bar.bind(pos=self._draw_soc_bar, size=self._draw_soc_bar)
        soc_card.add_widget(self._soc_bar)
        self._soc_val = 60.0
        batt_row.add_widget(soc_card)

        stats_card = Card(orientation="vertical", padding=[dp(10), dp(6)], spacing=dp(2))
        self._batt_stats = {}
        for key in ["Pack V", "Pack A", "Temp", "Fan", "SOH"]:
            row = BoxLayout(size_hint_y=None, height=dp(18))
            row.add_widget(MutedMono(text=key, font_size=sp(9), size_hint_x=0.5))
            val = Mono(text="—", font_size=sp(10), color=C["text"],
                        size_hint_x=0.5, halign="right")
            val.bind(size=lambda w,s: setattr(w,"text_size",s))
            row.add_widget(val)
            stats_card.add_widget(row)
            self._batt_stats[key] = val
        batt_row.add_widget(stats_card)
        cont.add_widget(batt_row)

        # ── Cell grid (28 modules)
        cont.add_widget(SectionLabel(text="  CELL BLOCK VOLTAGES (28 MODULES)"))
        self._cell_grid = GridLayout(cols=7, spacing=dp(3),
                                      size_hint_y=None, height=dp(80))
        self._cell_widgets = []
        for i in range(28):
            cell = Widget()
            with cell.canvas:
                col = Color(*C["teal"], 0.4)
                rect = RoundedRectangle(pos=cell.pos, size=cell.size, radius=[dp(2)])
            cell.bind(pos=lambda w,p,r=rect: setattr(r,"pos",p),
                      size=lambda w,s,r=rect: setattr(r,"size",s))
            self._cell_grid.add_widget(cell)
            self._cell_widgets.append((cell, col, rect))
        cont.add_widget(self._cell_grid)

        self._cell_delta = MutedMono(text="Δ — mV", font_size=sp(9),
                                      size_hint_y=None, height=dp(18), halign="right")
        cont.add_widget(self._cell_delta)

        # ── Regen
        cont.add_widget(SectionLabel(text="  REGENERATIVE BRAKING"))
        regen_card = Card(orientation="vertical", size_hint_y=None, height=dp(80),
                           padding=[dp(10), dp(8)], spacing=dp(4))
        regen_top = BoxLayout(size_hint_y=None, height=dp(22))
        regen_top.add_widget(MutedMono(text="REGEN POWER", font_size=sp(9)))
        self._regen_lbl = Mono(text="0.0 kW", font_size=sp(13), color=C["amber"],
                                 halign="right")
        self._regen_lbl.bind(size=lambda w,s: setattr(w,"text_size",s))
        regen_top.add_widget(self._regen_lbl)
        regen_card.add_widget(regen_top)
        self._regen_bar = Widget(size_hint_y=None, height=dp(10))
        self._regen_bar.bind(pos=self._draw_regen_bar, size=self._draw_regen_bar)
        self._regen_val = 0.0
        regen_card.add_widget(self._regen_bar)
        stats_row2 = BoxLayout(size_hint_y=None, height=dp(28))
        self._regen_wh = self._small_stat(stats_row2, "0 Wh", "RECOVERED")
        self._regen_ev = self._small_stat(stats_row2, "—",    "EV EVENTS")
        self._regen_ef = self._small_stat(stats_row2, "72%",  "EFFICIENCY")
        regen_card.add_widget(stats_row2)
        cont.add_widget(regen_card)

        # ── Motor stats
        cont.add_widget(SectionLabel(text="  MOTOR / GENERATOR UNITS"))
        mg_row = BoxLayout(size_hint_y=None, height=dp(120), spacing=dp(8))
        self._mg1 = self._motor_card(mg_row, "MG1 — GENERATOR")
        self._mg2 = self._motor_card(mg_row, "MG2 — DRIVE MOTOR")
        cont.add_widget(mg_row)

        # ── Hybrid DTCs
        cont.add_widget(SectionLabel(text="  HYBRID SYSTEM DTCs"))
        dtc_row = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(6))
        for ecu in ["HV ECU", "Battery ECU", "Inverter ECU"]:
            btn = StyledButton(text=ecu, btn_color=list(C["panel2"]) + [1])
            btn.font_size = sp(9)
            btn.color = C["teal"]
            btn.bind(on_press=lambda b, e=ecu: self._show_hybrid_dtcs(e))
            dtc_row.add_widget(btn)
        cont.add_widget(dtc_row)
        self._hybrid_dtc_box = BoxLayout(orientation="vertical",
                                          size_hint_y=None, spacing=dp(6))
        self._hybrid_dtc_box.bind(minimum_height=self._hybrid_dtc_box.setter("height"))
        cont.add_widget(self._hybrid_dtc_box)

        # Initialise cell base voltages
        import random
        random.seed(42)
        self._cell_base = []
        for i in range(28):
            weak = i in (5, 19)
            self._cell_base.append(6.85 + random.random()*0.1 if weak
                                    else 7.18 + random.random()*0.12)

        sv.add_widget(cont)
        outer.add_widget(sv)

        # Start hybrid update loop
        Clock.schedule_interval(self._update_hybrid, 0.35)
        return outer

    def _small_stat(self, parent, val, label):
        box = BoxLayout(orientation="vertical")
        v = Mono(text=val, font_size=sp(13), color=C["teal"], halign="center")
        v.bind(size=lambda w,s: setattr(w,"text_size",s))
        box.add_widget(v)
        box.add_widget(MutedMono(text=label, font_size=sp(7), halign="center"))
        parent.add_widget(box)
        return v

    def _motor_card(self, parent, title):
        card = Card(orientation="vertical", padding=[dp(8), dp(6)], spacing=dp(2))
        card.add_widget(MutedMono(text=title, font_size=sp(8), color=C["teal"],
                                   size_hint_y=None, height=dp(16)))
        lbls = {}
        for key in ["SPD","TRQ","PWR","TMP"]:
            row = BoxLayout(size_hint_y=None, height=dp(20))
            row.add_widget(MutedMono(text=key, font_size=sp(8), size_hint_x=0.4))
            v = Mono(text="—", font_size=sp(10), halign="right")
            v.bind(size=lambda w,s: setattr(w,"text_size",s))
            row.add_widget(v)
            card.add_widget(row)
            lbls[key] = v
        parent.add_widget(card)
        return lbls

    def _draw_soc_bar(self, *_):
        w = self._soc_bar
        ratio = max(0, min(1, self._soc_val / 100))
        color = C["teal"] if ratio > 0.4 else C["amber"] if ratio > 0.2 else C["red"]
        w.canvas.clear()
        with w.canvas:
            Color(*C["border"])
            RoundedRectangle(pos=w.pos, size=w.size, radius=[dp(4)])
            Color(*color)
            RoundedRectangle(pos=w.pos, size=(w.width*ratio, w.height), radius=[dp(4)])

    def _draw_regen_bar(self, *_):
        w = self._regen_bar
        ratio = max(0, min(1, self._regen_val / 27))
        w.canvas.clear()
        with w.canvas:
            Color(*C["border"])
            RoundedRectangle(pos=w.pos, size=w.size, radius=[dp(5)])
            Color(*C["teal"])
            RoundedRectangle(pos=w.pos, size=(w.width*ratio, w.height), radius=[dp(5)])

    def _update_hybrid(self, dt):
        t = time.time()
        cycle = t % 40
        if   cycle < 8:  mode, eng_kw, mg2_kw, regen_kw = "EV",     0,  18+5*math.sin(t*.5), 0
        elif cycle < 22: mode, eng_kw, mg2_kw, regen_kw = "HYBRID", 25+10*abs(math.sin(t*.4)), 30+8*math.sin(t*.3), 0
        elif cycle < 30: mode, eng_kw, mg2_kw, regen_kw = "REGEN",  0, 0, 12+8*abs(math.sin(t*.8))
        else:            mode, eng_kw, mg2_kw, regen_kw = "CHARGE", 15+5*math.sin(t*.3), 5*abs(math.sin(t)), 0

        soc     = max(20, min(80, 55 + 15*math.sin(t*0.1)))
        pack_v  = 195 + (soc-50)*0.3 + 2*math.sin(t*0.2)
        pack_a  = -(regen_kw*1000/pack_v) if mode=="REGEN" else eng_kw*1000/pack_v
        pack_t  = 28 + 4*math.sin(t*0.04)
        fan     = max(0, 1200+(pack_t-30)*200) if pack_t > 30 else 0
        mg1_spd = 1800+400*math.sin(t*0.4) if mode in ("HYBRID","CHARGE") else 200
        mg2_spd = 2500+800*math.sin(t*0.3) if mg2_kw > 0 else (2200 if mode=="REGEN" else 0)
        mg1_trq = 50+20*math.sin(t*0.4) if mode != "EV" else 0
        mg2_trq = 120+40*math.sin(t*0.3)
        inv_t   = 45+8*math.sin(t*0.05)

        # Power flow arrows
        self.pf_eng.text  = f"{eng_kw:.1f}kW"  if eng_kw  > 0.5 else "—"
        self.pf_batt.text = f"{soc:.0f}%"
        self.pf_mg2.text  = f"{mg2_kw:.1f}kW"  if mg2_kw  > 0.5 else (f"-{regen_kw:.1f}kW" if regen_kw > 0.5 else "—")
        self.pf_whl.text  = f"{self._get_demo_value('Vehicle Speed',t):.0f}km/h"

        arrow_color = lambda active: C["teal"] if active else C["border"]
        self.pf_a1.color = arrow_color(mode in ("HYBRID","CHARGE"))
        self.pf_a2.color = arrow_color(mode in ("EV","HYBRID") or mode=="REGEN")
        self.pf_a3.color = arrow_color(mode != "REGEN")

        # Drive mode chips
        for m, (card, col_inst, lbl) in self._mode_btns.items():
            active = m == mode
            col_inst.rgba = list(C["teal"])[:3] + [0.2] if active else list(C["panel"])
            lbl.color = C["teal"] if active else C["muted"]

        # SOC
        self._soc_val = soc
        self._soc_lbl.text = f"{soc:.0f}"
        self._draw_soc_bar()

        # Batt stats
        self._batt_stats["Pack V"].text = f"{pack_v:.1f} V"
        self._batt_stats["Pack A"].text = f"{pack_a:+.1f} A"
        self._batt_stats["Temp"].text   = f"{pack_t:.1f} °C"
        self._batt_stats["Fan"].text    = f"{int(fan)} rpm" if fan > 0 else "OFF"
        self._batt_stats["SOH"].text    = "91 %"

        # Cell voltages
        volts = [self._cell_base[i] + 0.05*math.sin(t*0.3 + i*0.4) for i in range(28)]
        v_min, v_max = min(volts), max(volts)
        for i, (cell, col_inst, rect) in enumerate(self._cell_widgets):
            v = volts[i]
            ratio = (v - v_min) / max(v_max - v_min, 0.001)
            if v < 7.0:   col_inst.rgba = list(C["red"])[:3]  + [0.5]
            elif v > 7.4: col_inst.rgba = list(C["amber"])[:3]+ [0.5]
            else:          col_inst.rgba = list(C["teal"])[:3] + [0.25 + ratio*0.45]
        self._cell_delta.text = f"Δ {(v_max-v_min)*1000:.0f} mV"

        # Regen
        self._regen_val = regen_kw
        self._regen_lbl.text = f"{regen_kw:.1f} kW"
        self._draw_regen_bar()

        # MG1
        mg1_pwr = abs(mg1_spd * mg1_trq / 9549)
        self._mg1["SPD"].text = f"{mg1_spd:.0f} rpm"
        self._mg1["TRQ"].text = f"{mg1_trq:.0f} Nm"
        self._mg1["PWR"].text = f"{mg1_pwr:.1f} kW"
        self._mg1["TMP"].text = f"{55+10*math.sin(t*0.05):.0f} °C"

        # MG2
        mg2_pwr = max(mg2_kw, regen_kw)
        self._mg2["SPD"].text = f"{abs(mg2_spd):.0f} rpm"
        self._mg2["TRQ"].text = f"{mg2_trq:.0f} Nm"
        self._mg2["PWR"].text = f"{mg2_pwr:.1f} kW"
        self._mg2["TMP"].text = f"{60+12*math.sin(t*0.06):.0f} °C"

    def _show_hybrid_dtcs(self, ecu):
        self._hybrid_dtc_box.clear_widgets()
        codes = HYBRID_DTCS.get(ecu, [])
        for code, desc in codes:
            row = Card(orientation="vertical", size_hint_y=None, height=dp(68),
                        padding=[dp(10), dp(6)], spacing=dp(2))
            header = BoxLayout(size_hint_y=None, height=dp(22))
            header.add_widget(Mono(text=code, font_size=sp(14), color=C["teal"]))
            header.add_widget(MutedMono(text=ecu, font_size=sp(9), halign="right"))
            header.children[0].bind(size=lambda w,s: setattr(w,"text_size",s))
            row.add_widget(header)
            lbl = Label(text=desc, font_size=sp(9), color=C["muted2"],
                         size_hint_y=None, height=dp(36),
                         text_size=(Window.width - dp(52), dp(36)),
                         halign="left", valign="top")
            row.add_widget(lbl)
            self._hybrid_dtc_box.add_widget(row)

    # ── DTC PAGE ─────────────────────────────────────────────────────────────
    def _build_dtc_page(self):
        outer = BoxLayout(orientation="vertical",
                           padding=[dp(10), dp(8)], spacing=dp(8))

        btn_row = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(8))
        read_btn = StyledButton(text="READ DTCs", btn_color=list(C["red"]) + [1])
        read_btn.bind(on_press=self._read_dtcs)
        pend_btn = StyledButton(text="PENDING", btn_color=list(C["panel2"]) + [1])
        pend_btn.bind(on_press=self._read_pending_dtcs)
        clr_btn  = StyledButton(text="CLEAR", btn_color=list(C["panel2"]) + [1])
        clr_btn.bind(on_press=self._clear_dtcs)
        btn_row.add_widget(read_btn)
        btn_row.add_widget(pend_btn)
        btn_row.add_widget(clr_btn)
        outer.add_widget(btn_row)

        self._dtc_status = Mono(text="Tap READ DTCs to scan",
                                 font_size=sp(11), color=C["muted"],
                                 size_hint_y=None, height=dp(30), halign="center")
        outer.add_widget(self._dtc_status)

        sv = ScrollView()
        self._dtc_list = BoxLayout(orientation="vertical", spacing=dp(6),
                                    size_hint_y=None)
        self._dtc_list.bind(minimum_height=self._dtc_list.setter("height"))
        sv.add_widget(self._dtc_list)
        outer.add_widget(sv)
        return outer

    def _read_dtcs(self, *_):
        self._dtc_status.text = "Reading..."
        threading.Thread(target=self._do_read_dtcs, args=(False,), daemon=True).start()

    def _read_pending_dtcs(self, *_):
        self._dtc_status.text = "Reading pending..."
        threading.Thread(target=self._do_read_dtcs, args=(True,), daemon=True).start()

    def _do_read_dtcs(self, pending):
        if self.mgr.demo_mode:
            codes = [("P0171","Stored"), ("P0420","Stored"), ("P0136","Pending")]
            codes = [(c,t) for c,t in codes if t==("Pending" if pending else "Stored")]
        else:
            raw   = self.mgr.read_dtcs()
            codes = [(c, "Stored") for c in raw]
        Clock.schedule_once(lambda dt: self._show_dtcs(codes))

    @mainthread
    def _show_dtcs(self, codes):
        self._dtc_list.clear_widgets()
        if not codes:
            self._dtc_status.text = "✓ No DTCs found"
            return
        self._dtc_status.text = f"⚠  {len(codes)} code(s) found"
        for code, typ in codes:
            desc  = DTC_DB.get(code, "Unknown — refer to service manual")
            row   = Card(orientation="vertical", size_hint_y=None, height=dp(72),
                          padding=[dp(10), dp(6)], spacing=dp(2))
            top   = BoxLayout(size_hint_y=None, height=dp(24))
            color = C["red"] if typ == "Stored" else C["amber"]
            top.add_widget(Mono(text=code, font_size=sp(15), color=color))
            top.add_widget(Mono(text=typ, font_size=sp(9), color=color, halign="right"))
            top.children[0].bind(size=lambda w,s: setattr(w,"text_size",s))
            row.add_widget(top)
            lbl = Label(text=desc, font_size=sp(9), color=C["muted2"],
                         size_hint_y=None, height=dp(36),
                         text_size=(Window.width - dp(52), dp(36)),
                         halign="left", valign="top")
            row.add_widget(lbl)
            self._dtc_list.add_widget(row)

    def _clear_dtcs(self, *_):
        self._confirm("Clear all DTCs?", "This will erase all stored codes and turn off the Check Engine light.",
                       self._do_clear_dtcs)

    def _do_clear_dtcs(self):
        ok = True if self.mgr.demo_mode else self.mgr.clear_dtcs()
        if ok:
            self._dtc_list.clear_widgets()
            self._dtc_status.text = "✓ DTCs cleared"

    # ── ACTIVE TESTS PAGE ────────────────────────────────────────────────────
    def _build_tests_page(self):
        outer = BoxLayout(orientation="vertical", padding=[dp(10), dp(6)], spacing=dp(6))

        warn = Label(
            text="⛔  Active tests directly control components.\nOnly activate when SAFE to do so.",
            font_size=sp(10), color=C["red"],
            size_hint_y=None, height=dp(44),
            text_size=(Window.width - dp(20), dp(44)),
            halign="left", valign="top"
        )
        outer.add_widget(warn)

        self._test_result = Mono(text="No test run", font_size=sp(10),
                                   color=C["amber"], size_hint_y=None, height=dp(28))
        outer.add_widget(self._test_result)

        sv   = ScrollView()
        cont = BoxLayout(orientation="vertical", spacing=dp(6), size_hint_y=None)
        cont.bind(minimum_height=cont.setter("height"))

        tests = [
            ("Cooling Fan Low",      "21","A0","01"),
            ("Cooling Fan High",     "21","A0","02"),
            ("Cooling Fan Off",      "21","A0","00"),
            ("Fuel Pump On",         "21","A2","01"),
            ("Fuel Pump Off",        "21","A2","00"),
            ("EVAP VSV On",          "21","A3","01"),
            ("EVAP VSV Off",         "21","A3","00"),
            ("Injector 1 Cut",       "22","0200","01"),
            ("Injector 2 Cut",       "22","0200","02"),
            ("All Injectors Resume", "22","0200","00"),
            ("MIL (CEL) On",         "21","A4","01"),
            ("MIL (CEL) Off",        "21","A4","00"),
            ("HV Fan Low",           "22","F410","01"),
            ("HV Fan High",          "22","F410","02"),
            ("HV Fan Off",           "22","F410","00"),
        ]

        for name, mode, pid, data in tests:
            row  = BoxLayout(size_hint_y=None, height=dp(52), spacing=dp(8))
            info = BoxLayout(orientation="vertical")
            info.add_widget(Mono(text=name, font_size=sp(12)))
            info.add_widget(MutedMono(text=f"Mode:{mode} PID:{pid} Data:{data}", font_size=sp(8)))
            is_off = any(x in name for x in ("Off","Resume","Low"))
            btn_c  = list(C["red"] if not is_off else C["panel"]) + [1]
            btn    = StyledButton(text="▶ RUN", size_hint_x=None, width=dp(80),
                                   btn_color=btn_c)
            btn.font_size = sp(10)
            btn.bind(on_press=lambda b, n=name, m=mode, p=pid, d=data:
                     self._run_test(n, m, p, d))
            row.add_widget(info)
            row.add_widget(btn)
            cont.add_widget(row)

        sv.add_widget(cont)
        outer.add_widget(sv)
        return outer

    def _run_test(self, name, mode, pid, data):
        self._confirm(
            f"Run: {name}",
            f"Mode:{mode} PID:{pid} Data:{data}\n\nEnsure it is SAFE to activate this component.",
            lambda: self._do_test(name, mode, pid, data)
        )

    def _do_test(self, name, mode, pid, data):
        if self.mgr.demo_mode:
            self._test_result.text = f"[DEMO] {name} → OK"
        else:
            resp = self.mgr.send_custom(mode, pid, data)
            self._test_result.text = f"{name} → {resp[:30]}"

    # ── CONSOLE PAGE ─────────────────────────────────────────────────────────
    def _build_console_page(self):
        outer = BoxLayout(orientation="vertical",
                           padding=[dp(10), dp(8)], spacing=dp(6))

        inp_row = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(6))
        from kivy.uix.textinput import TextInput
        self._con_input = TextInput(
            hint_text="Enter command...",
            multiline=False, font_name="RobotoMono-Regular",
            font_size=sp(12), foreground_color=C["green"],
            background_color=C["panel"], cursor_color=C["green"],
            size_hint_y=None, height=dp(46)
        )
        self._con_input.bind(on_text_validate=self._send_console)
        inp_row.add_widget(self._con_input)
        send_btn = StyledButton(text="SEND", size_hint_x=None, width=dp(72),
                                 btn_color=list(C["blue"]) + [1])
        send_btn.bind(on_press=self._send_console)
        inp_row.add_widget(send_btn)
        outer.add_widget(inp_row)

        quick_row = BoxLayout(size_hint_y=None, height=dp(38), spacing=dp(6))
        for cmd in ["ATI","ATDP","010C","0105","03","2101","2110"]:
            b = StyledButton(text=cmd, btn_color=list(C["panel2"])+[1],
                              height=dp(34))
            b.font_size = sp(9)
            b.color = C["blue"]
            b.bind(on_press=lambda x, c=cmd: self._quick_cmd(c))
            quick_row.add_widget(b)
        outer.add_widget(quick_row)

        sv = ScrollView()
        self._con_out = BoxLayout(orientation="vertical", spacing=dp(2),
                                   size_hint_y=None, padding=[0, dp(4)])
        self._con_out.bind(minimum_height=self._con_out.setter("height"))
        sv.add_widget(self._con_out)
        outer.add_widget(sv)
        self._sv_console = sv

        self._con_log("ToyotaScan Console ready", "info")
        self._con_log("Veepeak ELM327 Bluetooth SPP", "info")
        return outer

    def _send_console(self, *_):
        cmd = self._con_input.text.strip().upper()
        if not cmd: return
        self._con_input.text = ""
        self._con_log(f">> {cmd}", "cmd")
        threading.Thread(target=self._do_console, args=(cmd,), daemon=True).start()

    def _quick_cmd(self, cmd):
        self._con_input.text = cmd
        self._send_console()

    def _do_console(self, cmd):
        resp = self.mgr._send_raw(cmd) if self.mgr.connected or self.mgr.demo_mode else "Not connected"
        Clock.schedule_once(lambda dt: self._con_log(resp.strip() or "NO DATA", "resp"))

    @mainthread
    def _con_log(self, msg, kind="info"):
        colors = {"cmd": C["blue"], "resp": C["green"],
                  "info": C["muted"], "err": C["red"]}
        ts  = datetime.now().strftime("%H:%M:%S")
        lbl = Label(
            text=f"[{ts}] {msg}",
            font_name="RobotoMono-Regular",
            font_size=sp(9),
            color=colors.get(kind, C["muted"]),
            size_hint_y=None, height=dp(18),
            halign="left", valign="center",
            text_size=(Window.width - dp(20), dp(18))
        )
        self._con_out.add_widget(lbl)
        self._sv_console.scroll_y = 0

    # ── SHARED CONFIRM POPUP ─────────────────────────────────────────────────
    def _confirm(self, title, msg, callback):
        content = BoxLayout(orientation="vertical",
                             padding=[dp(14), dp(10)], spacing=dp(12))
        content.add_widget(Label(
            text=msg, font_size=sp(11), color=C["muted2"],
            text_size=(Window.width * 0.8 - dp(28), None),
            halign="left", size_hint_y=None, height=dp(70)
        ))
        btns = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        cancel = StyledButton(text="CANCEL", btn_color=list(C["panel2"]) + [1])
        confirm = StyledButton(text="CONFIRM", btn_color=list(C["red"]) + [1])
        btns.add_widget(cancel)
        btns.add_widget(confirm)
        content.add_widget(btns)

        popup = Popup(title=title, content=content,
                       size_hint=(0.88, None), height=dp(210),
                       background_color=C["surface"],
                       title_color=C["text"],
                       title_font="RobotoMono-Regular",
                       separator_color=C["border"])
        cancel.bind(on_press=popup.dismiss)
        confirm.bind(on_press=lambda *_: (popup.dismiss(), callback()))
        popup.open()


# ════════════════════════════════════════════════════════════════════════════
#  APP ROOT + SCREEN MANAGER
# ════════════════════════════════════════════════════════════════════════════
class ToyotaScanApp(App):
    def build(self):
        Window.clearcolor = C["bg"]

        if BLUETOOTH_AVAILABLE:
            request_permissions([
                Permission.BLUETOOTH,
                Permission.BLUETOOTH_ADMIN,
                Permission.BLUETOOTH_CONNECT,
                Permission.BLUETOOTH_SCAN,
                Permission.ACCESS_FINE_LOCATION,
            ])

        self.veepeak = VeepeakManager()

        sm = ScreenManager(transition=SlideTransition())
        sm.add_widget(ConnectScreen(name="connect", manager_ref=self.veepeak))
        sm.add_widget(MainScreen(name="main",    manager_ref=self.veepeak))
        return sm


if __name__ == "__main__":
    ToyotaScanApp().run()

#!/usr/bin/env python3
"""
PyRing – iskolai csengető program (PySide6 + pygame)

Telepítés:   pip install PySide6 pygame
Indítás:     python pyring.py
Exe készítés: pyinstaller --noconsole --onefile pring.py

Mappa szerkezet (a program mellett):
    pring.py
    Sound/            <- jelzo.mp3, becseng.mp3, kicseng.mp3, tuzriado3p.mp3, ...
    pring_config.json <- automatikusan jön létre
    sulics_multi.ini  <- (opcionális) a régi Pascal verzió beállításai, első indításkor átimportálja
"""
import configparser
import copy
import json
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame  # noqa: E402
from PySide6.QtCore import QTime, QTimer, Qt  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QAbstractSpinBox, QApplication, QFileDialog, QFrame, QGridLayout,
    QHBoxLayout, QLabel, QListWidget, QMainWindow, QMessageBox, QPushButton,
    QTimeEdit, QVBoxLayout, QWidget,
)

# ----------------------------------------------------------------------------
# Alapbeállítások
# ----------------------------------------------------------------------------
BASE_DIR = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
SOUND_DIR = BASE_DIR / "Sound"
CONFIG_FILE = BASE_DIR / "pring_config.json"
LEGACY_INI = BASE_DIR / "sulics_multi.ini"
LEGACY_INI_DEFAULTS = BASE_DIR / "sulics.ini"

LESSONS = 8
BREAKS = 7
GRACE_SECONDS = 10          # ennyi másodpercet késhet a ciklus, hogy a csengetés még megszólaljon
OFF = "00:00:00"            # ez az érték = kikapcsolt időpont
CLEAR_DELAY_SECONDS = 60    # az utolsó csengetés után ennyivel törlődnek a pipák

KINDS = [("jelzo", "Jelző csengő"), ("be", "Becsengetés"), ("ki", "Kicsengetés")]
KIND_LABEL = {"jelzo": "jelző csengetés", "be": "becsengetés", "ki": "kicsengetés"}
LEGACY_KEYS = {"jelzo": "jelzohang", "be": "behang", "ki": "kihang"}

HONAPOK = ["JANUÁR", "FEBRUÁR", "MÁRCIUS", "ÁPRILIS", "MÁJUS", "JÚNIUS",
           "JÚLIUS", "AUGUSZTUS", "SZEPTEMBER", "OKTÓBER", "NOVEMBER", "DECEMBER"]

REND_NEVEK = {"normal": "Normál", "rovid": "Rövid"}

# Egy csengetési rend: óránként [jelző, be, ki]
RENDEK = {
    "normal": [
        ["07:42:00", "07:45:00", "08:30:00"],
        ["08:42:00", "08:45:00", "09:30:00"],
        ["09:42:00", "09:45:00", "10:30:00"],
        ["10:42:00", "10:45:00", "11:30:00"],
        ["11:42:00", "11:45:00", "12:30:00"],
        ["12:42:00", "12:45:00", "13:30:00"],
        ["13:42:00", "13:45:00", "14:30:00"],
        ["14:32:00", "14:35:00", "15:20:00"],
    ],
    "rovid": [
        [OFF, "07:45:00", "08:15:00"],
        [OFF, "08:20:00", "08:50:00"],
        [OFF, "08:55:00", "09:25:00"],
        [OFF, "09:30:00", "10:00:00"],
        [OFF, "10:05:00", "10:35:00"],
        [OFF, "10:40:00", "11:10:00"],
        [OFF, "11:15:00", "11:45:00"],
        [OFF, "11:50:00", "12:20:00"],
    ],
}


def default_config() -> dict:
    return {
        "aktiv_rend": "normal",
        "rendek": copy.deepcopy(RENDEK),
        "hangok": {"jelzo": "jelzo.mp3", "be": "becseng.mp3", "ki": "kicseng.mp3"},
        # óra-specifikus hang felülírás, pl. {"3_be": "masik.mp3"} – ha nincs, az alap hang szól
        "ora_hangok": {},
        "szunetek": [{"ido": OFF, "fajl": ""} for _ in range(BREAKS)],
        "tuzriado": {"ido": "09:05:00", "fajl": "tuzriado3p.mp3"},
    }


# ----------------------------------------------------------------------------
# Konfiguráció betöltés / mentés / régi INI import
# ----------------------------------------------------------------------------
def norm_time(value: str) -> str:
    try:
        return datetime.strptime(value.strip(), "%H:%M:%S").strftime("%H:%M:%S")
    except (ValueError, AttributeError):
        return OFF


def read_ini(path: Path) -> configparser.ConfigParser | None:
    for enc in ("utf-8", "cp1250"):
        cp = configparser.ConfigParser(interpolation=None)
        try:
            if cp.read(path, encoding=enc):
                return cp
            return None
        except UnicodeDecodeError:
            continue
    return None


def import_legacy(cfg: dict) -> None:
    """A régi Pascal verzió INI fájljaiból átveszi a hangokat és szünet-időket."""
    sec = "CSENGETES"
    cp = read_ini(LEGACY_INI)
    if cp:
        for i in range(1, BREAKS + 1):
            cfg["szunetek"][i - 1] = {
                "ido": norm_time(cp.get(sec, f"szunet_{i}_ido", fallback="")),
                "fajl": cp.get(sec, f"szunet_{i}", fallback=""),
            }
        cfg["tuzriado"]["ido"] = norm_time(cp.get(sec, "tuzriado_ido", fallback="09:05:00"))
        for n in range(1, LESSONS + 1):
            for kind, key in LEGACY_KEYS.items():
                v = cp.get(sec, f"ora{n}_{key}", fallback="")
                if v:
                    cfg["ora_hangok"][f"{n}_{kind}"] = v
    cp = read_ini(LEGACY_INI_DEFAULTS)
    if cp:
        for kind, key in LEGACY_KEYS.items():
            v = cp.get(sec, key, fallback="")
            if v:
                cfg["hangok"][kind] = v


def load_config() -> dict:
    cfg = default_config()
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, encoding="utf-8") as f:
                cfg.update(json.load(f))
        except (OSError, json.JSONDecodeError):
            pass
    else:
        import_legacy(cfg)
    # hiányzó elemek pótlása
    for name, rows in RENDEK.items():
        cfg["rendek"].setdefault(name, copy.deepcopy(rows))
    while len(cfg["szunetek"]) < BREAKS:
        cfg["szunetek"].append({"ido": OFF, "fajl": ""})
    if cfg["aktiv_rend"] not in cfg["rendek"]:
        cfg["aktiv_rend"] = "normal"
    return cfg


def save_config(cfg: dict) -> None:
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


# ----------------------------------------------------------------------------
# Hang
# ----------------------------------------------------------------------------
class Audio:
    """Egyetlen csatornás lejátszó: az új hang mindig leváltja az előzőt."""

    def __init__(self):
        self.ok = True
        self.error = ""
        try:
            pygame.mixer.init()
        except pygame.error as e:  # nincs hangkártya stb.
            self.ok = False
            self.error = str(e)

    @staticmethod
    def resolve(name: str) -> Path | None:
        if not name:
            return None
        p = SOUND_DIR / name          # abszolút útvonalnál a pathlib az abszolútat adja vissza
        return p if p.is_file() else None

    def play(self, name: str) -> bool:
        p = self.resolve(name)
        if not (self.ok and p):
            return False
        try:
            pygame.mixer.music.load(str(p))
            pygame.mixer.music.play()
            return True
        except pygame.error:
            return False

    def stop(self) -> None:
        if self.ok:
            pygame.mixer.music.stop()

    def busy(self) -> bool:
        return self.ok and pygame.mixer.music.get_busy()

    def position_ms(self) -> int:
        return max(0, pygame.mixer.music.get_pos()) if self.ok else 0


def pick_sound(parent) -> str | None:
    start = str(SOUND_DIR if SOUND_DIR.exists() else BASE_DIR)
    f, _ = QFileDialog.getOpenFileName(
        parent, "Hanganyag kiválasztása", start,
        "Hangfájlok (*.mp3 *.wav *.ogg);;Minden fájl (*)")
    if not f:
        return None
    p = Path(f)
    try:
        return str(p.relative_to(SOUND_DIR))
    except ValueError:
        return str(p)


# ----------------------------------------------------------------------------
# Kis UI segédek
# ----------------------------------------------------------------------------
def make_time_edit() -> QTimeEdit:
    e = QTimeEdit()
    e.setDisplayFormat("HH:mm:ss")
    e.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
    e.setAlignment(Qt.AlignmentFlag.AlignCenter)
    return e


def set_edit(e: QTimeEdit, text: str) -> None:
    t = QTime.fromString(norm_time(text), "HH:mm:ss")
    e.setTime(t if t.isValid() else QTime(0, 0, 0))


def get_edit(e: QTimeEdit) -> str:
    return e.time().toString("HH:mm:ss")


def secs(e: QTimeEdit) -> int:
    return e.time().msecsSinceStartOfDay() // 1000


def fmt_ms(ms: int) -> str:
    s = ms // 1000
    return f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}"


class SzunetRow(QWidget):
    """Egy szünet sora: sorszám, fájlválasztó, P/S gomb, kezdési idő, lejátszási pozíció, fájlnév."""

    def __init__(self, idx: int, on_pick, on_play, on_stop):
        super().__init__()
        self.idx = idx
        self.file = ""

        num = QLabel(str(idx))
        num.setObjectName("num")
        num.setFixedSize(26, 26)
        num.setAlignment(Qt.AlignmentFlag.AlignCenter)

        pick = QPushButton("📂")
        pick.setObjectName("folder")
        pick.setFixedSize(34, 28)
        pick.setToolTip("Hanganyag kiválasztása")
        play = QPushButton("P")
        stop = QPushButton("S")
        for b in (play, stop):
            b.setFixedSize(34, 28)
        pick.clicked.connect(lambda: on_pick(idx))
        play.clicked.connect(lambda: on_play(idx))
        stop.clicked.connect(lambda: on_stop())

        self.time = make_time_edit()
        self.time.setFixedWidth(84)
        self.time.setToolTip("Automatikus indítás ideje (00:00:00 = kikapcsolva)")
        self.pos = QLabel(OFF)
        self.pos.setObjectName("pos")
        self.name = QLabel()
        self.name.setObjectName("fname")
        self.name.setMinimumWidth(280)
        self.set_file("")

        top = QHBoxLayout()
        top.setSpacing(8)
        top.addWidget(self.time)
        top.addWidget(self.pos)
        top.addStretch()
        right = QVBoxLayout()
        right.setSpacing(0)
        right.addLayout(top)
        right.addWidget(self.name)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 1, 0, 1)
        lay.addWidget(num)
        lay.addWidget(pick)
        lay.addWidget(play)
        lay.addWidget(stop)
        lay.addLayout(right, 1)

    def set_file(self, name: str) -> None:
        self.file = name
        self.name.setText(Path(name).name if name else "Hanganyag nincs ------------------------")


# ----------------------------------------------------------------------------
# Főablak
# ----------------------------------------------------------------------------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PyRing")
        self.cfg = load_config()
        self.audio = Audio()
        self.fired: set = set()
        self.fired_day = date.today()
        self.played: set = set()            # (óra, fajta) párok, amelyeknél a hang ténylegesen megszólalt → ✓
        self.clear_at: datetime | None = None   # mikor törlődjenek a pipák (utolsó csengetés után)
        self.fire_active = False
        self.playing: tuple | None = None   # pl. ("szunet", 3)
        self._closing_confirmed = False

        self._build_ui()
        self._load_rend_to_ui(self.cfg["aktiv_rend"])
        self._load_rest_to_ui()
        if not self.audio.ok:
            self.log(f"HIBA – hangeszköz nem érhető el: {self.audio.error}")
        if not SOUND_DIR.exists():
            self.log("Figyelem: a Sound mappa nem létezik a program mellett!")

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(250)
        self.tick()

    # ------------------------------------------------------------- felület
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(16, 10, 16, 10)
        root.setSpacing(14)

        root.addLayout(self._build_left())
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setObjectName("sep")
        root.addWidget(sep)
        root.addLayout(self._build_middle(), 1)
        root.addLayout(self._build_right())

    def _build_left(self) -> QVBoxLayout:
        col = QVBoxLayout()
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(2)
        self.lesson_edits: dict = {}
        self.lesson_checks: dict = {}
        for c, (_, title) in enumerate(KINDS):
            h = QLabel(title)
            h.setObjectName("head")
            h.setAlignment(Qt.AlignmentFlag.AlignCenter)
            grid.addWidget(h, 0, c)
        for n in range(1, LESSONS + 1):
            for c, (kind, _) in enumerate(KINDS):
                cell = QHBoxLayout()
                cell.setSpacing(2)
                e = make_time_edit()
                e.setFixedWidth(92)
                chk = QLabel("")
                chk.setObjectName("check")
                chk.setFixedWidth(20)
                cell.addWidget(e)
                cell.addWidget(chk)
                grid.addLayout(cell, n, c)
                self.lesson_edits[(n, kind)] = e
                self.lesson_checks[(n, kind)] = chk
        col.addLayout(grid)

        self.rend_label = QLabel("")
        self.rend_label.setObjectName("rend")
        self.rend_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        col.addWidget(self.rend_label)

        self.date_label = QLabel("")
        self.date_label.setObjectName("date")
        col.addWidget(self.date_label)
        self.clock_label = QLabel("00:00:00")
        self.clock_label.setObjectName("clock")
        col.addWidget(self.clock_label)
        col.addStretch()

        # alap hangok
        self.default_name: dict = {}
        sg = QGridLayout()
        sg.setVerticalSpacing(4)
        for r, (kind, title) in enumerate(KINDS):
            b = QPushButton(title)
            b.setFixedWidth(120)
            b.clicked.connect(lambda _=False, k=kind: self.pick_default(k))
            nm = QLabel("")
            nm.setObjectName("fname")
            nm.setMinimumWidth(200)
            pb = QPushButton("Lejátszás")
            pb.clicked.connect(lambda _=False, k=kind: self.manual_bell(k))
            sg.addWidget(b, r, 0)
            sg.addWidget(nm, r, 1)
            sg.addWidget(pb, r, 2)
            self.default_name[kind] = nm
        sg.setColumnStretch(1, 1)
        col.addLayout(sg)
        return col

    def _build_middle(self) -> QVBoxLayout:
        col = QVBoxLayout()
        title = QLabel("Szünet - Hanganyag lejátszása")
        title.setObjectName("head")
        col.addWidget(title)
        self.szunet_rows: list[SzunetRow] = []
        for i in range(1, BREAKS + 1):
            row = SzunetRow(i, self.pick_szunet, self.play_szunet_manual, self.stop_audio)
            self.szunet_rows.append(row)
            col.addWidget(row)
        col.addStretch()

        logt = QLabel("Művelet :")
        logt.setObjectName("head")
        col.addWidget(logt)
        self.log_list = QListWidget()
        self.log_list.setFixedHeight(110)
        col.addWidget(self.log_list)
        return col

    def _build_right(self) -> QVBoxLayout:
        col = QVBoxLayout()
        col.setSpacing(6)
        t = QLabel("TŰZRIADÓ")
        t.setObjectName("head")
        t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        col.addWidget(t)
        self.fire_edit = make_time_edit()
        self.fire_edit.setObjectName("fireTime")
        self.fire_edit.setFixedWidth(150)
        col.addWidget(self.fire_edit, 0, Qt.AlignmentFlag.AlignHCenter)

        b_fire = QPushButton("Tűzriadó jelzés")
        b_fire.setObjectName("danger")
        b_fire.clicked.connect(self.start_fire)
        b_stop = QPushButton("Tűzriadó leállítás")
        b_stop.clicked.connect(self.stop_fire)
        b_file = QPushButton("Tűzriadó hang…")
        b_file.clicked.connect(self.pick_fire)
        for b in (b_fire, b_stop, b_file):
            col.addWidget(b)
        col.addSpacing(8)

        b_rovid = QPushButton("Rövid csengetés")
        b_rovid.clicked.connect(lambda: self.switch_rend("rovid"))
        b_normal = QPushButton("Normál csengetés")
        b_normal.clicked.connect(lambda: self.switch_rend("normal"))
        col.addWidget(b_rovid)
        col.addWidget(b_normal)

        row = QHBoxLayout()
        b_about = QPushButton("Névjegy")
        b_about.clicked.connect(self.about)
        b_close = QPushButton("Bezár")
        b_close.clicked.connect(self.close)
        row.addWidget(b_about)
        row.addWidget(b_close)
        col.addLayout(row)

        b_save = QPushButton("Beállítások mentése")
        b_save.setObjectName("primary")
        b_save.clicked.connect(self.save_all)
        col.addWidget(b_save)
        col.addStretch()
        w = QWidget()
        w.setLayout(col)
        w.setFixedWidth(210)
        outer = QVBoxLayout()
        outer.addWidget(w)
        return outer

    # ------------------------------------------------------ adat <-> felület
    def _load_rend_to_ui(self, name: str):
        rows = self.cfg["rendek"][name]
        for n in range(1, LESSONS + 1):
            for c, (kind, _) in enumerate(KINDS):
                set_edit(self.lesson_edits[(n, kind)], rows[n - 1][c])
        self.cfg["aktiv_rend"] = name
        self.rend_label.setText(f"Aktív rend: {REND_NEVEK.get(name, name)}")

    def _store_rend_from_ui(self):
        name = self.cfg["aktiv_rend"]
        self.cfg["rendek"][name] = [
            [get_edit(self.lesson_edits[(n, k)]) for k, _ in KINDS]
            for n in range(1, LESSONS + 1)
        ]

    def _load_rest_to_ui(self):
        for kind, _ in KINDS:
            self.default_name[kind].setText(self.cfg["hangok"][kind])
        for row, data in zip(self.szunet_rows, self.cfg["szunetek"]):
            set_edit(row.time, data["ido"])
            row.set_file(data["fajl"])
        set_edit(self.fire_edit, self.cfg["tuzriado"]["ido"])

    def collect(self):
        self._store_rend_from_ui()
        self.cfg["szunetek"] = [{"ido": get_edit(r.time), "fajl": r.file} for r in self.szunet_rows]
        self.cfg["tuzriado"]["ido"] = get_edit(self.fire_edit)

    def save_all(self):
        self.collect()
        try:
            save_config(self.cfg)
            self.log("Beállítások mentve")
        except OSError as e:
            self.log(f"HIBA – mentés sikertelen: {e}")

    # ---------------------------------------------------------------- napló
    def log(self, text: str):
        self.log_list.addItem(f"{datetime.now():%H:%M:%S}  {text}")
        while self.log_list.count() > 300:
            self.log_list.takeItem(0)
        self.log_list.scrollToBottom()

    # -------------------------------------------------------------- lejátszás
    def play(self, name: str, label: str, tag: tuple | None = None) -> bool:
        if self.audio.play(name):
            self.playing = tag
            self.log(label)
            return True
        self.log(f"HIBA – nem játszható le: {label} ({name or 'nincs hang megadva'})")
        return False

    def bell_file(self, n: int, kind: str) -> str:
        return self.cfg["ora_hangok"].get(f"{n}_{kind}") or self.cfg["hangok"][kind]

    def stop_audio(self):
        self.audio.stop()
        self.playing = None
        self.fire_active = False

    # kézi csengetés (alap hangok)
    def manual_bell(self, kind: str):
        self.play(self.cfg["hangok"][kind], f"Kézi {KIND_LABEL[kind]}")

    def pick_default(self, kind: str):
        f = pick_sound(self)
        if f:
            self.cfg["hangok"][kind] = f
            self.default_name[kind].setText(f)

    # szünetzene
    def pick_szunet(self, idx: int):
        f = pick_sound(self)
        if f:
            self.szunet_rows[idx - 1].set_file(f)

    def play_szunet(self, idx: int, auto: bool = False):
        row = self.szunet_rows[idx - 1]
        prefix = "Szünet" if auto else "Kézi szünet"
        self.play(row.file, f"{prefix} {idx}: zene – {Path(row.file).name or '—'}", ("szunet", idx))

    def play_szunet_manual(self, idx: int):
        self.play_szunet(idx, auto=False)

    # tűzriadó
    def pick_fire(self):
        f = pick_sound(self)
        if f:
            self.cfg["tuzriado"]["fajl"] = f
            self.log(f"Tűzriadó hang: {f}")

    def start_fire(self):
        ok = self.play(self.cfg["tuzriado"]["fajl"], "TŰZRIADÓ JELZÉS", ("fire",))
        self.fire_active = ok

    def stop_fire(self):
        self.stop_audio()
        self.log("Tűzriadó leállítva")

    # --------------------------------------------------------- csengetési rend
    def switch_rend(self, name: str):
        if name == self.cfg["aktiv_rend"]:
            return
        self._store_rend_from_ui()          # a szerkesztett időket ne veszítsük el
        self._load_rend_to_ui(name)
        self.fired.clear()
        self.played.clear()                 # új rend: üres pipák
        self.clear_at = None
        self.log(f"Váltás: {REND_NEVEK.get(name, name)} csengetési rend")

    # --------------------------------------------------------------- időzítő
    def events(self):
        """(kulcs, másodperc, felirat, művelet) – minden automatikus esemény."""
        for n in range(1, LESSONS + 1):
            for kind, _ in KINDS:
                yield (("ora", n, kind), secs(self.lesson_edits[(n, kind)]),
                       f"{n}. óra {KIND_LABEL[kind]}",
                       lambda n=n, kind=kind: self.play(
                           self.bell_file(n, kind), f"{n}. óra {KIND_LABEL[kind]}"))
        for row in self.szunet_rows:
            yield (("szunet", row.idx), secs(row.time), f"Szünet {row.idx} zene",
                   lambda i=row.idx: self.play_szunet(i, auto=True))
        yield (("fire",), secs(self.fire_edit), "Tűzriadó", self.start_fire)

    def tick(self):
        now = datetime.now()
        if now.date() != self.fired_day:               # új nap: újra élesítés
            self.fired.clear()
            self.played.clear()
            self.clear_at = None
            self.fired_day = now.date()
        nowsec = now.hour * 3600 + now.minute * 60 + now.second

        self.date_label.setText(f"{now.year} {HONAPOK[now.month - 1]} {now.day:02d}")
        self.clock_label.setText(now.strftime("%H:%M:%S"))

        if self.fire_active and not self.audio.busy():
            self.fire_active = False

        if self.clear_at and now >= self.clear_at:     # az utolsó csengetés után letelt a várakozás
            self.played.clear()
            self.clear_at = None

        events = list(self.events())
        # a nap utolsó (bekapcsolt) csengetési ideje – ennek lejátszása után minden pipa törlődik
        lesson_times = [s for key, s, _, _ in events if key[0] == "ora" and s > 0]
        last_s = max(lesson_times, default=None)

        for key, s, label, action in events:
            if s <= 0:
                continue
            delta = nowsec - s
            if not (0 <= delta <= GRACE_SECONDS) or (key, s) in self.fired:
                continue
            self.fired.add((key, s))

            if self.fire_active and key != ("fire",):
                self.log(f"Kihagyva (tűzriadó van): {label}")
                ok = False
            else:
                ok = action()

            if key[0] == "ora":
                if ok:
                    self.played.add((key[1], key[2]))   # ✓ csak ha tényleg megszólalt
                if s == last_s:                         # utolsó csengetés: egy perc múlva tiszta lap
                    self.clear_at = now + timedelta(seconds=CLEAR_DELAY_SECONDS)

        for (n, kind), chk in self.lesson_checks.items():
            chk.setText("✓" if (n, kind) in self.played else "")

        # szünetzene lejátszási pozíció
        if self.playing and not self.audio.busy():
            self.playing = None
        for row in self.szunet_rows:
            if self.playing == ("szunet", row.idx):
                row.pos.setText(fmt_ms(self.audio.position_ms()))
            else:
                row.pos.setText(OFF)

    # ------------------------------------------------------------------ egyéb
    def about(self):
        QMessageBox.about(
            self, "Névjegy",
            "<b>PyRing</b><br>Iskolai csengető program<br><br>"
            "Python • PySide6 • pygame<br><br>Pogány Frigyes Technikum&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<br><br>dajka.lajos@poganyszki.hu")

    def closeEvent(self, event):
        if not self._closing_confirmed:
            r = QMessageBox.question(
                self, "Kilépés",
                "Ha bezárod a programot, nem lesz automatikus csengetés.\nBiztosan kilépsz?")
            if r != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self._closing_confirmed = True
        self.timer.stop()
        self.save_all()
        self.audio.stop()
        event.accept()


# ----------------------------------------------------------------------------
# Stílus (sötétkék / arany, a v1 kinézetéhez igazítva)
# ----------------------------------------------------------------------------
STYLE = """
QMainWindow, QWidget { background: #1b4560; color: #cfe8f5; font-family: 'Segoe UI', sans-serif; font-size: 14px; }
QLabel#head { color: #f4d27a; font-weight: bold; font-size: 15px; }
QLabel#num { color: #c04bff; border: 2px solid #c04bff; border-radius: 4px; font-weight: bold; background: transparent; }
QLabel#fname { background: #1f5272; color: #8fe3d2; padding: 1px 6px; font-weight: 600; font-size: 13px; }
QLabel#pos { background: #1f5272; color: #ffffff; padding: 1px 6px; font-weight: bold; }
QLabel#check { color: #25d0e8; font-weight: bold; }
QLabel#rend { color: #f4d27a; font-size: 14px; }
QLabel#date { color: #7db8f7; font-size: 20px; }
QLabel#clock { color: #ffffff; font-size: 64px; font-weight: 800; }
QFrame#sep { color: #b5c9d6; }
QTimeEdit { background: transparent; border: none; color: #f4d27a; font-size: 16px; padding: 2px; selection-background-color: #2a7aa8; }
QTimeEdit:focus { background: #245a7a; border-radius: 4px; }
QTimeEdit#fireTime { color: #ffffff; font-size: 20px; }
QPushButton { background: #f4f4f4; color: #111; border: 1px solid #c9c9c9; border-radius: 4px; padding: 5px 8px; font-size: 14px; }
QPushButton:hover { background: #ffffff; }
QPushButton:pressed { background: #d8d8d8; }
QPushButton#danger { background: #ffd9d4; color: #7a1208; font-weight: bold; }
QPushButton#primary { background: #f4d27a; font-weight: bold; }
QPushButton#folder { background: transparent; border: none; font-size: 18px; padding: 0px; }
QListWidget { background: #17394f; border: none; color: #cfe8f5; font-size: 14px; }
QToolTip { background: #ffffe0; color: #000; }
"""


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLE)
    win = MainWindow()
    hint = win.minimumSizeHint()
    avail = app.primaryScreen().availableGeometry()
    win.resize(min(hint.width() + 20, avail.width()),
               min(hint.height() + 10, avail.height() - 40))
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

"""Load the real Panel.qml and BarWidget.qml offscreen, against a real campaign.

    python3 tests/qml/panel_check.py <out folder>

Quickshell and omarchy-shell aren't here, so stand-ins take their place: Process runs
the plugin's actual bin/solo, FileView reads the actual files, and execDetached records
what the plugin would launch (GM turns, desktop effects) instead of launching it. Only
the layer-shell lines (anchors to screen edges, exclusive zone) are dropped from a copy
of Panel.qml. It prints QML errors and what was launched, and saves screenshots.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(HERE))

from PySide6.QtCore import Property, QFileSystemWatcher, QObject, QSize, QTimer, QUrl, Signal, Slot  # noqa: E402
from PySide6.QtGui import QColor, QGuiApplication  # noqa: E402
from PySide6.QtQml import QQmlEngine, qmlRegisterModule, qmlRegisterSingletonInstance, qmlRegisterType  # noqa: E402
from PySide6.QtQuick import QQuickItem, QQuickView  # noqa: E402

LAUNCHED = []


def prop(kind, name, default, notify=None):
    """A read-write Qt property stored on the instance."""
    def get(self):
        return getattr(self, "_" + name, default)

    def put(self, value):
        setattr(self, "_" + name, value)
        signal = getattr(self, name + "Changed", None)
        if signal is not None:
            signal.emit()
    return Property(kind, get, put, notify=notify)


class Shell(QObject):
    @Slot(str, result=str)
    def env(self, name):
        return os.environ.get(name, "")

    @Slot("QVariantList")
    def execDetached(self, command):
        LAUNCHED.append(list(command))


class Collector(QObject):
    streamFinished = Signal()
    textChanged = Signal()
    waitForEnd = prop(bool, "waitForEnd", True)
    text = prop(str, "text", "", notify=textChanged)


class Process(QObject):
    exited = Signal(int, int, arguments=["exitCode", "exitStatus"])
    runningChanged = Signal()
    commandChanged = Signal()
    command = prop("QVariantList", "command", [], notify=commandChanged)
    stdout = prop(QObject, "stdout", None)
    stderr = prop(QObject, "stderr", None)

    def _get_running(self):
        return getattr(self, "_running", False)

    def _set_running(self, value):
        if value and not self._get_running():
            self._running = True
            self.runningChanged.emit()
            QTimer.singleShot(0, self._run)

    running = Property(bool, _get_running, _set_running, notify=runningChanged)

    def _run(self):
        done = subprocess.run([str(c) for c in self.command], capture_output=True, text=True)
        for stream, text in ((self.stdout, done.stdout), (self.stderr, done.stderr)):
            if stream is not None:
                stream.text = text
                stream.streamFinished.emit()
        self._running = False
        self.runningChanged.emit()
        self.exited.emit(done.returncode, 0)


class FileView(QObject):
    fileChanged = Signal()
    loaded = Signal()
    loadFailed = Signal()
    pathChanged = Signal()
    watchChanges = prop(bool, "watchChanges", False)
    printErrors = prop(bool, "printErrors", True)
    blockLoading = prop(bool, "blockLoading", False)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._text = ""
        self._watcher = QFileSystemWatcher(self)
        self._watcher.fileChanged.connect(self._changed)
        self._watcher.directoryChanged.connect(self._changed)

    def _get_path(self):
        return getattr(self, "_path", "")

    def _set_path(self, value):
        # A new path drops the old watch, as Quickshell's does: the old file going isn't news.
        watched = self._watcher.files() + self._watcher.directories()
        if watched:
            self._watcher.removePaths(watched)
        self._path = value
        self.pathChanged.emit()
        if value:
            self._watch()
            if self.blockLoading:
                self.reload()
            else:
                QTimer.singleShot(0, self.reload)

    path = Property(str, _get_path, _set_path, notify=pathChanged)

    def _watch(self):
        # The folder, for a file replaced by a rename; the file, for one written in place.
        for path in (Path(self._path).parent, Path(self._path)):
            if path.exists() and str(path) not in self._watcher.files() + self._watcher.directories():
                self._watcher.addPath(str(path))

    def _changed(self, _):
        self._watch()
        if self.watchChanges:
            self.fileChanged.emit()

    @Slot()
    def reload(self):
        try:
            self._text = Path(self._path).read_text(encoding="utf-8")
        except OSError:
            self.loadFailed.emit()
        else:
            self.loaded.emit()

    @Slot(result=str)
    def text(self):
        return self._text


class PanelWindow(QQuickItem):
    colorChanged = Signal()
    color = prop(QColor, "color", QColor("transparent"), notify=colorChanged)


class FloatingWindow(QQuickItem):
    titleChanged = Signal()
    colorChanged = Signal()
    title = prop(str, "title", "", notify=titleChanged)
    color = prop(QColor, "color", QColor("transparent"), notify=colorChanged)
    minimumSize = prop(QSize, "minimumSize", QSize())


LAYER_SHELL = re.compile(r"^\s*(exclusionMode:.*|WlrLayershell\..*)$", re.M)
# The sidebar is sized by its screen edges in the shell; here, by the test window.
EDGES = "anchors { top: true; right: true; bottom: true }"


def main(out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp())
    os.environ["XDG_STATE_HOME"] = str(work / "state")
    os.environ["SOLO_HOME"] = str(work / "games")
    os.environ["XDG_RUNTIME_DIR"] = str(work / "run")
    # Begin runs `solo new --play`, which links solo and the skills into the home folder.
    os.environ["HOME"] = str(work / "home")
    os.environ["XDG_CACHE_HOME"] = str(work / "cache")
    # Something to play the sounds with, so the plugin plays them.
    (work / "bin").mkdir()
    (work / "bin" / "pw-play").write_text("#!/bin/sh\nexit 0\n")
    (work / "bin" / "pw-play").chmod(0o755)
    os.environ["PATH"] = f"{work / 'bin'}:{os.environ['PATH']}"
    import scenario
    # The test rules where a player's pack built from their book goes, so New adventure offers heroes.
    scenario.install_rules(work / "games")
    root = scenario.play(work)
    # The campaign (its hero died) is the current one, so Home lists it and the Hall remembers the hero.
    plugin = work / "plugin"
    plugin.mkdir()
    for name in ("book", "bin", "solo", "packs", "examples", "skills", "templates"):
        (plugin / name).symlink_to(REPO / name)
    (plugin / "Panel.qml").write_text(LAYER_SHELL.sub("", (REPO / "Panel.qml").read_text()).replace(EDGES, "width: 360; height: 1400"))
    shutil.copy(REPO / "BarWidget.qml", plugin / "BarWidget.qml")
    (work / "state" / "solo").mkdir(parents=True, exist_ok=True)
    (work / "state" / "solo" / "current").write_text(str(root) + "\n")

    app = QGuiApplication(sys.argv)
    shell = Shell()  # held here for the run: QML keeps no reference of its own to a singleton instance
    qmlRegisterSingletonInstance(QObject, "Quickshell", 1, 0, "Quickshell", shell)
    qmlRegisterType(PanelWindow, "Quickshell", 1, 0, "PanelWindow")
    qmlRegisterType(FloatingWindow, "Quickshell", 1, 0, "FloatingWindow")
    qmlRegisterType(Process, "Quickshell.Io", 1, 0, "Process")
    qmlRegisterType(Collector, "Quickshell.Io", 1, 0, "StdioCollector")
    qmlRegisterType(FileView, "Quickshell.Io", 1, 0, "FileView")
    qmlRegisterModule("Quickshell.Wayland", 1, 0)

    errors = []
    engine = QQmlEngine()  # one engine: the Quickshell stand-in is a single instance
    engine.addImportPath(str(HERE / "stubs"))
    engine.warnings.connect(lambda warnings: errors.extend(w.toString() for w in warnings))

    def load(name, width, height):
        view = QQuickView(engine, None)
        view.setResizeMode(QQuickView.SizeRootObjectToView)
        view.resize(width, height)
        view.setSource(QUrl.fromLocalFile(str(plugin / name)))
        if view.status() == QQuickView.Error:
            errors.extend(e.toString() for e in view.errors())
            return None
        view.show()
        return view

    def wait(ms):
        timer = QTimer()
        timer.setSingleShot(True)
        timer.start(ms)
        while timer.isActive():
            app.processEvents()

    panel = load("Panel.qml", 360, 1400)
    bar = load("BarWidget.qml", 60, 30)
    if panel is None or bar is None:
        print("\n".join(errors))
        return 1
    item = panel.rootObject()
    wait(800)
    item.open(json.dumps({"view": "table"}))
    wait(1500)
    panel.grabWindow().save(str(out / "table.png"))
    item.show("home")
    wait(2500)
    panel.grabWindow().save(str(out / "home.png"))
    item.setProperty("deleting", str(root))  # the card asking "delete for good?"
    wait(300)
    panel.grabWindow().save(str(out / "home-delete.png"))
    item.setProperty("deleting", "")
    item.open(json.dumps({"book": True}))
    wait(1500)
    errors += begin_and_ask(item, panel, out, work, wait)
    errors += desk_moments(item, panel, out, work, wait)
    errors += deleted_while_dying(item, bar, work, wait)
    print("bar tooltip:", bar.rootObject().tooltip())
    print("launched:")
    for command in LAUNCHED:
        print("  ", " ".join(str(c) for c in command[1:]))
    if errors:
        print("QML errors:\n  " + "\n  ".join(errors))
        return 2
    return 0


def begin_and_ask(item, panel, out, work, wait):
    """New adventure and the oracle from the panel, with what the player typed starting
    with a dash: it has to reach the engine as words, never as options."""
    problems = []
    item.show("new")
    wait(2500)
    panel.grabWindow().save(str(out / "new.png"))
    item.setProperty("heroName", "-Brokk")
    item.setProperty("tone", "-grim, and quiet")
    item.begin()
    wait(3000)
    if item.property("error"):
        return [f"Begin failed: {item.property('error')}"]
    game = Path((work / "state" / "solo" / "current").read_text().strip())
    state = json.loads((game / "state.json").read_text())
    if (state["pc"]["name"], state["prefs"]["tone"]) != ("-Brokk", "-grim, and quiet"):
        problems.append(f"Begin passed {state['pc']['name']!r} and {state['prefs']['tone']!r}")
    item.open(json.dumps({"view": "table"}))
    wait(1500)
    item.findChild(QObject, "question").setProperty("text", "-is anyone watching?")
    item.askOracle()
    wait(1500)
    log = json.loads((game / "state.json").read_text())["log"]
    if not any('"-is anyone watching?"' in entry["text"] for entry in log):
        problems.append(f"the oracle didn't get the question: {item.property('error') or log[-1]['text']}")
    panel.grabWindow().save(str(out / "table-alive.png"))
    return problems


def desk_moments(item, panel, out, work, wait):
    """With the Book open, a Dragon, a blow that leaves the hero dying, a Demon on a death
    roll and death: each has to set off its flash, hold or sound, timed to the dice."""
    from helpers import Dice
    from solo import campaign
    game = Path((work / "state" / "solo" / "current").read_text().strip())
    item.open(json.dumps({"book": True}))
    wait(1500)
    problems = []

    def expect(what, act, wanted, shot=None):
        LAUNCHED.clear()
        with campaign.session(game) as c:
            act(c)
        if shot:  # the Table's roll, still tumbling, then landed
            wait(250)
            panel.grabWindow().save(str(out / f"{shot}-tumbling.png"))
        wait(1500)
        if shot:
            panel.grabWindow().save(str(out / f"{shot}.png"))
        said = [" ".join(str(a) for a in command) for command in LAUNCHED]
        for want in wanted:
            if not any(want in line for line in said):
                problems.append(f"{what}: nothing launched with {want!r} (launched: {said})")

    expect("a Dragon", lambda c: c.check("awareness", rng=Dice(1, 3, 3, 3, 3)),
           ["pw-play " + str(work / "cache"), "/dice-", "desk --after 1.94 flash dragon", "sleep \"$0\"; exec \"$@\" 1.94 pw-play", "/dragon-"], shot="table-dragon")
    expect("a blow to dying", lambda c: c.wound("hero", "40", "a rockfall", armor=False, rng=Dice()),
           ["desk flash hit", "/hit-", "desk dying on 0", "/heartbeat-"], shot="table-dying")
    expect("a Demon on a death roll", lambda c: c.death_roll(rng=Dice(20, 3, 3, 3)),
           ["desk --after 1.94 flash demon", "desk --after 1.94 dying on 2", "/demon-"])
    expect("death", lambda c: c.death_roll(rng=Dice(20, 3, 3, 3)), ["desk --after 1.94 death", "/bell-"])
    return problems



def deleted_while_dying(item, bar, work, wait):
    """A campaign deleted while its hero lies dying: the d20 stops pulsing and the red lets
    go. Deleting takes `current` away before the folder, so the old state.json is never
    seen going; the game has to go with its campaign."""
    from helpers import Dice
    from solo import campaign
    solo = [str(REPO / "bin" / "solo")]
    game = work / "games" / "campaigns" / "doomed"
    subprocess.run(solo + ["new", "red-tusk", "--dir", str(game)], check=True, capture_output=True)
    wait(1500)
    with campaign.session(game) as c:
        c.wound("hero", "40", "a rockfall", armor=False, rng=Dice())
    wait(1500)
    problems = [] if bar.rootObject().property("dying") else ["the bar didn't see the hero dying before the delete"]
    LAUNCHED.clear()
    subprocess.run(solo + ["delete", str(game), "--yes"], check=True, capture_output=True)  # what the panel's Delete runs
    wait(1500)
    if bar.rootObject().property("dying") or bar.rootObject().property("pc") is not None:
        problems.append("the bar still shows the deleted campaign's dying hero")
    said = [" ".join(str(a) for a in command) for command in LAUNCHED]
    if not any("desk dying off" in line for line in said):
        problems.append(f"deleting a dying hero's campaign didn't let the red go (launched: {said})")
    if item.property("game") is not None:
        problems.append("the panel still holds the deleted campaign's game")
    return problems

if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "."))

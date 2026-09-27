"""The GM behind the Book: the player's default agent, run headless one turn at a time.

The Book (the plugin's story window) never talks to a model. It runs `solo gm turn` in
the background and watches `.solo/turn.json`, which this module rewrites as the agent
works: its status, the narration as it streams in, and a word about what it is doing
(reading the table, rolling, writing it down). When the turn ends, the narration is
recorded with the rest of the conversation (`said` events), so the campaign still keeps
the transcript and any agent session can be thrown away.

Only agents with a headless mode that streams JSON and resumes a session are driven
here: Claude Code and Codex. Any other default agent keeps its terminal window
(`solo play --terminal`); the Book still shows the story as it is recorded.

This is the only part of solo that runs an agent. The engine still never calls a model.
"""

import fcntl
import json
import os
import re
import signal
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path

from . import SoloError, campaign
from .library import REPO, state_home

# Every GM prompt that isn't the player's own words starts with this, so the transcript
# hook can tell them apart and never records one as something the player said.
PREAMBLE = "You are the game master of the solo campaign in this folder."
BOOK_PROMPT = (
    f"{PREAMBLE} Follow the solo-gm skill (or read AGENTS.md). The player reads you in the Book, "
    "a window that already shows everything said so far and every roll as it happens. "
    "Run `solo resume --book` and do exactly what it says."
)
# What a Claude Code session may run without asking. The campaign's settings.json says the
# same, but Claude ignores a project's permissions until its folder has been trusted in an
# interactive session, so the headless GM carries its own list.
NESTING = ("CLAUDECODE", "CLAUDE_CODE_SESSION_ID", "CLAUDE_CODE_CHILD_SESSION", "CLAUDE_PID", "CLAUDE_CODE_ENTRYPOINT")
_WRITE_EVERY = 0.08
# Seconds an agent may go without a word (no line on its stream) before its turn is ended.
# SOLO_GM_TIMEOUT changes it.
_QUIET_LIMIT = 180
# The GM's pace, which the player picks on the Table, and the effort level it asks of the
# agent. A quick turn arrives sooner and spends fewer tokens. A careful one thinks longer
# about the rules.
PACES = {"quick": "low", "normal": "medium", "careful": "high"}
# What the Book says the GM is doing, by the solo command it runs.
_DOING = {
    "scene": "reading the scene", "npc": "reading the scene", "rule": "looking up the rules",
    "state": "reading the table", "log": "reading the table", "resume": "reading the table",
    "recall": "remembering", "history": "remembering",
    "check": "rolling the dice", "push": "rolling the dice", "roll": "rolling the dice", "table": "rolling the dice",
    "ask": "asking the oracle", "voice": "listening", "attack": "rolling the dice", "enemy": "rolling the dice", "ally": "rolling the dice", "wound": "rolling the dice",
    "defend": "rolling the dice", "death-roll": "rolling the dice", "rally": "rolling the dice", "advance": "rolling the dice",
    "commit": "writing it down", "threat": "writing it down", "search": "rolling the dice", "scavenge": "rolling the dice", "move": "writing it down", "fight": "writing it down", "rest": "writing it down",
    "light": "writing it down", "mark": "writing it down", "say": "writing it down",
}


def default_agent():
    """The agent Omarchy launches (`omarchy default agent`); SOLO_AGENT overrides it."""
    chosen = os.environ.get("SOLO_AGENT")
    if chosen:
        return chosen.strip()
    try:
        return (Path.home() / ".config/omarchy/defaults/agent").read_text(encoding="utf-8").split()[0]
    except (OSError, IndexError):
        return ""


def supported(agent):
    return agent in ADAPTERS


def status(root):
    """turn.json as the Book reads it, with a dead turn (killed with the shell, say)
    reported as stopped rather than still thinking forever."""
    path = Path(root) / ".solo" / "turn.json"
    try:
        turn = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"status": "idle"}
    if turn.get("status") in ("thinking", "writing") and not _turn_alive(turn):
        turn["status"] = "stopped"
        _write_down_stopped(Path(root) / ".solo", turn)
    return turn


def _write_down_stopped(folder, turn):
    """The Book reads turn.json itself: a turn that died without finishing (the machine went
    down) would keep it waiting, the player unable to write, for good. Write it down as
    stopped, so the Book offers to try again; only while no turn holds the lock, so a turn
    just starting is never overwritten."""
    try:
        with open(folder / "turn.lock", "w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            if _load(folder / "turn.json").get("id") == turn.get("id"):
                temporary = folder / "turn.json.tmp"
                temporary.write_text(json.dumps({**turn, "status": "stopped", "agent_pid": None}, ensure_ascii=False), encoding="utf-8")
                os.replace(temporary, folder / "turn.json")
    except OSError:  # a turn holds the lock (BlockingIOError), or the folder can't be written
        pass


def stop(root):
    """Stop the turn in progress. What the GM had written so far is dropped; the
    player's words stay recorded, so the next turn answers them."""
    turn = status(root)
    if turn.get("status") not in ("thinking", "writing"):
        raise SoloError("the GM isn't writing anything right now")
    # The agent runs in a process group of its own. An agent may exit with an error of its
    # own when it's stopped, so the turn is told it was asked to, and says stopped, not failed.
    (Path(root) / ".solo" / "stop").write_text(f"{turn.get('id', '')}\n", encoding="utf-8")
    pid = turn.get("agent_pid")
    if pid and _alive(pid):
        try:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            pass


def turn(root, text=None, agent=None):
    """One exchange: record the player's words (if any), run the agent until it answers,
    record its answer. Without text the GM opens or picks up the story on its own."""
    root = Path(root)
    agent = agent or default_agent()
    folder = root / ".solo"
    folder.mkdir(exist_ok=True)
    with open(folder / "turn.lock", "w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SoloError("the GM is still writing; wait for it, or stop it") from None
        # A turn that was killed (the shell went down with it) can leave its agent running,
        # still rolling and writing. Two GMs on one table contradict each other: end it first.
        _reap(root)
        live = Live(folder / "turn.json", text)
        # From here the Book is watching: whatever goes wrong ends up in turn.json, where it
        # says what happened and offers to try again, instead of "thinking" for good.
        try:
            return _turn(root, folder, text, agent, live)
        except SoloError as error:
            return live.fail(str(error))
        except Exception as error:
            live.fail(f"Something went wrong ({type(error).__name__}: {error}).")
            raise


def _turn(root, folder, text, agent, live):
    if not agent:
        return live.fail("No default agent is set. Choose one with: omarchy default agent <name>")
    elif not supported(agent):
        return live.fail(f"Your default agent ({agent}) can't write in the Book yet. Open the GM in a terminal instead.")
    table = []
    if text and text.strip():
        with campaign.session(root) as c:
            c.say(text, "player")
            table = since_gm(c)
    saved = _load(folder / "agent.json")
    session = saved.get("session") if saved.get("agent") == agent else None
    adapter = ADAPTERS[agent]
    result = adapter.run(root, player_prompt(text, table) if session and text else BOOK_PROMPT, session, live)
    result["stopped"] = result.get("stopped") or _asked_to_stop(folder, live)
    if result.get("stale") and not result["stopped"]:
        # The agent lost the session (cleared, or another machine): start a fresh one,
        # which catches up from the campaign itself.
        live.reset()
        result = adapter.run(root, BOOK_PROMPT, None, live)
        result["stopped"] = result.get("stopped") or _asked_to_stop(folder, live)
    # What the turn cost, for play tests and the curious: the Book doesn't show it.
    live.update(usage=result.get("usage"))
    if result.get("session"):
        (folder / "agent.json").write_text(json.dumps({"agent": agent, "session": result["session"]}) + "\n", encoding="utf-8")
    if result.get("stopped"):
        live.update(force=True, status="stopped", text="", agent_pid=None)
        return live.data
    elif result.get("error"):
        return live.fail(result["error"])
    answer = drop_notes((result.get("text") or "").strip())
    if not answer:
        return live.fail("The GM finished without a word for you. Try again, or open it in a terminal.")
    with campaign.session(root) as c:
        c.say(answer, "gm")
    return live.finish(answer)


# Words a GM's notes to itself use and its narration never does.
_NOTES = re.compile(r"\b(narrate|narration|the player|commit(ted|s)?|the engine|solo [a-z-]+|scene text|GM text)\b", re.I)


_FENCE = re.compile(r"^:::[ \t]*gm\b.*?(^:::[ \t]*$|\Z)", re.S | re.M | re.I)


def drop_notes(text):
    """The final message goes into the Book as it is, and a GM sometimes opens it with a
    note to itself ("Library exit is now open. Time to narrate the payoff."), or copies a
    `::: gm` block into it as if the Book would hide it. Both are dropped: the fenced
    blocks wherever they are, the leading notes as long as narration follows them."""
    text = _FENCE.sub("", text)
    paragraphs = [p for p in re.split(r"\n\s*\n", text) if p.strip()]
    while len(paragraphs) > 1 and _NOTES.search(paragraphs[0]):
        paragraphs.pop(0)
    return "\n\n".join(p.strip() for p in paragraphs)


def since_gm(c, limit=30):
    """What happened at the table since the GM last spoke: the player's rolls, rests and
    oracle questions from the panel, and what they set off, one line each."""
    last = next((e["seq"] for e in reversed(c.events) if e["type"] == "said" and e["by"] == "gm"), 0)
    hidden = set(c.state["hidden"])
    return [f"#{e['seq']} {campaign.gm_line(e)}" + (" (hidden from the player)" if e["seq"] in hidden else "")
            for e in c.events if e["seq"] > last and e["type"] != "said"][-limit:]


def player_prompt(text, table):
    """A resumed turn: the player's words, after what they did at the table since the GM's
    last message, so the GM narrates those results instead of missing or repeating them.
    It opens with PREAMBLE, so the transcript hook never takes it for the player's words."""
    if not table:
        return text
    lines = "\n".join(f"- {line}" for line in table)
    return (f"{PREAMBLE} Since your last message the player did this at the table. It is already rolled and "
            f"recorded: narrate it, don't roll it again.\n{lines}\n\nThe player says:\n\n{text}")


class Live:
    """turn.json: what the Book shows while the GM works."""

    def __init__(self, path, player):
        self.path = path
        self.data = {
            "id": datetime.now().isoformat(timespec="milliseconds"), "status": "thinking", "player": (player or "").strip(),
            "text": "", "doing": "reading the table", "error": "", "pid": os.getpid(), "started": _started(os.getpid()),
            "agent_pid": None,
        }
        self.written = 0.0
        self.write(force=True)

    def reset(self):
        self.update(text="", status="thinking")

    def update(self, force=False, **changes):
        self.data.update(changes)
        self.write(force)

    def write(self, force=False):
        now = time.monotonic()
        if force or now - self.written >= _WRITE_EVERY:
            temporary = self.path.with_name("turn.json.tmp")
            temporary.write_text(json.dumps(self.data, ensure_ascii=False), encoding="utf-8")
            os.replace(temporary, self.path)
            self.written = now

    def fail(self, message):
        self.update(force=True, status="error", error=message, agent_pid=None)
        return self.data

    def finish(self, answer):
        self.update(force=True, status="done", text=answer, doing="", agent_pid=None)
        return self.data


class Adapter:
    """Runs one agent turn and reads its JSON lines. Subclasses build the command and
    read the events; `run` returns {session, text, error, stale}."""

    def command(self, prompt, session):
        raise NotImplementedError

    def read(self, event, result, live):
        raise NotImplementedError

    def run(self, root, prompt, session, live):
        env = {k: v for k, v in os.environ.items() if k not in NESTING}
        # The GM's `solo` is this plugin's, whether or not `solo setup` put one on PATH.
        # SOLO_BOOK: this turn's final message is recorded by `turn`, so `solo say` stands down.
        env.update(PATH=f"{REPO / 'bin'}:{env.get('PATH', '')}", PWD=str(root), SOLO_GM=str(root), SOLO_BOOK="1")
        # stderr goes to a file: a pipe nobody reads while stdout streams can fill and stall the agent.
        with tempfile.TemporaryFile("w+") as errors:
            try:
                process = subprocess.Popen(
                    self.command(prompt, session), cwd=root, env=env, stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE, stderr=errors, text=True, start_new_session=True,
                    preexec_fn=_die_with_parent,
                )
            except OSError as error:
                return {"error": f"Couldn't start the GM ({error.strerror or error})."}
            live.update(force=True, agent_pid=process.pid)
            result = {"session": session, "text": "", "error": "", "stale": False}
            # An agent that hangs (a stalled connection, a question nobody will answer) would
            # leave the Book thinking for good: one that goes quiet too long is ended.
            limit, heard, silent = _quiet_limit(), time.monotonic(), threading.Event()

            def watch():
                while process.poll() is None and time.monotonic() - heard < limit:
                    time.sleep(1)
                if process.poll() is None:
                    silent.set()
                    _end_group(process)

            threading.Thread(target=watch, daemon=True).start()
            with process:
                for line in process.stdout:
                    heard = time.monotonic()
                    try:
                        event = json.loads(line)
                    except ValueError:
                        continue
                    if isinstance(event, dict):
                        self.read(event, result, live)
            errors.seek(0)
            errors = errors.read()
        if silent.is_set():
            result["error"] = f"The GM said nothing for {limit:g} seconds, so its turn was ended. Try again."
        elif process.returncode < 0:
            result["stopped"] = True
        elif process.returncode and not result["text"]:
            # An agent can report a lost session on stderr, in its own error event, or both.
            result["stale"] = bool(session) and self.lost(f"{errors}\n{result['error']}")
            if result["stale"]:
                result["error"] = ""
            elif not result["error"]:
                result["error"] = _last_line(errors) or f"The GM stopped with an error (exit {process.returncode})."
        return result

    def lost(self, errors):
        """Whether the agent refused to resume because it has no such session."""
        text = errors.lower()
        return "no conversation" in text or "not found" in text or "no session" in text


class Claude(Adapter):
    """Claude Code: `claude -p` with stream-json, partial messages for live typing."""

    def command(self, prompt, session):
        tools = [f"Bash(solo {name}:*)" for name in campaign_commands()]
        command = ["claude", "-p", "--output-format", "stream-json", "--verbose", "--include-partial-messages",
                   "--allowedTools", *tools]
        # The prompt goes last, after --: the player's words can start with a dash.
        return command + _model() + ["--effort", effort()] + (["--resume", session] if session else []) + ["--", prompt]

    def read(self, event, result, live):
        kind = event.get("type")
        if kind == "system" and event.get("subtype") == "init":
            result["session"] = event.get("session_id") or result["session"]
        elif kind == "stream_event":
            inner = event.get("event", {})
            block = inner.get("content_block", {})
            if inner.get("type") == "content_block_start" and block.get("type") == "tool_use":
                # Text before a tool call is the GM thinking aloud, not narration.
                live.update(force=True, text="", status="thinking")
            elif inner.get("type") == "content_block_delta" and inner.get("delta", {}).get("type") == "text_delta":
                live.update(status="writing", text=live.data["text"] + inner["delta"].get("text", ""))
        elif kind == "assistant":
            for block in event.get("message", {}).get("content", []):
                if block.get("type") == "tool_use":
                    live.update(force=True, doing=doing((block.get("input") or {}).get("command", "")))
        elif kind == "result":
            result["session"] = event.get("session_id") or result["session"]
            usage = event.get("usage") or {}
            result["usage"] = {
                "model_calls": event.get("num_turns"),
                "input_tokens": sum(usage.get(k) or 0 for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")),
                "cached_input_tokens": usage.get("cache_read_input_tokens"),
                "output_tokens": usage.get("output_tokens"),
                "cost_usd": event.get("total_cost_usd"),
            }
            if event.get("is_error") or event.get("subtype") != "success":
                reason = event.get("result") or "\n".join(map(str, event.get("errors") or []))
                result["error"] = _first_line(reason) or "The GM ran into an error."
            else:
                result["text"] = event.get("result") or live.data["text"]


class Codex(Adapter):
    """Codex: `codex exec --json`, resumed by thread id. Its messages come whole."""

    def command(self, prompt, session):
        # Codex has no list of allowed commands: its sandbox lets the GM write in the campaign
        # folder (which `solo` needs) and nowhere else. (`--full-auto` said the same, until
        # Codex dropped it.)
        command = ["codex", "exec", "--json", "--skip-git-repo-check", "--sandbox", "workspace-write",
                   "-c", f'model_reasoning_effort="{effort()}"'] + _model()
        return command + (["resume", session] if session else []) + ["--", prompt]

    def read(self, event, result, live):
        kind = event.get("type")
        item = event.get("item") or {}
        if kind == "thread.started":
            result["session"] = event.get("thread_id") or result["session"]
        elif kind == "item.started" and item.get("type") == "command_execution":
            live.update(force=True, doing=doing(item.get("command", "")), text="", status="thinking")
        elif kind == "item.completed" and item.get("type") == "agent_message":
            result["text"] = item.get("text", "")
            live.update(force=True, status="writing", text=result["text"])
        elif kind == "turn.completed":
            usage = event.get("usage") or {}
            result["usage"] = {"model_calls": None, "input_tokens": usage.get("input_tokens"), "cached_input_tokens": usage.get("cached_input_tokens"),
                               "output_tokens": usage.get("output_tokens"), "cost_usd": None}
        elif kind in ("turn.failed", "error"):
            message = (event.get("error") or {}).get("message") if isinstance(event.get("error"), dict) else event.get("message")
            result["error"] = _first_line(message or "") or "The GM ran into an error."


ADAPTERS = {"claude": Claude(), "codex": Codex()}


def _quiet_limit():
    try:
        return float(os.environ.get("SOLO_GM_TIMEOUT") or _QUIET_LIMIT)
    except ValueError:
        return float(_QUIET_LIMIT)


def _end_group(process):
    """End an agent and whatever it started (its own process group): politely, then for good."""
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(process.pid, sig)
            process.wait(5)
            return
        except ProcessLookupError:
            return
        except subprocess.TimeoutExpired:
            continue


def _model():
    """SOLO_GM_MODEL picks the GM's model (play tests compare them); otherwise the agent's own default."""
    model = os.environ.get("SOLO_GM_MODEL", "").strip()
    return ["--model", model] if model else []


def pace():
    """The GM's pace. It is the player's time and tokens, not the story's, so one pace
    holds for every campaign."""
    saved = _load(state_home() / "gm.json").get("pace")
    return saved if saved in PACES else "normal"


def set_pace(name):
    if name not in PACES:
        raise SoloError(f"no pace {name!r}; paces: {', '.join(PACES)}")
    path = state_home() / "gm.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"pace": name}) + "\n", encoding="utf-8")
    return name


def effort():
    """SOLO_GM_EFFORT sets the agent's effort level outright (play tests compare them); otherwise the pace."""
    return os.environ.get("SOLO_GM_EFFORT", "").strip() or PACES[pace()]


def campaign_commands():
    from .cli import GM_COMMANDS
    return GM_COMMANDS


def doing(command):
    """"solo check sneaking --boons 1" -> "rolling the dice"."""
    words = str(command).replace("'", " ").replace('"', " ").split()
    name = words[words.index("solo") + 1] if "solo" in words[:-1] else ""
    return _DOING.get(name, "thinking")


def _die_with_parent():
    """In the agent's process, before it starts: on Linux, have the kernel end it when the
    `solo gm turn` that started it dies, however that happens."""
    if sys.platform.startswith("linux"):
        import ctypes
        PR_SET_PDEATHSIG = 1
        ctypes.CDLL(None, use_errno=True).prctl(PR_SET_PDEATHSIG, signal.SIGTERM)


def _reap(root):
    """End the agent of an earlier turn that outlived its `solo gm turn`. Only a process
    that carries this campaign's SOLO_GM marker is touched, so a recycled pid never is."""
    turn = _load(Path(root) / ".solo" / "turn.json")
    pid = turn.get("agent_pid")
    if _turn_alive(turn) or not _ours(pid, root):
        return
    try:
        group = os.getpgid(int(pid))
        os.killpg(group, signal.SIGTERM)
        for _ in range(50):
            time.sleep(0.1)
            if not _alive(pid):
                return
        os.killpg(group, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass


def _ours(pid, root):
    """Whether `pid` is a GM agent this module started for the campaign at `root`."""
    try:
        environ = Path(f"/proc/{int(pid)}/environ").read_bytes().split(b"\0")
    except (OSError, ValueError, TypeError):
        return False
    return f"SOLO_GM={Path(root)}".encode() in environ


def _load(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _turn_alive(turn):
    """Whether the `solo gm turn` that wrote turn.json still runs: its pid is alive and is
    still the same process. A pid alone gets reused, soon after a reboot, and a turn killed
    with the machine would say "thinking" for good (a turn.json with no start time is
    taken at its pid's word)."""
    pid = turn.get("pid")
    return _alive(pid) and turn.get("started") in (None, _started(pid))


def _started(pid):
    """When a process started, in clock ticks since boot (Linux), or None."""
    try:
        return int(Path(f"/proc/{int(pid)}/stat").read_text().rsplit(")", 1)[1].split()[19])
    except (OSError, ValueError, IndexError, TypeError):
        return None


def _alive(pid):
    if not pid:
        return False
    try:
        os.kill(int(pid), 0)
        return True
    except (ProcessLookupError, ValueError, TypeError):
        return False
    except PermissionError:
        return True


def _asked_to_stop(folder, live):
    """Whether `solo gm stop` was run on this turn (it leaves the turn's id behind)."""
    try:
        return (folder / "stop").read_text(encoding="utf-8").strip() == live.data["id"]
    except OSError:
        return False


def _last_line(text):
    """An agent's stderr ends with what went wrong; warnings come before it."""
    return next((line.strip() for line in reversed(str(text).splitlines()) if line.strip()), "")[:300]


def _first_line(text):
    return next((line.strip() for line in str(text).splitlines() if line.strip()), "")[:300]

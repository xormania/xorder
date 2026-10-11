"""FIFO admission for cooperative processes, with kernel-backed live tickets."""
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import tempfile
import time


class RunQueue:
    def __init__(self, folder, workspace, env):
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)
        self.started = time.monotonic()
        self.ticket = None
        self.path = None
        maximum = int(env.get("XORDER_TEST_MAX_WAITERS", "64"))
        if not 1 <= maximum <= 1024:
            raise ValueError("XORDER_TEST_MAX_WAITERS must be between 1 and 1024")
        with self._guard():
            live = self._live()
            if len(live) >= maximum:
                raise ValueError(f"Host test FIFO queue is full ({maximum} waiting runs); retry after a run finishes")
            counter = self.folder / "sequence"
            try:
                previous = int(counter.read_text())
            except (FileNotFoundError, ValueError):
                previous = 0
            sequence = max(previous, max((int(path.stem) for path in live), default=0)) + 1
            # The queue guard serializes registration, not wall-clock estimates.
            with tempfile.NamedTemporaryFile(mode="w", prefix="sequence-", dir=self.folder, delete=False) as temporary:
                temporary.write(str(sequence))
                temporary.flush()
                os.fsync(temporary.fileno())
                filename = Path(temporary.name)
            filename.replace(counter)
            self.path = self.folder / f"{sequence:020d}.json"
            self.ticket = self.path.open("x+")
            fcntl.flock(self.ticket, fcntl.LOCK_EX)
            json.dump({"workspace": str(workspace), "project": env.get("UXOR_PROJECT") or env.get("FLOWBITE_PROJECT"),
                       "pid": os.getpid(), "started_at": time.time()}, self.ticket)
            self.ticket.flush()

    @contextmanager
    def _guard(self):
        with (self.folder / "guard").open("a+") as guard:
            fcntl.flock(guard, fcntl.LOCK_EX)
            yield

    def _live(self):
        live = []
        for path in sorted(self.folder.glob("*.json")):
            if path == self.path:
                live.append(path)
                continue
            with path.open("a+") as ticket:
                try:
                    fcntl.flock(ticket, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    live.append(path)
                    continue
                # Death/cancellation releases the kernel ticket, even if finally
                # could not run. Remove only stale ticket metadata under guard.
                path.unlink(missing_ok=True)
        return live

    @contextmanager
    def turn(self):
        with self._guard():
            live = self._live()
            yield live.index(self.path) + 1, len(live)

    def admitted(self):
        """Called while holding turn(), after acquiring the real host lease."""
        self.path.unlink(missing_ok=True)
        self.ticket.close()
        self.ticket = None

    def elapsed(self):
        return time.monotonic() - self.started

    def close(self):
        if self.ticket is not None:
            with self._guard():
                self.path.unlink(missing_ok=True)
                self.ticket.close()
                self.ticket = None

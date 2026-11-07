"""Single-writer, fsync-before-ack, append-only journal with a hard byte bound."""

import fcntl
import json
import os
from pathlib import Path
from typing import Any, Self

from .protocol import clone, encode

JOURNAL_LIMIT = 16 * 1024 * 1024


class JournalFull(BufferError):
    pass


class Journal:
    def __init__(self, path: Path, limit: int = JOURNAL_LIMIT, reserve: int = 65536):
        if not 0 < reserve < limit <= JOURNAL_LIMIT:
            raise ValueError("invalid journal bounds")
        self.path, self.limit, self.reserve = path, limit, reserve
        path.parent.mkdir(parents=True, exist_ok=True)
        self.fd = os.open(path, os.O_RDWR | os.O_APPEND | os.O_CREAT, 0o600)
        try:
            fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.size = os.fstat(self.fd).st_size
            if self.size > limit:
                raise ValueError("journal exceeds configured bound")
            data = os.read(self.fd, self.size)
            if data and not data.endswith(b"\n"):
                raise ValueError("truncated journal tail; preserve file for recovery")
            self._entries = [json.loads(line) for line in data.splitlines()]
            if any(not isinstance(row, dict) for row in self._entries):
                raise ValueError("invalid journal record")
            self.failed = False
        except BaseException:
            os.close(self.fd)
            raise

    def append(self, value: dict[str, Any], *, control: bool = False) -> None:
        if self.failed:
            raise OSError("journal requires recovery after a write failure")
        data = encode(value) + b"\n"
        bound = self.limit if control else self.limit - self.reserve
        if self.size + len(data) > bound:
            raise JournalFull("journal capacity reached; no evidence evicted")
        try:
            offset = 0
            while offset < len(data):
                written = os.write(self.fd, data[offset:])
                if not written:
                    raise OSError("short journal write")
                offset += written
            os.fsync(self.fd)
        except OSError:
            self.failed = True
            raise
        self.size += len(data)
        self._entries.append(clone(value))

    def entries(self) -> list[dict[str, Any]]:
        return clone(self._entries)  # type: ignore[no-any-return]

    def close(self) -> None:
        if self.fd >= 0:
            os.close(self.fd)
            self.fd = -1

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

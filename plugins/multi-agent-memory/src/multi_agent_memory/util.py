"""共享小工具：时间、frontmatter、路径段、分词、内容指纹。"""
from __future__ import annotations

import hashlib
import json
import os
import re
import socket
import tempfile
from datetime import datetime
from pathlib import Path

from .errors import MemoryHubError

_TOKEN_CHUNK = re.compile(r"[^\s,，;；、]+")
_CJK_RUN = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]+")
_LATIN_TOKEN = re.compile(r"[a-z0-9][a-z0-9_./-]{0,63}", re.IGNORECASE)


def content_fingerprint(text: str) -> str:
    normalized = " ".join(text.split()).casefold()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def tokenize_query(query: str) -> list[str]:
    """确定性分词：空白/标点切分，CJK 用二元组，便于无空格中文查询。"""
    terms: list[str] = []
    for chunk in _TOKEN_CHUNK.findall(query.strip()):
        last = 0
        for match in _CJK_RUN.finditer(chunk):
            other = chunk[last : match.start()]
            if other:
                terms.extend(token.casefold() for token in _LATIN_TOKEN.findall(other))
            cjk = match.group(0)
            if len(cjk) == 1:
                terms.append(cjk)
            else:
                terms.extend(cjk[index : index + 2] for index in range(len(cjk) - 1))
            last = match.end()
        trailing = chunk[last:]
        if trailing:
            terms.extend(token.casefold() for token in _LATIN_TOKEN.findall(trailing))
    return list(dict.fromkeys(term for term in terms if term))


def now() -> datetime:
    return datetime.now().astimezone()


def one_line(value: str) -> str:
    return " ".join(value.replace("\x00", "").split())


def safe_segment(value: str, label: str) -> str:
    value = value.strip()
    if not value or value in {".", ".."}:
        raise MemoryHubError(f"{label}不能为空")
    if any(char in value for char in ("/", "\\", "\x00")):
        raise MemoryHubError(f"{label}不能包含路径分隔符")
    if any(ord(char) < 32 for char in value):
        raise MemoryHubError(f"{label}不能包含控制字符")
    return value


def slug(value: str, fallback: str = "note") -> str:
    value = re.sub(r"[^\w\-\u4e00-\u9fff]+", "-", value, flags=re.UNICODE)
    return value.strip("-")[:60] or fallback


def normalize_memory_key(value: str) -> str:
    text = one_line(value)
    if not text:
        raise MemoryHubError("记忆 key 不能为空")
    if any(char in text for char in ("/", "\\", "\x00")):
        raise MemoryHubError("记忆 key 不能包含路径分隔符")
    if any(ord(char) < 32 for char in text):
        raise MemoryHubError("记忆 key 不能包含控制字符")
    if len(text) > 120:
        raise MemoryHubError("记忆 key 过长（最多 120 字符）")
    return text.casefold()


def choice(value: str, allowed: set[str], label: str) -> str:
    value = value.strip().casefold()
    if value not in allowed:
        choices = "、".join(sorted(allowed))
        raise MemoryHubError(f"{label}必须是：{choices}")
    return value


def frontmatter(metadata: dict[str, object]) -> str:
    lines = ["---"]
    for key, value in metadata.items():
        lines.append(f"{key}: {json.dumps(value, ensure_ascii=False)}")
    lines.extend(["---", ""])
    return "\n".join(lines)


def split_frontmatter(content: str) -> tuple[dict[str, object], str]:
    if not content.startswith("---\n"):
        return {}, content
    boundary = content.find("\n---\n", 4)
    if boundary < 0:
        return {}, content
    metadata: dict[str, object] = {}
    for line in content[4:boundary].splitlines():
        key, separator, raw_value = line.partition(":")
        if not separator or not key.strip():
            continue
        try:
            metadata[key.strip()] = json.loads(raw_value.strip())
        except json.JSONDecodeError:
            metadata[key.strip()] = raw_value.strip()
    return metadata, content[boundary + 5 :]


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, path)
    finally:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass


def pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes

        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
        if handle:
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def lock_owner_gone(payload: dict[str, object]) -> bool:
    pid = payload.get("pid")
    if not isinstance(pid, int):
        return False
    host = payload.get("host")
    if isinstance(host, str) and host and host != socket.gethostname():
        return False
    return not pid_alive(pid)

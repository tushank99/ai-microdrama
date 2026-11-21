"""Parse a plain-text microdrama screenplay into episodes and timestamped beats.

Assumed format (same shape as a typical timestamped screenplay):
    EPISODE 1: Title
    [00:00] INT. MANSION - NIGHT
    [00:03] ARIA: You lied to me.
    [00:05] (Damien slaps the glass off the table.)
Lines without a timestamp are attached to the previous beat.
"""
import re
from dataclasses import dataclass, field

EP_RE = re.compile(r"^\s*EPISODE\s+(\d+)\s*[:\-]?\s*(.*)$", re.I)
TS_RE = re.compile(r"^\s*\[(\d{1,2}):(\d{2})\]\s*(.*)$")


@dataclass
class Beat:
    t: int          # seconds from episode start
    text: str


@dataclass
class Episode:
    number: int
    title: str
    beats: list = field(default_factory=list)

    @property
    def duration(self) -> int:
        return self.beats[-1].t if self.beats else 0

    def window(self, start: int, end: int) -> str:
        return "\n".join(f"[{b.t//60:02d}:{b.t%60:02d}] {b.text}"
                         for b in self.beats if start <= b.t <= end)

    def opening(self, secs: int = 15) -> str:
        return self.window(0, secs)

    def ending(self, secs: int = 20) -> str:
        return self.window(max(0, self.duration - secs), self.duration)


def parse_screenplay(text: str) -> list:
    episodes, cur = [], None
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue
        m = EP_RE.match(line)
        if m:
            cur = Episode(int(m.group(1)), m.group(2).strip())
            episodes.append(cur)
            continue
        if cur is None:
            continue
        m = TS_RE.match(line)
        if m:
            cur.beats.append(Beat(int(m.group(1)) * 60 + int(m.group(2)), m.group(3).strip()))
        elif cur.beats:
            cur.beats[-1].text += " " + line.strip()
    return episodes

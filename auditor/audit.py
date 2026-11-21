"""Cliffhanger Auditor: score each episode's opening hook and closing cliffhanger.

Two layers:
  1. Rules (free, deterministic, explainable) - keyword/structure signals.
  2. LLM judge (swappable) - reads the opening + ending of each episode in batches,
     returns scores, the cliffhanger type and a concrete rewrite suggestion.
Final verdict uses the LLM score when available; big rule/LLM disagreement is flagged
for a human editor instead of being silently resolved.
"""
import re

from . import llm
from .parse import Episode

# ---------------------------------------------------------------- rules layer
TENSION = r"slap|gun|knife|blood|dead|die|kill|pregnan|divorce|lie|lied|liar|secret|betray|affair|" \
          r"scream|shatter|smash|crash|fire|arrest|police|kidnap|ambulance|faint|collapse|stolen|" \
          r"father|mother|son|daughter|twin|heir|contract|fired|evict|threat|blackmail|who are you|" \
          r"you're not|it was you|truth|dna|will|inheritance"
RESOLUTION = r"hug|smile|laugh|goodnight|good night|sleep|everything is fine|it's okay now|" \
             r"thank you|i love you too|relax|sigh of relief|the end|happily|celebrat|cheers"
OPEN_ENDED = r"\?\s*$|—\s*$|\.\.\.\s*$|door (?:bursts|swings|opens)|phone (?:rings|buzzes)|" \
             r"freezes|turns around|reveal|walks in|enters|cut to black|smash cut"


def _hits(pattern: str, text: str) -> int:
    return len(re.findall(pattern, text, re.I))


def rule_scores(ep: Episode) -> dict:
    opening, ending = ep.opening(), ep.ending()
    last_beats = " ".join(b.text for b in ep.beats[-2:])

    hook = 3 + 2 * min(_hits(TENSION, opening), 3) + (1 if "!" in opening else 0)
    cliff = (3 + 1.5 * min(_hits(TENSION, ending), 3)
             + 2.5 * min(_hits(OPEN_ENDED, last_beats), 1)
             - 3 * min(_hits(RESOLUTION, last_beats), 1))
    clamp = lambda x: int(max(0, min(10, round(x))))
    return {"rule_hook": clamp(hook), "rule_cliff": clamp(cliff)}


# ---------------------------------------------------------------- LLM layer
PROMPT = """You are a senior story editor for vertical microdramas (1-2 min episodes, ReelShort/DramaBox style).
Viewers decide in the first 3 seconds whether to keep watching, and decide at the last 5 seconds whether
to unlock/play the next episode. Judge ONLY what is on the page below.

For EACH episode return:
- hook_score 0-10: does the first ~3-15 s grab a scrolling viewer (conflict, shock, reveal, strong line)?
- cliff_score 0-10: does the episode END on an unresolved question that forces the next episode?
  Endings that resolve, calm down, or end on a hug/goodnight score low.
- cliff_type: one of reveal | threat | interruption | betrayal | arrival | decision | question | none
- issue: one short sentence on the main weakness (or "none")
- fix: one concrete rewrite of the final beat (max 25 words) that would raise cliff_score.
  Use only characters/facts already in the text; do not invent new plot facts beyond the ending.

Return ONLY a JSON array, one object per episode, with keys:
episode, hook_score, cliff_score, cliff_type, issue, fix

Story context so far (may be empty): {context}

{episodes}
"""


def llm_scores(episodes: list, batch: int = 10, context: str = "", **llm_opts) -> dict:
    out = {}
    for i in range(0, len(episodes), batch):
        chunk = episodes[i:i + batch]
        body = "\n\n".join(
            f"### EPISODE {e.number} ({e.duration}s) - {e.title}\nOPENING:\n{e.opening()}\nENDING:\n{e.ending()}"
            for e in chunk)
        raw = llm.complete(PROMPT.format(context=context or "-", episodes=body), **llm_opts)
        for row in llm.extract_json(raw):
            out[int(row["episode"])] = row
    return out


# ---------------------------------------------------------------- combine
def audit(episodes: list, paywall_ep: int = 10, threshold: int = 6,
          provider: str = None, model: str = None, api_key: str = None) -> list:
    provider = (provider or llm.provider()).lower()
    judged = {}
    llm_error = None
    if provider != "none":
        try:
            judged = llm_scores(episodes, provider_name=provider, model=model, api_key=api_key)
        except Exception as exc:  # keep working rules-only rather than crash
            llm_error = str(exc)[:200]

    rows = []
    for ep in episodes:
        r = rule_scores(ep)
        j = judged.get(ep.number, {})
        hook = j.get("hook_score", r["rule_hook"])
        cliff = j.get("cliff_score", r["rule_cliff"])
        near_paywall = abs(ep.number - paywall_ep) <= 1
        flags = []
        if cliff < threshold:
            flags.append("WEAK_CLIFFHANGER")
        if hook < threshold:
            flags.append("WEAK_HOOK")
        if near_paywall and cliff < threshold + 2:
            flags.append("PAYWALL_RISK")
        if j and abs(j["cliff_score"] - r["rule_cliff"]) >= 4:
            flags.append("HUMAN_CHECK")  # rules and model disagree a lot
        rows.append({
            "episode": ep.number, "title": ep.title, "duration_s": ep.duration,
            "hook_score": hook, "cliff_score": cliff,
            "rule_hook": r["rule_hook"], "rule_cliff": r["rule_cliff"],
            "cliff_type": j.get("cliff_type", "-"),
            "issue": j.get("issue", "-"), "fix": j.get("fix", "-"),
            "last_line": ep.beats[-1].text if ep.beats else "",
            "flags": ",".join(flags),
            "scored_by": provider if j else "rules",
            "llm_error": llm_error or "",
        })
    return rows

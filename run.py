"""CLI: python run.py <script.txt> [--labels labels.csv] [--paywall 10] [--provider groq] [--model ...] [--out outputs/x]"""
import argparse
import json
from pathlib import Path

import pandas as pd

from auditor.audit import audit
from auditor.parse import parse_screenplay


def evaluate(df: pd.DataFrame, labels_path: str) -> dict:
    lab = pd.read_csv(labels_path)
    m = df.merge(lab, on="episode")
    res = {}
    for col, flag in (("weak_cliff", "WEAK_CLIFFHANGER"), ("weak_hook", "WEAK_HOOK")):
        pred = m["flags"].str.contains(flag).astype(int)
        tp = int(((pred == 1) & (m[col] == 1)).sum())
        fp = int(((pred == 1) & (m[col] == 0)).sum())
        fn = int(((pred == 0) & (m[col] == 1)).sum())
        res[col] = {"tp": tp, "fp": fp, "fn": fn,
                    "precision": round(tp / (tp + fp), 2) if tp + fp else None,
                    "recall": round(tp / (tp + fn), 2) if tp + fn else None,
                    "misses": m.loc[(pred == 0) & (m[col] == 1), "episode"].tolist(),
                    "false_alarms": m.loc[(pred == 1) & (m[col] == 0), "episode"].tolist()}
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("script")
    ap.add_argument("--labels")
    ap.add_argument("--paywall", type=int, default=10)
    ap.add_argument("--provider", help="gemini|groq|openai|anthropic|claude_cli|none")
    ap.add_argument("--model")
    ap.add_argument("--out", default="outputs/run")
    a = ap.parse_args()
    eps = parse_screenplay(Path(a.script).read_text(encoding="utf-8"))
    df = pd.DataFrame(audit(eps, paywall_ep=a.paywall, provider=a.provider, model=a.model))
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    df.to_csv(out / "audit.csv", index=False)
    df.to_json(out / "audit.json", orient="records", indent=2)

    pd.set_option("display.width", 200)
    print(df[["episode", "hook_score", "cliff_score", "rule_cliff", "cliff_type", "flags"]].to_string(index=False))
    if a.labels:
        ev = evaluate(df, a.labels)
        (out / "eval.json").write_text(json.dumps(ev, indent=2))
        print(json.dumps(ev, indent=2))


if __name__ == "__main__":
    main()

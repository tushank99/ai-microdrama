"""Builds docs/solution.pdf (python docs/make_pdf.py)."""
from pathlib import Path

from fpdf import FPDF

S = [
("h", "Cliffhanger Auditor - Kuku AI Generalist Assignment, Problem 3"),
("p", "Prototype: repo with run steps (README.md). Raw outputs: outputs/. Stack: Python, pandas, Streamlit, any LLM via one swappable function."),
("h2", "1. Problem and why I picked it"),
("p", "Who: the story editor who reviews AI-generated microdrama scripts before they go to video generation. "
      "Step: checking that every episode opens on a hook and ends on a cliffhanger. Output: a per-episode table of scores, flags and a suggested fix for the last beat."),
("p", "Why it matters: microdramas earn money episode by episode. After a free run, each new episode is a paid unlock, so the last 5 seconds of an episode are the conversion moment. "
      "One flat ending (a goodnight or a hug that settles things), especially just before the paywall, loses viewers for every later episode. AI-written scripts are prone to this: "
      "models like to tidy things up and resolve conflict. Today the only check is a human reading every episode, while shows ship weekly."),
("p", "Why over Problems 1 and 2: Problem 1 (promos) works after the show is made and helps acquisition. This one works upstream at script stage, where a fix costs a rewritten line "
      "instead of regenerated video, and it protects retention and revenue on every episode. Problem 2 is outside Kuku's core business. "
      "Honest gap: in the time box I did not systematically gather viewer reviews or watch-time data, so 'weak endings drive drop-off' is an assumption the team should check against its own episode-to-episode retention."),
("h2", "2. Assumptions"),
("b", "Scripts arrive as text with an [mm:ss] timestamp on each beat and 'EPISODE N' headers (the format the input pack describes). No input pack was in my workspace, so I wrote two synthetic test shows (18 episodes)."),
("b", "Hook = first ~15 s on the page; cliffhanger = last ~20 s. The paywall episode is configurable (default 10); the episodes on either side of it get a stricter threshold."),
("b", "The tool advises and the editor decides. It never rewrites the script itself."),
("h2", "3. How it works"),
("b", "Parse (code): split into episodes and timestamped beats, then cut out the opening and ending windows."),
("b", "Rules (code, free): tension, open-ending and resolution keyword signals give a baseline 0-10 score. It is instant, explainable and works with no API."),
("b", "LLM judge (AI): openings and endings for 10 episodes go into one call, and the model returns JSON with hook_score, cliff_score, cliff_type, issue and fix. Batching keeps cost low."),
("b", "Combine (code): flags WEAK_CLIFFHANGER / WEAK_HOOK (score < 6) and PAYWALL_RISK. HUMAN_CHECK appears when the rules and the LLM differ by 4 or more points; that disagreement goes to a person instead of being resolved silently."),
("b", "Model swap: llm.complete() supports Gemini, Groq, any OpenAI-compatible endpoint, Anthropic and the local Claude CLI. Change one flag or env var (--provider / --model)."),
("h2", "4. Does it work? (real runs, labels written before running)"),
("t", [["Test set", "Mode", "Weak-cliff P / R", "Weak-hook P / R"],
       ["Show A (12 eps)", "rules only", "0.44 / 1.00", "0.50 / 1.00"],
       ["Show A (12 eps)", "LLM (Claude Haiku)", "1.00 / 1.00", "1.00 / 1.00"],
       ["Hard cases (6 eps)", "rules only", "0.60 / 1.00", "0.50 / 1.00"],
       ["Hard cases (6 eps)", "LLM (Claude Haiku)", "1.00 / 1.00", "1.00 / 1.00"]]),
("p", "The hard set was built to fool keywords: a loud ending that is resolved, a quiet but ominous ending, a shock in the middle that is undone by the end, and a withheld decision. "
      "Rules miss the quiet-ominous and withheld-decision endings; the LLM catches them. Caveat: I wrote both the scripts and the labels, so 18 episodes is a smoke test, not proof. "
      "The real test is the editors' own labels on the 50-episode pack."),
("h2", "5. Where it fails"),
("b", "Detection is good; the suggested fixes are the weak part. In 3 of 15 fixes the model broke story logic: one fix said 'you still lied about the affair' right after the reveal that the woman was his sister; one pulled in 'the drive', a fact from a different episode; one just restated the existing syringe beat."),
("b", "It judges each episode on its own. It does not know arc context (for example a deliberate breather episode), and it cannot see acting, music or visuals, which may land a cliffhanger the text does not show."),
("b", "Rules are tuned to English and to genre keywords. Other languages need the LLM path."),
("b", "Scores from different models are not calibrated against each other, so after a model swap the threshold needs re-checking on a labelled set."),
("h2", "6. Scale and cost"),
("p", "About 300 tokens per episode go in and about 80 come out. A 60-episode show is roughly 25k tokens: free on the Gemini or Groq free tiers, and well under $0.05 even on a frontier model. "
      "That is trivial at 10+ shows a week. The rules layer always runs, so it doubles as a fallback when the API is down. A person stays in the loop for every flagged episode and every HUMAN_CHECK. "
      "Next steps: pass a story-so-far summary as context to fix arc blindness, and make fixes cite only facts from the same episode."),
("h2", "7. How I would know it worked with a real team"),
("b", "Agreement: editor-labelled weak endings on past shows vs flags (target recall above 0.9, so the tool does not miss what editors would catch)."),
("b", "Adoption: share of flags the editor acts on, and share of suggested fixes used as written or lightly edited."),
("b", "Outcome: next-episode play-through and paywall unlock rate for flagged episodes that were fixed vs a matched set left unfixed, plus editor minutes per show."),
("h2", "8. AI tools used and one place they got it wrong"),
("p", "I used Claude Code to write the code and Claude Haiku (through the Claude CLI) as the judge. Where AI got it wrong: the first rule layer equated tension words with a cliffhanger, "
      "which flagged 5 strong endings as weak (precision 0.44) and would miss loud-but-resolved endings in other cases. The judge model also invents plot facts in its suggested fixes (section 5). "
      "That is why the fix is only a suggestion and every flag goes to an editor."),
]


def build(out="docs/solution.pdf"):
    pdf = FPDF(format="A4")
    pdf.set_margins(14, 12, 14)
    pdf.set_auto_page_break(True, 12)
    pdf.add_page()
    for kind, val in S:
        if kind == "h":
            pdf.set_font("Helvetica", "B", 13); pdf.multi_cell(0, 6, val, new_x="LMARGIN", new_y="NEXT"); pdf.ln(1)
        elif kind == "h2":
            pdf.ln(1.5); pdf.set_font("Helvetica", "B", 10.5); pdf.multi_cell(0, 5, val, new_x="LMARGIN", new_y="NEXT")
        elif kind == "p":
            pdf.set_font("Helvetica", "", 8.8); pdf.multi_cell(0, 4.1, val, new_x="LMARGIN", new_y="NEXT"); pdf.ln(0.8)
        elif kind == "b":
            pdf.set_font("Helvetica", "", 8.8); pdf.multi_cell(0, 4.1, "-  " + val, new_x="LMARGIN", new_y="NEXT")
        elif kind == "t":
            w = [42, 46, 46, 46]
            for i, row in enumerate(val):
                pdf.set_font("Helvetica", "B" if i == 0 else "", 8.5)
                for c, cell in enumerate(row):
                    pdf.cell(w[c], 5, cell, border=1)
                pdf.ln()
            pdf.ln(1)
    pdf.output(out)
    print("pages:", pdf.page_no())


if __name__ == "__main__":
    build()


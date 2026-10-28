"""Prepare a diverse human-review queue from verified policy/teacher disagreements.

The teacher supplies review candidates, not correctness labels. No teacher
choice is used for training until a person reviews the recorded visible state.
"""

import argparse
import json
from collections import Counter
from html import escape
from math import isfinite
from pathlib import Path
from urllib.parse import quote

import torch

from goat_ai.agents import (
    TacticalHeuristicAgent,
    load_card_facts,
    load_card_races,
    load_flip_monster_codes,
)
from goat_ai.agents.card_metadata import load_weak_flip_monster_attack
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.evaluation.replay_review import review_candidates
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory
from goat_ai.replay.fingerprint import sha256_file
from goat_ai.training import load_policy_agent
from goat_ai.training.policy import POLICY_INFERENCE_VERSION, encode_decision
from scripts.render_replay import _card_names, render_replay


def select_diverse_candidates(candidates: list[dict], limit: int,
                              per_replay: int, *, rank_by: str = "probability"
                              ) -> list[dict]:
    """Take confident disagreements without letting one prompt dominate."""
    if limit < 1 or per_replay < 1 or rank_by not in ("probability", "logit"):
        raise ValueError("review limits must be positive")
    score_key = "probability_margin" if rank_by == "probability" else "logit_margin"
    chosen = []
    fingerprints = set()
    replay_counts: Counter[str] = Counter()
    for candidate in sorted(candidates, key=lambda item: (
            not item["audit_flags"], -item[score_key],
            item["trajectory"], item["decision_index"])):
        fingerprint = candidate["_fingerprint"]
        replay = candidate["trajectory"]
        if fingerprint in fingerprints or replay_counts[replay] >= per_replay:
            continue
        fingerprints.add(fingerprint)
        replay_counts[replay] += 1
        chosen.append({key: value for key, value in candidate.items()
                       if key != "_fingerprint"})
        if len(chosen) == limit:
            break
    return chosen


def action_summary(action) -> dict:
    """Present only the structured action the agent could already select."""
    return {"kind": action.kind, "parameters": action.parameters}


def visible_faceup_age(observation, code: int, minimum: int) -> int | None:
    """Match only field cards whose identity and age are public to this player."""
    ages = [card.faceup_turns for card in observation.field
            if card.position == "faceup" and card.code == code
            and card.faceup_turns is not None and card.faceup_turns >= minimum]
    return max(ages, default=None)


def disagreement_fingerprint(record, teacher_action) -> tuple:
    selected = record.selected_action
    # A response card such as Ring can be offered on many chains. Keep one
    # review example per offered card, while target/announcement prompts need
    # their resolving source to distinguish unrelated choices.
    chain_source = (record.observation.chain[-1].card_code
                    if record.observation.chain and selected.kind in (
                        "select_card", "select_cards", "announce_race",
                        "announce_attribute", "announce_number") else None)
    phase = None if selected.kind == "pass" and teacher_action.kind == "chain" else (
        record.observation.phase)
    return (phase, chain_source,
            selected.kind, selected.parameters.get("code"),
            teacher_action.kind, teacher_action.parameters.get("code"))


def write_review_index(selected: list[dict], output: Path,
                       native_root: Path) -> Path:
    """Link player-visible label frames and separate full-information review."""
    codes = {action["parameters"].get("code")
             for item in selected for action in (
                 item["policy_action"], item["teacher_action"])}
    codes.update(item.get("visible_faceup_card") for item in selected)
    names = _card_names({code for code in codes if type(code) is int and code > 0},
                        native_root)

    def action_label(action: dict) -> str:
        code = action["parameters"].get("code")
        name = names.get(code, f"Card {code}") if code else ""
        return escape(f"{action['kind'].replace('_', ' ')} {name}".strip())

    def frame_link(path: Path, fragment: str) -> str:
        relative = path.relative_to(output.parent.resolve())
        return quote(str(relative), safe="/") + "#" + fragment

    flagged = []
    disagreements = []
    queue_items = []
    for number, item in enumerate(selected, 1):
        viewer, fragment = item["viewer"].split("#", 1)
        label_href = frame_link(Path(viewer), fragment)
        reveal_path = Path(viewer).with_suffix(".review.html")
        reveal_href = (frame_link(reveal_path, fragment)
                       if reveal_path.is_file() else None)
        reveal = (f'<a href="{escape(reveal_href, quote=True)}">Reveal all cards</a>'
                  if reveal_path.is_file() else "")
        teacher_agrees = item["policy_action"] == item["teacher_action"]
        age_code = item.get("visible_faceup_card")
        age_note = (f"{names.get(age_code, f'Card {age_code}')} face-up for "
                    f"{item['visible_faceup_turns']} turn boundaries"
                    if age_code is not None else "")
        reason = (", ".join(flag.replace("_", " ") for flag in item["audit_flags"])
                  if item["audit_flags"] else age_note
                  if age_note else "Tactical agent suggests another play")
        choices = (f'<p><strong>Both agents played:</strong> '
                   f'{action_label(item["policy_action"])}</p>'
                  if teacher_agrees else
                   f'<p><strong>AI played:</strong> {action_label(item["policy_action"])}<br>'
                   f'<strong>Tactical suggests:</strong> {action_label(item["teacher_action"])}</p>')
        card = (
            f'<article class="review-card" id="item-{number}" data-queue-index="{number - 1}">'
            f'<div class="card-top"><span class="badge">#{number} · '
            f'{"Flagged play" if item["audit_flags"] else "Alternative" if not teacher_agrees else "Review"}</span>'
            f'<span>Turn {item["turn"]} · {escape(item["phase"].replace("_", " "))}'
            f' · decision {item["viewer_frame"]}</span></div>'
            f'<h3>{escape(reason)}</h3>'
            f'{choices}'
            f'<div class="links"><a class="primary" href="{escape(label_href, quote=True)}">Open label view</a>'
            f'{reveal}<button class="bookmark-item" type="button" hidden '
            f'aria-label="Bookmark review item {number}">Bookmark</button></div></article>')
        queue_items.append({"visible": label_href, "reveal": reveal_href,
                            "title": f"#{number} · {reason}",
                            "source": item.get("trajectory_sha256"),
                            "decision_index": item.get("decision_index")})
        (flagged if item["audit_flags"] else disagreements).append(card)
    queue_json = json.dumps(queue_items, ensure_ascii=True).replace("<", "\\u003c")
    html = ("<!doctype html><html lang=\"en\"><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            "<title>GOAT AI review queue</title><style>"
            "*{box-sizing:border-box}body{font:16px system-ui;background:#071925;"
            "color:#f1f6f8;max-width:1180px;margin:0 auto;padding:20px}"
            "h1{margin:0 0 8px}h2{margin:28px 0 12px}h3{margin:8px 0;font-size:1.05rem}"
            "p{line-height:1.45}a{color:#8bd9ee}ol{padding-left:24px;line-height:1.55}"
            ".intro{background:#172731;border:1px solid #36535e;border-radius:12px;"
            "padding:18px}.grid{display:grid;grid-template-columns:repeat(auto-fit,"
            "minmax(min(100%,350px),1fr));gap:12px}.review-card{background:#172731;"
            "border:1px solid #36535e;border-radius:12px;padding:16px;min-width:0}"
            ".card-top{display:flex;justify-content:space-between;gap:12px;"
            "flex-wrap:wrap;color:#a7c5ca;font-size:.85rem}.badge{color:#ffe2a3}"
            ".links{display:flex;gap:10px;flex-wrap:wrap;margin-top:14px}"
            ".links a{display:inline-block;border:1px solid #4f7980;border-radius:7px;"
            "padding:8px 10px;text-decoration:none}.links a:hover{background:#306575}"
            ".links .primary{background:#234854;color:#fff}"
            "button,input{font:inherit}button{cursor:pointer;background:#234854;color:#fff;"
            "border:1px solid #4f7980;border-radius:7px;padding:7px 10px}"
            "button:disabled{opacity:.45;cursor:default}#queue-search{width:100%;max-width:480px;"
            "padding:9px;background:#0b2430;color:#fff;border:1px solid #4f7980;"
            "border-radius:7px;margin:12px 0}"
            ".review-card[hidden]{display:none}.stage[hidden]{display:none}"
            ".stage{position:fixed;inset:0;z-index:10;background:#071925;"
            "display:grid;grid-template-rows:auto minmax(0,1fr)}"
            ".stage-bar{display:flex;align-items:center;gap:8px;flex-wrap:wrap;"
            "padding:7px 12px;background:#172731;border-bottom:1px solid #36535e}"
            ".stage-title{flex:1;min-width:180px;overflow:hidden;text-overflow:ellipsis;"
            "white-space:nowrap}#stage-frame{width:100%;height:100%;border:0}"
            "</style><section class=\"intro\"><h1>GOAT AI review queue</h1>"
            "<p>Each card opens a complete duel at one decision worth examining."
            " Flags and Tactical suggestions are prompts, not confirmed mistakes."
            " A flagged play can be one both agents made. For automatic saving,"
            " launch the local review server described in docs/replay_audit.md.</p>"
            "<ol><li>Choose <strong>Open label view</strong> to see exactly what the"
            " acting AI player could see. The sidebar shows its selected action"
            " and all legal alternatives.</li><li>Use the queue bar to move between"
            " review items. Inside the replay, Previous and Next move between"
            " decisions in that duel.</li>"
            "<li>Use Bookmark to mark an item for later without endorsing any action."
            " Bookmarks save locally when using the review server and are never"
            " training labels.</li><li>If you know a better legal action, click"
            " Choose a different action beside the AI's play, then choose it from"
            " All legal actions. When this queue is opened through the local review server,"
            " choices save automatically. An offline file viewer still offers a"
            " manual label download. <strong>Reveal all cards</strong> opens a separate inspection"
            " view with hidden cards shown; labeling is disabled there.</li></ol>"
            "</section><label for=\"queue-search\">Find a review item</label><br>"
            "<input id=\"queue-search\" type=\"search\" placeholder=\"Search card, action, or flag\">"
            "<h2>Flagged decisions</h2><div class=\"grid\">"
            + "".join(flagged) + "</div><h2>Other choices to compare</h2>"
            "<div class=\"grid\">" + "".join(disagreements) + "</div>"
            "<section class=\"stage\" id=\"stage\" hidden aria-label=\"Review replay\">"
            "<nav class=\"stage-bar\" aria-label=\"Review queue navigation\">"
            "<button id=\"back-to-queue\" type=\"button\">← Queue</button>"
            "<button id=\"previous-item\" type=\"button\">Previous item</button>"
            "<span id=\"item-position\"></span>"
            "<button id=\"next-item\" type=\"button\">Next item</button>"
            "<button id=\"toggle-reveal\" type=\"button\">Reveal all cards</button>"
            "<button id=\"stage-bookmark\" type=\"button\" hidden>Bookmark</button>"
            "<span class=\"stage-title\" id=\"stage-title\"></span>"
            "<a id=\"open-tab\" target=\"_blank\" rel=\"noopener\">Open in new tab</a>"
            "</nav><iframe id=\"stage-frame\" title=\"GOAT AI replay viewer\"></iframe>"
            "</section><script>\"use strict\";const items=" + queue_json + ";"
            "const stage=document.getElementById('stage'),frame=document.getElementById('stage-frame');"
            "let current=-1,mode='visible',pendingLabels=false;"
            "let bookmarks=new Set(),bookmarkMode=false;"
            "const bookmarkKey=item=>`${item.source}:${item.decision_index}`;"
            "function updateBookmarks(){document.querySelectorAll('.bookmark-item').forEach(button=>{"
            "const i=Number(button.closest('.review-card').dataset.queueIndex);"
            "button.hidden=!bookmarkMode||!items[i].source;"
            "const saved=bookmarks.has(bookmarkKey(items[i]));"
            "button.textContent=saved?'★ Bookmarked':'☆ Bookmark';"
            "button.setAttribute('aria-pressed',String(saved));});"
            "const button=document.getElementById('stage-bookmark');"
            "button.hidden=!bookmarkMode||current<0||!items[current]?.source;"
            "if(!button.hidden){const saved=bookmarks.has(bookmarkKey(items[current]));"
            "button.textContent=saved?'★ Bookmarked':'☆ Bookmark';"
            "button.setAttribute('aria-pressed',String(saved));}}"
            "async function toggleBookmark(i){if(!bookmarkMode||!items[i]?.source)return;"
            "const item=items[i],saved=!bookmarks.has(bookmarkKey(item));"
            "const response=await fetch('/api/review/bookmark',{method:'POST',"
            "headers:{'Content-Type':'application/json'},body:JSON.stringify({"
            "source:item.source,decision_index:item.decision_index,bookmarked:saved})});"
            "const data=await response.json();if(!response.ok)throw Error(data.error||'Bookmark save failed');"
            "bookmarks=new Set(data.bookmarks.map(bookmarkKey));updateBookmarks();}"
            "async function loadBookmarks(){if(location.protocol!=='http:'||"
            "!['127.0.0.1','localhost'].includes(location.hostname))return;"
            "try{const response=await fetch('/api/review/bookmarks');if(!response.ok)return;"
            "const data=await response.json();bookmarks=new Set(data.bookmarks.map(bookmarkKey));"
            "bookmarkMode=true;updateBookmarks();}catch(_){}}loadBookmarks();"
            "document.querySelectorAll('.bookmark-item').forEach(button=>button.onclick=()=>{"
            "toggleBookmark(Number(button.closest('.review-card').dataset.queueIndex))"
            ".catch(error=>alert(error.message));});"
            "document.getElementById('stage-bookmark').onclick=()=>{"
            "toggleBookmark(current).catch(error=>alert(error.message));};"
            "window.addEventListener('message',event=>{if(event.source===frame.contentWindow&&"
            "event.data?.type==='goat-ai-review-label-state')"
            "pendingLabels=Boolean(event.data.pending);});"
            "function mayLeave(){return !pendingLabels||confirm('You have labels that have not been saved. Leave this duel and discard them?');}"
            "function openItem(i,wanted='visible'){if(i<0||i>=items.length)return;"
            "if(current>=0&&!mayLeave())return;pendingLabels=false;"
            "current=i;mode=wanted==='reveal'&&items[i].reveal?'reveal':'visible';"
            "const url=items[i][mode];frame.src=url;stage.hidden=false;"
            "document.getElementById('item-position').textContent=`${i+1} / ${items.length}`;"
            "document.getElementById('stage-title').textContent=items[i].title;"
            "updateBookmarks();"
            "document.getElementById('open-tab').href=url;"
            "document.getElementById('previous-item').disabled=i===0;"
            "document.getElementById('next-item').disabled=i===items.length-1;"
            "const toggle=document.getElementById('toggle-reveal');"
            "toggle.disabled=!items[i].reveal;toggle.textContent=mode==='reveal'"
            "?'Return to label view':'Reveal all cards';"
            "history.replaceState(null,'',`#item=${i+1}&mode=${mode}`);"
            "}"
            "document.querySelectorAll('.review-card').forEach(card=>{"
            "card.querySelectorAll('.links a').forEach(link=>link.addEventListener('click',e=>{"
            "if(e.ctrlKey||e.metaKey||e.shiftKey||e.button!==0)return;"
            "e.preventDefault();openItem(Number(card.dataset.queueIndex),"
            "link.classList.contains('primary')?'visible':'reveal');}));});"
            "document.getElementById('back-to-queue').onclick=()=>{if(!mayLeave())return;"
            "pendingLabels=false;stage.hidden=true;"
            "frame.removeAttribute('src');history.replaceState(null,'',location.pathname);"
            "document.getElementById(`item-${current+1}`)?.scrollIntoView({block:'center'});};"
            "document.getElementById('previous-item').onclick=()=>openItem(current-1,mode);"
            "document.getElementById('next-item').onclick=()=>openItem(current+1,mode);"
            "document.getElementById('toggle-reveal').onclick=()=>openItem(current,"
            "mode==='reveal'?'visible':'reveal');"
            "document.getElementById('queue-search').oninput=e=>{const term=e.target.value.toLowerCase();"
            "document.querySelectorAll('.review-card').forEach(card=>{"
            "card.hidden=!card.textContent.toLowerCase().includes(term);});};"
            "const match=location.hash.match(/^#item=(\\d+)&mode=(visible|reveal)$/);"
            "if(match)openItem(Number(match[1])-1,match[2]);"
            "</script></html>\n")
    index = output.with_suffix(".html")
    index.write_text(html, encoding="utf-8")
    return index


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("replays", nargs="+", type=Path)
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--per-replay", type=int, default=2)
    parser.add_argument("--rank-by", choices=("probability", "logit"),
                        default="probability",
                        help="rank disagreements by probability or raw AI-to-Tactical score gap")
    parser.add_argument("--min-logit-margin", type=float, default=0.0,
                        help="keep only disagreements where the raw model favors its action "
                             "over Tactical by at least this score gap")
    parser.add_argument("--visible-faceup-card", type=int,
                        help="review decisions while this known face-up card is on the field")
    parser.add_argument("--min-faceup-turns", type=int, default=1,
                        help="minimum public turn boundaries since that card became face-up")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--render-viewers", action="store_true",
                        help="write offline HTML for replays represented in the queue")
    args = parser.parse_args()
    if (args.limit < 1 or args.per_replay < 1
            or not isfinite(args.min_logit_margin) or args.min_logit_margin < 0):
        parser.error("review limits must be positive")
    if ((args.visible_faceup_card is not None and args.visible_faceup_card <= 0)
            or args.min_faceup_turns < 0
            or args.visible_faceup_card is None and args.min_faceup_turns != 1):
        parser.error("face-up age filter needs a positive card ID and nonnegative age")
    if len({path.resolve() for path in args.replays}) != len(args.replays):
        parser.error("duplicate replay path")
    checkpoint_hash = sha256_file(args.checkpoint)
    agent = load_policy_agent(args.checkpoint)
    model = agent.model.eval()
    flip_codes = load_flip_monster_codes(args.native_root)
    card_races = load_card_races(args.native_root)
    weak_flip_attacks = load_weak_flip_monster_attack(args.native_root)
    card_facts = load_card_facts(args.native_root)

    def fresh_teacher():
        # A counterfactual attack choice was not necessarily executed in the
        # recorded policy duel. Do not carry its private pending-attack cache
        # into the next review decision; real context is in the observation.
        return TacticalHeuristicAgent(
            flip_codes, card_races, card_facts=card_facts,
            v8_guards=True, v9_guards=True, v10_guards=True, v11_guards=True,
            v12_guards=True, v13_guards=True, v14_guards=True)
    candidates = []
    replay_report = []
    for path in args.replays:
        source_hash = sha256_file(path)
        trajectory = read_trajectory(path)
        metadata = trajectory.skill_metadata or {}
        seat = metadata.get("demonstrator_seat")
        if (trajectory.source != "policy_evaluation" or type(seat) is not int
                or seat not in (0, 1)
                or metadata.get("policy_checkpoint_sha256") != checkpoint_hash
                or metadata.get("policy_inference") != "greedy"
                or metadata.get("policy_inference_version") != POLICY_INFERENCE_VERSION
                or metadata.get("policy_feature_version") != model.feature_version):
            raise ValueError(f"{path}: expected a plain greedy replay from this checkpoint")
        verified = verify_trajectory(
            trajectory, ExperimentalOcgcoreEngine(args.native_root))
        audit_trajectory_visibility(trajectory)
        if sha256_file(path) != source_hash:
            raise ValueError(f"{path}: replay changed during verification")
        audit_by_index: dict[int, list[str]] = {}
        for finding in review_candidates(trajectory, card_races, weak_flip_attacks,
                                         card_facts=card_facts):
            audit_by_index.setdefault(finding.decision_index, []).append(finding.category)
        disagreements = 0
        policy_choices = 0
        replay_agent = load_policy_agent(args.checkpoint)
        for index, record in enumerate(trajectory.decisions):
            if record.observation.acting_player != seat:
                continue
            policy_choices += 1
            legal = record.legal_actions
            if replay_agent.select_action(record.observation, legal) != record.selected_action:
                raise ValueError(f"{path}: greedy policy choice differs at {index}")
            if len(legal) == 1:
                continue
            age = (visible_faceup_age(record.observation, args.visible_faceup_card,
                                      args.min_faceup_turns)
                   if args.visible_faceup_card is not None else None)
            if args.visible_faceup_card is not None and age is None:
                continue
            features = encode_decision(record.observation, legal, agent.vocabulary,
                                       model.feature_version)
            with torch.inference_mode():
                logits = model(features.to(next(model.parameters()).device))
                probabilities = torch.softmax(logits, 0).cpu()
            policy_index = legal.index(record.selected_action)
            alternative = fresh_teacher().select_action(record.observation, legal)
            if alternative not in legal:
                raise ValueError(f"{path}: teacher choice is illegal at {index}")
            disagreed = alternative != record.selected_action
            audit_flags = audit_by_index.get(index, [])
            if not disagreed and not audit_flags and age is None:
                continue
            disagreements += disagreed
            teacher_index = legal.index(alternative)
            margin = float(probabilities[policy_index] - probabilities[teacher_index])
            logit_margin = float(logits[policy_index] - logits[teacher_index])
            if args.min_logit_margin and (not disagreed
                                          or logit_margin < args.min_logit_margin):
                continue
            candidates.append({
                "trajectory": str(path.resolve()),
                "trajectory_sha256": source_hash,
                "decision_index": index,
                "viewer_frame": index + 1,
                "seat": seat,
                "turn": record.observation.turn,
                "phase": record.observation.phase,
                "legal_action_count": len(legal),
                "policy_action": action_summary(record.selected_action),
                "teacher_action": action_summary(alternative),
                "policy_probability": round(float(probabilities[policy_index]), 6),
                "teacher_probability": round(float(probabilities[teacher_index]), 6),
                "probability_margin": round(margin, 6),
                "logit_margin": round(logit_margin, 6),
                "audit_flags": audit_flags,
                "teacher_disagrees": disagreed,
                **({"visible_faceup_card": args.visible_faceup_card,
                    "visible_faceup_turns": age} if age is not None else {}),
                "_fingerprint": (("audit", tuple(audit_flags),
                                  record.selected_action.kind,
                                  record.selected_action.parameters.get("code"))
                                 if audit_flags else
                                 disagreement_fingerprint(record, alternative)
                                 if disagreed else
                                 ("timed", args.visible_faceup_card, age,
                                  record.observation.phase, record.selected_action.kind,
                                  record.selected_action.parameters.get("code"))),
            })
        replay_report.append({"trajectory": str(path.resolve()),
                              "trajectory_sha256": source_hash,
                              "verified_decisions": verified,
                              "policy_choices": policy_choices,
                              "disagreements": disagreements})
    selected = select_diverse_candidates(candidates, args.limit, args.per_replay,
                                         rank_by=args.rank_by)
    if args.render_viewers:
        viewer_dir = args.output.parent / (args.output.stem + "_viewers")
        for path in sorted({item["trajectory"] for item in selected}):
            source = Path(path)
            digest = next(item["trajectory_sha256"] for item in selected
                          if item["trajectory"] == path)
            if sha256_file(source) != digest:
                raise ValueError(f"{path}: replay changed before rendering")
            output = viewer_dir / f"{source.stem}_{digest[:12]}.html"
            render_replay(source, output, args.native_root)
            render_replay(source, output.with_suffix(".review.html"),
                          args.native_root, reviewer_reveal=True)
            for item in selected:
                if item["trajectory"] == path:
                    item["viewer"] = str(output.resolve()) + f"#decision={item['viewer_frame']}"
    report = {"schema_version": 1,
              "purpose": "human_review_candidates_not_training_labels",
              "checkpoint_sha256": checkpoint_hash,
              "teacher": "TacticalHeuristicAgent_v14",
              "rank_by": args.rank_by,
              "min_logit_margin": args.min_logit_margin,
              "selection": ("public_faceup_age_then_model_margin_distinct_prompt"
                            if args.visible_faceup_card is not None else
                            "visible_audit_then_model_margin_distinct_prompt_max_per_replay"),
              **({"visible_faceup_card": args.visible_faceup_card,
                  "min_faceup_turns": args.min_faceup_turns}
                 if args.visible_faceup_card is not None else {}),
              "replays": replay_report,
              "candidate_count": len(candidates),
              "selected": selected}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    if args.render_viewers:
        write_review_index(selected, args.output, args.native_root)
    print(json.dumps({"output": str(args.output), "replays": len(replay_report),
                      "candidate_count": len(candidates), "selected": len(selected),
                      "verified_decisions": sum(item["verified_decisions"]
                                                for item in replay_report)}))


if __name__ == "__main__":
    main()

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
from goat_ai.agents.tactical_guard import (
    safe_idle_own_ring_indices,
    safe_optional_own_loss_indices,
    safe_target_indices,
)
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.evaluation.replay_review import review_candidates
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory
from goat_ai.replay.fingerprint import sha256_file
from goat_ai.training import load_policy_agent
from goat_ai.training.policy import POLICY_INFERENCE_VERSION, encode_decision
from scripts.render_replay import _card_names, _option_texts, render_replay


def select_diverse_candidates(candidates: list[dict], limit: int,
                              per_replay: int, *, rank_by: str = "probability",
                              dedupe_fingerprints: bool = True,
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
        if ((dedupe_fingerprints and fingerprint in fingerprints)
                or replay_counts[replay] >= per_replay):
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


def recorded_policy_options(inference: str, card_facts: dict) -> dict:
    """Rebuild the recorded visible inference mode before shortlisting it."""
    if inference == "greedy":
        return {}
    versions = {"greedy_own_loss_guard_v1": 1,
                "greedy_own_loss_guard_v2": 2,
                "greedy_own_loss_guard_v3": 3}
    if inference not in versions:
        raise ValueError(f"unsupported policy inference {inference!r}")
    version = versions[inference]
    return {"own_loss_guard": True, "own_loss_guard_version": version,
            "card_facts": card_facts if version == 2 else None}


def visible_ring_guard_alternative(observation, legal, scores):
    """Suggest the exact v3 surviving action at an idle-own-Ring prompt."""
    indices = safe_optional_own_loss_indices(observation, legal, range(len(legal)))
    kept = safe_idle_own_ring_indices(observation, legal, indices)
    if len(kept) == len(indices):
        raise ValueError("reviewed Ring activation was not filtered by v3")
    kept = safe_target_indices(observation, legal, kept,
                               protect_removal_targets=True)
    return legal[max(kept, key=lambda choice: scores[choice].item())]


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


def optional_upstream_activation(trajectory, forced_index: int) -> int | None:
    """Find the avoidable activation behind a forced effect-choice prompt."""
    forced = trajectory.decisions[forced_index]
    if len(forced.legal_actions) != 1:
        return None
    return matching_upstream_activation(trajectory, forced_index)


def matching_upstream_activation(trajectory, target_index: int) -> int | None:
    """Find the nearest optional activation matching a visible chain source."""
    forced = trajectory.decisions[target_index]
    if not forced.observation.chain:
        return None
    source = forced.observation.chain[-1]
    for prior_index in range(target_index - 1, max(-1, target_index - 65), -1):
        prior = trajectory.decisions[prior_index]
        if prior.observation.turn != forced.observation.turn:
            break
        if (prior.observation.acting_player == forced.observation.acting_player
                and activation_matches_chain_source(prior.selected_action, source)
                and any(action.kind == "pass" for action in prior.legal_actions)):
            return prior_index
    return None


def activation_matches_chain_source(action, source) -> bool:
    """Match a visible effect activation to its chain link when slots are known.

    An activation from hand can move to the Spell/Trap Zone before the chain
    prompt, so its action location need not equal the link's final location.
    A field activation retains its slot, which disambiguates same-name cards.
    """
    if (action.kind not in ("activate", "chain")
            or action.parameters.get("code") != source.card_code
            or action.actor != source.controller):
        return False
    location = action.parameters.get("location")
    return (location != source.location
            or action.parameters.get("sequence") is None
            or action.parameters["sequence"] == source.sequence)


def write_review_index(selected: list[dict], output: Path,
                       native_root: Path, *, comparison_label: str = "Tactical") -> Path:
    """Link player-visible label frames and separate full-information review."""
    codes = {action["parameters"].get("code")
             for item in selected for action in (
                 item["policy_action"], item["teacher_action"])}
    codes.update(item.get("visible_faceup_card") for item in selected)
    codes.update(item.get("option_source_card") for item in selected)
    names = _card_names({code for code in codes if type(code) is int and code > 0},
                        native_root)
    option_texts = _option_texts({code for code in codes if type(code) is int and code > 0},
                                 native_root)

    def action_label(action: dict) -> str:
        prompt_id = action["parameters"].get("prompt_id")
        if action["kind"] == "select_option" and type(prompt_id) is int:
            return escape(option_texts.get(prompt_id, "Select effect option"))
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
        option_code = item.get("option_source_card")
        option_note = (f"Review {names.get(option_code, f'Card {option_code}')} effect choice"
                       if option_code is not None else "")
        upstream_note = item.get("review_note")
        reason = (f"Earlier activation before review #{item['source_item_number']}"
                  + (f": {upstream_note[:160]}" if upstream_note else "")
                  if upstream_note is not None else
                  ", ".join(flag.replace("_", " ") for flag in item["audit_flags"])
                  if item["audit_flags"] else age_note
                  if age_note else option_note
                  if option_note else f"{comparison_label} suggests another play")
        choices = (f'<p><strong>Both agents played:</strong> '
                   f'{action_label(item["policy_action"])}</p>'
                  if teacher_agrees else
                   f'<p><strong>AI played:</strong> {action_label(item["policy_action"])}<br>'
                   f'<strong>{escape(comparison_label)} suggests:</strong> '
                   f'{action_label(item["teacher_action"])}</p>')
        card = (
            f'<article class="review-card" id="item-{number}" data-queue-index="{number - 1}">'
            f'<div class="card-top"><span class="badge">#{number} · '
            f'{"Flagged play" if item["audit_flags"] else "Alternative" if not teacher_agrees else "Review"}</span>'
            f'<span class="label-status" hidden>✓ Labeled</span>'
            f'<span class="note-status" hidden>✎ Noted</span>'
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
            ".label-status{color:#a8ead0;font-weight:700}"
            ".note-status{color:#ffe2a3;font-weight:700}"
            ".links{display:flex;gap:10px;flex-wrap:wrap;margin-top:14px}"
            ".links a{display:inline-block;border:1px solid #4f7980;border-radius:7px;"
            "padding:8px 10px;text-decoration:none}.links a:hover{background:#306575}"
            ".links .primary{background:#234854;color:#fff}"
            "button,input{font:inherit}button{cursor:pointer;background:#234854;color:#fff;"
            "border:1px solid #4f7980;border-radius:7px;padding:7px 10px}"
            "button:disabled{opacity:.45;cursor:default}#queue-search{width:100%;max-width:480px;"
            "padding:9px;background:#0b2430;color:#fff;border:1px solid #4f7980;"
            "border-radius:7px;margin:12px 0}"
            "#review-progress{margin:12px 0 4px;color:#a8ead0}"
            "#labeled-filter{display:inline-flex;gap:7px;align-items:center;margin:4px 0 12px}"
            ".review-card[hidden],.stage[hidden],#labeled-filter[hidden]{display:none}"
            ".stage{position:fixed;inset:0;z-index:10;background:#071925;"
            "display:grid;grid-template-rows:auto minmax(0,1fr)}"
            ".stage-bar{display:flex;align-items:center;gap:8px;flex-wrap:wrap;"
            "padding:7px 12px;background:#172731;border-bottom:1px solid #36535e}"
            ".stage-title{flex:1;min-width:180px;overflow:hidden;text-overflow:ellipsis;"
            "white-space:nowrap}#stage-frame{width:100%;height:100%;border:0}"
            "</style><section class=\"intro\"><h1>GOAT AI review queue</h1>"
            "<p>Each card opens a complete duel at one decision worth examining."
            f" Flags and {escape(comparison_label)} suggestions are prompts, not confirmed mistakes."
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
            " view with hidden cards shown; labeling is disabled there.</li>"
            "<li>If the bad play happened earlier, choose <strong>The earlier action was the mistake</strong>"
            " in Review finding and save a note. Use <strong>Review earlier activation</strong>"
            " to open its own legal-action review in the local server. The note alone"
            " does not become a training label.</li>"
            "<li>If the recorded action itself is clearly bad but no replacement is known,"
            " choose <strong>Reject the AI's recorded action</strong> and save the note."
            " This is a negative-only review for later validation and training.</li>"
            "<li>Saved choices and recorded-action rejections hide their items from the queue by default."
            " Use Show labeled items to revisit or change them; they are not deleted.</li></ol>"
            "</section><p id=\"review-progress\" aria-live=\"polite\">"
            "Offline view: choices are not saved automatically. Run"
            " <code>./start_review_viewer.sh path/to/queue.json</code>"
            " from the project folder, then use the localhost page it opens.</p>"
            "<label id=\"labeled-filter\" hidden><input id=\"show-labeled\" "
            "type=\"checkbox\">Show labeled items</label><br>"
            "<label for=\"queue-search\">Find a review item</label><br>"
            "<input id=\"queue-search\" type=\"search\" placeholder=\"Search card, action, or flag\">"
            "<h2>Flagged decisions</h2><div class=\"grid\">"
            + "".join(flagged) + "</div><h2>Other choices to compare</h2>"
            "<div class=\"grid\">" + "".join(disagreements) + "</div>"
            "<section class=\"stage\" id=\"stage\" hidden aria-label=\"Review replay\">"
            "<nav class=\"stage-bar\" aria-label=\"Review queue navigation\">"
            "<button id=\"back-to-queue\" type=\"button\">← Queue</button>"
            "<button id=\"previous-item\" type=\"button\">Previous item</button>"
            "<span id=\"item-position\"></span>"
            "<span id=\"stage-label-status\"></span>"
            "<button id=\"next-item\" type=\"button\">Next item</button>"
            "<button id=\"toggle-reveal\" type=\"button\">Reveal all cards</button>"
            "<button id=\"review-upstream\" type=\"button\" disabled>Review earlier activation</button>"
            "<button id=\"stage-bookmark\" type=\"button\" hidden>Bookmark</button>"
            "<span class=\"stage-title\" id=\"stage-title\"></span>"
            "<a id=\"open-tab\" target=\"_blank\" rel=\"noopener\">Open in new tab</a>"
            "</nav><iframe id=\"stage-frame\" title=\"GOAT AI replay viewer\"></iframe>"
            "</section><script>\"use strict\";const items=" + queue_json + ";"
            "const stage=document.getElementById('stage'),frame=document.getElementById('stage-frame');"
            "let current=-1,mode='visible',pendingLabels=false,labelSaving=false,saveFailure='';"
            "let saveWaiters=[];"
            "let bookmarks=new Set(),bookmarkMode=false;"
            "const bookmarkKey=item=>`${item.source}:${item.decision_index}`;"
            "let labels=new Map(),notes=new Map(),progressMode=false;"
            "function reviewed(item){const key=bookmarkKey(item);"
            "return labels.has(key)||notes.get(key)==='reject_recorded';}"
            "function reviewStatus(item){const key=bookmarkKey(item);"
            "return labels.has(key)?'✓ Labeled':notes.get(key)==='reject_recorded'"
            "?'✓ Rejected':'Unlabeled';}"
            "function neighbor(direction){let i=current+direction;"
            "while(i>=0&&i<items.length&&progressMode"
            "&&!document.getElementById('show-labeled').checked"
            "&&reviewed(items[i]))i+=direction;return i;}"
            "function updateNavigation(){document.getElementById('previous-item').disabled="
            "neighbor(-1)<0;document.getElementById('next-item').disabled="
            "neighbor(1)>=items.length;}"
            "function applyFilters(){const term=document.getElementById('queue-search').value.toLowerCase();"
            "const show=document.getElementById('show-labeled').checked;"
            "document.querySelectorAll('.review-card').forEach(card=>{"
            "const item=items[Number(card.dataset.queueIndex)];"
            "card.hidden=(progressMode&&!show&&reviewed(item))"
            "||!card.textContent.toLowerCase().includes(term);});}"
            "function updateProgress(){document.querySelectorAll('.review-card').forEach(card=>{"
            "const item=items[Number(card.dataset.queueIndex)];"
            "card.querySelector('.label-status').hidden=!reviewed(item);"
            "card.querySelector('.label-status').textContent=reviewStatus(item);"
            "card.querySelector('.note-status').hidden=!notes.has(bookmarkKey(item));});"
            "const reviewedCount=items.filter(reviewed).length;"
            "document.getElementById('review-progress').textContent="
            "`${reviewedCount} of ${items.length} review items reviewed · ${labels.size} choices · ${notes.size} noted · ${items.length-reviewedCount} unreviewed`;"
            "document.getElementById('labeled-filter').hidden=false;"
            "document.getElementById('stage-label-status').textContent="
            "current<0?'':reviewStatus(items[current]);"
            "document.getElementById('review-upstream').disabled=current<0||!progressMode;"
            "applyFilters();if(current>=0)updateNavigation();}"
            "async function loadProgress(){if(location.protocol!=='http:'||"
            "!['127.0.0.1','localhost'].includes(location.hostname))return;"
            "try{const response=await fetch('/api/review/progress');"
            "if(!response.ok)throw Error('Saved progress unavailable');"
            "const data=await response.json();labels=new Map(data.choices.map(choice=>"
            "[bookmarkKey(choice),choice.action_index]));"
            "notes=new Map((data.notes||[]).map(note=>[bookmarkKey(note),note.kind]));"
            "progressMode=true;updateProgress();}catch(error){"
            "document.getElementById('review-progress').textContent="
            "`${error.message}. Restart this queue with ./start_review_viewer.sh.`;}}"
            "loadProgress();"
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
            "window.addEventListener('message',event=>{if(!stage.hidden&&event.source===frame.contentWindow&&"
            "event.data?.type==='goat-ai-review-label-state')"
            "{pendingLabels=Boolean(event.data.pending);"
            "labelSaving=Boolean(event.data.saving);"
            "saveFailure=String(event.data.error||'');"
            "document.getElementById('stage-label-status').textContent=labelSaving?'Saving…':"
            "pendingLabels?saveFailure||'Unsaved choice':document.getElementById('stage-label-status').textContent;"
            "if(!labelSaving){saveWaiters.splice(0).forEach(resolve=>resolve());}"
            "if(!pendingLabels)loadProgress();}});"
            "async function mayLeave(){"
            "let child=null,state=null;"
            "try{child=frame.contentWindow;state=child?.goatAiReviewNavigationState?.();}"
            "catch(_){/* Offline file viewers may have an opaque iframe origin. */}"
            "if(state){"
            "pendingLabels=state.pending;labelSaving=state.saving;saveFailure=state.error;"
            "if(labelSaving)await state.actionSave;"
            "state=child.goatAiReviewNavigationState();"
            "pendingLabels=state.pending;labelSaving=state.saving;saveFailure=state.error;}"
            "if(labelSaving){"
            "await new Promise(resolve=>{const timeout=setTimeout(resolve,30000);"
            "saveWaiters.push(()=>{clearTimeout(timeout);resolve();});});}"
            "if(labelSaving){alert('Your choice is still saving. Keep this duel open until the save finishes.');return false;}"
            "return !pendingLabels||confirm((saveFailure?saveFailure+'. ':'')+"
            "'You have a choice or note that has not been saved. Leave this duel and discard it?');}"
            "async function openItem(i,wanted='visible'){if(i<0||i>=items.length)return;"
            "if(current>=0&&!await mayLeave())return;pendingLabels=false;labelSaving=false;"
            "current=i;mode=wanted==='reveal'&&items[i].reveal?'reveal':'visible';"
            "const url=items[i][mode];let navigated=false;"
            "try{const currentUrl=new URL(frame.src,location.href),"
            "nextUrl=new URL(url,location.href);"
            "if(currentUrl.origin===nextUrl.origin&&currentUrl.pathname===nextUrl.pathname"
            "&&currentUrl.search===nextUrl.search){"
            "const target=nextUrl.hash.match(/^#decision=(\\d+)$/);"
            "if(target)navigated=frame.contentWindow.goatAiNavigateToDecision?.(Number(target[1]))===true;"
            "}}catch(_){/* A different-origin replay requires iframe navigation. */}"
            "if(!navigated)frame.src=url;stage.hidden=false;"
            "document.getElementById('item-position').textContent=`${i+1} / ${items.length}`;"
            "document.getElementById('stage-title').textContent=items[i].title;"
            "updateBookmarks();"
            "document.getElementById('stage-label-status').textContent="
            "progressMode?reviewStatus(items[i]):'';"
            "document.getElementById('review-upstream').disabled=!progressMode;"
            "document.getElementById('open-tab').href=url;"
            "updateNavigation();"
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
            "document.getElementById('back-to-queue').onclick=async()=>{if(!await mayLeave())return;"
            "pendingLabels=false;labelSaving=false;stage.hidden=true;"
            "frame.removeAttribute('src');history.replaceState(null,'',location.pathname);"
            "document.getElementById(`item-${current+1}`)?.scrollIntoView({block:'center'});"
            "loadProgress();};"
            "document.getElementById('previous-item').onclick=()=>openItem(neighbor(-1),mode);"
            "document.getElementById('next-item').onclick=()=>openItem(neighbor(1),mode);"
            "document.getElementById('toggle-reveal').onclick=()=>openItem(current,"
            "mode==='reveal'?'visible':'reveal');"
            "document.getElementById('review-upstream').onclick=async()=>{"
            "if(current<0||!progressMode||!await mayLeave())return;"
            "const button=document.getElementById('review-upstream');button.disabled=true;"
            "try{const item=items[current];const response=await fetch('/api/review/upstream',{"
            "method:'POST',headers:{'Content-Type':'application/json'},"
            "body:JSON.stringify({source:item.source,decision_index:item.decision_index})});"
            "const data=await response.json();if(!response.ok)throw Error(data.error||"
            "'Earlier activation review unavailable');location.assign(data.url);"
            "}catch(error){alert(error.message);button.disabled=false;}};"
            "document.getElementById('queue-search').oninput=applyFilters;"
            "document.getElementById('show-labeled').onchange=()=>{applyFilters();"
            "if(current>=0)updateNavigation();};"
            "window.addEventListener('focus',loadProgress);"
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
    parser.add_argument("--comparison-checkpoint", type=Path,
                        help="compare with a second policy checkpoint instead of Tactical v14")
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--per-replay", type=int, default=2)
    parser.add_argument("--rank-by", choices=("probability", "logit"),
                        default="probability",
                        help="rank disagreements by probability or raw AI-to-Tactical score gap")
    parser.add_argument("--min-logit-margin", type=float, default=0.0,
                        help="keep only disagreements where the raw model favors its action "
                             "over Tactical by at least this score gap")
    parser.add_argument("--focus-audit-category", action="append", default=[],
                        help="keep only these visible review-flag categories; allow distinct "
                             "game contexts for the same card and action")
    parser.add_argument("--visible-faceup-card", type=int,
                        help="review decisions while this known face-up card is on the field")
    parser.add_argument("--review-option-prompts", action="store_true",
                        help="review every learner-seat multi-choice effect menu, "
                             "including choices the comparison agent agrees with")
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
    if args.review_option_prompts and args.visible_faceup_card is not None:
        parser.error("choose either option-prompt or face-up-age review")
    if len({path.resolve() for path in args.replays}) != len(args.replays):
        parser.error("duplicate replay path")
    checkpoint_hash = sha256_file(args.checkpoint)
    agent = load_policy_agent(args.checkpoint)
    model = agent.model.eval()
    comparison_hash = (sha256_file(args.comparison_checkpoint)
                       if args.comparison_checkpoint else None)
    comparison_agent = (load_policy_agent(args.comparison_checkpoint)
                        if args.comparison_checkpoint else None)
    comparison_label = "Comparison policy" if comparison_agent else "Tactical"
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
    unresolved_forced_prompts = 0
    for path in args.replays:
        source_hash = sha256_file(path)
        trajectory = read_trajectory(path)
        metadata = trajectory.skill_metadata or {}
        seat = metadata.get("demonstrator_seat")
        if (trajectory.source != "policy_evaluation" or type(seat) is not int
                or seat not in (0, 1)
                or metadata.get("policy_checkpoint_sha256") != checkpoint_hash
                or metadata.get("policy_inference_version") != POLICY_INFERENCE_VERSION
                or metadata.get("policy_feature_version") != model.feature_version):
            raise ValueError(f"{path}: expected a greedy replay from this checkpoint")
        inference = metadata.get("policy_inference")
        policy_options = recorded_policy_options(inference, card_facts)
        verified = verify_trajectory(
            trajectory, ExperimentalOcgcoreEngine(args.native_root))
        audit_trajectory_visibility(trajectory)
        if sha256_file(path) != source_hash:
            raise ValueError(f"{path}: replay changed during verification")
        comparison_choices_verified = None
        if (comparison_agent is not None
                and metadata.get("opponent_checkpoint_sha256") == comparison_hash):
            comparison_choices_verified = 0
            for index, record in enumerate(trajectory.decisions):
                if record.observation.acting_player == seat:
                    continue
                if comparison_agent.select_action(record.observation,
                                                  record.legal_actions) != record.selected_action:
                    raise ValueError(f"{path}: recorded comparison policy differs at {index}")
                comparison_choices_verified += 1
        audit_by_index: dict[int, list[str]] = {}
        upstream_by_index: dict[int, int] = {}
        for finding in review_candidates(trajectory, card_races, weak_flip_attacks,
                                         card_facts=card_facts):
            if (args.focus_audit_category
                    and finding.category in args.focus_audit_category
                    and len(trajectory.decisions[finding.decision_index].legal_actions) == 1):
                upstream = optional_upstream_activation(
                    trajectory, finding.decision_index)
                if upstream is None:
                    unresolved_forced_prompts += 1
                    continue
                audit_by_index.setdefault(upstream, []).append(finding.category)
                upstream_by_index[upstream] = finding.decision_index
                continue
            audit_by_index.setdefault(finding.decision_index, []).append(finding.category)
        disagreements = 0
        policy_choices = 0
        replay_agent = load_policy_agent(args.checkpoint, **policy_options)
        for index, record in enumerate(trajectory.decisions):
            if record.observation.acting_player != seat:
                continue
            policy_choices += 1
            legal = record.legal_actions
            if replay_agent.select_action(record.observation, legal) != record.selected_action:
                raise ValueError(f"{path}: greedy policy choice differs at {index}")
            if len(legal) == 1:
                continue
            if args.review_option_prompts and not all(
                    action.kind == "select_option" for action in legal):
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
            audit_flags = audit_by_index.get(index, [])
            ring_guard_review = "ring_idle_only_own_faceup" in audit_flags
            alternative = (next(action for action in legal if action.kind == "pass")
                           if index in upstream_by_index else
                           visible_ring_guard_alternative(record.observation, legal, logits)
                           if ring_guard_review else
                           comparison_agent.select_action(record.observation, legal)
                           if comparison_agent else
                           fresh_teacher().select_action(record.observation, legal))
            if alternative not in legal:
                raise ValueError(f"{path}: teacher choice is illegal at {index}")
            disagreed = alternative != record.selected_action
            if not disagreed and not audit_flags and age is None \
                    and not args.review_option_prompts:
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
                **({"alternative_source": "visible_ring_guard_v3"}
                   if ring_guard_review else {}),
                **({"upstream_target_decision_index": upstream_by_index[index]}
                   if index in upstream_by_index else {}),
                **({"option_source_card": record.observation.chain[-1].card_code}
                   if args.review_option_prompts and record.observation.chain else {}),
                **({"visible_faceup_card": args.visible_faceup_card,
                    "visible_faceup_turns": age} if age is not None else {}),
                "_fingerprint": (("option", str(path.resolve()), index)
                                 if args.review_option_prompts else
                                 ("audit", tuple(audit_flags),
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
                              "policy_inference": inference,
                              "verified_decisions": verified,
                              "policy_choices": policy_choices,
                              "disagreements": disagreements,
                              "comparison_choices_verified": comparison_choices_verified})
    if args.focus_audit_category:
        wanted = set(args.focus_audit_category)
        candidates = [candidate for candidate in candidates
                      if wanted.intersection(candidate["audit_flags"])]
        if not candidates:
            raise ValueError("no verified decisions matched the requested audit categories")
    selected = select_diverse_candidates(
        candidates, args.limit, args.per_replay, rank_by=args.rank_by,
        dedupe_fingerprints=not args.focus_audit_category)
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
              "teacher": ("visible_ring_guard_v3"
                          if selected and all(item.get("alternative_source")
                                              == "visible_ring_guard_v3" for item in selected)
                          else "mixed_visible_guard_and_policy"
                          if any(item.get("alternative_source")
                                 == "visible_ring_guard_v3" for item in selected)
                          else "PolicyAgent" if comparison_agent
                          else "TacticalHeuristicAgent_v14"),
              **({"comparison_checkpoint_sha256": comparison_hash}
                 if comparison_hash else {}),
              "rank_by": args.rank_by,
              "min_logit_margin": args.min_logit_margin,
              "selection": ("focused_visible_audit_distinct_game_contexts"
                            if args.focus_audit_category else
                            "learner_select_option_prompts"
                            if args.review_option_prompts else
                            "public_faceup_age_then_model_margin_distinct_prompt"
                            if args.visible_faceup_card is not None else
                            "visible_audit_then_model_margin_distinct_prompt_max_per_replay"),
              **({"review_option_prompts": True} if args.review_option_prompts else {}),
              **({"focus_audit_categories": sorted(set(args.focus_audit_category))}
                 if args.focus_audit_category else {}),
              **({"visible_faceup_card": args.visible_faceup_card,
                  "min_faceup_turns": args.min_faceup_turns}
                 if args.visible_faceup_card is not None else {}),
              "replays": replay_report,
              "candidate_count": len(candidates),
              **({"unresolved_forced_prompts": unresolved_forced_prompts}
                 if args.focus_audit_category else {}),
              "selected": selected}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    if args.render_viewers:
        write_review_index(selected, args.output, args.native_root,
                           comparison_label=("Legal alternative"
                                             if args.focus_audit_category else
                                             comparison_label))
    print(json.dumps({"output": str(args.output), "replays": len(replay_report),
                      "candidate_count": len(candidates), "selected": len(selected),
                      "verified_decisions": sum(item["verified_decisions"]
                                                for item in replay_report)}))


if __name__ == "__main__":
    main()

/* Original synthesized duel effects. No third-party game audio is bundled. */
(function () {
  const storageKey = "goat-ai-duel-muted";
  let muted = false;
  try { muted = localStorage.getItem(storageKey) === "1"; } catch (_) { /* file URLs */ }
  let context = null;
  let lastSound = -Infinity;
  const patterns = {
    summon: [[330, 0, .10, "triangle", 460], [495, .08, .17, "triangle", 620]],
    activate: [[780, 0, .09, "sine", 980], [1050, .07, .16, "triangle", 680]],
    chain: [[620, 0, .08, "square", 760], [810, .08, .09, "square", 950]],
    move: [[260, 0, .11, "triangle", 170]],
    draw: [[410, 0, .07, "sine", 730]],
    phase: [[520, 0, .09, "sine", 680], [780, .08, .12, "sine", 880]],
    attack: [[170, 0, .17, "sawtooth", 90], [85, .10, .13, "triangle", 55]],
    damage: [[230, 0, .11, "sawtooth", 120], [130, .09, .18, "triangle", 65]],
    heal: [[470, 0, .10, "sine", 650], [690, .09, .15, "sine", 850]],
    flip: [[380, 0, .10, "triangle", 570], [610, .09, .11, "sine", 760]],
    end: [[520, 0, .10, "sine", 390], [390, .09, .17, "sine", 260]],
  };
  function updateButtons() {
    document.querySelectorAll("[data-duel-mute]").forEach(button => {
      button.textContent = muted ? "🔇 Sound off" : "🔊 Sound on";
      button.setAttribute("aria-pressed", String(!muted));
      button.title = muted ? "Unmute duel sounds" : "Mute duel sounds";
    });
  }
  function play(kind) {
    if (muted || !patterns[kind]) return;
    const AudioContext = window.AudioContext || window.webkitAudioContext;
    if (!AudioContext) return;
    try {
      context ||= new AudioContext();
      if (context.state === "suspended") context.resume();
      const now = context.currentTime;
      if (now - lastSound < .035) return;
      lastSound = now;
      for (const [start, delay, length, wave, finish] of patterns[kind]) {
        const oscillator = context.createOscillator();
        const volume = context.createGain();
        const at = now + delay;
        oscillator.type = wave;
        oscillator.frequency.setValueAtTime(start, at);
        oscillator.frequency.exponentialRampToValueAtTime(finish, at + length);
        volume.gain.setValueAtTime(.0001, at);
        volume.gain.exponentialRampToValueAtTime(.055, at + .012);
        volume.gain.exponentialRampToValueAtTime(.0001, at + length);
        oscillator.connect(volume).connect(context.destination);
        oscillator.start(at);
        oscillator.stop(at + length + .01);
      }
    } catch (_) { /* An unsupported or blocked audio device must not stop play. */ }
  }
  function toggle() {
    muted = !muted;
    try { localStorage.setItem(storageKey, muted ? "1" : "0"); } catch (_) { /* file URLs */ }
    updateButtons();
    if (!muted) play("phase");
  }
  function action(kind) {
    if (["normal_summon", "special_summon", "set_monster"].includes(kind)) return "summon";
    if (kind === "flip_summon") return "flip";
    if (["activate", "yes"].includes(kind)) return "activate";
    if (kind === "chain") return "chain";
    if (kind === "attack") return "attack";
    if (["set_spell_trap", "place", "tribute", "change_position"].includes(kind)) return "move";
    if (["battle_phase", "main2", "end_phase"].includes(kind)) return "phase";
    return null;
  }
  window.DuelAudio = {play, toggle, action, get muted() { return muted; }};
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", updateButtons);
  else updateButtons();
})();

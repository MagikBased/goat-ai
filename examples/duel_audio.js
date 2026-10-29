/* Original synthesized duel effects. No third-party game audio is bundled. */
(function () {
  const storageKey = "goat-ai-duel-muted";
  let muted = false;
  try { muted = localStorage.getItem(storageKey) === "1"; } catch (_) { /* file URLs */ }
  let context = null;
  let lastSound = -Infinity;
  const unavailable = new Set();
  const files = {summon:"summon.wav", special:"specialsummon.wav", move:"set.wav",
    activate:"activate.wav", chain:"activate.wav", attack:"attack.wav",
    damage:"damage.wav", heal:"gainlp.wav", phase:"phase.wav", end:"phase.wav",
    flip:"flip.wav", draw:"draw.wav"};
  const patterns = {
    summon: [[330, 0, .10, "triangle", 460], [495, .08, .17, "triangle", 620]],
    special: [[300, 0, .10, "triangle", 600], [640, .08, .18, "sine", 940]],
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
  function synth(kind) {
    const AudioContext = window.AudioContext || window.webkitAudioContext;
    if (!AudioContext) return;
    try {
      context ||= new AudioContext();
      if (context.state === "suspended") context.resume();
      const now = context.currentTime;
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
  function play(kind) {
    if (muted || !patterns[kind]) return;
    const now = performance.now();
    if (now - lastSound < 35) return;
    lastSound = now;
    const file = files[kind];
    const base = /^https?:$/.test(location.protocol) ? "/local-duel-sounds"
      : location.protocol === "file:" ? window.GOAT_LOCAL_SOUND_BASE : null;
    if (base && !base.includes("__") && file && !unavailable.has(file)) {
      try {
        const clip = new Audio(`${base}/${file}`);
        let failed = false;
        const fallback = () => {
          if (failed) return;
          failed = true; unavailable.add(file); if (!muted) synth(kind);
        };
        clip.volume = .45;
        clip.onerror = fallback;
        clip.play().catch(fallback);
        return;
      } catch (_) { unavailable.add(file); }
    }
    synth(kind);
  }
  function toggle() {
    muted = !muted;
    try { localStorage.setItem(storageKey, muted ? "1" : "0"); } catch (_) { /* file URLs */ }
    updateButtons();
    if (!muted) play("phase");
  }
  function action(kind) {
    if (kind === "normal_summon") return "summon";
    if (kind === "special_summon") return "special";
    if (kind === "flip_summon") return "flip";
    if (["activate", "yes"].includes(kind)) return "activate";
    if (kind === "chain") return "chain";
    if (kind === "attack") return "attack";
    if (["set_monster", "set_spell_trap", "place", "tribute", "change_position"].includes(kind)) return "move";
    if (["battle_phase", "main2", "end_phase"].includes(kind)) return "phase";
    return null;
  }
  window.DuelAudio = {play, toggle, action, get muted() { return muted; }};
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", updateButtons);
  else updateButtons();
})();

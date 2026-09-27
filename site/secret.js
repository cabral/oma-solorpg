// ↑ ↑ ↓ ↓ ← → ← → B A
//
// A door that wasn't there. A hidden level for oma-solorpg's page, played in a copy of the
// Book: a hero drawn by the engine, a d20 that tumbles and lands, a torch that burns down,
// a hidden countdown that reaches you as omens, death rolls, a gravestone with your last
// words, and thirty candles, one for each life. The candles and the names of the fallen
// are kept in this browser, so the hall remembers who went down before you.
//
// Every word of it is this page's own. No rules from any book: the numbers are made up.
(function () {
  "use strict";

  var CSS = [
    ".sl{position:fixed;inset:0;z-index:80;background:var(--bg);color:var(--text);display:flex;flex-direction:column;overflow:hidden;animation:sl-in .6s ease-out}",
    "@keyframes sl-in{from{opacity:0;transform:scale(1.02)}}",
    ".sl.out{animation:sl-out .5s ease-in forwards}@keyframes sl-out{to{opacity:0;transform:scale(.98)}}",
    ".sl-page{flex:1;display:grid;grid-template-columns:minmax(0,300px) minmax(0,1fr);gap:clamp(16px,3vw,48px);padding:clamp(14px,2.4vw,34px) clamp(14px,3vw,48px) 0;min-height:0;max-width:1320px;width:100%;margin:0 auto}",
    ".sl-side{overflow:auto;padding-bottom:20px;font-size:12.5px}",
    ".sl-side .portrait{font-size:12px;margin-bottom:10px}",
    ".sl-name{font-family:var(--serif);font-size:26px;line-height:1.1;margin:0 0 .15em}",
    ".sl-info,.sl-cond-none{color:var(--dim)}",
    ".sl-side .meter{margin:.2em 0}",
    ".sl-conds{color:var(--urgent);min-height:1.4em;margin:.4em 0}",
    ".sl-dark{color:var(--urgent);font-family:var(--serif);font-style:italic}",
    ".sl-torch{color:var(--gold)}",
    ".sl-candles{margin:.9em 0;color:var(--dim)}.sl-candles b{color:var(--gold);font-weight:500}",
    ".sl-side h4{font-weight:400;color:var(--dim);letter-spacing:.2em;font-size:11.5px;margin:18px 0 6px}",
    ".sl-route{list-style:none;margin:0;padding:0;color:var(--dim)}.sl-route li{padding-left:0}.sl-route li+li:before{content:'|';display:block;color:var(--faint)}",
    ".sl-route .here{color:var(--text)}",
    ".sl-story{display:flex;flex-direction:column;min-height:0}",
    ".sl-top{display:flex;justify-content:space-between;align-items:flex-start;gap:14px}",
    ".sl-scene{font-family:var(--serif);font-weight:500;font-variant-caps:small-caps;letter-spacing:.04em;font-size:clamp(26px,3vw,36px);line-height:1.1;margin:0}",
    ".sl-where{color:var(--dim);font-size:12px;margin:.2em 0 0}",
    ".sl-links{display:flex;gap:14px;font-size:12px;white-space:nowrap}.sl-links button{background:none;border:0;color:var(--dim);cursor:pointer;padding:0}.sl-links button:hover{color:var(--accent)}",
    ".sl-fight{border:1px solid var(--faint);background:var(--surface);padding:10px 14px;margin:14px 0 0;font-size:12px}",
    ".sl-fight .row{display:flex;align-items:center;justify-content:space-around;gap:10px;flex-wrap:wrap}",
    ".sl-fight pre{margin:0;line-height:1.05;font-size:12px}",
    ".sl-fight .who{font-weight:700;margin-top:4px}.sl-fight .blow{color:var(--urgent);margin-top:6px}.sl-fight .blow.good{color:var(--accent)}",
    ".sl-fight .arrow{color:var(--dim)}",
    ".sl-log{flex:1;overflow:auto;padding:18px 4px 18px 0;scroll-behavior:smooth}",
    ".sl-log>*{animation:sl-beat .5s ease-out}@keyframes sl-beat{from{opacity:0;transform:translateY(6px)}}",
    ".sl-gm{font-family:var(--serif);font-size:clamp(17px,1.5vw,20px);line-height:1.6;margin:0 0 .9em;max-width:40em}",
    ".sl-gm em{color:var(--text);font-style:italic}",
    ".sl-gm.drop:first-letter{float:left;color:var(--gold);font-size:3.3em;line-height:.86;padding:.07em .1em 0 0}",
    ".sl-player{font-family:var(--serif);font-style:italic;color:var(--dim);border-left:2px solid var(--faint);padding-left:14px;margin:.2em 0 1em;font-size:18px}",
    ".sl-rolled{display:flex;gap:8px;align-items:baseline;margin:0 0 .5em;font-size:13px}.sl-rolled b{font-weight:600}.sl-rolled .die{color:var(--accent)}.sl-rolled.fail .die,.sl-rolled.demon .die{color:var(--urgent)}.sl-rolled.dragon .die{color:var(--gold)}.sl-rolled .dim{font-size:12px}",
    ".sl-voice{border-left:3px solid var(--accent);padding:2px 0 2px 12px;margin:0 0 1em}.sl-voice .v{color:var(--accent);letter-spacing:.12em;font-size:12px}.sl-voice p{margin:0;font-family:var(--serif);font-style:italic;font-size:18px}",
    ".sl-omen{text-align:center;color:var(--dim);font-family:var(--serif);font-style:italic;margin:.4em 0 1.2em;animation:sl-omen 2.4s ease-out}@keyframes sl-omen{0%{opacity:0;letter-spacing:.3em;color:var(--accent)}}",
    ".sl-note{color:var(--dim);font-size:12.5px;margin:0 0 .6em}.sl-note.hurt{color:var(--urgent)}.sl-note.good{color:var(--accent)}.sl-note.gold{color:var(--gold)}",
    ".sl-rule{display:flex;align-items:center;justify-content:center;gap:10px;margin:1.6em 0 .6em;color:var(--gold);font-size:10px}.sl-rule:before,.sl-rule:after{content:'';width:60px;height:1px;background:var(--faint)}",
    ".sl-rule-title{text-align:center;font-family:var(--serif);font-variant-caps:small-caps;letter-spacing:.08em;font-size:22px;margin:0 0 .8em}",
    ".sl-choices{display:grid;gap:6px;padding:12px 0 18px;border-top:1px solid var(--faint)}",
    ".sl-choice{display:flex;gap:10px;align-items:baseline;text-align:left;background:none;border:1px solid var(--faint);padding:9px 14px;cursor:pointer;font-family:var(--serif);font-size:18px;color:var(--text)}",
    ".sl-choice:hover,.sl-choice:focus-visible{border-color:var(--accent)}",
    ".sl-choice kbd{font-family:var(--mono);font-size:11px;color:var(--dim);min-width:1.2em}",
    ".sl-choice .sk{margin-left:auto;font-family:var(--mono);font-size:11.5px;color:var(--dim);white-space:nowrap}",
    ".sl-choice.danger{border-color:color-mix(in srgb,var(--urgent) 50%,transparent)}.sl-choice.danger:hover{border-color:var(--urgent)}",
    ".sl-choice.primary{border-color:var(--accent)}",
    ".sl-words{display:flex;gap:8px}.sl-words input{flex:1;background:var(--bg);border:1px solid var(--accent);color:var(--text);font:italic 18px var(--serif);padding:9px 12px}",
    ".sl-heroes{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:10px;margin:12px 0}",
    ".sl-hero{background:none;border:2px solid var(--idle);padding:12px;cursor:pointer;text-align:left;color:var(--text);display:grid;gap:4px}",
    ".sl-hero:hover,.sl-hero:focus-visible{border-color:var(--accent)}",
    ".sl-hero pre{margin:0 auto 6px;font-size:9px;line-height:1.02}",
    ".sl-hero b{font-family:var(--serif);font-size:21px;font-weight:500}.sl-hero span{color:var(--dim);font-size:11.5px}",
    ".sl-overlay{position:absolute;inset:0;display:grid;place-items:center;background:color-mix(in srgb,var(--bg) 55%,transparent);opacity:0;pointer-events:none;transition:opacity .35s;z-index:3}",
    ".sl-overlay.on{opacity:1;pointer-events:auto}",
    ".sl-card-inner{text-align:center;width:min(900px,90vw)}",
    ".sl-card-inner .rule span{width:0;transition:width 1.3s cubic-bezier(.2,.7,.2,1)}.sl-overlay.on .rule span{width:min(24vw,220px)}.sl-overlay.on .rule i{opacity:1}",
    ".sl-card-title{font-family:var(--serif);font-variant-caps:small-caps;font-weight:500;font-size:clamp(34px,5.5vw,64px);letter-spacing:.04em;margin:.3em 0 .15em;display:grid}",
    ".sl-card-title>*{grid-area:1/1}",
    ".sl-card-sub{font-family:var(--serif);font-style:italic;color:var(--dim);font-size:20px;margin:0 0 .6em}",
    ".sl-dicebox{position:relative}",
    ".sl-stone{white-space:pre;font-family:var(--mono);line-height:1.02;font-size:clamp(9px,1.25vw,13px);margin:0;text-align:left;position:relative;animation:sl-rise 1.6s cubic-bezier(.2,.8,.3,1)}",
    "@keyframes sl-rise{from{transform:translateY(40vh);opacity:0}}",
    ".sl-stone .st{color:var(--dim)}.sl-stone .cv{color:color-mix(in srgb,var(--text) 55%,var(--dim))}.sl-stone .nm{color:var(--text)}",
    ".sl-end{background:color-mix(in srgb,var(--bg) 94%,transparent);overflow:auto}",
    ".sl-epi{text-align:center;font-family:var(--serif);position:relative}.sl-epi .fell{font-size:20px;color:var(--dim);margin:.6em 0 .2em}.sl-epi .last{font-size:22px;font-style:italic;margin:0 0 .8em}",
    ".sl-epi .acts{justify-content:center}",
    ".sl-ash{position:absolute;inset:0;pointer-events:none;overflow:hidden}.sl-ash i{position:absolute;top:-10px;width:3px;height:3px;background:var(--dim);border-radius:50%;opacity:.6;animation:sl-ash linear infinite}",
    "@keyframes sl-ash{to{transform:translate(var(--dx),110vh)}}",
    ".sl-dragon{color:var(--gold);white-space:pre;line-height:1.05;font-size:12px;margin:0 0 1em;text-shadow:0 0 12px color-mix(in srgb,var(--gold) 30%,transparent)}",
    "@media (max-width:760px){.sl-page{grid-template-columns:1fr;overflow:auto}.sl-side{display:grid;grid-template-columns:auto 1fr;gap:4px 14px;align-items:start;overflow:visible;padding-bottom:0}.sl-side .portrait{font-size:7.5px;grid-row:span 6}.sl-side h4,.sl-route{display:none}.sl-story{min-height:70vh}.sl-log{overflow:visible}}"
  ].join("\n");

  // Heroes: faces from the engine (art.js); the numbers are this game's own.
  var HEROES = [
    { id: "ragna", name: "Ragna", info: "Adult · Dwarf · Fighter", hp: 14, wp: 11, con: 14, weapon: "broadsword", dmg: [1, 8, 4],
      skills: { fight: ["Swords", 14], notice: ["Awareness", 10], sneak: ["Sneaking", 5], lore: ["Myths & Legends", 5], talk: ["Persuasion", 8], evade: ["Evade", 10] } },
    { id: "maren", name: "Maren", info: "Old · Human · Mage", hp: 9, wp: 18, con: 10, weapon: "a fireball", dmg: [2, 6, 0],
      skills: { fight: ["Elementalism", 15], notice: ["Awareness", 12], sneak: ["Sneaking", 8], lore: ["Myths & Legends", 15], talk: ["Persuasion", 12], evade: ["Evade", 8] } },
    { id: "elowen", name: "Elowen", info: "Young · Elf · Hunter", hp: 11, wp: 13, con: 11, weapon: "longbow", dmg: [1, 12, 0],
      skills: { fight: ["Bows", 15], notice: ["Awareness", 14], sneak: ["Sneaking", 13], lore: ["Myths & Legends", 9], talk: ["Persuasion", 7], evade: ["Evade", 12] } },
    { id: "varg", name: "Varg", info: "Adult · Wolfkin · Knight", hp: 15, wp: 10, con: 15, weapon: "longsword", dmg: [1, 10, 4],
      skills: { fight: ["Swords", 15], notice: ["Awareness", 12], sneak: ["Sneaking", 8], lore: ["Myths & Legends", 7], talk: ["Persuasion", 10], evade: ["Evade", 9] } },
    { id: "quillon", name: "Quillon", info: "Adult · Mallard · Thief", hp: 10, wp: 10, con: 11, weapon: "knife", dmg: [1, 8, 0],
      skills: { fight: ["Knives", 12], notice: ["Awareness", 11], sneak: ["Sneaking", 15], lore: ["Myths & Legends", 6], talk: ["Persuasion", 9], evade: ["Evade", 13] } },
    { id: "bramble", name: "Bramble", info: "Young · Halfling · Bard", hp: 9, wp: 13, con: 10, weapon: "a lute to the head", dmg: [1, 6, 0],
      skills: { fight: ["Knives", 9], notice: ["Awareness", 10], sneak: ["Sneaking", 13], lore: ["Myths & Legends", 13], talk: ["Performance", 15], evade: ["Evade", 13] } }
  ];
  var CONDITIONS = ["exhausted", "sickly", "dazed", "angry", "scared", "disheartened"];
  var MIMIC = [
    "   _________",
    "  /\\/\\/\\/\\/\\/\\",
    " |  O     O  |",
    " |\\/\\/\\/\\/\\/\\|",
    " |_____◆_____|"
  ];
  var DRAGON = [
    "                  __/\\__        zZ",
    "     ___......___/ -  - \\     z",
    "  .-'  /\\  /\\  /\\ \\  ^^ /__",
    " <  .-'  ''  ''  ''\\____/  '-.___",
    "  '-'  $  $$   $$$  $$  $$$  $   '~~",
    "   $$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$"
  ];
  var DRAGON_AWAKE = [
    "    /\\___/\\   ~",
    "   / (O) (O)\\ ~ ~",
    "  <  \\_vvv_/ >===",
    "    \\/\\/\\/\\/"
  ];
  var NOISE = "░▒▓█/\\|<>*+#%&@$~=-_";

  var C, root, S, token = 0;
  var STOP = { stop: true };

  function $(s, r) { return (r || root).querySelector(s); }
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function md(s) { return esc(s).replace(/\*([^*]+)\*/g, "<em>$1</em>"); }
  function d(n, sides) { var t = 0; for (var i = 0; i < n; i++) t += 1 + Math.floor(Math.random() * sides); return t; }
  function alive(t) { if (t !== token) throw STOP; }
  function sleep(ms) { var t = token; return new Promise(function (r) { setTimeout(r, C.reduced ? Math.min(ms, 60) : ms); }).then(function () { alive(t); }); }
  function load(key, fallback) { var v = C.store.get(key); if (v === null) return fallback; try { return JSON.parse(v); } catch (e) { return fallback; } }
  function save(key, value) { C.store.set(key, JSON.stringify(value)); }

  // Opening and closing the Book ------------------------------------------------------

  function open(context) {
    C = context;
    if (document.documentElement.classList.contains("secret-open")) return;
    document.documentElement.classList.add("secret-open");
    if (!document.getElementById("sl-style")) {
      var style = document.createElement("style");
      style.id = "sl-style";
      style.textContent = CSS;
      document.head.appendChild(style);
    }
    var ws = document.querySelector(".workspaces");
    if (ws && !ws.querySelector(".secret")) {
      var a = document.createElement("a");
      a.className = "secret";
      a.href = "#";
      a.textContent = "B·A";
      a.title = "The door that wasn't there";
      a.addEventListener("click", function (e) { e.preventDefault(); });
      ws.appendChild(a);
    }
    root = document.createElement("div");
    root.className = "sl";
    root.setAttribute("role", "dialog");
    root.setAttribute("aria-modal", "true");
    root.setAttribute("aria-label", "The Door That Wasn't There, a hidden adventure");
    root.innerHTML =
      '<div class="sl-page">' +
      '  <aside class="sl-side">' +
      '    <pre class="portrait sl-face" aria-hidden="true"></pre>' +
      '    <p class="sl-name"></p><p class="sl-info"></p>' +
      '    <p class="meter"><span class="dim">HP</span> <span class="bar-blocks sl-hp"></span> <span class="num sl-hpn"></span></p>' +
      '    <p class="meter"><span class="dim">WP</span> <span class="bar-blocks sl-wp"></span> <span class="num sl-wpn"></span></p>' +
      '    <p class="sl-conds"></p><p class="sl-torch"></p>' +
      '    <p class="sl-candles"></p>' +
      '    <h4>THE WAY HERE</h4><ol class="sl-route"></ol>' +
      '  </aside>' +
      '  <section class="sl-story">' +
      '    <header class="sl-top"><div><h2 class="sl-scene">A Hidden Level</h2><p class="sl-where"></p></div>' +
      '      <nav class="sl-links"><button type="button" class="sl-close">close the Book</button></nav></header>' +
      '    <div class="sl-fight" hidden></div>' +
      '    <div class="sl-log" aria-live="polite"></div>' +
      '    <div class="sl-choices"></div>' +
      '  </section>' +
      '</div>' +
      '<div class="sl-overlay sl-card"><div class="sl-card-inner">' +
      '  <div class="rule" aria-hidden="true"><span></span><i>◆</i><span></span></div>' +
      '  <p class="sl-card-title"><span class="noise"></span><span class="final"></span></p><p class="sl-card-sub"></p>' +
      '  <div class="rule" aria-hidden="true"><span></span><i>◆</i><span></span></div></div></div>' +
      '<div class="sl-overlay sl-dice"><div class="sl-dicebox"><div class="dice-card"><p class="dice-label"></p><div class="dice-row"></div>' +
      '  <p class="dice-need"></p><p class="verdict">&nbsp;</p><span class="ring"></span></div><div class="sparks"></div></div></div>' +
      '<div class="sl-overlay sl-end"></div>';
    document.body.appendChild(root);
    $(".sl-close").addEventListener("click", close);
    root.addEventListener("keydown", onKey);
    document.addEventListener("keydown", cheat);
    newGame();
  }

  function close() {
    token += 1;
    C.FX.run("restore", true);
    document.removeEventListener("keydown", cheat);
    root.classList.add("out");
    var gone = root;
    setTimeout(function () {
      gone.remove();
      document.documentElement.classList.remove("secret-open");
      var a = document.querySelector(".workspaces .secret");
      if (a) a.remove();
    }, 480);
  }

  function onKey(e) {
    if (e.key === "Escape") { e.preventDefault(); close(); return; }
    if (/INPUT|TEXTAREA/.test(e.target.tagName)) return;
    var n = parseInt(e.key, 10);
    if (n >= 1 && n <= 9) {
      var b = root.querySelectorAll(".sl-choices .sl-choice, .sl-heroes .sl-hero")[n - 1];
      if (b) { e.preventDefault(); b.click(); }
    }
  }

  // The old code, entered again inside: the candles relight.
  var cheatAt = 0, CODE = ["arrowup", "arrowup", "arrowdown", "arrowdown", "arrowleft", "arrowright", "arrowleft", "arrowright", "b", "a"];
  function cheat(e) {
    var k = (e.key || "").toLowerCase();
    if (k === CODE[cheatAt]) {
      cheatAt += 1;
      if (cheatAt === CODE.length) {
        cheatAt = 0;
        save("oma-secret-lives", 30);
        if (S) { S.lives = 30; side(); }
        C.Sound.play("chime");
        C.toast("30 lives", "Every candle in the hall lights at once. The old code still works.", "gold");
      }
    } else cheatAt = k === CODE[0] ? 1 : 0;
  }

  // The page ------------------------------------------------------------------------

  function side() {
    if (!S.hero) return;
    var h = S.hero;
    C.drawFace($(".sl-face"), h.id, mood(), false);
    $(".sl-name").textContent = h.name;
    $(".sl-info").textContent = h.info;
    meter($(".sl-hp"), S.hp, h.hp); $(".sl-hpn").textContent = S.hp + "/" + h.hp;
    meter($(".sl-wp"), S.wp, h.wp); $(".sl-wpn").textContent = S.wp + "/" + h.wp;
    $(".sl-conds").innerHTML = S.dying ? "dying · " + S.dying.ok + " saved, " + S.dying.bad + " failed" : S.conds.length ? esc(S.conds.join(" · ")) : "";
    $(".sl-torch").innerHTML = S.torch > 0 ? "torch " + "▮".repeat(S.torch) + '<span class="dim">' + "▯".repeat(4 - S.torch) + "</span>" : S.dark ? '<span class="sl-dark">It is dark here.</span>' : '<span class="dim">no light burning</span>';
    $(".sl-candles").innerHTML = "candles in the hall: <b>" + S.lives + "</b> of 30";
    $(".sl-route").innerHTML = S.route.map(function (r, i) { return '<li class="' + (i === S.route.length - 1 ? "here" : "") + '">' + (i === S.route.length - 1 ? "◉ " : "○ ") + esc(r) + "</li>"; }).join("");
  }
  function meter(el, v, max) {
    var cells = 14, f = Math.max(0, Math.min(cells, Math.round(cells * v / Math.max(1, max))));
    el.classList.toggle("low", v * 4 <= max);
    el.innerHTML = "█".repeat(f) + '<span class="empty">' + "░".repeat(cells - f) + "</span>";
  }
  function mood() {
    if (S.dead) return "dead";
    if (S.dying) return "dying";
    if (S.conds.length) return S.conds[S.conds.length - 1];
    if (S.triumph) return "triumph";
    return S.hp * 4 <= S.hero.hp ? "hurt" : "calm";
  }
  function flickerFace() { C.drawFace($(".sl-face"), S.hero.id, mood(), true); }

  function add(html, cls) {
    var log = $(".sl-log"), el = document.createElement("div");
    el.className = cls || "";
    el.innerHTML = html;
    log.appendChild(el);
    log.scrollTop = log.scrollHeight;
    return el;
  }
  function note(text, cls) { add(esc(text), "sl-note " + (cls || "")); }

  // The GM's words stream in; its first words in a scene get the drop cap.
  async function gm(text) {
    var t = token;
    C.Sound.play("page");
    var paras = text.split("\n\n");
    for (var p = 0; p < paras.length; p++) {
      var el = add("", "sl-gm" + (S.fresh ? " drop" : ""));
      S.fresh = false;
      var words = paras[p].split(" "), shown = "";
      for (var i = 0; i < words.length; i++) {
        shown += (i ? " " : "") + words[i];
        el.innerHTML = md(shown);
        $(".sl-log").scrollTop = 1e9;
        if (!C.reduced) await new Promise(function (r) { setTimeout(r, 22 + Math.random() * 34); });
        alive(t);
      }
      await sleep(260);
    }
  }
  function player(text) { add(esc(text), "sl-player"); }
  function omen(text) { C.Sound.play("omen"); C.FX.run("omen"); add("~ " + esc(text) + " ~", "sl-omen"); }

  function choose(options) {
    var t = token;
    options = options.filter(Boolean);
    var box = $(".sl-choices");
    box.innerHTML = "";
    return new Promise(function (resolve) {
      options.forEach(function (o, i) {
        var b = document.createElement("button");
        b.type = "button";
        b.className = "sl-choice" + (o.danger ? " danger" : "") + (o.primary ? " primary" : "");
        b.innerHTML = "<kbd>" + (i + 1) + "</kbd><span>" + esc(o.text) + "</span>" + (o.skill ? '<span class="sk">' + esc(o.skill) + "</span>" : "");
        b.addEventListener("click", function () {
          if (t !== token) return;
          box.innerHTML = "";
          if (o.say !== false) player(o.say || o.text);
          resolve(o.id);
        });
        box.appendChild(b);
      });
      var first = box.querySelector("button");
      if (first) first.focus({ preventScroll: true });
    });
  }

  // A title card: the scene's name decrypting out of noise.
  async function enter(title, sub) {
    var t = token;
    S.fresh = true;
    S.route.push(title);
    S.scene = title;
    S.time += S.route.length > 1 ? 15 : 0;
    if (S.torch > 0 && S.route.length > 1) {
      S.torch -= 1;
      if (!S.torch) { S.dark = true; note("Your torch gutters and goes out.", "hurt"); }
    }
    $(".sl-scene").textContent = title;
    $(".sl-where").textContent = "A hidden level · Day 1, " + String(Math.floor(S.time / 60)).padStart(2, "0") + ":" + String(S.time % 60).padStart(2, "0");
    side();
    add('<div class="sl-rule">◆</div><p class="sl-rule-title">' + esc(title) + "</p>");
    var card = $(".sl-card"), noise = $(".sl-card .noise"), fin = $(".sl-card .final");
    $(".sl-card-sub").textContent = sub || "The Door That Wasn't There";
    fin.textContent = title;
    fin.style.opacity = 0;
    noise.style.opacity = 1;
    noise.style.cssText = "font-family:var(--mono);font-size:.6em;color:var(--accent);letter-spacing:.12em;align-self:center;transition:opacity .45s";
    card.classList.add("on");
    C.Sound.play("scene");
    var shown = 0, still = 0;
    while (shown < title.length) {
      // About every other tick a letter settles, and never fewer than one in three.
      if (Math.random() < 0.55 || ++still >= 3) { shown += 1; still = 0; }
      var out = "";
      for (var i = 0; i < title.length; i++) out += i < shown || title[i] === " " ? title[i] : NOISE[Math.floor(Math.random() * NOISE.length)];
      noise.textContent = out;
      await new Promise(function (r) { setTimeout(r, C.reduced ? 1 : 38); });
      alive(t);
    }
    noise.style.opacity = 0;
    fin.style.transition = "opacity .6s";
    fin.style.opacity = 1;
    await sleep(1500);
    card.classList.remove("on");
    await sleep(400);
  }

  // The dice moment -------------------------------------------------------------------

  async function moment(label, target, faces, result, outcome) {
    var t = token;
    var box = $(".sl-dice"), card = $(".sl-dice .dice-card"), row = $(".sl-dice .dice-row"), verdict = $(".sl-dice .verdict"), ring = $(".sl-dice .ring");
    card.className = "dice-card";
    card.style.removeProperty("--verdict");
    verdict.className = "verdict";
    verdict.innerHTML = "&nbsp;";
    $(".sl-dice .dice-label").textContent = label.toUpperCase();
    $(".sl-dice .dice-need").textContent = target ? "needs " + target + " or less" : "";
    function draw(fs, landed) {
      row.innerHTML = fs.map(function (f) {
        var cls = "d20" + (landed ? (fs.length > 1 ? (f === result ? " counts" : " dim") : " counts") : "");
        return '<pre class="' + cls + '">' + esc(C.d20Art(f)) + "</pre>";
      }).join("");
    }
    box.classList.add("on");
    C.Sound.play("dice");
    await C.tumble({ row: row, finals: faces, draw: draw });
    alive(t);
    var color = outcome.dragon ? "var(--gold)" : !outcome.success ? "var(--urgent)" : "var(--accent)";
    card.style.setProperty("--verdict", color);
    card.classList.add(outcome.dragon ? "dragon" : outcome.demon ? "demon" : outcome.success ? "ok" : "fail", "pop");
    verdict.textContent = outcome.dragon ? "DRAGON" : outcome.demon ? "DEMON" : outcome.success ? "SUCCESS" : "FAILURE";
    void verdict.offsetWidth;
    verdict.classList.add("on");
    ring.classList.remove("go"); void ring.offsetWidth; ring.classList.add("go");
    C.Sound.play("land");
    if (outcome.dragon) { C.Sound.play("chime", 0.05); C.burst($(".sl-dice .sparks"), "var(--gold)", 70, 200); C.FX.run("dragon"); }
    if (outcome.demon) { C.Sound.play("growl", 0.05); card.classList.add("shake"); C.burst($(".sl-dice .sparks"), "var(--urgent)", 40, 150, true); C.FX.run("demon"); }
    await new Promise(function (r) {
      var done = false, finish = function () { if (!done) { done = true; box.removeEventListener("click", finish); r(); } };
      box.addEventListener("click", finish);
      setTimeout(finish, C.reduced ? 300 : outcome.dragon || outcome.demon ? 2100 : 1400);
    });
    alive(t);
    box.classList.remove("on");
    await sleep(250);
  }

  // d20 under the skill; a boon rolls another and keeps the lower, a bane the higher.
  async function check(skill, opts) {
    opts = opts || {};
    var name = skill[0], target = skill[1];
    var boons = (opts.boons || 0) + S.boon, banes = opts.banes || 0;
    if (S.boon) S.boon = 0;
    var extra = Math.abs(boons - banes), faces = [];
    for (var i = 0; i <= extra; i++) faces.push(1 + Math.floor(Math.random() * 20));
    var result = boons > banes ? Math.min.apply(null, faces) : banes > boons ? Math.max.apply(null, faces) : faces[0];
    var out = { result: result, dragon: result === 1, demon: result === 20 };
    out.success = out.dragon || (!out.demon && result <= target);
    await moment((opts.pushed ? "pushed · " : "") + name, target, faces, result, out);
    var kind = out.dragon ? "dragon" : out.demon ? "demon" : out.success ? "" : "fail";
    add('<span class="die">⚄</span><b>' + esc(name) + "</b> " + result + " vs " + target + " " +
      (out.dragon ? "DRAGON" : out.demon ? "DEMON" : out.success ? "success" : "failure") +
      (extra ? ' <span class="dim">(' + faces.join(", ") + ", " + (extra > 1 ? extra + (boons > banes ? " boons" : " banes") : boons > banes ? "a boon" : "a bane") + ")</span>" : "") +
      (opts.pushed ? ' <span class="dim">pushed</span>' : ""), "sl-rolled " + kind);
    if (out.dragon) { S.triumph = true; flickerFace(); setTimeout(function () { if (S) { S.triumph = false; side(); } }, 5000); }
    if (!out.success && !out.demon && !opts.pushed && opts.pushable !== false) {
      var free = CONDITIONS.filter(function (c) { return S.conds.indexOf(c) === -1; });
      if (free.length) {
        var pick = await choose([{ id: "stand", text: "Let it stand.", say: false }].concat(free.slice(0, 6).map(function (c) {
          return { id: c, text: "Push it: take " + c + ", and roll again.", say: false, danger: true };
        })));
        if (pick !== "stand") {
          S.conds.push(pick);
          note("You push yourself, and you are " + pick + ".", "hurt");
          flickerFace();
          side();
          return check(skill, { boons: opts.boons, banes: opts.banes, pushed: true });
        }
      }
    }
    return out;
  }

  // The likelihood oracle, the one the engine uses when a game has no chart of its own.
  async function oracle(question, likely) {
    var roll = d(1, 100), even = { likely: 65, even: 50, unlikely: 35 }[likely || "even"];
    var yes = roll <= even, extreme = roll <= even / 5 || roll > 100 - (100 - even) / 5;
    var answer = yes ? (extreme ? "Yes, and…" : "Yes") : (extreme ? "No, and…" : "No");
    add('<span class="die">?</span> asked "' + esc(question) + '" <span class="dim">(' + (likely || "even") + ", rolled " + roll + ")</span>: <b>" + answer + "</b>", "sl-rolled");
    await sleep(400);
    return { yes: yes, extreme: extreme };
  }

  // A quiet roll on entering: only a success reaches the margin.
  async function voice(skill, text, banes) {
    var faces = [1 + Math.floor(Math.random() * 20)];
    if (banes) faces.push(1 + Math.floor(Math.random() * 20));
    var r = Math.max.apply(null, faces);
    if (r > skill[1] && r !== 1) return false;
    await sleep(500);
    add('<span class="v">' + esc(skill[0].toUpperCase()) + " [" + skill[1] + "] SUCCESS</span><p>" + md(text) + "</p>", "sl-voice");
    return true;
  }

  // Harm, dying and death --------------------------------------------------------------

  async function hurt(n, why, foe) {
    S.hp = Math.max(0, S.hp - n);
    C.FX.run("hit");
    note("→ " + why + ": " + n + " damage", "hurt");
    flickerFace();
    side();
    fightUpdate(why + ": " + n + " damage", false);
    if (S.hp === 0 && !S.dying) return dying(foe);
    return true;
  }
  async function dying(foe) {
    S.dying = { ok: 0, bad: 0 };
    S.foe = foe;
    C.FX.run("dying");
    flickerFace();
    side();
    await gm("The world tilts and goes quiet at the edges. You are on the floor, and you are not sure how long you have been there. *Stay with it.*");
    while (S.dying) {
      await choose([{ id: "roll", text: "Death roll.", skill: "CON " + S.hero.con, say: false, danger: true }]);
      var out = await check(["Death roll · CON", S.hero.con], { pushable: false });
      S.dying.ok += out.dragon ? 2 : out.success ? 1 : 0;
      S.dying.bad += out.demon ? 2 : out.success ? 0 : 1;
      if (!out.success) C.FX.run("dying");
      side();
      if (S.dying.ok >= 3) {
        S.dying = null;
        S.hp = 1;
        C.FX.run("restore", true);
        flickerFace();
        side();
        await gm("Breath comes back like a door kicked open. You are alive, just, and you are not going to be clever again for a while.");
        return true;
      }
      if (S.dying.bad >= 3) { await death(); return false; }
    }
    return true;
  }

  async function death() {
    var t = token;
    S.dying = null;
    S.dead = true;
    S.lives = Math.max(0, S.lives - 1);
    save("oma-secret-lives", S.lives);
    C.FX.run("death");
    flickerFace();
    side();
    fightEnd();
    await gm("Somewhere above you, in a hall of thirty cups, a candle goes out.");
    add("Your last words?", "sl-note gold");
    var box = $(".sl-choices");
    box.innerHTML = '<form class="sl-words"><input maxlength="90" placeholder="Not like this…" aria-label="Your last words"><button class="sl-choice primary" type="submit">Carve them</button></form>';
    var input = box.querySelector("input");
    input.focus();
    var words = await new Promise(function (r) {
      box.querySelector("form").addEventListener("submit", function (e) { e.preventDefault(); r(input.value.trim()); });
    });
    alive(t);
    box.innerHTML = "";
    if (words) player(words);
    var fallen = load("oma-secret-fallen", []);
    fallen.unshift({ name: S.hero.name, info: S.hero.info, where: S.scene, foe: S.foe || "the dark", words: words });
    save("oma-secret-fallen", fallen.slice(0, 30));
    stone(words);
  }

  // The gravestone, built the way book/Epitaph.qml builds it.
  function stone(words) {
    var face = window.OMA_ART.heroes[S.hero.id].dead[0];
    var name = S.hero.name.toUpperCase().split("").join(" "), info = S.hero.info;
    var w = Math.max(28, face.reduce(function (m, l) { return Math.max(m, l.length); }, 0) + 8, name.length + 6, info.length + 6);
    var carved = ["", "R . I . P", ""].concat(face).concat(["", "", "", ""]);
    function centred(s, width) { var l = Math.floor((width - s.length) / 2); return " ".repeat(Math.max(0, l)) + s + " ".repeat(Math.max(0, width - s.length - l)); }
    var rows = [];
    rows.push('<span class="st">    .-' + "~".repeat(w - 6) + "-.    </span>");
    rows.push('<span class="st">  .\'' + " ".repeat(w - 2) + "'.  </span>");
    rows.push('<span class="st"> /' + " ".repeat(w + 2) + "\\ </span>");
    for (var i = 0; i < carved.length; i++) {
      var named = i === carved.length - 3 ? name : i === carved.length - 2 ? info : "";
      var inner = named ? '<span class="nm">' + esc(centred(named, w)) + "</span>" : '<span class="cv">' + esc(centred(carved[i], w)) + "</span>";
      rows.push('<span class="st"> | </span>' + inner + '<span class="st"> | </span>');
    }
    rows.push('<span class="st"> |' + "_".repeat(w + 2) + "| </span>");
    var grass = "", tufts = ["\\|/", ",,", "'", "\\|/", ",", ",,,", "'"];
    while (grass.length < w + 6) grass += tufts[grass.length % tufts.length] + " ";
    rows.push('<span class="st">' + esc(grass.slice(0, w + 6)) + "</span>");
    var end = $(".sl-end");
    var ash = "";
    for (var a = 0; a < (C.reduced ? 0 : 40); a++) ash += '<i style="left:' + Math.random() * 100 + "%;--dx:" + (Math.random() * 80 - 40) + "px;animation-duration:" + (6 + Math.random() * 8) + "s;animation-delay:" + (-Math.random() * 10) + 's"></i>';
    var lives = S.lives;
    end.innerHTML = '<div class="sl-ash">' + ash + '</div><div class="sl-epi"><pre class="sl-stone">' + rows.join("\n") + "</pre>" +
      '<p class="fell">Fell in ' + esc(S.scene) + ", to " + esc(S.foe || "the dark") + ".</p>" +
      (words ? '<p class="last">“' + esc(words) + "”</p>" : "") +
      '<p class="dim">' + (lives ? lives + (lives === 1 ? " candle still burns." : " candles still burn.") : "The last candle is out.") + "</p>" +
      '<p class="acts">' + (lives ? '<button type="button" class="act primary sl-again">spend a life</button>' : '<button type="button" class="act primary sl-relight">relight the candles</button>') +
      '<button type="button" class="act sl-leave">close the Book</button></p></div>';
    end.classList.add("on");
    var again = end.querySelector(".sl-again, .sl-relight");
    again.addEventListener("click", function () {
      if (again.classList.contains("sl-relight")) save("oma-secret-lives", 30);
      end.classList.remove("on");
      C.FX.run("restore", true);
      newGame();
    });
    end.querySelector(".sl-leave").addEventListener("click", close);
    again.focus();
  }

  async function victory(deed) {
    var t = token;
    fightEnd();
    C.FX.run("restore", true);
    await enter("The Door Closes", "The Door That Wasn't There");
    await gm("You come up into the corridor you know. Behind you there is no door, only stone, the same stone as always.\n\n" + deed + " Nobody will believe you. It doesn't matter.");
    var heroes = load("oma-secret-heroes", []);
    heroes.unshift({ name: S.hero.name, info: S.hero.info, deed: deed });
    save("oma-secret-heroes", heroes.slice(0, 30));
    C.Sound.play("chime");
    C.FX.run("dragon");
    add("Your name is carved over a door that isn't there: <b>" + esc(S.hero.name) + "</b>, " + esc(S.hero.info.toLowerCase()) + ".", "sl-note gold");
    var c = await choose([
      { id: "again", text: "Find the door again.", say: false, primary: true },
      { id: "close", text: "Close the Book.", say: false }
    ]);
    alive(t);
    if (c === "again") newGame(); else close();
  }

  // Fights, drawn in text -----------------------------------------------------------------

  function fightStart(foe) {
    S.fight = foe;
    C.Sound.play("drum");
    fightUpdate("", true);
  }
  function fightUpdate(blow, good) {
    var box = $(".sl-fight");
    if (!S.fight) return;
    var f = S.fight, sprites = window.OMA_ART.sprites;
    var hero = S.hero.id === "maren" ? sprites.hero_magic : S.hero.id === "elowen" ? sprites.hero_ranged : sprites.hero;
    box.hidden = false;
    box.innerHTML = '<div class="dim">ROUND ' + f.round + " [" + esc(S.hero.name) + "] [" + esc(f.name) + ']</div><div class="row">' +
      '<div><pre>' + esc(hero.join("\n")) + '</pre><div class="who">' + esc(S.hero.name.toUpperCase()) + "</div>" + S.hp + "/" + S.hero.hp + " HP</div>" +
      '<div class="arrow">' + (good ? "──✕──▶" : "◀──✕──") + "</div>" +
      "<div><pre>" + esc((f.hp > 0 ? f.art : window.OMA_ART.sprites.fallen).join("\n")) + '</pre><div class="who">' + esc(f.name) + "</div>" + Math.max(0, f.hp) + "/" + f.max + " HP</div></div>" +
      (blow ? '<div class="blow' + (good ? " good" : "") + '">' + esc(blow) + "</div>" : "");
  }
  function fightEnd() { S.fight = null; var box = $(".sl-fight"); if (box) { box.hidden = true; box.innerHTML = ""; } }

  // The adventure ----------------------------------------------------------------------

  function newGame() {
    token += 1;
    S = {
      hero: null, hp: 0, wp: 0, conds: [], torch: 0, dark: false, boon: 0, route: [], scene: "", time: 0,
      clock: 0, scale: false, gold: 0, dead: false, dying: null, triumph: false, fight: null, fresh: true,
      lives: load("oma-secret-lives", 30)
    };
    if (typeof S.lives !== "number") S.lives = 30;
    $(".sl-log").innerHTML = "";
    $(".sl-choices").innerHTML = "";
    fightEnd();
    $(".sl-end").classList.remove("on");
    run(pickHero);
  }
  function run(scene) {
    scene().catch(function (e) { if (e !== STOP) { console.error(e); } });
  }

  async function pickHero() {
    var t = token;
    $(".sl-side").style.visibility = "hidden";
    $(".sl-scene").textContent = "Who walks through?";
    $(".sl-where").textContent = "A hidden level for oma-solorpg";
    $(".sl-face").innerHTML = "";
    $(".sl-name").textContent = "";
    $(".sl-info").textContent = "";
    $(".sl-candles").innerHTML = S.lives < 30 ? "candles in the hall: <b>" + S.lives + "</b> of 30" : "";
    if (S.lives <= 0) {
      add("Every candle in the hall is out.", "sl-note hurt");
      var r = await choose([{ id: "relight", text: "Relight the candles.", say: false, primary: true }, { id: "close", text: "Close the Book.", say: false }]);
      if (r === "close") return close();
      save("oma-secret-lives", 30);
      S.lives = 30;
    }
    var intro = add('<p class="sl-gm">You found a door that wasn\'t there. Before it opens, choose who walks through it. Every face below was drawn by the engine, the same way the Book draws your hero.</p><div class="sl-heroes"></div>');
    var grid = intro.querySelector(".sl-heroes");
    var chosen = await new Promise(function (resolve) {
      HEROES.forEach(function (h) {
        var b = document.createElement("button");
        b.type = "button";
        b.className = "sl-hero";
        var pre = document.createElement("pre");
        pre.className = "portrait";
        C.drawFace(pre, h.id, "calm", false);
        b.appendChild(pre);
        b.insertAdjacentHTML("beforeend", "<b>" + esc(h.name) + "</b><span>" + esc(h.info) + "</span><span>" +
          esc(h.skills.fight.join(" ") + " · " + h.skills.sneak.join(" ") + " · " + h.skills.talk.join(" ")) + "</span><span>HP " + h.hp + " · WP " + h.wp + "</span>");
        b.addEventListener("click", function () { if (t === token) resolve(h); });
        grid.appendChild(b);
      });
      grid.querySelector("button").focus({ preventScroll: true });
    });
    alive(t);
    S.hero = chosen;
    $(".sl-side").style.visibility = "";
    S.hp = chosen.hp;
    S.wp = chosen.wp;
    $(".sl-log").innerHTML = "";
    return door();
  }

  async function door() {
    await enter("The Door That Wasn't There", "a hidden level for oma-solorpg");
    await gm("You have walked this corridor a hundred times. Today there is a door in it: small and square, older than the stones around it, and carved with arrows. Up, up, down, down, left, right, left, right. Under them, two runes you don't know. *B. A.*\n\nIt is already open. Warm air breathes out of it, and it smells of candle wax and old coins.");
    await voice(S.hero.skills.notice, "The arrows are worn smooth, as if thousands of thumbs had pressed them in order.");
    var asked = false;
    for (;;) {
      var c = await choose([
        { id: "go", text: "I go through.", primary: true },
        !S.torch && !S.lit && { id: "torch", text: "I light my torch first." },
        !asked && { id: "ask", text: "Is it a trap?", skill: "ask the oracle" }
      ]);
      if (c === "go") return candles();
      if (c === "torch") { S.torch = 4; S.lit = true; S.dark = false; C.Sound.play("torch"); side(); await gm("The flame catches and leans toward the door, as if the door were breathing in."); }
      if (c === "ask") {
        asked = true;
        var a = await oracle("Is it a trap?", "unlikely");
        await gm(a.yes
          ? (a.extreme ? "Yes, and it knows your name. You hear it whispered from inside, fondly, like an old friend's." : "Yes. Of course it is. Every door in a place like this is a trap for someone.")
          : (a.extreme ? "No, and it has been waiting for you for a very long time." : "No. But something inside is awake, and it heard you ask."));
      }
    }
  }

  async function candles() {
    await enter("The Hall of Thirty Candles");
    var lost = 30 - S.lives;
    await gm("Thirty iron cups stand along the walls, a candle in each, and a voice with no mouth counts them for you. *Thirty lives,* it says. *Spend them how you like.*\n\n" +
      (lost === 0 ? "All thirty burn. The floor is smooth and clean, as if nobody had ever come this way." :
        lost === 1 ? "Twenty-nine burn. The dark one is yours, from the last time. There is one name carved into the floor." :
          (30 - lost) + " burn. The dark ones are yours, every one of them. The floor is carved with names."));
    var fallen = load("oma-secret-fallen", []), heroes = load("oma-secret-heroes", []);
    var read = false;
    for (;;) {
      var c = await choose([
        { id: "down", text: "I take the stairs down.", primary: true },
        !read && (fallen.length || heroes.length) && { id: "read", text: "I read the names carved into the floor." }
      ]);
      if (c === "down") return pantry();
      read = true;
      add('<div class="sl-rule">◆</div><p class="sl-rule-title">The Hall of the Fallen</p>');
      fallen.slice(0, 8).forEach(function (f) {
        note("✝ " + f.name + ", " + f.info.toLowerCase() + ". Fell in " + f.where + ", to " + f.foe + "." + (f.words ? ' "' + f.words + '"' : ""));
      });
      heroes.slice(0, 5).forEach(function (h) { note("◆ " + h.name + " came back out. " + h.deed, "gold"); });
      await gm(fallen.length ? "Some of the names are still warm to the touch." : "Only the heroes' names. Nobody has died here yet. The hall seems patient about it.");
    }
  }

  async function pantry() {
    await enter("The Mimic's Pantry");
    await gm("A pantry, of all things. Shelves of jars gone black, a ham that has turned to stone, a wheel of cheese with a sword stuck in it. In the middle of the floor sits a chest with brass corners, its lid ajar, and a glint of gold inside.");
    var knew = await voice(S.hero.skills.notice, "There is dust on everything in this room except the chest.", S.dark ? 1 : 0);
    var mimic = { name: "The mimic", art: MIMIC, hp: 12, max: 12, round: 1 };
    var revealed = false;
    for (;;) {
      var c = await choose([
        !revealed && { id: "open", text: "I open the chest.", danger: !knew },
        !revealed && { id: "prod", text: "I prod the chest from a safe distance." },
        revealed && { id: "fight", text: "I fight it. It's a chest.", skill: S.hero.skills.fight.join(" ") },
        { id: "leave", text: revealed ? "I let it keep its gold and go down." : "I leave it alone and go down." }
      ]);
      if (c === "leave") { if (revealed) await gm("It watches you go with its tongue out, like a disappointed dog."); return riddle(); }
      if (c === "prod") {
        revealed = true;
        await gm("You reach out with your " + S.hero.weapon.replace(/^a /, "") + " and tap the lid. The chest yawns. There are teeth in it, a great many, and a tongue as long as your arm, and it is *delighted* to see you.");
        continue;
      }
      if (c === "open") {
        await gm("The lid opens by itself before your fingers reach it, and the chest is all teeth.");
        fightStart(mimic);
        var ok = await mimicTurn(mimic, knew);
        if (!ok) return;
        revealed = true;
      } else {
        fightStart(mimic);
      }
      var won = await mimicFight(mimic);
      if (!won) return;
      S.gold += 1;
      S.boon += 1;
      await gm("It shudders and goes still, a chest again. Inside, on a bed of old teeth: one gold coin, stamped on both sides with a twenty-sided die. It is warm, and it feels lucky. *A boon on your next roll.*");
      fightEnd();
      return riddle();
    }
  }
  async function mimicTurn(m, ready) {
    var roll = d(1, 6);
    if (roll <= 3) {
      if (ready) note("You saw the dust. You were ready for it: a boon.", "good");
      var ev = await check(S.hero.skills.evade, { boons: ready ? 1 : 0 });
      if (ev.success) { fightUpdate("The mimic snaps at empty air.", true); note("← The mimic lunges and snaps shut on nothing."); return true; }
      return hurt(d(2, 4), "The mimic bites", "a mimic");
    }
    if (roll <= 5) {
      if (S.conds.indexOf("dazed") === -1) { S.conds.push("dazed"); flickerFace(); side(); }
      note("← Its tongue slaps you across the face. You are dazed.", "hurt");
      fightUpdate("Its tongue slaps you: dazed", false);
      return true;
    }
    note("← It swallows one of your boots and seems pleased with itself.");
    fightUpdate("It eats a boot", false);
    return true;
  }
  async function mimicFight(m) {
    for (;;) {
      var c = await choose([
        { id: "hit", text: "I attack with " + (S.hero.weapon.indexOf("a ") === 0 ? S.hero.weapon : "my " + S.hero.weapon) + ".", skill: S.hero.skills.fight.join(" "), primary: true },
        { id: "run", text: "I get out of its reach and run for the stairs.", skill: S.hero.skills.evade.join(" ") }
      ]);
      if (c === "run") {
        var ev = await check(S.hero.skills.evade);
        if (ev.success) { fightEnd(); await gm("You're past it and on the stairs before it can turn around. Chests are not built for turning around."); return riddle().then(function () { return false; }); }
        var go = await hurt(d(2, 4), "The mimic catches your heel", "a mimic");
        if (!go) return false;
        continue;
      }
      var out = await check(S.hero.skills.fight);
      if (out.success) {
        var dmg = d(S.hero.dmg[0], S.hero.dmg[1]) + (S.hero.dmg[2] ? d(1, S.hero.dmg[2]) : 0) + (out.dragon ? d(S.hero.dmg[0], S.hero.dmg[1]) : 0);
        m.hp -= dmg;
        note("→ " + (out.dragon ? "A Dragon: double damage. " : "") + "You hit the mimic for " + dmg + ".", "good");
        fightUpdate("You hit it for " + dmg + (m.hp <= 0 ? ", down!" : ""), true);
        if (m.hp <= 0) return true;
      } else {
        fightUpdate("You miss", false);
      }
      m.round += 1;
      var ok = await mimicTurn(m);
      if (!ok) return false;
    }
  }

  async function riddle() {
    await enter("The Riddle Stair");
    await gm("The stair turns down and down, and halfway a face of stone blocks the way with its eyes closed. They open when you're close enough to smell its breath, which smells of chalk.\n\n*Answer and the stair goes on,* it says. *Answer wrong and it goes on faster.*\n\n*I have twenty faces and I never frown. I decide, but I never think. Every table holds its breath when I'm thrown, and fears my highest face.*");
    var hinted = false;
    for (;;) {
      var c = await choose([
        { id: "die", text: hinted ? "\"A die. A twenty-sided die.\" (you're sure)" : "\"A die. A twenty-sided die.\"" },
        { id: "crown", text: "\"A crown.\"" },
        { id: "fate", text: "\"Fate.\"" },
        !hinted && { id: "lore", text: "I try to remember the old riddles.", skill: S.hero.skills.lore.join(" ") }
      ]);
      if (c === "lore") {
        hinted = true;
        var out = await check(S.hero.skills.lore);
        await gm(out.success
          ? "You remember it: a table of friends, late at night, and one of them rolling a twenty and everyone groaning at once. *Every table fears its highest face.*"
          : "Nothing comes. The face waits, and it is very good at waiting.");
        continue;
      }
      if (c === "die") {
        S.boon += 1;
        await gm("The face grins, which it was not built to do, and the stone cracks around the grin. *And may it land on one for you,* it says, and sinks into the wall. You feel lucky. *A boon on your next roll.*");
        return hoard();
      }
      await gm(c === "fate" ? "*Close,* says the face, *and wrong.* The steps fold flat under your feet and the stair becomes a slide." : "*A crown has one face, and it is always frowning,* says the face. The steps fold flat under your feet and the stair becomes a slide.");
      var ok = await hurt(d(1, 6), "You tumble down the slide", "a riddle");
      if (!ok) return;
      return hoard();
    }
  }

  async function hoard() {
    await enter("The Hoard Beneath");
    add(esc(DRAGON.join("\n")), "sl-dragon");
    await gm("The stair ends in a cave as big as a cathedral, and the cave is full of gold. Coins and cups and crowns, and among them things you have no names for: small grey boxes with a slot in one end, a flat thing with a cross on it and two round buttons, a cartridge whose label has worn away.\n\nOn top of it all, curled like a cat, a dragon sleeps. Each breath it lets out stirs the coins like surf. One scale on its flank has come loose and hangs by a thread, bright as a new coin.");
    await voice(S.hero.skills.notice, "Its left eye is not quite closed.");
    var sung = false;
    for (;;) {
      var sneak = S.hero.skills.sneak, banes = S.torch > 0 ? 1 : 0;
      var c = await choose([
        !S.scale && { id: "scale", text: "I creep up and take the loose scale.", skill: sneak.join(" ") + (banes ? " · a bane, your torch" : ""), primary: true },
        S.torch > 0 && { id: "snuff", text: "I snuff my torch first." },
        !sung && !S.scale && { id: "sing", text: "I sing it deeper into sleep.", skill: S.hero.skills.talk.join(" ") },
        S.scale && { id: "greed", text: "I fill my pockets with gold, too.", skill: sneak.join(" ") + " · a bane", danger: true },
        S.scale && { id: "leave", text: "I leave. Now.", primary: true },
        !S.scale && { id: "talk", text: "I wake it, politely, and ask for the scale.", skill: S.hero.skills.talk.join(" "), danger: true }
      ]);
      if (c === "leave") return victory("You carry a dragon's scale that is still warm" + (S.gold > 1 ? ", and your pockets clink" : "") + ".");
      if (c === "snuff") { S.torch = 0; S.dark = true; side(); await gm("Dark, then, except for the gold, which has a light of its own down here."); continue; }
      if (c === "sing") {
        sung = true;
        var song = await check(S.hero.skills.talk);
        if (song.success) { S.clock = Math.max(0, S.clock - 1); S.boon += 1; await gm("You hum something your grandmother hummed. The dragon's breathing slows and deepens, and a coin slides off its snout with a sound like a small bell. *A boon on your next roll.*"); }
        else { await stir(1); await gm("Your voice cracks on the high note. The dragon's ear turns toward you, then away."); }
        continue;
      }
      if (c === "talk") {
        var talk = await check(S.hero.skills.talk, { banes: 1 });
        if (talk.success) {
          await gm("One golden eye opens, then the other. It listens to the whole speech without blinking, which is worse than anything. Then it laughs, a sound like a landslide in a bell tower, and breathes on the loose scale until it falls into your hands. *For the story,* it says. *Tell it well.*");
          S.scale = true;
          return victory("You carry a dragon's scale it gave you itself, which nobody will believe either.");
        }
        return wakes("It was not in the mood to be asked.");
      }
      if (c === "scale" || c === "greed") {
        var out = await check(sneak, { banes: banes + (c === "greed" ? 1 : 0) });
        if (out.success) {
          if (c === "scale") {
            S.scale = true;
            await gm(out.dragon
              ? "You take the scale, and a small crown that was lying against it, and the dragon smiles in its sleep as if you had told it a joke."
              : "The thread gives. The scale is in your hand, warm as bread, and the dragon sleeps on.");
            if (out.dragon) S.gold += 3;
          } else {
            S.gold += 5;
            await gm("Cups, coins, a ring with an eye in it. Your pockets are heavy and the dragon hasn't moved. You are either very good or very lucky.");
          }
          continue;
        }
        if (out.demon) return wakes("A coin slides, and another, and then the whole slope of gold goes like a landslide.");
        await stir(2);
        if (S.clock >= 4) return wakes("The coins shift under its weight as it rolls over, and it's looking at you.");
        await gm("A coin clinks. You freeze with one foot in the air, and the breathing goes on, slower.");
      }
    }
  }
  async function stir(n) {
    S.clock += n;
    if (S.clock === 1) omen("The coins shift, as if something underneath them turned over in its sleep.");
    else if (S.clock === 2 || S.clock === 3) omen("The dragon's breathing has changed. The candles upstairs gutter all at once.");
  }
  async function wakes(why) {
    await gm(why + "\n\nBoth eyes are open now. They are the size of shields and the colour of a Dragon on a d20.");
    var dragon = { name: "The dragon", art: DRAGON_AWAKE, hp: 99, max: 99, round: 1 };
    fightStart(dragon);
    var c = await choose([
      { id: "run", text: "I run for the stair.", skill: S.hero.skills.evade.join(" "), primary: true },
      { id: "fight", text: "I fight it.", skill: S.hero.skills.fight.join(" "), danger: true }
    ]);
    if (c === "fight") {
      var out = await check(S.hero.skills.fight);
      if (out.dragon) {
        fightEnd();
        await gm("You hit it on the nose. Exactly on the nose. It is so surprised that it sneezes, and the sneeze throws you back up the stairs, singed, alive, with the loose scale stuck to your cloak.");
        S.scale = true;
        return victory("You hit a dragon on the nose and carry its scale for proof.");
      }
      note(out.success ? "→ You hit it. It doesn't notice." : "→ You miss, which may be for the best.");
    } else {
      var ev = await check(S.hero.skills.evade);
      if (ev.success) {
        fightEnd();
        await gm("You run. Behind you the cave fills with fire, and the fire comes up the stair after you like water up a pipe, and it is one step too slow.");
        return victory(S.scale ? "You carry a dragon's scale, and your eyebrows are gone." : "You carry nothing but your life, and your eyebrows are gone.");
      }
    }
    await gm("It breathes.");
    var lived = await hurt(d(4, 6), "Dragonfire", "a dragon");
    if (!lived) return;
    fightEnd();
    await gm("You come to on the stair, smoking, and climb. The dragon doesn't follow. Dragons don't need to.");
    return victory(S.scale ? "You carry a dragon's scale and a great many burns." : "You carry a great many burns, and a story.");
  }

  window.OMA_SECRET = { open: open };
})();

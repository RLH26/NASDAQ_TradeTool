async function loadIdeas({ bypassCache = false } = {}) {
  const subtitle = document.getElementById("subtitle");
  const stats = document.getElementById("stats");
  const list = document.getElementById("list");

  subtitle.textContent = "Updating…";

  const url = "ideas.json" + (bypassCache ? `?t=${Date.now()}` : "");
  const res = await fetch(url).catch(() => null);
  if (!res) {
    subtitle.textContent = "No data yet (ideas.json missing)";
    return;
  }
  const data = await res.json();

  subtitle.textContent =
    `Last update: ${data.generated_utc} • NASDAQ: ${data.universe_count} • Ideas: ${data.ideas.length}`;

  stats.innerHTML = `
    <b>Idea buckets</b><br>
    ${Object.entries(data.bucket_counts)
      .map(([k,v]) => `${k}: <b>${v}</b>`)
      .join("<br>")}
  `;

  list.innerHTML = data.ideas.map(i => `
    <article class="card">
      <b>${i.ticker}</b> — ${i.bucket}<br>
      <small>Score: ${i.score} | ${i.form_type} | ${i.filed_date}</small>
      <p>${i.why_now}</p>
      <a href="${i.filing_url}" target="_blank">SEC Filing</a>
    </article>
  `).join("");
}

document.getElementById("refresh").onclick = () =>
  loadIdeas({ bypassCache: true });

loadIdeas();
async function loadMoversIndex() {
  const res = await fetch("movers.json?t=" + Date.now(), { cache: "no-store" });
  if (!res.ok) throw new Error("movers.json not found yet (run the Action first).");
  return await res.json();
}

function fmtPct(x) {
  if (x === null || x === undefined) return "n/a";
  return (x * 100).toFixed(1) + "%";
}

function esc(s) {
  return (s || "").replace(/[&<>"']/g, (c) => ({
    "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"
  }[c]));
}

async function handleTickerCheck() {
  const out = document.getElementById("checkResult");
  const t = (document.getElementById("tickerInput").value || "").trim().toUpperCase();
  if (!t) { out.innerHTML = "Enter a ticker."; return; }

  out.innerHTML = "Checking…";

  let data;
  try {
    data = await loadMoversIndex();
  } catch (e) {
    out.innerHTML = esc(e.message);
    return;
  }

  const hit = (data.items || []).find(x => x.ticker === t);

  if (!hit) {
    out.innerHTML = `No >${data.thresholds?.one_day_jump_pct || 20}% 1-day jump detected for <b>${esc(t)}</b> in the last ${data.lookback_days || 5} trading days.`;
    return;
  }

  const newsLabel = hit.news_classification === "no_obvious_news"
    ? `<span style="padding:3px 8px; border-radius:999px; border:1px solid rgba(255,255,255,.2);">No obvious headlines</span>`
    : `<span style="padding:3px 8px; border-radius:999px; border:1px solid rgba(255,255,255,.2);">Headlines found</span>`;

  out.innerHTML = `
    <div style="display:flex; gap:10px; flex-wrap:wrap; align-items:center;">
      <div style="font-size:18px; font-weight:900;">${esc(hit.ticker)}</div>
      ${newsLabel}
      <div style="margin-left:auto; opacity:.8;">Jump day: <b>${esc(hit.jump_date)}</b></div>
    </div>

    <div style="margin-top:8px; display:flex; gap:14px; flex-wrap:wrap; opacity:.9;">
      <div>1D jump: <b>${fmtPct(hit.one_day_jump)}</b></div>
      <div>5D move: <b>${fmtPct(hit.five_day_move)}</b></div>
      <div>News hits (window): <b>${hit.news_hits}</b></div>
    </div>

    <div style="margin-top:10px; opacity:.9;">
      <div style="font-weight:800; margin-bottom:6px;">Top headlines found before jump</div>
      ${hit.top_headlines.length ? `
        <ul>
          ${hit.top_headlines.map(a => `<li><a href="${a.url}" target="_blank" rel="noopener noreferrer">${esc(a.title)}</a> <span style="opacity:.7;">(${esc(a.published)})</span></li>`).join("")}
        </ul>
      ` : `<div style="opacity:.8;">None returned by the news scan in the window before the jump.</div>`}
    </div>
  `;
}

document.getElementById("checkBtn").addEventListener("click", handleTickerCheck);

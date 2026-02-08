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

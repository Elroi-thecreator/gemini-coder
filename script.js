"use strict";

const POSTS = [
  {
    title: "The Art of Leaving Things Out",
    date: "2025-06-12",
    tag: "Craft",
    excerpt:
      "Every feature you don't build is a bug you never ship. Simplicity isn't subtraction for its own sake — it's making room for what matters.",
  },
  {
    title: "Write Code Like a Paragraph",
    date: "2025-05-28",
    tag: "Code",
    excerpt:
      "Good code reads like prose: clear subjects, short sentences, and no clever detours. If a reviewer needs to reread a line, rewrite the line.",
  },
  {
    title: "One Page Is Enough",
    date: "2025-05-03",
    tag: "Design",
    excerpt:
      "This entire blog is three files. No framework, no build step, no bundle. Constraints aren't limitations — they're the shortest path to done.",
  },
  {
    title: "Ship Small, Ship Often",
    date: "2025-04-15",
    tag: "Process",
    excerpt:
      "A tiny change deployed today teaches you more than a perfect plan for next quarter. Momentum compounds; intentions don't.",
  },
];

const postsEl = document.getElementById("posts");
const noResultsEl = document.getElementById("no-results");
const searchInput = document.getElementById("search-input");
const themeToggle = document.getElementById("theme-toggle");

function formatDate(iso) {
  return new Date(iso + "T00:00:00").toLocaleDateString("en-US", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}

function renderPosts(query = "") {
  const q = query.trim().toLowerCase();
  const filtered = POSTS.filter(
    (p) =>
      !q ||
      p.title.toLowerCase().includes(q) ||
      p.excerpt.toLowerCase().includes(q) ||
      p.tag.toLowerCase().includes(q)
  );

  postsEl.innerHTML = "";
  noResultsEl.hidden = filtered.length > 0;

  const frag = document.createDocumentFragment();
  for (const post of filtered) {
    const article = document.createElement("article");
    article.className = "post";

    const meta = document.createElement("div");
    meta.className = "post-meta";
    const tag = document.createElement("span");
    tag.className = "tag";
    tag.textContent = post.tag;
    const time = document.createElement("time");
    time.dateTime = post.date;
    time.textContent = formatDate(post.date);
    meta.append(tag, time);

    const h2 = document.createElement("h2");
    h2.textContent = post.title;

    const p = document.createElement("p");
    p.textContent = post.excerpt;

    const link = document.createElement("a");
    link.className = "read-more";
    link.href = "#posts";
    link.textContent = "Read more →";

    article.append(meta, h2, p, link);
    frag.appendChild(article);
  }
  postsEl.appendChild(frag);
}

searchInput.addEventListener("input", () => renderPosts(searchInput.value));

document.getElementById("search-form").addEventListener("submit", (e) => {
  e.preventDefault();
  renderPosts(searchInput.value);
});

function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  themeToggle.textContent = theme === "dark" ? "☀️" : "🌙";
  try {
    localStorage.setItem("theme", theme);
  } catch {
    /* storage unavailable — theme just won't persist */
  }
}

themeToggle.addEventListener("click", () => {
  const current = document.documentElement.dataset.theme === "dark" ? "dark" : "light";
  applyTheme(current === "dark" ? "light" : "dark");
});

(function init() {
  let saved = null;
  try {
    saved = localStorage.getItem("theme");
  } catch {
    /* ignore */
  }
  const prefersDark =
    window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
  applyTheme(saved || (prefersDark ? "dark" : "light"));
  renderPosts();
})();

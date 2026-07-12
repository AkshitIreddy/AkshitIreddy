#!/usr/bin/env python3
"""
Generate a self-contained, synthwave-themed GitHub stats card as an SVG,
from live GitHub API data. Reliable (lives in your repo, never 503s) and
theme-matched to the wave banner.

Usage:  python make_stats.py [username]
Reads optional GITHUB_TOKEN from the environment for a higher rate limit
(used by the auto-refresh GitHub Action; not required locally for public data).
"""
import json
import os
import sys
import urllib.request
import urllib.error

USER = sys.argv[1] if len(sys.argv) > 1 else "AkshitIreddy"
TOKEN = os.environ.get("GITHUB_TOKEN", "").strip()

# ---- palette (matches the wave banner) -------------------------------------
PINK    = "#ff2e97"
HOTPINK = "#ff5edb"
PURPLE  = "#b45cff"
VIOLET  = "#7c5cff"
CYAN    = "#22d3ee"
BLUE    = "#4f9dff"
NUM     = "#ff4da6"   # number colour — reads on both dark & light backgrounds
LABEL   = "#8b949e"   # GitHub's neutral grey — safe on both themes


def gh(path):
    url = path if path.startswith("http") else f"https://api.github.com/{path}"
    req = urllib.request.Request(url, headers={
        "User-Agent": "profile-stats-card",
        "Accept": "application/vnd.github+json",
        **({"Authorization": f"Bearer {TOKEN}"} if TOKEN else {}),
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def fetch():
    user = gh(f"users/{USER}")
    repos, page = [], 1
    while True:
        batch = gh(f"users/{USER}/repos?per_page=100&type=owner&page={page}")
        if not batch:
            break
        repos.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    owned = [r for r in repos if not r.get("fork")]
    stars = sum(r["stargazers_count"] for r in owned)
    forks = sum(r["forks_count"] for r in owned)

    lang_bytes = {}
    for r in owned:
        try:
            for lang, b in gh(f"repos/{r['full_name']}/languages").items():
                lang_bytes[lang] = lang_bytes.get(lang, 0) + b
        except urllib.error.HTTPError:
            pass

    try:
        commits = gh(f"search/commits?q=author:{USER}&per_page=1").get("total_count", 0)
    except urllib.error.HTTPError:
        commits = 0

    return {
        "stars": stars,
        "commits": commits,
        "repos": user.get("public_repos", len(owned)),
        "followers": user.get("followers", 0),
        "forks": forks,
        "langs": lang_bytes,
    }


def fmt(n):
    return f"{n:,}"


# ---- neon icons (simple stroke glyphs, drawn centred at (cx, cy)) ----------
def icon_star(cx, cy, c):
    import math
    pts = []
    for i in range(10):
        r = 17 if i % 2 == 0 else 7
        a = -math.pi / 2 + i * math.pi / 5
        pts.append(f"{cx + r*math.cos(a):.1f},{cy + r*math.sin(a):.1f}")
    return f'<polygon points="{" ".join(pts)}" fill="{c}"/>'

def icon_commit(cx, cy, c):
    return (f'<g stroke="{c}" stroke-width="3" stroke-linecap="round" fill="none">'
            f'<line x1="{cx-20}" y1="{cy}" x2="{cx-7}" y2="{cy}"/>'
            f'<line x1="{cx+7}" y1="{cy}" x2="{cx+20}" y2="{cy}"/>'
            f'<circle cx="{cx}" cy="{cy}" r="7"/></g>')

def icon_repo(cx, cy, c):
    return (f'<g stroke="{c}" stroke-width="3" stroke-linejoin="round" '
            f'stroke-linecap="round" fill="none">'
            f'<path d="M{cx-14} {cy-16} h20 a4 4 0 0 1 4 4 v28 h-20 a4 4 0 0 0 -4 4 z"/>'
            f'<line x1="{cx-14}" y1="{cy+16}" x2="{cx-14}" y2="{cy-16}"/></g>')

def icon_person(cx, cy, c):
    return (f'<g stroke="{c}" stroke-width="3" fill="none" stroke-linecap="round">'
            f'<circle cx="{cx}" cy="{cy-9}" r="7"/>'
            f'<path d="M{cx-13} {cy+16} a13 12 0 0 1 26 0"/></g>')

def icon_fork(cx, cy, c):
    return (f'<g stroke="{c}" stroke-width="3" fill="{c}" stroke-linecap="round">'
            f'<circle cx="{cx-13}" cy="{cy-13}" r="4.5"/>'
            f'<circle cx="{cx+13}" cy="{cy-13}" r="4.5"/>'
            f'<circle cx="{cx}" cy="{cy+14}" r="4.5"/>'
            f'<path fill="none" d="M{cx-13} {cy-9} v4 a6 6 0 0 0 6 6 h14 '
            f'a6 6 0 0 0 6 -6 v-4 M{cx} {cy+2} v8"/></g>')


TILE_DEFS = [
    ("stars",     "Stars",     icon_star,   HOTPINK),
    ("followers", "Followers", icon_person, CYAN),
    ("repos",     "Repos",     icon_repo,   PURPLE),
    ("commits",   "Commits",   icon_commit, PINK),
    ("forks",     "Forks",     icon_fork,   BLUE),
]

LANG_COLORS = [HOTPINK, CYAN, PURPLE, PINK, BLUE, VIOLET]


def build(data):
    W, H = 1280, 300
    centers = [160, 400, 640, 880, 1120]
    tiles = []
    for (key, label, icon, color), cx in zip(TILE_DEFS, centers):
        val = fmt(data[key])
        tiles.append(
            f'<g filter="url(#ng)">{icon(cx, 66, color)}</g>'
            f'<text x="{cx}" y="150" text-anchor="middle" '
            f'font-family="\'Segoe UI\',system-ui,-apple-system,Helvetica,Arial,sans-serif" '
            f'font-size="46" font-weight="800" fill="{NUM}" filter="url(#ng)">{val}</text>'
            f'<text x="{cx}" y="182" text-anchor="middle" '
            f'font-family="\'Segoe UI\',system-ui,-apple-system,Helvetica,Arial,sans-serif" '
            f'font-size="16" font-weight="600" letter-spacing="2.5" fill="{LABEL}">'
            f'{label.upper()}</text>'
        )

    # language bar (byte-accurate, top 5 + other)
    langs = sorted(data["langs"].items(), key=lambda kv: kv[1], reverse=True)
    total = sum(b for _, b in langs) or 1
    top = langs[:5]
    other = sum(b for _, b in langs[5:])
    seg = list(top) + ([("Other", other)] if other else [])

    bx, bw, by, bh = 160, 960, 214, 16
    x = bx
    bar = []
    for i, (name, b) in enumerate(seg):
        w = bw * (b / total)
        col = LANG_COLORS[i % len(LANG_COLORS)]
        bar.append(f'<rect x="{x:.1f}" y="{by}" width="{max(w-2,1):.1f}" height="{bh}" '
                   f'rx="4" fill="{col}"/>')
        x += w
    # centred legend row
    items = "".join(
        f'<circle cx="{lx0}" cy="270" r="5" fill="{col}"/>'
        f'<text x="{lx0+11}" y="275" font-family="\'Segoe UI\',system-ui,sans-serif" '
        f'font-size="15" fill="{LABEL}">{name} {pct}</text>'
        for (name, pct, col, lx0) in _legend_positions(seg, LANG_COLORS)
    )

    defs = ('<defs>'
            '<filter id="ng" x="-40%" y="-40%" width="180%" height="180%">'
            '<feGaussianBlur stdDeviation="2.4" result="b"/>'
            '<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>'
            '</filter></defs>')

    body = (f'{"".join(tiles)}'
            f'<g>{"".join(bar)}</g>'
            f'{items}')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
            f'width="{W}" height="{H}" role="img" '
            f'aria-label="GitHub stats for {USER}">{defs}{body}</svg>\n')


def _legend_positions(seg, colors):
    # estimate item widths and centre the whole legend row
    widths = [30 + (len(name) + 4) * 8.5 for name, _ in seg]
    total_w = sum(widths)
    start = (1280 - total_w) / 2
    out = []
    x = start
    langs_total = sum(b for _, b in seg) or 1
    for i, (name, b) in enumerate(seg):
        pct = f"{b/langs_total*100:.0f}%"
        out.append((name, pct, colors[i % len(colors)], x))
        x += widths[i]
    return out


if __name__ == "__main__":
    os.makedirs("assets", exist_ok=True)
    data = fetch()
    print("stats:", {k: v for k, v in data.items() if k != "langs"})
    print("langs:", sorted(data["langs"].items(), key=lambda kv: kv[1], reverse=True)[:6])
    svg = build(data)
    with open("assets/stats.svg", "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"wrote assets/stats.svg ({len(svg)/1024:.1f} KB)")

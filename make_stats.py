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
import re
import sys
from datetime import datetime, timezone
from html import unescape
from urllib.parse import quote
import urllib.request

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


def contribution_count_for_year(year):
    """Return the public profile's contribution total for one calendar year.

    GitHub's profile calendar includes anonymized private/internal activity
    when the user has chosen to publish those counts. Fetching the public
    calendar therefore matches what profile visitors see without granting this
    workflow access to any private repository names or contents.
    """
    username = quote(USER, safe="")
    url = (f"https://github.com/users/{username}/contributions"
           f"?from={year}-01-01&to={year}-12-31")
    req = urllib.request.Request(url, headers={
        "User-Agent": "profile-stats-card",
        "Accept": "text/html",
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        page = r.read().decode("utf-8", errors="replace")

    # Keep the match scoped to headings so thousands of daily tooltip counts
    # cannot be mistaken for the annual total.
    for heading in re.findall(r"<h2\b[^>]*>(.*?)</h2>", page,
                              flags=re.IGNORECASE | re.DOTALL):
        text = unescape(re.sub(r"<[^>]+>", " ", heading))
        text = re.sub(r"\s+", " ", text).strip()
        match = re.search(
            rf"([0-9][0-9,]*)\s+contributions?\s+in\s+{year}\b",
            text,
            flags=re.IGNORECASE,
        )
        if match:
            return int(match.group(1).replace(",", ""))

    raise RuntimeError(f"Could not parse GitHub contribution total for {year}")


def lifetime_contributions(created_at):
    start_year = int(created_at[:4])
    current_year = datetime.now(timezone.utc).year
    yearly = {
        year: contribution_count_for_year(year)
        for year in range(start_year, current_year + 1)
    }
    print("contributions by year:", yearly)
    return sum(yearly.values())


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

    contributions = lifetime_contributions(user["created_at"])

    return {
        "stars": stars,
        "contributions": contributions,
        "repos": user.get("public_repos", len(owned)),
        "followers": user.get("followers", 0),
        "forks": forks,
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

def icon_contribution(cx, cy, c):
    # A compact contribution-calendar glyph with varied activity levels.
    cells = [
        (-18, -13, .35), (-7, -13, .75), (4, -13, 1), (15, -13, .55),
        (-18, -2, .7), (-7, -2, 1), (4, -2, .45), (15, -2, .85),
        (-18, 9, .3), (-7, 9, .6), (4, 9, .9), (15, 9, .4),
    ]
    squares = "".join(
        f'<rect x="{cx+dx}" y="{cy+dy}" width="8" height="8" rx="2" '
        f'fill="{c}" fill-opacity="{opacity}"/>'
        for dx, dy, opacity in cells
    )
    return f'<g>{squares}</g>'

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
    ("stars",   "Stars",   icon_star,   HOTPINK),
    ("repos",   "Repos",   icon_repo,   PURPLE),
    ("contributions", "Contributions", icon_contribution, PINK),
    ("forks",   "Forks",   icon_fork,   BLUE),
]

def build(data):
    # Compact four-metric card. The icons sit slightly closer to the top edge
    # so the card follows the wave divider with a little less visual gap.
    W, H = 1280, 190
    n = len(TILE_DEFS)
    centers = [W * (i + 0.5) / n for i in range(n)]  # evenly spaced for any count
    tiles = []
    for (key, label, icon, color), cx in zip(TILE_DEFS, centers):
        val = fmt(data[key])
        tiles.append(
            f'<g filter="url(#ng)">{icon(cx, 54, color)}</g>'
            f'<text x="{cx}" y="132" text-anchor="middle" '
            f'font-family="\'Segoe UI\',system-ui,-apple-system,Helvetica,Arial,sans-serif" '
            f'font-size="46" font-weight="800" fill="{NUM}" filter="url(#ng)">{val}</text>'
            f'<text x="{cx}" y="164" text-anchor="middle" '
            f'font-family="\'Segoe UI\',system-ui,-apple-system,Helvetica,Arial,sans-serif" '
            f'font-size="16" font-weight="600" letter-spacing="2.5" fill="{LABEL}">'
            f'{label.upper()}</text>'
        )

    defs = ('<defs>'
            '<filter id="ng" x="-40%" y="-40%" width="180%" height="180%">'
            '<feGaussianBlur stdDeviation="2.4" result="b"/>'
            '<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>'
            '</filter></defs>')

    body = "".join(tiles)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
            f'width="{W}" height="{H}" role="img" '
            f'aria-label="GitHub stats for {USER}">{defs}{body}</svg>\n')
if __name__ == "__main__":
    os.makedirs("assets", exist_ok=True)
    data = fetch()
    print("stats:", data)
    svg = build(data)
    with open("assets/stats.svg", "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"wrote assets/stats.svg ({len(svg)/1024:.1f} KB)")

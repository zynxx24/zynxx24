"""Build the SVG cards shown on the GitHub profile README.

Style: neo-brutal (thick black outlines, hard 6px offset shadows, flat bright fills),
picked with SquidWings' style_pick. Every number comes from the GitHub REST API, so the
cards never show a statistic that is not real. Standard library only, so the daily
GitHub Action needs no installs.

    GITHUB_TOKEN=... python scripts/build_profile.py
"""

from __future__ import annotations

import base64
import json
import os
import urllib.request
from datetime import date, datetime
from pathlib import Path
from xml.sax.saxutils import escape

USER = "zynxx24"
ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
FONTS = ASSETS / "fonts"

PINK, CYAN, YELLOW = "#FF90E8", "#90F1EF", "#FFE14D"
THEMES = {
    # line = outlines and hard shadows; panel = fill for neutral blocks; text = text on panel.
    "light": {"line": "#000000", "panel": "#FFFDF5", "text": "#000000", "muted": "#3D3A33"},
    "dark": {"line": "#FFFDF5", "panel": "#1A1814", "text": "#FFFDF5", "muted": "#D6D1C4"},
}
INK = "#000000"  # text on the bright fills is always black (all three fills are > 10:1)

FEATURED = [
    {
        "repo": "SquidWings",
        "fill": PINK,
        "blurb": "Open-source AI agent for the terminal and the web, in Bahasa Indonesia. Runs on any OpenAI-compatible model.",
        "stack": "Python · CLI · Web UI",
    },
    {
        "repo": "CateringKu-ZynxWira-",
        "title": "CateringKu",
        "fill": YELLOW,
        "blurb": "Catering marketplace with customer, vendor and admin roles, promo codes and server-side pricing.",
        "stack": "Laravel 13 · Vue 3 · Inertia",
    },
    {
        "repo": "KasTep",
        "fill": CYAN,
        "blurb": "Offline-first Android app that tracks our class cash for XII PPLG.",
        "stack": "Kotlin · Jetpack Compose",
    },
    {
        "repo": "Kas-XIIPPLG---cash-management",
        "title": "Kas XII PPLG",
        "fill": PINK,
        "blurb": "Class cash dashboard on the web, backed by a small HTTP API written in C.",
        "stack": "C · HTML · JavaScript",
    },
]

STACK = [
    ("Python", PINK), ("PHP", YELLOW), ("Laravel", CYAN), ("Vue", PINK), ("TypeScript", YELLOW),
    ("React", CYAN), ("Next.js", PINK), ("Node.js", YELLOW), ("Kotlin", CYAN),
    ("Jetpack Compose", PINK), ("C", YELLOW), ("Tailwind", CYAN), ("Linux", PINK), ("Git", YELLOW),
]

METRICS = json.loads((FONTS / "metrics.json").read_text())


# --------------------------------------------------------------------------- GitHub API

def api(path: str):
    request = urllib.request.Request(f"https://api.github.com{path}", headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "profile-cards",
        **({"Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}"} if os.environ.get("GITHUB_TOKEN") else {}),
    })
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def collect() -> dict:
    user = api(f"/users/{USER}")
    repos = [r for r in api(f"/users/{USER}/repos?per_page=100&type=owner") if not r["fork"]]
    languages: dict[str, int] = {}
    for repo in repos:
        for name, size in api(f"/repos/{USER}/{repo['name']}/languages").items():
            languages[name] = languages.get(name, 0) + size
    return {
        "joined": user["created_at"][:10],
        "public_repos": user["public_repos"],
        "own_repos": len(repos),
        "stars": sum(r["stargazers_count"] for r in repos),
        "languages": languages,
        "last_push": max(r["pushed_at"] for r in repos)[:10],
        "repos": {r["name"]: r for r in repos},
    }


# --------------------------------------------------------------------------- SVG helpers

def text_width(text: str, font: str, size: float) -> float:
    table = METRICS[font]
    return sum(table.get(ch, 0.6) for ch in text) * size


def wrap(text: str, font: str, size: float, width: float, max_lines: int) -> list[str]:
    lines, current = [], ""
    for word in text.split():
        trial = f"{current} {word}".strip()
        if text_width(trial, font, size) <= width:
            current = trial
            continue
        lines.append(current)
        current = word
    lines.append(current)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        while text_width(lines[-1] + "...", font, size) > width:
            lines[-1] = lines[-1].rsplit(" ", 1)[0]
        lines[-1] += "..."
    return lines


def font_css() -> str:
    def embed(file: str) -> str:
        return base64.b64encode((FONTS / file).read_bytes()).decode()
    return (
        "@font-face{font-family:'Unbounded';font-weight:800;"
        f"src:url(data:font/woff2;base64,{embed('Unbounded-800.woff2')}) format('woff2')}}"
        "@font-face{font-family:'Space Grotesk';font-weight:300 700;"
        f"src:url(data:font/woff2;base64,{embed('SpaceGrotesk.woff2')}) format('woff2')}}"
        ".h{font-family:'Unbounded',sans-serif;font-weight:800}"
        ".b{font-family:'Space Grotesk',sans-serif;font-weight:500}"
        ".s{font-family:'Space Grotesk',sans-serif;font-weight:700}"
    )


def svg(width: int, height: int, title: str, body: str, extra_css: str = "") -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="t">'
        f'<title id="t">{escape(title)}</title><style>{font_css()}{extra_css}</style>{body}</svg>\n'
    )


def block(x, y, w, h, fill, theme, radius=10, shadow=6, stroke=3) -> str:
    """A neo-brutal slab: hard offset shadow, then the filled outlined shape."""
    line = THEMES[theme]["line"]
    return (
        f'<rect x="{x + shadow}" y="{y + shadow}" width="{w}" height="{h}" rx="{radius}" fill="{line}"/>'
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}" '
        f'stroke="{line}" stroke-width="{stroke}"/>'
    )


def label(x, y, text, fill, theme, size=15, rotate=0.0, color=INK) -> tuple[str, float]:
    """A boxed sticker label; returns the markup and its width."""
    w = text_width(text, "SpaceGrotesk-700", size) + 26
    h = size + 18
    transform = f' transform="rotate({rotate} {x + w / 2} {y + h / 2})"' if rotate else ""
    markup = (
        f"<g{transform}>{block(x, y, w, h, fill, theme, radius=7, shadow=4, stroke=2.5)}"
        f'<text class="s" x="{x + 13}" y="{y + h / 2 + size * 0.35}" font-size="{size}" fill="{color}">'
        f"{escape(text)}</text></g>"
    )
    return markup, w


# --------------------------------------------------------------------------- cards

def banner(theme: str) -> str:
    t = THEMES[theme]
    w, h = 880, 330
    body = block(4, 4, w - 16, h - 18, t["panel"], theme, radius=16)
    chip, _ = label(36, 34, "XII PPLG · SMKN 2 Kuta Selatan, Bali", CYAN, theme)
    body += chip
    body += f'<text class="h" x="36" y="150" font-size="76" fill="{t["text"]}">Zyn</text>'
    body += f'<text class="s" x="40" y="186" font-size="20" fill="{t["muted"]}">@{USER}</text>'
    intro = "Student developer. I build an AI agent, Laravel web apps and Android cash apps for my class."
    for i, line in enumerate(wrap(intro, "SpaceGrotesk-500", 21, 470, 3)):
        body += f'<text class="b" x="36" y="{232 + i * 29}" font-size="21" fill="{t["text"]}">{escape(line)}</text>'

    # Stickers on the right, slightly crooked like they were slapped on by hand.
    for (text, fill, rot), (sx, sy) in zip(
        [("AI agent", PINK, -5), ("Laravel + Vue", YELLOW, 3), ("Kotlin", CYAN, -2), ("C", PINK, 6)],
        [(600, 52), (612, 118), (640, 184), (770, 190)],
    ):
        markup, _ = label(sx, sy, text, fill, theme, size=19, rotate=rot)
        body += markup

    # One line of terminal, with the only motion on the card: a blinking cursor.
    prompt = "$ building SquidWings"
    px = 600
    body += f'<text class="s" x="{px}" y="276" font-size="17" fill="{t["text"]}">{escape(prompt)}</text>'
    cursor_x = px + text_width(prompt, "SpaceGrotesk-700", 17) + 4
    body += f'<rect class="cursor" x="{cursor_x:.1f}" y="262" width="10" height="18" fill="{t["text"]}"/>'
    css = (
        "@keyframes blink{50%{opacity:0}}.cursor{animation:blink 1.1s steps(1) infinite}"
        "@media (prefers-reduced-motion:reduce){.cursor{animation:none}}"
    )
    return svg(w, h, "Zyn (@zynxx24): student developer from Bali", body, css)


def project_card(spec: dict, repo: dict, theme: str) -> str:
    w, h = 430, 250
    title = spec.get("title", spec["repo"])
    body = block(4, 4, w - 16, h - 18, spec["fill"], theme, radius=14)
    # Chips sit on a bright fill, so they keep black outlines in both themes.
    lang, lang_w = label(24, 22, repo.get("language") or "Code", THEMES["light"]["panel"], "light", size=14)
    body += lang
    stars = repo["stargazers_count"]
    if stars:
        star_markup, _ = label(24 + lang_w + 14, 22, f"{stars} star" + ("" if stars == 1 else "s"), "#FFFFFF", "light", size=14)
        body += star_markup
    body += f'<text class="h" x="24" y="104" font-size="27" fill="{INK}">{escape(title)}</text>'
    for i, line in enumerate(wrap(spec["blurb"], "SpaceGrotesk-500", 17, w - 64, 3)):
        body += f'<text class="b" x="24" y="{138 + i * 23}" font-size="17" fill="{INK}">{escape(line)}</text>'
    body += f'<text class="s" x="24" y="{h - 36}" font-size="14" fill="{INK}">{escape(spec["stack"])}</text>'
    return svg(w, h, f"{title}: {spec['blurb']}", body)


def stack_card(theme: str) -> str:
    w = 880
    x, y, rows = 8, 10, 1
    body = ""
    for text, fill in STACK:
        width = text_width(text, "SpaceGrotesk-700", 17) + 26
        if x + width > w - 16:
            x, y, rows = 8, y + 56, rows + 1
        markup, width = label(x, y, text, fill, theme, size=17)
        body += markup
        x += width + 16
    return svg(w, 10 + rows * 56, "Languages and tools: " + ", ".join(t for t, _ in STACK), body)


def stats_card(data: dict, theme: str) -> str:
    t = THEMES[theme]
    w, h = 880, 232
    body = block(4, 4, w - 16, h - 18, t["panel"], theme, radius=16)
    years = (date.today() - datetime.fromisoformat(data["joined"]).date()).days // 365
    tiles = [
        (str(data["own_repos"]), "own public repos", YELLOW),
        (str(data["stars"]), "stars received", PINK),
        (f"{years}+" if years else "<1", "years on GitHub", CYAN),
    ]
    for i, (value, caption, fill) in enumerate(tiles):
        tx = 30 + i * 150
        body += block(tx, 30, 130, 120, fill, theme, radius=10, shadow=5, stroke=2.5)
        body += f'<text class="h" x="{tx + 16}" y="96" font-size="38" fill="{INK}">{escape(value)}</text>'
        for j, line in enumerate(wrap(caption, "SpaceGrotesk-700", 14, 100, 2)):
            body += f'<text class="s" x="{tx + 16}" y="{120 + j * 17}" font-size="14" fill="{INK}">{escape(line)}</text>'

    # Languages by code size across own repositories (GitHub's linguist byte counts).
    total = sum(data["languages"].values()) or 1
    ranked = sorted(data["languages"].items(), key=lambda kv: -kv[1])
    top, rest = ranked[:5], sum(v for _, v in ranked[5:])
    if rest:
        top.append(("Other", rest))
    fills = [PINK, YELLOW, CYAN, PINK, YELLOW, CYAN]
    bx, by, bw, bh = 500, 44, 340, 34
    body += f'<text class="s" x="{bx}" y="{by - 10}" font-size="15" fill="{t["text"]}">Languages by code size</text>'
    body += f'<rect x="{bx + 5}" y="{by + 5}" width="{bw}" height="{bh}" rx="6" fill="{t["line"]}"/>'
    cursor = bx
    legend_y = by + bh + 34
    for i, (name, size) in enumerate(top):
        seg = bw * size / total
        body += (
            f'<rect x="{cursor:.1f}" y="{by}" width="{max(seg, 2):.1f}" height="{bh}" fill="{fills[i]}" '
            f'stroke="{t["line"]}" stroke-width="2.5"/>'
        )
        cursor += seg
        col, row = i % 2, i // 2
        lx, ly = bx + col * 175, legend_y + row * 30
        body += f'<rect x="{lx}" y="{ly - 13}" width="16" height="16" rx="3" fill="{fills[i]}" stroke="{t["line"]}" stroke-width="2"/>'
        body += (
            f'<text class="s" x="{lx + 26}" y="{ly}" font-size="15" fill="{t["text"]}">'
            f'{escape(name)} <tspan class="b" fill="{t["muted"]}">{size / total * 100:.1f}%</tspan></text>'
        )

    note = f"Live from the GitHub API. Last push {data['last_push']}."
    body += f'<text class="b" x="30" y="{h - 36}" font-size="14" fill="{t["muted"]}">{escape(note)}</text>'
    summary = (
        f"{data['own_repos']} own public repositories, {data['stars']} stars, top languages "
        + ", ".join(f"{n} {s / total * 100:.0f}%" for n, s in top)
    )
    return svg(w, h, summary, body)


# --------------------------------------------------------------------------- main

def write(name: str, content: str) -> None:
    path = ASSETS / name
    if not path.exists() or path.read_text() != content:
        path.write_text(content)
        print("wrote", path.relative_to(ROOT))


def main() -> None:
    data = collect()
    for theme in THEMES:
        write(f"banner-{theme}.svg", banner(theme))
        write(f"stack-{theme}.svg", stack_card(theme))
        write(f"stats-{theme}.svg", stats_card(data, theme))
        for spec in FEATURED:
            repo = data["repos"].get(spec["repo"])
            if repo is None:
                raise SystemExit(f"Featured repository {spec['repo']} is missing or private; update FEATURED.")
            slug = spec.get("title", spec["repo"]).lower().replace(" ", "-")
            write(f"project-{slug}-{theme}.svg", project_card(spec, repo, theme))


if __name__ == "__main__":
    main()

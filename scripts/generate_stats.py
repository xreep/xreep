#!/usr/bin/env python3
"""Nightly generator. Standard library only.
Writes assets/{stats,streak,langs,year}.svg and the projects block in README.md.
Usage:  GITHUB_TOKEN=... GH_LOGIN=xreep python3 scripts/generate_stats.py"""
import html, math, json, os, sys, urllib.request
from datetime import datetime, timedelta, timezone
from svgkit import ROOT, CHAR_W, FONT_SIZE, RAMP, svg, write_if_changed

LOGIN = os.environ.get("GH_LOGIN") or "xreep"
TOKEN = os.environ.get("GITHUB_TOKEN")
LANGS_INCLUDE_FORKS = False   # forks distort language bytes; they are still LISTED as projects
TOP_LANGS = 8
W = 800

Q_USER = """query($login:String!,$from:DateTime!,$to:DateTime!){user(login:$login){
 followers{totalCount}
 contributionsCollection(from:$from,to:$to){
  totalCommitContributions totalIssueContributions
  totalPullRequestContributions totalPullRequestReviewContributions
  contributionCalendar{totalContributions weeks{contributionDays{date contributionCount}}}}}}"""

Q_REPOS = """query($login:String!,$after:String){user(login:$login){
 repositories(privacy:PUBLIC,ownerAffiliations:OWNER,first:100,after:$after,
              orderBy:{field:PUSHED_AT,direction:DESC}){
  pageInfo{hasNextPage endCursor}
  nodes{name url description homepageUrl isFork isArchived stargazerCount pushedAt
   primaryLanguage{name}
   languages(first:20,orderBy:{field:SIZE,direction:DESC}){edges{size node{name}}}}}}}"""

def gql(query, variables):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Authorization": f"bearer {TOKEN}", "User-Agent": "profile-generator"})
    with urllib.request.urlopen(req, timeout=60) as r:
        out = json.load(r)
    if out.get("errors"):
        raise SystemExit(f"GraphQL error: {out['errors']}")
    return out["data"]["user"]

def window():
    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=364)
    return today, start, f"{start}T00:00:00Z", f"{today}T23:59:59Z"

def fetch(frm, to):
    u = gql(Q_USER, {"login": LOGIN, "from": frm, "to": to})
    repos, after = [], None
    while True:                                   # every public repo, all pages
        r = gql(Q_REPOS, {"login": LOGIN, "after": after})["repositories"]
        repos += r["nodes"]
        if not r["pageInfo"]["hasNextPage"]:
            break
        after = r["pageInfo"]["endCursor"]
    return u, repos

def t(x, y, s, size=13, cls="fg", weight=400, extra=""):
    return (f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" class="{cls}" {extra}>'
            f'{html.escape(str(s), quote=False)}</text>')

def hero(u, weeks):
    cc = u["contributionsCollection"]
    total = cc["contributionCalendar"]["totalContributions"]
    wk = [sum(d["contributionCount"] for d in w["contributionDays"]) for w in weeks]
    mx = max(wk + [1]); x0, x1, y0, y1 = 340, W, 24, 92
    pts = [(x0 + i * (x1 - x0) / max(len(wk) - 1, 1), y1 - v / mx * (y1 - y0)) for i, v in enumerate(wk)]
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    area = f"{x0},{y1} {line} {x1},{y1}"
    b = t(0, 56, f"{total:,}", 48, "fg", 700) + t(0, 80, "contributions in the past year", 13, "dim")
    b += f'<polygon points="{area}" class="accf" opacity=".14"/>'
    b += f'<polyline points="{line}" class="accs" fill="none" stroke-width="2" stroke-linejoin="round"/>'
    b += t(x0, 110, "weekly total", 11, "dim")
    items = [("commits", cc["totalCommitContributions"]), ("pull requests", cc["totalPullRequestContributions"]),
             ("issues", cc["totalIssueContributions"]), ("reviews", cc["totalPullRequestReviewContributions"]),
             ("followers", u["followers"]["totalCount"])]
    for i, (k, v) in enumerate(items):
        x = i * 160
        b += t(x, 138, f"{v:,}", 20, "fg", 700) + t(x, 156, k, 11, "dim")
    return svg(W, 170, b, label=f"{total} contributions in the past year")

def streaks(days, today):
    counts = {d["date"]: d["contributionCount"] for d in days}
    dates = sorted(counts)
    best = (0, None, None); run, rs = 0, None
    for d in dates:
        if counts[d] > 0:
            run, rs = (run + 1, rs) if run else (1, d)
            if run > best[0]: best = (run, rs, d)
        else:
            run = 0
    cur, cur_end = 0, None
    d = today if counts.get(str(today), 0) > 0 else today - timedelta(days=1)
    while counts.get(str(d), 0) > 0:
        cur += 1; cur_end = cur_end or d; d -= timedelta(days=1)
    dash = "\u2013"
    cur_rng = f"{d + timedelta(days=1)} {dash} {cur_end}" if cur else "\u2014"
    best_rng = f"{best[1]} {dash} {best[2]}" if best[0] else "\u2014"
    b = t(0, 46, cur, 44, "fg", 700) + t(len(str(cur)) * 26.4 + 10, 46, "days", 14, "dim")
    b += t(0, 70, "current streak", 13, "dim") + t(0, 90, cur_rng, 12, "dim")
    b += t(400, 46, best[0], 44, "fg", 700) + t(400 + len(str(best[0])) * 26.4 + 10, 46, "days", 14, "dim")
    b += t(400, 70, "longest streak, past year", 13, "dim") + t(400, 90, best_rng, 12, "dim")
    return svg(W, 108, b, label=f"current streak {cur} days, longest {best[0]} days")

def langs(repos):
    byt, cnt = {}, {}
    for r in repos:
        if r["isFork"] and not LANGS_INCLUDE_FORKS: continue
        for e in r["languages"]["edges"]:
            n = e["node"]["name"]; byt[n] = byt.get(n, 0) + e["size"]; cnt[n] = cnt.get(n, 0) + 1
    tot = sum(byt.values()); rows = sorted(byt.items(), key=lambda kv: -kv[1])[:TOP_LANGS]
    if not rows:
        return svg(W, 40, t(0, 24, "no language data yet", 13, "dim"), label="languages")
    b = t(0, 14, "language", 11, "dim") + t(600, 14, "share", 11, "dim") + t(690, 14, "repos", 11, "dim")
    for i, (n, v) in enumerate(rows):
        y = 40 + i * 26; pct = v / tot * 100
        b += t(0, y, n, 13) + f'<rect x="170" y="{y - 11}" width="{max(pct, .5) * 4.2:.1f}" height="12" class="accf" rx="2"/>'
        b += t(600, y, f"{pct:.1f}%", 13) + t(690, y, cnt[n], 13, "dim")
    return svg(W, 40 + len(rows) * 26, b, label="top languages by bytes")

def year(weeks):
    PX, LH = 14, 17
    allc = [d["contributionCount"] for w in weeks for d in w["contributionDays"]]
    mx = max(allc + [1]); rows = [[] for _ in range(7)]
    for wi, w in enumerate(weeks):
        for r in range(7): rows[r].append(" ")
        for d in w["contributionDays"]:
            dt = datetime.strptime(d["date"], "%Y-%m-%d").date(); r = (dt.weekday() + 1) % 7; c = d["contributionCount"]
            if c == 0: rows[r][wi] = "."
            else:
                lvl = max(1, math.ceil(math.sqrt(c / mx) * 11)); rows[r][wi] = RAMP[min(12, 1 + lvl)]
    b, last_m, last_x = "", None, -99
    for wi, w in enumerate(weeks):
        dt = datetime.strptime(w["contributionDays"][0]["date"], "%Y-%m-%d")
        if dt.month != last_m and wi * PX - last_x >= 40:
            b += t(wi * PX, 12, dt.strftime("%b").lower(), 11, "dim"); last_x = wi * PX
        last_m = dt.month
    for r, row in enumerate(rows):
        spans = "".join('<tspan class="dim">.</tspan>' if ch == "." else html.escape(ch, quote=False) for ch in row)
        b += (f'<text x="0" y="{34 + r * LH}" font-size="{FONT_SIZE}" class="fg" letter-spacing="{PX - CHAR_W:.2f}" '
              f'xml:space="preserve">{spans}</text>')
    b += t(0, 34 + 7 * LH + 8, "less  " + RAMP[1:] + "  more", 11, "dim", extra='xml:space="preserve"')
    return svg(W, 34 + 7 * LH + 18, b, label="contribution calendar, one character per day")

def projects_block(repos):
    """EVERY public repo. No top-N, no collapsing, no cutoff."""
    if not repos:
        return "<samp>no public repositories yet</samp>"
    out = [f"<samp>{len(repos)} public repositories \u00b7 all listed</samp>", ""]
    for r in repos:
        desc = html.escape((r["description"] or "").strip(), quote=False)
        head = f"- **[{r['name']}]({r['url']})**" + (f" \u2014 {desc}" if desc else "")
        meta = [r["primaryLanguage"]["name"] if r["primaryLanguage"] else "no code",
                f"\u2605 {r['stargazerCount']}", f"pushed {r['pushedAt'][:7]}"]
        if r["isFork"]: meta.append("fork")
        if r["isArchived"]: meta.append("archived")
        live = f" \u00b7 [live]({r['homepageUrl']})" if r["homepageUrl"] else ""
        sep = " \u00b7 "
        out.append(f"{head}<br><samp>{sep.join(meta)}</samp>{live}")
    return "\n".join(out)

def update_readme(block):
    p = ROOT / "README.md"; s = p.read_text(); a, z = "<!--PROJECTS:START-->", "<!--PROJECTS:END-->"
    i, j = s.find(a), s.find(z)
    if i < 0 or j < i:
        print("README markers missing; projects not updated"); return
    write_if_changed(p, s[:i + len(a)] + "\n" + block + "\n" + s[j:])

def main():
    if not TOKEN:
        sys.exit("GITHUB_TOKEN not set")
    today, start, frm, to = window()
    u, repos = fetch(frm, to)
    weeks = u["contributionsCollection"]["contributionCalendar"]["weeks"]
    days = [d for w in weeks for d in w["contributionDays"]]
    A = ROOT / "assets"
    write_if_changed(A / "stats.svg", hero(u, weeks))
    write_if_changed(A / "streak.svg", streaks(days, today))
    write_if_changed(A / "langs.svg", langs(repos))
    write_if_changed(A / "year.svg", year(weeks))
    update_readme(projects_block(repos))
    print(f"ok: {len(repos)} repos, {len(days)} days")

if __name__ == "__main__":
    main()

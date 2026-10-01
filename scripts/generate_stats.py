#!/usr/bin/env python3
"""Nightly generator. Standard library only.
Writes assets/{stats,streak,langs,year}.svg and the activity + projects blocks in README.md.
Usage:  GITHUB_TOKEN=... GH_LOGIN=xreep python3 scripts/generate_stats.py"""
import html, math, json, os, sys, urllib.request
from datetime import datetime, timedelta, timezone
from svgkit import ROOT, CHAR_W, FONT_SIZE, RAMP, svg, write_if_changed

LOGIN = os.environ.get("GH_LOGIN") or "xreep"
TOKEN = os.environ.get("GITHUB_TOKEN")
LANGS_INCLUDE_FORKS = False   # forks distort language bytes; they are still LISTED as projects
TOP_LANGS = 8
W = 800
TZ = timezone(timedelta(minutes=int(os.environ.get("TZ_OFFSET_MIN", "330"))))
TZ_NAME = os.environ.get("TZ_NAME", "Asia/Kolkata")
MAX_PAGES = 20

Q_USER = """query($login:String!,$from:DateTime!,$to:DateTime!){user(login:$login){
 id followers{totalCount}
 contributionsCollection(from:$from,to:$to){
  totalCommitContributions totalIssueContributions
  totalPullRequestContributions totalPullRequestReviewContributions
  contributionCalendar{totalContributions weeks{contributionDays{date contributionCount}}}}}}"""

Q_REPOS = """query($login:String!,$after:String){user(login:$login){
 repositories(privacy:PUBLIC,ownerAffiliations:OWNER,first:100,after:$after,
              orderBy:{field:PUSHED_AT,direction:DESC}){
  pageInfo{hasNextPage endCursor}
  nodes{name url description homepageUrl isFork isArchived stargazerCount pushedAt diskUsage
   primaryLanguage{name}
   languages(first:20,orderBy:{field:SIZE,direction:DESC}){edges{size node{name}}}}}}}"""

Q_COMMITS = """query($owner:String!,$name:String!,$id:ID!,$after:String){repository(owner:$owner,name:$name){
 defaultBranchRef{target{... on Commit{history(first:100,after:$after,author:{id:$id}){
  pageInfo{hasNextPage endCursor} nodes{authoredDate}}}}}}}"""

def gql(query, variables):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Authorization": f"bearer {TOKEN}", "User-Agent": "profile-generator"})
    with urllib.request.urlopen(req, timeout=60) as r:
        out = json.load(r)
    if out.get("errors"):
        raise SystemExit(f"GraphQL error: {out['errors']}")
    return out["data"]

def window():
    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=364)
    return today, start, f"{start}T00:00:00Z", f"{today}T23:59:59Z"

def fetch(frm, to):
    u = gql(Q_USER, {"login": LOGIN, "from": frm, "to": to})["user"]
    repos, after = [], None
    while True:                                   # every public repo, all pages
        r = gql(Q_REPOS, {"login": LOGIN, "after": after})["user"]["repositories"]
        repos += r["nodes"]
        if not r["pageInfo"]["hasNextPage"]:
            break
        after = r["pageInfo"]["endCursor"]
    return u, repos

def commit_times(uid, repos):
    out = []
    for r in repos:
        if r["isFork"]:
            continue
        after = None
        for _ in range(MAX_PAGES):
            d = gql(Q_COMMITS, {"owner": LOGIN, "name": r["name"], "id": uid, "after": after})["repository"]
            ref = d and d["defaultBranchRef"]
            if not ref:
                break
            h = ref["target"]["history"]
            out += [n["authoredDate"] for n in h["nodes"]]
            if not h["pageInfo"]["hasNextPage"]:
                break
            after = h["pageInfo"]["endCursor"]
    return [datetime.fromisoformat(x.replace("Z", "+00:00")).astimezone(TZ) for x in out]

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

HEAT_CSS = """<style>
.l0{fill:#ebedf0}.l1{fill:#c6dcfb}.l2{fill:#79aef5}.l3{fill:#3b82e6}.l4{fill:#0b5cc4}
@media (prefers-color-scheme:dark){.l0{fill:#1c2129}.l1{fill:#0e3366}.l2{fill:#1957a8}.l3{fill:#2f7fe0}.l4{fill:#79b8ff}}
</style>"""

def year(weeks, total):
    C, G, L, T = 11, 3, 30, 24
    P = C + G
    nz = sorted(d["contributionCount"] for w in weeks for d in w["contributionDays"] if d["contributionCount"] > 0)
    q = lambda p: nz[min(len(nz) - 1, int(p * len(nz)))] if nz else 1
    th = (q(.25), q(.5), q(.75))
    lvl = lambda c: 0 if c == 0 else 1 if c <= th[0] else 2 if c <= th[1] else 3 if c <= th[2] else 4
    b, last_m, last_x, best = HEAT_CSS, None, -99, (0, "")
    for wi, w in enumerate(weeks):
        x = L + wi * P
        dt0 = datetime.strptime(w["contributionDays"][0]["date"], "%Y-%m-%d")
        if dt0.month != last_m and x - last_x >= 36:
            b += t(x, T - 9, dt0.strftime("%b").lower(), 11, "dim"); last_x = x
        last_m = dt0.month
        delay = wi * 0.025; dur = delay + 0.35
        g = (f'<g><animate attributeName="opacity" values="0;0;1" '
             f'keyTimes="0;{delay / dur:.3f};1" dur="{dur:.2f}s" fill="freeze"/>')
        for d in w["contributionDays"]:
            dt = datetime.strptime(d["date"], "%Y-%m-%d"); r = (dt.weekday() + 1) % 7; c = d["contributionCount"]
            if c > best[0]: best = (c, d["date"])
            g += f'<rect x="{x}" y="{T + r * P}" width="{C}" height="{C}" rx="2.5" class="l{lvl(c)}"/>'
        b += g + "</g>"
    for r, name in ((1, "mon"), (3, "wed"), (5, "fri")):
        b += t(0, T + r * P + 9, name, 10, "dim")
    fy = T + 7 * P + 20
    b += t(L, fy, f"{total:,} contributions in the past year", 12, "fg", 700)
    if best[0]:
        b += t(L + 300, fy, f"busiest day {best[1]} \u00b7 {best[0]}", 11, "dim")
    lx = W - 5 * P - 34
    b += t(lx - 34, fy, "less", 10, "dim")
    for k in range(5):
        b += f'<rect x="{lx + k * P}" y="{fy - 10}" width="{C}" height="{C}" rx="2.5" class="l{k}"/>'
    b += t(lx + 5 * P + 4, fy, "more", 10, "dim")
    return svg(W, fy + 10, b, label=f"{total} contributions in the past year, heatmap")

def bar(pct, width=25):
    n = round(pct / 100 * width)
    return "\u2588" * n + "\u2591" * (width - n)

def row(label, value, pct):
    return f"{label:<25}{value:<20}{bar(pct)}   {pct:05.2f} %"

def pl(n, word):
    return f"{n:,} {word}" + ("" if n == 1 else "s")

def human_kb(kb):
    for unit in ("kB", "MB", "GB"):
        if kb < 1000:
            return f"{kb:.1f} {unit}"
        kb /= 1000
    return f"{kb:.1f} TB"

def activity_block(u, repos, times, today):
    total = u["contributionsCollection"]["contributionCalendar"]["totalContributions"]
    stars = sum(r["stargazerCount"] for r in repos)
    disk = sum(r.get("diskUsage") or 0 for r in repos)
    out = ["**\U0001f431 My GitHub Data**", "",
           f"> \U0001f4e6 {human_kb(disk)} used in GitHub's storage", ">",
           f"> \U0001f3c6 {pl(total, 'contribution')} in the past year", ">",
           f"> \U0001f4dc {len(repos)} public {'repository' if len(repos) == 1 else 'repositories'}", ">",
           f"> \u2b50 {pl(stars, 'star')} earned", ">",
           f"> \U0001f465 {pl(u['followers']['totalCount'], 'follower')}", ""]
    if not times:
        out.append("<samp>no commits found yet</samp>")
    else:
        n = len(times)
        slots = [("\U0001f31e Morning", 6, 12), ("\U0001f306 Daytime", 12, 18),
                 ("\U0001f303 Evening", 18, 24), ("\U0001f319 Night", 0, 6)]
        cnt = [sum(1 for x in times if a <= x.hour < z) for _, a, z in slots]
        title = "an Early \U0001f424" if cnt[0] + cnt[1] >= cnt[2] + cnt[3] else "a Night \U0001f989"
        out += [f"**I'm {title}**", "", "```text"]
        out += [row(lab, pl(c, "commit"), c / n * 100) for (lab, _, _), c in zip(slots, cnt)]
        out += ["```", ""]
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        dc = [sum(1 for x in times if x.weekday() == k) for k in range(7)]
        out += [f"\U0001f4c5 **I'm most productive on {days[dc.index(max(dc))]}**", "", "```text"]
        out += [row(dn, pl(c, "commit"), c / n * 100) for dn, c in zip(days, dc)]
        out += ["```", "", f"<sub>{n} commits across public repositories \u00b7 times in {TZ_NAME}</sub>", ""]
    out.append(f"<sub>last updated {today} \u00b7 drawn by this repository's own workflow, no third-party services</sub>")
    return "\n".join(out)

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

def update_readme(blocks):
    p = ROOT / "README.md"; s = p.read_text()
    for key, block in blocks.items():
        a, z = f"<!--{key}:START-->", f"<!--{key}:END-->"
        i, j = s.find(a), s.find(z)
        if i < 0 or j < i:
            print(f"README markers for {key} missing"); continue
        s = s[:i + len(a)] + "\n" + block + "\n" + s[j:]
    write_if_changed(p, s)

def main():
    if not TOKEN:
        sys.exit("GITHUB_TOKEN not set")
    today, start, frm, to = window()
    u, repos = fetch(frm, to)
    times = commit_times(u["id"], repos)
    weeks = u["contributionsCollection"]["contributionCalendar"]["weeks"]
    days = [d for w in weeks for d in w["contributionDays"]]
    total = u["contributionsCollection"]["contributionCalendar"]["totalContributions"]
    A = ROOT / "assets"
    write_if_changed(A / "stats.svg", hero(u, weeks))
    write_if_changed(A / "streak.svg", streaks(days, today))
    write_if_changed(A / "langs.svg", langs(repos))
    write_if_changed(A / "year.svg", year(weeks, total))
    update_readme({"ACTIVITY": activity_block(u, repos, times, today), "PROJECTS": projects_block(repos)})
    print(f"ok: {len(repos)} repos, {len(days)} days, {len(times)} commits")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Profile README stats in the anmol098/waka-readme-stats layout. Standard library only.
Fills the waka and projects sections of README.md.
Optional secret WAKATIME_API_KEY adds Code Time and This Week panels."""
import base64, html, json, os, sys, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOGIN = os.environ.get("GH_LOGIN") or "xreep"
TOKEN = os.environ.get("GITHUB_TOKEN")
WAKA = os.environ.get("WAKATIME_API_KEY", "").strip()
TZ = timezone(timedelta(minutes=int(os.environ.get("TZ_OFFSET_MIN", "330"))))
MAX_PAGES = 20

Q_USER = """query($login:String!,$from:DateTime!,$to:DateTime!){user(login:$login){
 id isHireable followers{totalCount}
 contributionsCollection(from:$from,to:$to){contributionCalendar{totalContributions}}}}"""

Q_REPOS = """query($login:String!,$after:String){user(login:$login){
 repositories(privacy:PUBLIC,ownerAffiliations:OWNER,first:100,after:$after,
              orderBy:{field:PUSHED_AT,direction:DESC}){
  pageInfo{hasNextPage endCursor}
  nodes{name url description homepageUrl isFork isArchived stargazerCount pushedAt diskUsage
   primaryLanguage{name}}}}}"""

Q_COMMITS = """query($owner:String!,$name:String!,$id:ID!,$after:String){repository(owner:$owner,name:$name){
 defaultBranchRef{target{... on Commit{history(first:100,after:$after,author:{id:$id}){
  pageInfo{hasNextPage endCursor} nodes{authoredDate additions}}}}}}}"""

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

def fetch(now):
    frm = f"{now.year}-01-01T00:00:00Z"
    u = gql(Q_USER, {"login": LOGIN, "from": frm, "to": now.strftime("%Y-%m-%dT%H:%M:%SZ")})["user"]
    repos, after = [], None
    while True:                                   # every public repo, all pages
        r = gql(Q_REPOS, {"login": LOGIN, "after": after})["user"]["repositories"]
        repos += r["nodes"]
        if not r["pageInfo"]["hasNextPage"]:
            break
        after = r["pageInfo"]["endCursor"]
    return u, repos

def commit_stats(uid, repos):
    times, lines = [], 0
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
            for n in h["nodes"]:
                times.append(datetime.fromisoformat(n["authoredDate"].replace("Z", "+00:00")).astimezone(TZ))
                lines += n["additions"] or 0
            if not h["pageInfo"]["hasNextPage"]:
                break
            after = h["pageInfo"]["endCursor"]
    return times, lines

def waka(path):
    if not WAKA:
        return None
    try:
        req = urllib.request.Request(f"https://wakatime.com/api/v1/users/current/{path}", headers={
            "Authorization": "Basic " + base64.b64encode(WAKA.encode()).decode(), "User-Agent": "profile-generator"})
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)["data"]
    except Exception as e:
        print(f"wakatime {path} skipped: {e}")
        return None

def bar(pct, width=25):
    n = round(pct / 100 * width)
    return "\u2588" * n + "\u2591" * (width - n)

def row(label, value, pct):
    return f"{label:<25}{value:<20}{bar(pct)}   {pct:05.2f} % "

def pl(n, word):
    return f"{n} {word}" + ("" if n == 1 else "s")

def human_kb(kb):
    for unit in ("kB", "MB", "GB"):
        if kb < 1000:
            return f"{kb:.1f} {unit}"
        kb /= 1000
    return f"{kb:.1f} TB"

def human_lines(n):
    if n >= 1_000_000:
        return f"{n / 1_000_000:.2f} million"
    if n >= 1_000:
        return f"{n / 1_000:.2f} thousand"
    return str(n)

def badge(label, msg):
    e = lambda s: urllib.parse.quote(s.replace("-", "--").replace("_", "__"), safe="")
    return f"![{label}](http://img.shields.io/badge/{e(label)}-{e(msg)}-blue?style=flat)"

def waka_rows(items, n=5):
    return [row(i["name"], i["text"], i["percent"]) for i in (items or [])[:n]] or ["No Activity Tracked This Week"]

def waka_block(u, repos, times, lines, now):
    out = []
    alltime = waka("all_time_since_today")
    if alltime:
        out += [badge("Code Time", alltime.get("text", "0 mins")), ""]
    out += [f"![Profile Views](https://komarev.com/ghpvc/?username={LOGIN}&label=Profile%20Views&color=blue&style=flat)", ""]
    out += [badge("From Hello World I've Written", f"{human_lines(lines)} lines of code"), ""]
    hire = "\U0001f4bc Opted to Hire" if u["isHireable"] else "\U0001f6ab Not Opted to Hire"
    out += ["**\U0001f431 My GitHub Data** ", "",
            f"> \U0001f4e6 {human_kb(sum(r.get('diskUsage') or 0 for r in repos))} Used in GitHub's Storage ", " > ",
            f"> \U0001f3c6 {u['contributionsCollection']['contributionCalendar']['totalContributions']:,} Contributions in the Year {now.year}", " > ",
            f"> {hire}", " > ",
            f"> \U0001f4dc {len(repos)} Public Repositories ", " > ",
            f"> \u2b50 {pl(sum(r['stargazerCount'] for r in repos), 'Star')} Earned ", " > ",
            f"> \U0001f465 {pl(u['followers']['totalCount'], 'Follower')} ", ""]
    if times:
        n = len(times)
        slots = [("\U0001f31e Morning", 6, 12), ("\U0001f306 Daytime", 12, 18),
                 ("\U0001f303 Evening", 18, 24), ("\U0001f319 Night", 0, 6)]
        cnt = [sum(1 for x in times if a <= x.hour < z) for _, a, z in slots]
        title = "an Early \U0001f424" if cnt[0] + cnt[1] >= cnt[2] + cnt[3] else "a Night \U0001f989"
        out += [f"**I'm {title}** ", "", "```text"]
        out += [row(lab, pl(c, "commit"), c / n * 100) for (lab, _, _), c in zip(slots, cnt)]
        out += ["```"]
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        dc = [sum(1 for x in times if x.weekday() == k) for k in range(7)]
        out += [f"\U0001f4c5 **I'm Most Productive on {days[dc.index(max(dc))]}** ", "", "```text"]
        out += [row(dn, pl(c, "commit"), c / n * 100) for dn, c in zip(days, dc)]
        out += ["```", ""]
    week = waka("stats/last_7_days")
    if week:
        out += ["", "\U0001f4ca **This Week I Spent My Time On** ", "", "```text",
                f"\U0001f551\ufe0e Time Zone: {week.get('timezone', 'UTC')}", "",
                "\U0001f4ac Programming Languages: ", *waka_rows(week.get("languages")), "",
                "\U0001f525 Editors: ", *waka_rows(week.get("editors")), "",
                "\U0001f4bb Operating System: ", *waka_rows(week.get("operating_systems")), "```", ""]
    cnt = {}
    for r in repos:
        if not r["isFork"] and r["primaryLanguage"]:
            k = r["primaryLanguage"]["name"]; cnt[k] = cnt.get(k, 0) + 1
    if cnt:
        tot = sum(cnt.values()); top = sorted(cnt.items(), key=lambda kv: -kv[1])[:5]
        out += [f"**I Mostly Code in {top[0][0]}** ", "", "```text"]
        out += [row(k, pl(v, "repo"), v / tot * 100) for k, v in top]
        out += ["```", ""]
    out += ["", "", "", f" Last Updated on {now.strftime('%d/%m/%Y %H:%M:%S')} UTC"]
    return "\n".join(out)

def projects_block(repos):
    """EVERY public repo. No top-N, no collapsing, no cutoff."""
    if not repos:
        return "No public repositories yet."
    out = []
    for r in repos:
        desc = html.escape((r["description"] or "").strip(), quote=False)
        head = f"- **[{r['name']}]({r['url']})**" + (f" \u2014 {desc}" if desc else "")
        meta = [r["primaryLanguage"]["name"] if r["primaryLanguage"] else "no code",
                f"\u2b50 {r['stargazerCount']}", f"updated {r['pushedAt'][:7]}"]
        if r["isFork"]: meta.append("fork")
        if r["isArchived"]: meta.append("archived")
        live = f" \u00b7 [live]({r['homepageUrl']})" if r["homepageUrl"] else ""
        sep = " \u00b7 "
        out.append(f"{head}<br><sub>{sep.join(meta)}</sub>{live}")
    return "\n".join(out)

def update_readme(blocks):
    p = ROOT / "README.md"; s = p.read_text()
    for key, block in blocks.items():
        a, z = f"<!--START_SECTION:{key}-->", f"<!--END_SECTION:{key}-->"
        i, j = s.find(a), s.find(z)
        if i < 0 or j < i:
            print(f"README markers for {key} missing"); continue
        s = s[:i + len(a)] + "\n" + block + "\n" + s[j:]
    if not p.exists() or p.read_text() != s:
        p.write_text(s)

def main():
    if not TOKEN:
        sys.exit("GITHUB_TOKEN not set")
    now = datetime.now(timezone.utc).replace(microsecond=0)
    u, repos = fetch(now)
    times, lines = commit_stats(u["id"], repos)
    update_readme({"waka": waka_block(u, repos, times, lines, now), "projects": projects_block(repos)})
    print(f"ok: {len(repos)} repos, {len(times)} commits, {lines} lines")

if __name__ == "__main__":
    main()

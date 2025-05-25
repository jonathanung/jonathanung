import os
import math
import requests
import svgwrite
from dateutil import parser
from datetime import date, timedelta

# ─── CONFIG ───────────────────────────────────────────
GH_TOKEN   = os.getenv("GH_TOKEN")
GL_TOKEN   = os.getenv("GL_TOKEN")
GH_USER    = "jonathanung"
GL_USER    = "jonathan.keith.ung"
# ──────────────────────────────────────────────────────

def fetch_github_calendar():
    url = "https://api.github.com/graphql"
    query = """
    query($login:String!) {
      user(login:$login) {
        contributionsCollection {
          contributionCalendar {
            weeks {
              contributionDays {
                date
                contributionCount
              }
            }
          }
        }
      }
    }
    """
    resp = requests.post(url,
      json={'query': query, 'variables': {'login': GH_USER}},
      headers={'Authorization': f'bearer {GH_TOKEN}'}
    )
    resp.raise_for_status()
    data = resp.json()["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    cal = {}
    for week in data:
        for day in week["contributionDays"]:
            cal[day["date"]] = day["contributionCount"]
    return cal

def fetch_gitlab_events():
    # first get user ID
    users = requests.get("https://gitlab.com/api/v4/users",
      headers={'PRIVATE-TOKEN': GL_TOKEN},
      params={'username': GL_USER}
    ).json()
    uid = users[0]["id"]

    cal = {}
    page = 1
    one_year_ago = date.today() - timedelta(days=365)
    while True:
        resp = requests.get(f"https://gitlab.com/api/v4/users/{uid}/events",
          headers={'PRIVATE-TOKEN': GL_TOKEN},
          params={'action':'created', 'per_page':100, 'page': page}
        )
        resp.raise_for_status()
        events = resp.json()
        if not events: break

        for ev in events:
            dt = parser.isoparse(ev["created_at"]).date()
            if dt < one_year_ago:
                return cal
            cal[str(dt)] = cal.get(str(dt), 0) + 1

        page += 1

    return cal

def merge_calendars(gh, gl):
    merged = {}
    all_dates = set(gh) | set(gl)
    for d in all_dates:
        merged[d] = gh.get(d, 0) + gl.get(d, 0)
    return merged

def draw_heatmap(cal_map, filename="combined-heatmap.svg"):
    # Build a week-by-week grid for the last 52 weeks
    end = date.today()
    start = end - timedelta(days=365)
    # Build list of all dates
    dates = [start + timedelta(days=i) for i in range(366)]
    # Group by week: ISO calendar week starting Mondays
    weeks = []
    week = []
    for d in dates:
        # pad the first week so that its length is multiple of 7
        if d.weekday() == 0 and week:
            weeks.append(week)
            week = []
        week.append(d)
    weeks.append(week)

    # SVG parameters
    cell = 12
    gap  = 4
    rows = 7
    cols = len(weeks)
    maxv = max(cal_map.values()) or 1

    dwg = svgwrite.Drawing(filename,
        size=(cols*(cell+gap), rows*(cell+gap)),
        profile='tiny'
    )
    for x, week in enumerate(weeks):
        for y in range(7):
            try:
                d = week[y]
            except IndexError:
                continue
            c = cal_map.get(str(d), 0)
            # scale fill: 0 → #ebedf0, max → #216e39
            intensity = int((c / maxv)**0.5 * 4)  # sqrt scale
            colors = ["#ebedf0", "#c6e48b", "#7bc96f", "#239a3b", "#196127"]
            fill = colors[intensity]
            dwg.add(dwg.Rect(
                insert=(x*(cell+gap), y*(cell+gap)),
                size=(cell, cell),
                fill=fill,
                stroke='none'
            ))
    dwg.save()

if __name__ == "__main__":
    print("Fetching GitHub…")
    gh_cal = fetch_github_calendar()
    print("Fetching GitLab…")
    gl_cal = fetch_gitlab_events()
    print("Merging…")
    merged = merge_calendars(gh_cal, gl_cal)
    print("Drawing SVG…")
    draw_heatmap(merged)
    print("Done → combined-heatmap.svg")

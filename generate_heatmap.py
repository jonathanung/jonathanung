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
    
    # Group by week: Sunday to Saturday
    weeks = []
    current_week = []
    
    for d in dates:
        # Start a new week on Sunday (weekday=6)
        if d.weekday() == 6 and current_week:  # 6 is Sunday in Python's datetime
            weeks.append(current_week)
            current_week = []
        current_week.append(d)
    
    # Add the last week if it's not empty
    if current_week:
        weeks.append(current_week)
    
    # SVG parameters
    cell = 12
    gap = 4
    rows = 7  # Sunday to Saturday
    cols = len(weeks)
    maxv = max(cal_map.values()) if cal_map else 1
    
    # Calculate total contributions
    total_contributions = sum(cal_map.values())
    
    # Create the SVG drawing with additional space for the total count
    dwg = svgwrite.Drawing(filename,
        size=(cols*(cell+gap) + 100, rows*(cell+gap) + 20),  # Extra space for the total count
        profile='tiny'
    )
    colors = ["#ebedf0", "#c6e48b", "#7bc96f", "#239a3b", "#196127"]
    
    # Add total contributions text at top right
    dwg.add(dwg.text(
        f"Total: {total_contributions}",
        insert=(cols*(cell+gap) - 10, 15),
        fill="black",
        font_size="12px",
        text_anchor="end"
    ))
    
    # Order of days: Sunday(6), Monday(0), Tuesday(1), Wednesday(2), Thursday(3), Friday(4), Saturday(5)
    day_order = [6, 0, 1, 2, 3, 4, 5]  # Mapping from position to weekday
    
    for x, week in enumerate(weeks):
        for y, weekday in enumerate(day_order):
            # Find the day in this week that matches the current weekday
            matching_days = [d for d in week if d.weekday() == weekday]
            if not matching_days:
                continue
                
            d = matching_days[0]
            c = cal_map.get(str(d), 0)
            intensity = int((c / maxv)**0.5 * (len(colors)-1)) if c > 0 else 0
            fill = colors[intensity]
            
            dwg.add(dwg.rect(
                insert=(x*(cell+gap), y*(cell+gap) + 20),  # Add offset for the total count
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

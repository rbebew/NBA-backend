
from fastapi import FastAPI, HTTPException
from nba_api.stats.endpoints import leaguegamefinder, teamdashlineups, leaguedashplayerstats
from datetime import datetime, date
import pandas as pd
import requests
import time

app = FastAPI(title="NBA Boxscore API", version="1.0")

# -------------------------------------------------
# HEADERS
# -------------------------------------------------
NBA_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://www.nba.com/"
}

NBA_STATS_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://www.nba.com/",
    "Origin": "https://www.nba.com",
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9"
}

# -------------------------------------------------
# SIMPLE CACHE (for slow NBA endpoints)
# -------------------------------------------------
CACHE = {}
CACHE_TTL = 3600

def cached(key, fn):
    now = time.time()
    if key in CACHE:
        data, ts = CACHE[key]
        if now - ts < CACHE_TTL:
            return data

    data = fn()
    CACHE[key] = (data, now)
    return data

# -------------------------------------------------
# Helper: fetch JSON safely
# -------------------------------------------------
def fetch_json(url: str):
    try:
        r = requests.get(url, headers=NBA_HEADERS, timeout=20)
        r.raise_for_status()
        return r.json()
    except Exception:
        raise HTTPException(502, "NBA data unavailable")

# -------------------------------------------------
# 1️⃣ Games today
# -------------------------------------------------
@app.get("/games/today")
def games_today():
    url = "https://cdn.nba.com/static/json/liveData/scoreboard/todaysScoreboard_00.json"
    data = fetch_json(url)

    games = []
    for g in data["scoreboard"]["games"]:
        games.append({
            "game_id": g["gameId"],
            "game_status": g["gameStatus"],
            "game_status_text": g["gameStatusText"],
            "start_time_utc": g.get("gameTimeUTC"),
            "home_team_id": g["homeTeam"]["teamId"],
            "home_team_name": g["homeTeam"]["teamName"],
            "home_score": g["homeTeam"]["score"],
            "away_team_id": g["awayTeam"]["teamId"],
            "away_team_name": g["awayTeam"]["teamName"],
            "away_score": g["awayTeam"]["score"]
        })

    return {"games": games}

# -------------------------------------------------
# 2️⃣ Games history
# -------------------------------------------------
@app.get("/games")
def games_history(season: str = "2025-26"):
    def fetch():
        games = leaguegamefinder.LeagueGameFinder(season_nullable=season)
        return games.get_dict()

    return cached(f"games_{season}", fetch)

# -------------------------------------------------
# 3️⃣ Full boxscore
# -------------------------------------------------
@app.get("/games/{game_id}")
def game_boxscore(game_id: str):
    url = f"https://cdn.nba.com/static/json/liveData/boxscore/boxscore_{game_id}.json"
    data = fetch_json(url)
    return data["game"]

# -------------------------------------------------
# 4️⃣ Player stats for a game
# -------------------------------------------------
@app.get("/games/{game_id}/players")
def game_players(game_id: str):
    url = f"https://cdn.nba.com/static/json/liveData/boxscore/boxscore_{game_id}.json"
    game = fetch_json(url)["game"]

    players = []
    for team in [game["homeTeam"], game["awayTeam"]]:
        for p in team["players"]:
            players.append({
                "player_id": p["personId"],
                "name": p["name"],
                "team": team["teamName"],
                "minutes": p["statistics"]["minutes"],
                "points": p["statistics"]["points"],
                "rebounds": p["statistics"]["reboundsTotal"],
                "assists": p["statistics"]["assists"],
                "steals": p["statistics"]["steals"],
                "blocks": p["statistics"]["blocks"],
                "turnovers": p["statistics"]["turnovers"]
            })

    return {"game_id": game_id, "players": players}

# -------------------------------------------------
# 5️⃣ Team stats for a game
# -------------------------------------------------
@app.get("/games/{game_id}/teams")
def game_teams(game_id: str):
    url = f"https://cdn.nba.com/static/json/liveData/boxscore/boxscore_{game_id}.json"
    game = fetch_json(url)["game"]

    teams = []
    for team in [game["homeTeam"], game["awayTeam"]]:
        stats = team["statistics"]
        teams.append({
            "team_id": team["teamId"],
            "team_name": team["teamName"],
            "points": stats["points"],
            "rebounds": stats["reboundsTotal"],
            "assists": stats["assists"],
            "fg_pct": stats["fieldGoalsPercentage"],
            "three_pct": stats["threePointersPercentage"],
            "ft_pct": stats["freeThrowsPercentage"]
        })

    return {"game_id": game_id, "teams": teams}

# -------------------------------------------------
# 6️⃣ Upcoming games
# -------------------------------------------------
@app.get("/games/upcoming")
def upcoming():
    url = "https://cdn.nba.com/static/json/staticData/scheduleLeagueV2_1.json"
    data = fetch_json(url)

    now = datetime.utcnow()
    games = []

    for d in data["leagueSchedule"]["gameDates"]:
        for g in d["games"]:
            start = datetime.fromisoformat(g["gameDateTimeUTC"].replace("Z",""))
            if start > now:
                games.append({
                    "game_id": g["gameId"],
                    "start_time_utc": g["gameDateTimeUTC"],
                    "home_team_id": g["homeTeam"]["teamId"],
                    "away_team_id": g["awayTeam"]["teamId"]
                })

    return games

# -------------------------------------------------
# 7️⃣ Team lineup stats
# -------------------------------------------------
@app.get("/teams/{team_id}/Teamstats")
def team_stats(
    team_id: int,
    season: str = "2025-26",
    season_type: str = "Regular Season"
):

    try:

        lineups = teamdashlineups.TeamDashLineups(
            team_id=team_id,
            season=season,
            season_type_all_star=season_type,
            per_mode_detailed="PerGame",
            measure_type_detailed_defense="Base",
            pace_adjust="N",
            plus_minus="N",
            rank="N",
            timeout=60
        )

        df = lineups.get_data_frames()[0]

        return {
            "team_id": team_id,
            "season": season,
            "season_type": season_type,
            "lineups": df.fillna(0).to_dict(orient="records")
        }

    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"NBA TeamDashLineups error: {str(e)}"
        )

# -------------------------------------------------
# 8️⃣ Player stats
# -------------------------------------------------
@app.get("/teams/{team_id}/playerstats")
def team_player_stats(
    team_id: int,
    season: str = "2025-26",
    season_type: str = "Regular Season"
):

    try:

        players = leaguedashplayerstats.LeagueDashPlayerStats(
            team_id_nullable=team_id,
            season=season,
            season_type_all_star=season_type,
            per_mode_detailed="PerGame",
            timeout=60
        )

        df = players.get_data_frames()[0]

        return {
            "team_id": team_id,
            "season": season,
            "season_type": season_type,
            "players": df.fillna(0).to_dict(orient="records")
        }

    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"NBA LeagueDashPlayerStats error: {str(e)}"
        )# -------------------------------------------------
# 9️⃣ Daily Lineups
# -------------------------------------------------
@app.get("/lineups/daily")
def daily_lineups(date: str = None):

    if not date:
        date = datetime.utcnow().strftime("%Y%m%d")

    url = f"https://stats.nba.com/js/data/leaders/00_daily_lineups_{date}.json"

    try:
        r = requests.get(url, headers=NBA_STATS_HEADERS, timeout=20)
        r.raise_for_status()
        return {"date": date, "data": r.json()}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"NBA daily lineups unavailable: {str(e)}")

@app.get("/")
def root():
    return {"status": "NBA Boxscore API running"}

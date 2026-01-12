from fastapi import FastAPI, HTTPException
import requests
from datetime import datetime
from nba_api.stats.endpoints import (
    leaguegamefinder
)
from datetime import date
import pandas as pd

app = FastAPI(title="NBA Boxscore API", version="1.0")

NBA_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://www.nba.com/"
}

# -------------------------------------------------
# Helper: fetch JSON safely
# -------------------------------------------------
def fetch_json(url: str):
    try:
        r = requests.get(url, headers=NBA_HEADERS, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception:
        raise HTTPException(502, "NBA data unavailable")

# -------------------------------------------------
# 1️⃣ Games today (played + live)
# -------------------------------------------------
@app.get("/games/today")
def games_today():
    url = (
        "https://cdn.nba.com/static/json/liveData/"
        "scoreboard/todaysScoreboard_00.json"
    )

    data = fetch_json(url)

    games = []
    for g in data["scoreboard"]["games"]:
        games.append({
            # GAME
            "game_id": g["gameId"],
            "game_status": g["gameStatus"],          # 1=upcoming, 2=live, 3=final
            "game_status_text": g["gameStatusText"],

            # TIME
            "start_time_utc": g.get("gameTimeUTC"),

            # HOME
            "home_team_id": g["homeTeam"]["teamId"],
            "home_team_name": g["homeTeam"]["teamName"],
            "home_score": g["homeTeam"]["score"],

            # AWAY
            "away_team_id": g["awayTeam"]["teamId"],
            "away_team_name": g["awayTeam"]["teamName"],
            "away_score": g["awayTeam"]["score"]
        })

    return {
        "games": games
    }
# -------------------
# HISTORIK / KAMPE
# -------------------

@app.get("/games")
def games_history(season: str = "2025-26"):
    games = leaguegamefinder.LeagueGameFinder(season_nullable=season)
    return games.get_dict()
# -------------------------------------------------
# 2️⃣ Full boxscore (raw)
# -------------------------------------------------
@app.get("/games/{game_id}")
def game_boxscore(game_id: str):
    url = (
        "https://cdn.nba.com/static/json/liveData/"
        f"boxscore/boxscore_{game_id}.json"
    )

    data = fetch_json(url)
    return data["game"]

# -------------------------------------------------
# 3️⃣ Player stats for a game
# -------------------------------------------------
@app.get("/games/{game_id}/players")
def game_players(game_id: str):
    url = (
        "https://cdn.nba.com/static/json/liveData/"
        f"boxscore/boxscore_{game_id}.json"
    )

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

    return {
        "game_id": game_id,
        "players": players
    }

# -------------------------------------------------
# 4️⃣ Team stats for a game
# -------------------------------------------------
@app.get("/games/{game_id}/teams")
def game_teams(game_id: str):
    url = (
        "https://cdn.nba.com/static/json/liveData/"
        f"boxscore/boxscore_{game_id}.json"
    )

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

    return {
        "game_id": game_id,
        "teams": teams
    }
# -------------------------------------------------
# 5 Future games
# -------------------------------------------------

@app.get("/games/upcoming")
def upcoming():
    with open("schedule.json") as f:
        data = json.load(f)

    now = datetime.utcnow()

    return [
        {
            "game_id": g["gameId"],
            "start_time_utc": g["gameDateTimeUTC"],
            "home_team_id": g["homeTeam"]["teamId"],
            "away_team_id": g["awayTeam"]["teamId"]
        }
        for g in data["leagueSchedule"]["games"]
        if parse_utc(g["gameDateTimeUTC"]) > now
    ]

# -------------------
# LIVE DATA
# -------------------


# -------------------------------------------------
# Root
# -------------------------------------------------
@app.get("/")
def root():
    return {"status": "NBA Boxscore API running"}

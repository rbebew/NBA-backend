from fastapi import FastAPI, HTTPException
import requests
from datetime import datetime

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
    today = datetime.utcnow().strftime("%Y%m%d")

    url = (
        "https://cdn.nba.com/static/json/liveData/"
        f"scoreboard/todaysScoreboard_00.json"
    )

    data = fetch_json(url)

    games = []
    for g in data["scoreboard"]["games"]:
        games.append({
            "game_id": g["gameId"],
            "status": g["gameStatusText"],
            "home_team": g["homeTeam"]["teamName"],
            "away_team": g["awayTeam"]["teamName"],
            "home_score": g["homeTeam"]["score"],
            "away_score": g["awayTeam"]["score"]
        })

    return {"date": today, "games": games}

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
# Root
# -------------------------------------------------
@app.get("/")
def root():
    return {"status": "NBA Boxscore API running"}
from fastapi import FastAPI, HTTPException, Query
import requests
from datetime import datetime
import re

app = FastAPI(title="NBA Boxscore API", version="2.0")

NBA_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://www.nba.com/"
}

NBA_SCOREBOARD_URL = (
    "https://cdn.nba.com/static/json/liveData/"
    "scoreboard/todaysScoreboard_00.json"
)

NBA_BOXSCORE_URL = (
    "https://cdn.nba.com/static/json/liveData/"
    "boxscore/boxscore_{game_id}.json"
)

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
# 1️⃣ Games by date (VIGTIGT – NYT ENDPOINT)
# -------------------------------------------------
@app.get("/games")
def games_by_date(
    date: str = Query(..., description="YYYYMMDD (NBA game date)")
):
    """
    Henter alle NBA-kampe for en given dato (NBA game date).
    """

    # Valider dato-format
    if not re.match(r"^\d{8}$", date):
        raise HTTPException(400, "Invalid date format. Use YYYYMMDD")

    data = fetch_json(NBA_SCOREBOARD_URL)

    games = []
    for g in data["scoreboard"]["games"]:
        # NBA scoreboard indeholder allerede gameDate
        if g.get("gameDate") != date:
            continue

        games.append({
            "game_id": g["gameId"],
            "status": g["gameStatusText"],
            "home_team": g["homeTeam"]["teamName"],
            "away_team": g["awayTeam"]["teamName"],
            "home_score": g["homeTeam"]["score"],
            "away_score": g["awayTeam"]["score"]
        })

    return {
        "date": date,
        "games": games
    }

# -------------------------------------------------
# 2️⃣ Games today (kun convenience / UI)
# -------------------------------------------------
@app.get("/games/today")
def games_today():
    """
    Returnerer NBA scoreboard som den er lige nu.
    Brug kun til preview – IKKE til batch sync.
    """
    today = datetime.utcnow().strftime("%Y%m%d")

    data = fetch_json(NBA_SCOREBOARD_URL)

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

    return {
        "date": today,
        "games": games
    }

# -------------------------------------------------
# 3️⃣ Full boxscore (raw)
# -------------------------------------------------
@app.get("/games/{game_id}")
def game_boxscore(game_id: str):
    url = NBA_BOXSCORE_URL.format(game_id=game_id)
    data = fetch_json(url)
    return data["game"]

# -------------------------------------------------
# 4️⃣ Player stats for a game
# -------------------------------------------------
@app.get("/games/{game_id}/players")
def game_players(game_id: str):
    url = NBA_BOXSCORE_URL.format(game_id=game_id)
    game = fetch_json(url)["game"]

    players = []

    for team in [game["homeTeam"], game["awayTeam"]]:
        for p in team["players"]:
            stats = p["statistics"]

            players.append({
                "player_id": p["personId"],
                "name": p["name"],
                "team": team["teamName"],          # MATCHER Base44
                "team_id": team["teamId"],         # 🔑 VIGTIG
                "minutes": stats["minutes"],
                "points": stats["points"],
                "rebounds": stats["reboundsTotal"],
                "assists": stats["assists"],
                "steals": stats["steals"],
                "blocks": stats["blocks"],
                "turnovers": stats["turnovers"]
            })

    return {
        "game_id": game_id,
        "players": players
    }

# -------------------------------------------------
# 5️⃣ Team stats for a game
# -------------------------------------------------
@app.get("/games/{game_id}/teams")
def game_teams(game_id: str):
    url = NBA_BOXSCORE_URL.format(game_id=game_id)
    game = fetch_json(url)["game"]

    teams = []

    for team in [game["homeTeam"], game["awayTeam"]]:
        stats = team["statistics"]

        teams.append({
            "team_id": team["teamId"],            # 🔑 BRUGES OVERALT
            "team_name": team["teamName"],
            "points": stats["points"],
            "rebounds": stats["reboundsTotal"],
            "assists": stats["assists"],
            "steals": stats["steals"],
            "blocks": stats["blocks"],
            "turnovers": stats["turnovers"],
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

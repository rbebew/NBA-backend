from fastapi import FastAPI
import time

from nba_api.live.nba.endpoints import (
    scoreboard,
    boxscore,
    playbyplay
)

from nba_api.stats.endpoints import (
    LeagueGameFinder,
    CommonAllPlayers,
    PlayerCareerStats,
    TeamDetails,
    ShotChartDetail,
    PlayerDashboardByGeneralSplits
)

app = FastAPI(title="NBA Free API", version="1.0")

# -------------------
# SIMPLE CACHE
# -------------------

cache = {}
CACHE_TTL = {
    "live": 30,
    "playbyplay": 15,
    "advanced": 21600,   # 6 hours
    "shotchart": 86400   # 24 hours
}

def get_cache(key):
    if key in cache:
        entry = cache[key]
        if time.time() - entry["time"] < entry["ttl"]:
            return entry["data"]
    return None

def set_cache(key, data, ttl):
    cache[key] = {
        "time": time.time(),
        "data": data,
        "ttl": ttl
    }

# -------------------
# ROOT
# -------------------

@app.get("/")
def root():
    return {"status": "NBA API running"}

# -------------------
# LIVE GAMES
# -------------------

@app.get("/live")
def live_games():
    cached = get_cache("live")
    if cached:
        return cached

    data = scoreboard.ScoreBoard().get_dict()
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

    result = {"games": games}
    set_cache("live", result, CACHE_TTL["live"])
    return result

# -------------------
# GAME DETAILS / BOXSCORE
# -------------------

@app.get("/games/{game_id}")
def game_boxscore(game_id: str):
    data = boxscore.BoxScore(game_id=game_id).get_dict()

    return {
        "game_id": game_id,
        "home_team": data["game"]["homeTeam"]["teamName"],
        "away_team": data["game"]["awayTeam"]["teamName"],
        "players": (
            data["game"]["homeTeam"]["players"] +
            data["game"]["awayTeam"]["players"]
        )
    }

# -------------------
# PLAY BY PLAY
# -------------------

@app.get("/games/{game_id}/playbyplay")
def game_play_by_play(game_id: str):
    cache_key = f"pbp_{game_id}"
    cached = get_cache(cache_key)
    if cached:
        return cached

    data = playbyplay.PlayByPlay(game_id=game_id).get_dict()
    actions = []

    for a in data["game"]["actions"]:
        actions.append({
            "clock": a.get("clock"),
            "period": a.get("period"),
            "team": a.get("teamTricode"),
            "description": a.get("description"),
            "score_home": a.get("scoreHome"),
            "score_away": a.get("scoreAway")
        })

    result = {
        "game_id": game_id,
        "actions": actions
    }

    set_cache(cache_key, result, CACHE_TTL["playbyplay"])
    return result

# -------------------
# GAMES HISTORY
# -------------------

@app.get("/games")
def games_history(season: str = "2023-24"):
    games = leaguegamefinder.LeagueGameFinder(
        season_nullable=season
    ).get_dict()
    return games

# -------------------
# PLAYERS
# -------------------

@app.get("/players")
def all_players():
    players = CommonAllPlayers().get_dict()
    return players

@app.get("/players/{player_id}")
def player_career(player_id: str):
    career = playercareerstats.PlayerCareerStats(
        player_id=player_id
    ).get_dict()
    return career

# -------------------
# TEAMS
# -------------------

@app.get("/teams/{team_id}")
def team_info(team_id: str):
    team = teamdetails.TeamDetails(team_id=team_id).get_dict()
    return team

# -------------------
# ADVANCED STATS
# -------------------

@app.get("/players/{player_id}/advanced")
def player_advanced(player_id: str):
    cache_key = f"adv_{player_id}"
    cached = get_cache(cache_key)
    if cached:
        return cached

    data = PlayerDashboardByGeneralSplits(
    player_id=player_id
).get_dict()

    row = data["resultSets"][0]["rowSet"][0]

    result = {
        "player_id": player_id,
        "true_shooting_pct": row[27],
        "usage_pct": row[26],
        "pie": row[30]
    }

    set_cache(cache_key, result, CACHE_TTL["advanced"])
    return result

# -------------------
# ON / OFF STATS
# -------------------

@app.get("/players/{player_id}/onoff")
def player_onoff(player_id: str):
    data = PlayerOnOffDetails(
    player_id=player_id
).get_dict()

    rows = data["resultSets"][0]["rowSet"]

    return {
        "player_id": player_id,
        "on_court": {
            "net_rating": rows[0][6],
            "off_rating": rows[0][7],
            "def_rating": rows[0][8]
        },
        "off_court": {
            "net_rating": rows[1][6],
            "off_rating": rows[1][7],
            "def_rating": rows[1][8]
        }
    }

# -------------------
# SHOT CHART
# -------------------

@app.get("/players/{player_id}/shotchart")
def player_shotchart(player_id: str, season: str = "2023-24"):
    cache_key = f"shot_{player_id}_{season}"
    cached = get_cache(cache_key)
    if cached:
        return cached

    data = shotchartdetail.ShotChartDetail(
        player_id=player_id,
        team_id=0,
        season_nullable=season,
        season_type_all_star="Regular Season"
    ).get_dict()

    shots = []
    for row in data["resultSets"][0]["rowSet"]:
        shots.append({
            "x": row[17],
            "y": row[18],
            "made": row[20] == 1,
            "shot_type": row[9]
        })

    result = {
        "player_id": player_id,
        "season": season,
        "shots": shots
    }

    set_cache(cache_key, result, CACHE_TTL["shotchart"])
    return result
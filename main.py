from fastapi import FastAPI, HTTPException
import time
import datetime

# ---------------- NBA HEADERS (CRITICAL FOR CLOUD) ----------------
from nba_api.stats.library.http import NBAStatsHTTP

NBAStatsHTTP.headers.update({
    "Host": "stats.nba.com",
    "Connection": "keep-alive",
    "Accept": "application/json, text/plain, */*",
    "x-nba-stats-token": "true",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.nba.com/",
    "Accept-Language": "en-US,en;q=0.9"
})

# ---------------- LIVE ENDPOINTS ----------------
from nba_api.live.nba.endpoints import (
    scoreboard,
    boxscore,
    playbyplay
)

# ---------------- STATS ENDPOINTS ----------------
from nba_api.stats.endpoints import (
    LeagueGameFinder,
    CommonAllPlayers,
    PlayerCareerStats,
    TeamDetails,
    ShotChartDetail,
    PlayerDashboardByGeneralSplits,
    LeagueDashTeamStats
)

# ---------------- STATIC DATA ----------------
from nba_api.stats.static import teams as nba_teams

app = FastAPI(title="NBA Free API", version="1.0")

# ---------------- SIMPLE CACHE ----------------
cache = {}

CACHE_TTL = {
    "live": 30,
    "playbyplay": 15,
    "advanced": 21600,
    "shotchart": 86400,
    "team_stats": 21600
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

# ---------------- ROOT ----------------
@app.get("/")
def root():
    return {"status": "NBA API running"}

# ---------------- LIVE GAMES ----------------
@app.get("/live")
def live_games():
    cached = get_cache("live")
    if cached:
        return cached

    try:
        data = scoreboard.ScoreBoard().get_dict()
    except Exception:
        raise HTTPException(502, "NBA live service unavailable")

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

# ---------------- GAME DETAILS ----------------
@app.get("/games/{game_id}")
def game_boxscore(game_id: str):
    try:
        data = boxscore.BoxScore(game_id=game_id).get_dict()
    except Exception:
        raise HTTPException(502, "NBA boxscore unavailable")

    return {
        "game_id": game_id,
        "home_team": data["game"]["homeTeam"]["teamName"],
        "away_team": data["game"]["awayTeam"]["teamName"],
        "players": (
            data["game"]["homeTeam"]["players"] +
            data["game"]["awayTeam"]["players"]
        )
    }

# ---------------- PLAY BY PLAY ----------------
@app.get("/games/{game_id}/playbyplay")
def game_play_by_play(game_id: str):
    cache_key = f"pbp_{game_id}"
    cached = get_cache(cache_key)
    if cached:
        return cached

    try:
        data = playbyplay.PlayByPlay(game_id=game_id).get_dict()
    except Exception:
        raise HTTPException(502, "NBA play-by-play unavailable")

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

    result = {"game_id": game_id, "actions": actions}
    set_cache(cache_key, result, CACHE_TTL["playbyplay"])
    return result

# ---------------- PLAYERS ----------------
@app.get("/players")
def all_players():
    try:
        return CommonAllPlayers().get_dict()
    except Exception:
        raise HTTPException(502, "NBA players unavailable")

@app.get("/players/{player_id}")
def player_career(player_id: str):
    try:
        return PlayerCareerStats(player_id=player_id).get_dict()
    except Exception:
        raise HTTPException(502, "NBA player stats unavailable")

# ---------------- PLAYER ADVANCED ----------------
@app.get("/players/{player_id}/advanced")
def player_advanced(player_id: str):
    cache_key = f"adv_{player_id}"
    cached = get_cache(cache_key)
    if cached:
        return cached

    try:
        data = PlayerDashboardByGeneralSplits(player_id=player_id).get_dict()
    except Exception:
        raise HTTPException(502, "NBA advanced stats unavailable")

    row = data["resultSets"][0]["rowSet"][0]

    result = {
        "player_id": player_id,
        "true_shooting_pct": row[27],
        "usage_pct": row[26],
        "pie": row[30]
    }

    set_cache(cache_key, result, CACHE_TTL["advanced"])
    return result

# ---------------- SHOT CHART ----------------
@app.get("/players/{player_id}/shotchart")
def player_shotchart(player_id: str, season: str = "2023-24"):
    cache_key = f"shot_{player_id}_{season}"
    cached = get_cache(cache_key)
    if cached:
        return cached

    try:
        data = ShotChartDetail(
            player_id=player_id,
            team_id=0,
            season_nullable=season,
            season_type_all_star="Regular Season"
        ).get_dict()
    except Exception:
        raise HTTPException(502, "NBA shot chart unavailable")

    shots = []
    for row in data["resultSets"][0]["rowSet"]:
        shots.append({
            "x": row[17],
            "y": row[18],
            "made": row[20] == 1,
            "shot_type": row[9]
        })

    result = {"player_id": player_id, "season": season, "shots": shots}
    set_cache(cache_key, result, CACHE_TTL["shotchart"])
    return result

# ---------------- ALL TEAMS (MAPPING) ----------------
@app.get("/teams")
def all_teams():
    teams = nba_teams.get_teams()
    return {
        "teams": [{
            "team_id": t["id"],
            "full_name": t["full_name"],
            "abbreviation": t["abbreviation"],
            "city": t["city"],
            "nickname": t["nickname"]
        } for t in teams]
    }

# ---------------- TEAM DETAILS ----------------
@app.get("/teams/{team_id}")
def team_info(team_id: int):
    try:
        return TeamDetails(team_id=team_id).get_dict()
    except Exception:
        raise HTTPException(502, "NBA team info unavailable")

# ---------------- TEAM SEASON STATS ----------------
@app.get("/teams/{team_id}/stats")
def team_season_stats(team_id: int, season: str = "2023-24"):
    # season validation
    try:
        start_year = int(season.split("-")[0])
    except Exception:
        raise HTTPException(400, "Invalid season format (YYYY-YY)")

    if start_year > datetime.datetime.now().year:
        raise HTTPException(400, "Season not available yet")

    cache_key = f"teamstats_{team_id}_{season}"
    cached = get_cache(cache_key)
    if cached:
        return cached

    try:
        data = LeagueDashTeamStats(
            season=season,
            per_mode_detailed="PerGame"
        ).get_dict()
    except Exception:
        raise HTTPException(502, "NBA team stats unavailable")

    headers = data["resultSets"][0]["headers"]
    rows = data["resultSets"][0]["rowSet"]

    for row in rows:
        team = dict(zip(headers, row))
        if team["TEAM_ID"] == team_id:
            result = {
                "team_id": team_id,
                "team_name": team["TEAM_NAME"],
                "season": season,
                "games_played": team["GP"],
                "points_per_game": team["PTS"],
                "rebounds_per_game": team["REB"],
                "assists_per_game": team["AST"],
                "field_goal_pct": team["FG_PCT"],
                "three_point_pct": team["FG3_PCT"],
                "free_throw_pct": team["FT_PCT"],
                "offensive_rating": team.get("OFF_RATING", team.get("OFF_RTG")),
                "defensive_rating": team.get("DEF_RATING", team.get("DEF_RTG")),
                "net_rating": team.get("NET_RATING", team.get("NET_RTG"))
            }

            set_cache(cache_key, result, CACHE_TTL["team_stats"])
            return result

    raise HTTPException(404, "Team not found")
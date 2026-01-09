from fastapi import FastAPI, HTTPException
import time
import datetime

# -------------------------------------------------
# NBA HEADERS (REQUIRED FOR CLOUD / RENDER)
# -------------------------------------------------
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

# -------------------------------------------------
# NBA IMPORTS
# -------------------------------------------------
from nba_api.live.nba.endpoints import scoreboard, boxscore, playbyplay
from nba_api.stats.endpoints import (
    LeagueGameFinder,
    CommonAllPlayers,
    PlayerCareerStats,
    TeamDetails,
    ShotChartDetail,
    PlayerDashboardByGeneralSplits,
    LeagueDashTeamStats
)
from nba_api.stats.static import teams as nba_teams

# -------------------------------------------------
# APP
# -------------------------------------------------
app = FastAPI(title="NBA Free API", version="1.1")

# -------------------------------------------------
# SIMPLE CACHE
# -------------------------------------------------
cache = {}

CACHE_TTL = {
    "live": 30,
    "playbyplay": 15,
    "advanced": 21600,
    "shotchart": 86400,
    "team_stats": 21600,
    "meta": 3600
}

def get_cache(key):
    entry = cache.get(key)
    if not entry:
        return None
    if time.time() - entry["time"] < entry["ttl"]:
        return entry["data"]
    return None

def set_cache(key, data, ttl):
    cache[key] = {
        "time": time.time(),
        "data": data,
        "ttl": ttl
    }

# -------------------------------------------------
# CURRENT NBA SEASON (STATS-SAFE)
# -------------------------------------------------
def compute_current_season():
    now = datetime.datetime.now()
    year = now.year
    month = now.month

    # NBA team stats are unreliable before March
    if month < 3:
        start_year = year - 1
    else:
        start_year = year

    return f"{start_year}-{str(start_year + 1)[-2:]}"

@app.get("/meta/current-season")
def current_season():
    cached = get_cache("current_season")
    if cached:
        return cached

    season = compute_current_season()
    result = {
        "season": season,
        "note": "Latest NBA season with reliable team statistics"
    }

    set_cache("current_season", result, CACHE_TTL["meta"])
    return result

# -------------------------------------------------
# ROOT
# -------------------------------------------------
@app.get("/")
def root():
    return {"status": "NBA API running"}

# -------------------------------------------------
# LIVE GAMES
# -------------------------------------------------
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
    for g in data.get("scoreboard", {}).get("games", []):
        games.append({
            "game_id": g.get("gameId"),
            "status": g.get("gameStatusText"),
            "home_team": g.get("homeTeam", {}).get("teamName"),
            "away_team": g.get("awayTeam", {}).get("teamName"),
            "home_score": g.get("homeTeam", {}).get("score"),
            "away_score": g.get("awayTeam", {}).get("score")
        })

    result = {"games": games}
    set_cache("live", result, CACHE_TTL["live"])
    return result

# -------------------------------------------------
# PLAYERS
# -------------------------------------------------
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

# -------------------------------------------------
# ALL TEAMS (MAPPING)
# -------------------------------------------------
@app.get("/teams")
def all_teams():
    teams = nba_teams.get_teams()
    return {
        "teams": [
            {
                "team_id": t["id"],
                "full_name": t["full_name"],
                "abbreviation": t["abbreviation"],
                "city": t["city"],
                "nickname": t["nickname"]
            } for t in teams
        ]
    }

# -------------------------------------------------
# TEAM DETAILS
# -------------------------------------------------
@app.get("/teams/{team_id}")
def team_info(team_id: int):
    try:
        return TeamDetails(team_id=team_id).get_dict()
    except Exception:
        raise HTTPException(502, "NBA team info unavailable")

# -------------------------------------------------
# TEAM SEASON STATS (AUTO CURRENT SEASON)
# -------------------------------------------------
@app.get("/teams/{team_id}/stats")
def team_season_stats(team_id: int, season: str | None = None):
    if season is None:
        season = compute_current_season()

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

    result_sets = data.get("resultSets", [])
    if not result_sets:
        raise HTTPException(502, "NBA team stats empty")

    headers = result_sets[0].get("headers", [])
    rows = result_sets[0].get("rowSet", [])

    if not headers or not rows:
        raise HTTPException(502, "NBA team stats malformed")

    for row in rows:
        team = {k: v for k, v in zip(headers, row)}
        if team.get("TEAM_ID") == team_id:
            result = {
                "team_id": team_id,
                "team_name": team.get("TEAM_NAME"),
                "season": season,
                "games_played": team.get("GP"),
                "points_per_game": team.get("PTS"),
                "rebounds_per_game": team.get("REB"),
                "assists_per_game": team.get("AST"),
                "field_goal_pct": team.get("FG_PCT"),
                "three_point_pct": team.get("FG3_PCT"),
                "free_throw_pct": team.get("FT_PCT"),
                "offensive_rating": team.get("OFF_RATING") or team.get("OFF_RTG"),
                "defensive_rating": team.get("DEF_RATING") or team.get("DEF_RTG"),
                "net_rating": team.get("NET_RATING") or team.get("NET_RTG")
            }

            set_cache(cache_key, result, CACHE_TTL["team_stats"])
            return result

    raise HTTPException(404, "Team not found")
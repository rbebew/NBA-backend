from fastapi import FastAPI
from nba_api.live.nba.endpoints import scoreboard, boxscore
from nba_api.stats.endpoints import (
    leaguegamefinder,
    playercareerstats,
    commonallplayers,
    teamdetails
)

app = FastAPI(title="NBA Free API", version="1.0")

# -------------------
# LIVE DATA
# -------------------

@app.get("/live")
def live_games():
    games = scoreboard.ScoreBoard()
    return games.get_dict()

@app.get("/live/{game_id}")
def live_boxscore(game_id: str):
    game = boxscore.BoxScore(game_id=game_id)
    return game.get_dict()

# -------------------
# HISTORIK / KAMPE
# -------------------

@app.get("/games")
def games_history(season: str = "2023-24"):
    games = leaguegamefinder.LeagueGameFinder(season_nullable=season)
    return games.get_dict()

# -------------------
# SPILLERE
# -------------------

@app.get("/players")
def all_players():
    players = commonallplayers.CommonAllPlayers()
    return players.get_dict()

@app.get("/players/{player_id}")
def player_career(player_id: str):
    career = playercareerstats.PlayerCareerStats(player_id=player_id)
    return career.get_dict()

# -------------------
# HOLD
# -------------------

@app.get("/teams/{team_id}")
def team_info(team_id: str):
    team = teamdetails.TeamDetails(team_id=team_id)
    return team.get_dict()
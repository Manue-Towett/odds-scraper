import re
import json
import uuid
import threading
import dataclasses
from queue import Queue
from typing import Optional
from datetime import datetime

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.espn.com{}"

SCEDULE_URL = "https://www.espn.com/{}/schedule"

HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
    "Dnt": "1",
    "Pragma": "no-cache",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

@dataclasses.dataclass
class Game:
    date: str
    season_year: int
    home_team: Optional[str] = None
    home_team_abbr: Optional[str] = None
    home_team_short_name: Optional[str] = None
    home_team_logo: Optional[str] = None
    home_team_color: Optional[str] = None
    away_team: Optional[str] = None
    away_team_abbr: Optional[str] = None
    away_team_short_name: Optional[str] = None
    away_team_color: Optional[str] = None
    away_team_logo: Optional[str] = None
    home_score: Optional[str] = None
    away_score: Optional[str] = None
    venue: Optional[str] = None
    completed: Optional[bool] = None
    espn_link: Optional[str] = None
    home_spread: Optional[str] = None
    away_spread: Optional[str] = None
    home_total: Optional[str] = None
    away_total: Optional[str] = None
    home_record: Optional[str] = None
    home_record_extended: Optional[str] = None
    away_record: Optional[str] = None
    away_record_extended: Optional[str] = None

@dataclasses.dataclass
class Team:
    id: str
    href: str
    name: str
    shortName: str
    abbrev: str
    logo: str

class ESPNScraper:
    """Scrapes past games from espn website https://www.espn.com/"""
    def __init__(self) -> None:
        self.queue = Queue()
        self.games: list[Game] = []
        self.teams_crawled: list[str] = []

        [threading.Thread(target=self.__work, daemon=True).start() for _ in range(10)]

    def __request(self, url: str) -> requests.Response:
        """Requests data from the website"""
        while True:
            try:
                response = requests.get(url, headers=HEADERS)

                if response.ok:
                    return response
                
            except: pass
    
    @staticmethod
    def __extract_script_text(response: requests.Response) -> str:
        soup = BeautifulSoup(response.text, "html.parser")

        for script in soup.select("script"):
            script_text = script.get_text(strip=True)

            if re.search(r"window\['__espnfitt__'\]", script_text):
                return script_text.split("window['__espnfitt__']=")[-1].strip()
    
    def __extract_odds(self, response: requests.Response, game: Game) -> None:
        """Extract game odds from the response object"""
        try:
            text = self.__extract_script_text(response)

            data = json.loads(text.rstrip(";"))

            with open("./data/nba_schedule.json", "w") as file:
                json.dump(data, file, indent=4)

            game_package = data["page"]["content"]["gamepackage"]

            try:
                game_odds = game_package["gameOdds"]["odds"]

                for game_odd in game_odds:
                    if game_odd["line"]["primaryTextFullWide"] == game.home_team:
                        game.home_spread = game_odd["pointSpread"]["primary"]
                        game.home_total = game_odd["total"]["primary"]
                    elif game_odd["line"]["primaryTextFullWide"] == game.away_team:
                        game.away_spread = game_odd["pointSpread"]["primary"]
                        game.away_total = game_odd["total"]["primary"]
                        
            except: pass

            try:
                teams = game_package["gmStrp"]["tms"]

                for team in teams:
                    if team["displayName"] == game.home_team:
                        game.home_record = team["records"][0]["summary"]
                        home_only = team["records"][1]["summary"]
                        game.home_record_extended = f"{game.home_record}, {home_only}"
                    elif team["displayName"] == game.away_team:
                        game.away_record = team["records"][0]["summary"]
                        away_only = team["records"][1]["summary"]
                        game.away_record_extended = f"{game.away_record}, {away_only}"
            except: pass

        except:pass
    
    def __extract_games(self, response: requests.Response) -> list[Game]:
        """Extracts games from the response object"""
        text = self.__extract_script_text(response)

        data = json.loads(text.rstrip(";"))

        games = []

        try:
            events = data["page"]["content"]["events"]

            with open("./data/nba_schedule.json", "w") as file:
                json.dump(events, file, indent=4)

            for _, values in events.items():
                for value in values:
                        game = Game(date=value["date"], season_year="2024")

                        for competitor in value["competitors"]:
                            if competitor["isHome"]:
                                game.home_team = competitor["displayName"]
                                game.home_team_abbr = competitor["abbrev"]
                                game.home_team_logo = competitor["logo"]
                                game.home_team_color = competitor["teamColor"]
                                game.home_team_short_name = competitor["shortDisplayName"]
                                
                                try:
                                    game.home_score = competitor["score"]
                                except:
                                    game.home_score = 0
                            else:
                                game.away_team = competitor["displayName"]
                                game.away_team_abbr = competitor["abbrev"]
                                game.away_team_logo = competitor["logo"]
                                game.away_team_color = competitor["teamColor"]
                                game.away_team_short_name = competitor["shortDisplayName"]

                                try:
                                    game.away_score = competitor["score"]
                                except:
                                    game.away_score = 0
                        
                        game.venue = value["venue"]["fullName"]

                        game.completed = value["completed"]

                        game.espn_link = value["link"]

                        games.append(game)

        except Exception as e: print(e)

        return games
    
    def __work(self) -> None:
        while True:
            game_link, game = self.queue.get()

            response = self.__request(game_link)

            self.__extract_odds(response, game)

            self.queue.task_done()
    
    def get_logo(self, url: str) -> str:
        response = self.__request(url)

        image_name = f"{uuid.uuid4().__str__()}.{url.split('.')[-1]}"

        with open(image_name, "wb") as f:
            f.write(response.content)
        
        return image_name

    def run(self, league: str) -> None:
        url = SCEDULE_URL.format(league)

        if "college" in url:
            date = datetime.now()

            day, month = date.day+2, date.month

            month = f"0{month}" if month < 10 else month

            day = f"0{day}" if day < 10 else day

            url += f"/_/date/{date.year}{month}{day}"

        response = self.__request(url)

        games = self.__extract_games(response)

        for game in games:
            if game.completed: continue

            game_link = BASE_URL.format(game.espn_link)

            self.queue.put((game_link, game))

        self.games.extend(games)

        self.queue.join()

        with open(f"{league}.json", "w") as file:
            json.dump([dataclasses.asdict(game) for game in self.games], file, indent=4)
    

app = ESPNScraper()
app.run("nba")
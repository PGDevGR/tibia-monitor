import requests
from bs4 import BeautifulSoup
import sqlite3
from datetime import datetime, timedelta
from collections import defaultdict
import time
import json

class TibiaMonitor:
    def __init__(self, world_name="Karmeya", db_path="tibia_monitor.db"):
        self.world_name = world_name
        self.db_path = db_path
        self.base_url = f"https://www.tibia.com/community/?subtopic=worlds&world={world_name}"
        self.init_database()
    
    def init_database(self):
        """Inicjalizacja bazy danych"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Tabela dla statusów online
        c.execute('''CREATE TABLE IF NOT EXISTS player_status
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      player_name TEXT,
                      timestamp DATETIME,
                      is_online INTEGER,
                      level INTEGER,
                      vocation TEXT)''')
        
        # Indeksy dla szybszych zapytań
        c.execute('''CREATE INDEX IF NOT EXISTS idx_player_timestamp 
                     ON player_status(player_name, timestamp)''')
        
        conn.commit()
        conn.close()
    
    def fetch_online_players(self):
        """Pobiera listę graczy online z Tibia.com"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(self.base_url, headers=headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Znajdź tabelę z graczami online
            players_online = []
            tables = soup.find_all('table', class_='Table3')
            
            for table in tables:
                rows = table.find_all('tr')
                for row in rows[1:]:  # Pomiń nagłówek
                    cols = row.find_all('td')
                    if len(cols) >= 3:
                        name = cols[0].get_text(strip=True)
                        level = cols[1].get_text(strip=True)
                        vocation = cols[2].get_text(strip=True)
                        
                        if name and level.isdigit():
                            players_online.append({
                                'name': name,
                                'level': int(level),
                                'vocation': vocation
                            })
            
            return players_online
        
        except Exception as e:
            print(f"Błąd podczas pobierania danych: {e}")
            return []
    
    def save_snapshot(self, players_online):
        """Zapisuje snapshot graczy online"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        timestamp = datetime.now()
        
        # Zapisz graczy online
        for player in players_online:
            c.execute('''INSERT INTO player_status 
                         (player_name, timestamp, is_online, level, vocation)
                         VALUES (?, ?, 1, ?, ?)''',
                      (player['name'], timestamp, player['level'], player['vocation']))
        
        conn.commit()
        conn.close()
        
        print(f"[{timestamp}] Zapisano {len(players_online)} graczy online")
    
    def get_player_sessions(self, player_name, hours=24):
        """Pobiera sesje gracza z ostatnich X godzin"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        c.execute('''SELECT timestamp, is_online 
                     FROM player_status 
                     WHERE player_name = ? AND timestamp > ?
                     ORDER BY timestamp''',
                  (player_name, cutoff_time))
        
        results = c.fetchall()
        conn.close()
        
        return results
    
    def analyze_correlation(self, player1, player2, hours=24):
        """Analizuje korelację między dwoma graczami"""
        sessions1 = self.get_player_sessions(player1, hours)
        sessions2 = self.get_player_sessions(player2, hours)
        
        if not sessions1 or not sessions2:
            return 0, "Brak danych"
        
        # Konwertuj na zbiory czasów online
        times1 = {datetime.fromisoformat(s[0]) for s in sessions1 if s[1] == 1}
        times2 = {datetime.fromisoformat(s[0]) for s in sessions2 if s[1] == 1}
        
        # Sprawdź czy nigdy nie byli online jednocześnie
        overlap = len(times1 & times2)
        total_checks = max(len(times1), len(times2))
        
        if total_checks == 0:
            return 0, "Brak danych"
        
        # Im mniej overlappingu, tym większa szansa na multi
        if overlap == 0 and len(times1) > 10 and len(times2) > 10:
            # Sprawdź czy logowania następują po sobie
            all_times = sorted(list(times1) + list(times2))
            rapid_switches = 0
            
            for i in range(len(all_times) - 1):
                time_diff = (all_times[i + 1] - all_times[i]).total_seconds()
                if time_diff < 600:  # 10 minut
                    rapid_switches += 1
            
            correlation_score = min(95, (1 - overlap / total_checks) * 100 + rapid_switches * 5)
            return correlation_score, f"Nigdy nie online razem, {rapid_switches} szybkich zmian"
        
        correlation_score = max(0, (1 - overlap / total_checks) * 100)
        return correlation_score, f"{overlap} razy online razem z {total_checks} sprawdzeń"
    
    def find_potential_multis(self, min_correlation=70, hours=24):
        """Znajduje potencjalne multi-chary"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        # Pobierz aktywnych graczy z ostatnich 24h
        c.execute('''SELECT DISTINCT player_name 
                     FROM player_status 
                     WHERE timestamp > ?
                     GROUP BY player_name
                     HAVING COUNT(*) > 10''',
                  (cutoff_time,))
        
        active_players = [row[0] for row in c.fetchall()]
        conn.close()
        
        print(f"Analizuję {len(active_players)} aktywnych graczy...")
        
        results = []
        checked = set()
        
        for i, player1 in enumerate(active_players):
            for player2 in active_players[i+1:]:
                pair = tuple(sorted([player1, player2]))
                if pair in checked:
                    continue
                
                checked.add(pair)
                score, reason = self.analyze_correlation(player1, player2, hours)
                
                if score >= min_correlation:
                    results.append({
                        'player1': player1,
                        'player2': player2,
                        'correlation_score': score,
                        'reason': reason
                    })
        
        return sorted(results, key=lambda x: x['correlation_score'], reverse=True)
    
    def run_monitoring(self, interval_minutes=10):
        """Główna pętla monitoringu"""
        print(f"Rozpoczynam monitoring świata {self.world_name}")
        print(f"Częstotliwość: co {interval_minutes} minut")
        
        while True:
            try:
                players = self.fetch_online_players()
                if players:
                    self.save_snapshot(players)
                else:
                    print("Brak danych - możliwy błąd scrapingu")
                
                time.sleep(interval_minutes * 60)
                
            except KeyboardInterrupt:
                print("\nZatrzymano monitoring")
                break
            except Exception as e:
                print(f"Błąd: {e}")
                time.sleep(60)

# Przykład użycia
if __name__ == "__main__":
    monitor = TibiaMonitor("Karmeya")
    
    # Opcja 1: Uruchom monitoring
    # monitor.run_monitoring(interval_minutes=10)
    
    # Opcja 2: Jednorazowa analiza
    monitor.run_monitoring(interval_minutes=10)

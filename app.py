from flask import Flask, render_template_string, jsonify, request
from tibia_monitor import TibiaMonitor
import threading
import json

app = Flask(__name__)
monitor = TibiaMonitor("Karmeya")

# Uruchom monitoring w tle
def background_monitoring():
    monitor.run_monitoring(interval_minutes=10)

monitoring_thread = threading.Thread(target=background_monitoring, daemon=True)
monitoring_thread.start()

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="pl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Tibia Multi-Char Detector - {{ world }}</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            color: #fff;
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        header {
            text-align: center;
            margin-bottom: 40px;
        }
        h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }
        .subtitle {
            opacity: 0.9;
            font-size: 1.1em;
        }
        .controls {
            background: rgba(255,255,255,0.1);
            backdrop-filter: blur(10px);
            border-radius: 15px;
            padding: 25px;
            margin-bottom: 30px;
        }
        .control-row {
            display: flex;
            gap: 15px;
            align-items: center;
            flex-wrap: wrap;
        }
        label {
            font-weight: 600;
        }
        input, select, button {
            padding: 10px 20px;
            border-radius: 8px;
            border: none;
            font-size: 16px;
        }
        input, select {
            background: rgba(255,255,255,0.9);
            color: #333;
        }
        button {
            background: #ff6b35;
            color: white;
            cursor: pointer;
            font-weight: 600;
            transition: all 0.3s;
        }
        button:hover {
            background: #ff8555;
            transform: translateY(-2px);
        }
        .loading {
            text-align: center;
            padding: 40px;
            font-size: 1.2em;
        }
        .results {
            background: rgba(255,255,255,0.1);
            backdrop-filter: blur(10px);
            border-radius: 15px;
            padding: 25px;
        }
        .result-card {
            background: rgba(255,255,255,0.15);
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 15px;
            border-left: 4px solid #ff6b35;
            transition: all 0.3s;
        }
        .result-card:hover {
            background: rgba(255,255,255,0.2);
            transform: translateX(5px);
        }
        .player-names {
            font-size: 1.3em;
            font-weight: 600;
            margin-bottom: 10px;
        }
        .correlation-score {
            display: inline-block;
            padding: 5px 15px;
            border-radius: 20px;
            font-weight: 600;
            margin: 10px 0;
        }
        .score-high { background: #ff4444; }
        .score-medium { background: #ffaa44; }
        .score-low { background: #44aa44; }
        .reason {
            opacity: 0.9;
            font-style: italic;
        }
        .stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .stat-card {
            background: rgba(255,255,255,0.15);
            border-radius: 10px;
            padding: 20px;
            text-align: center;
        }
        .stat-value {
            font-size: 2.5em;
            font-weight: 700;
            color: #ff6b35;
        }
        .stat-label {
            opacity: 0.8;
            margin-top: 5px;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🎮 Tibia Multi-Char Detector</h1>
            <div class="subtitle">Świat: {{ world }} | Monitoring 24/7</div>
        </header>

        <div class="controls">
            <div class="control-row">
                <label for="hours">Okres analizy:</label>
                <select id="hours">
                    <option value="6">6 godzin</option>
                    <option value="12">12 godzin</option>
                    <option value="24" selected>24 godziny</option>
                    <option value="48">48 godzin</option>
                    <option value="168">7 dni</option>
                </select>

                <label for="minScore">Min. prawdopodobieństwo:</label>
                <select id="minScore">
                    <option value="50">50%</option>
                    <option value="60">60%</option>
                    <option value="70" selected>70%</option>
                    <option value="80">80%</option>
                    <option value="90">90%</option>
                </select>

                <button onclick="analyze()">🔍 Analizuj</button>
                <button onclick="checkPlayers()">👥 Porównaj graczy</button>
            </div>
        </div>

        <div class="stats" id="stats"></div>
        <div class="results" id="results">
            <p style="text-align: center; opacity: 0.7;">
                Kliknij "Analizuj" aby wyszukać potencjalne multi-chary
            </p>
        </div>
    </div>

    <script>
        async function analyze() {
            const hours = document.getElementById('hours').value;
            const minScore = document.getElementById('minScore').value;
            
            document.getElementById('results').innerHTML = 
                '<div class="loading">⏳ Analizuję dane... To może potrwać chwilę.</div>';
            
            try {
                const response = await fetch(`/api/analyze?hours=${hours}&min_score=${minScore}`);
                const data = await response.json();
                displayResults(data);
            } catch (error) {
                document.getElementById('results').innerHTML = 
                    '<div class="loading">❌ Błąd: ' + error.message + '</div>';
            }
        }

        function displayResults(data) {
            const resultsDiv = document.getElementById('results');
            
            if (data.results.length === 0) {
                resultsDiv.innerHTML = 
                    '<p style="text-align: center;">Nie znaleziono podejrzanych par graczy.</p>';
                return;
            }

            let html = '<h2 style="margin-bottom: 20px;">🔍 Znalezione podejrzane pary:</h2>';
            
            data.results.forEach(result => {
                const score = result.correlation_score;
                let scoreClass = 'score-low';
                if (score >= 80) scoreClass = 'score-high';
                else if (score >= 60) scoreClass = 'score-medium';
                
                html += `
                    <div class="result-card">
                        <div class="player-names">
                            ${result.player1} ⚔️ ${result.player2}
                        </div>
                        <div class="correlation-score ${scoreClass}">
                            Prawdopodobieństwo multi: ${score.toFixed(1)}%
                        </div>
                        <div class="reason">
                            📊 ${result.reason}
                        </div>
                    </div>
                `;
            });
            
            resultsDiv.innerHTML = html;
        }

        async function checkPlayers() {
            const player1 = prompt("Podaj nazwę pierwszego gracza:");
            const player2 = prompt("Podaj nazwę drugiego gracza:");
            
            if (!player1 || !player2) return;
            
            document.getElementById('results').innerHTML = 
                '<div class="loading">⏳ Sprawdzam korelację...</div>';
            
            try {
                const hours = document.getElementById('hours').value;
                const response = await fetch(
                    `/api/compare?player1=${player1}&player2=${player2}&hours=${hours}`
                );
                const data = await response.json();
                
                displayResults({ results: [data] });
            } catch (error) {
                document.getElementById('results').innerHTML = 
                    '<div class="loading">❌ Błąd: ' + error.message + '</div>';
            }
        }

        // Auto-refresh co 5 minut
        setInterval(() => {
            if (document.getElementById('results').children.length > 1) {
                analyze();
            }
        }, 300000);
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE, world=monitor.world_name)

@app.route('/api/analyze')
def api_analyze():
    hours = int(request.args.get('hours', 24))
    min_score = int(request.args.get('min_score', 70))
    
    results = monitor.find_potential_multis(min_correlation=min_score, hours=hours)
    
    return jsonify({
        'results': results,
        'analyzed_hours': hours,
        'min_score': min_score
    })

@app.route('/api/compare')
def api_compare():
    player1 = request.args.get('player1')
    player2 = request.args.get('player2')
    hours = int(request.args.get('hours', 24))
    
    if not player1 or not player2:
        return jsonify({'error': 'Brak nazw graczy'}), 400
    
    score, reason = monitor.analyze_correlation(player1, player2, hours)
    
    return jsonify({
        'player1': player1,
        'player2': player2,
        'correlation_score': score,
        'reason': reason
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)

from pathlib import Path
import re
from collections import defaultdict
from flask import Flask, render_template_string, request, jsonify
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SubtitleProcessor:
    def __init__(self, directory_path=None):
        self.word_occurrences = defaultdict(list)
        self.word_counts = defaultdict(int)
        if directory_path:
            self.process_directory(directory_path)
        
    def process_subtitle_file(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                content = f.read()
            
            lines = content.split('\n')
            text_lines = []
            
            i = 0
            while i < len(lines):
                line = lines[i].strip()
                if line and not line.isdigit() and '-->' not in line and not line.startswith('[') and not line.startswith('('):
                    text_lines.append(line)
                i += 1
                    
            for line in text_lines:
                words = re.findall(r'\b[a-zA-Z]+\b', line.lower())
                
                for word in words:
                    if len(word) > 1:  # Ignora palavras de uma letra
                        self.word_counts[word] += 1
                        self.word_occurrences[word].append({
                            'line': line.strip(),
                            'file': str(file_path.name)
                        })
                        
            logger.info(f"Processado arquivo {file_path.name} - Encontradas {len(words)} palavras")
                        
        except Exception as e:
            logger.error(f"Erro ao processar arquivo {file_path}: {str(e)}")

    def process_directory(self, directory_path):
        path = Path(directory_path)
        files_processed = 0
        for srt_file in path.glob('*.srt'):
            logger.info(f"Processando arquivo: {srt_file.name}")
            self.process_subtitle_file(srt_file)
            files_processed += 1
            
        logger.info(f"Total de arquivos processados: {files_processed}")
        logger.info(f"Total de palavras únicas encontradas: {len(self.word_counts)}")
            
    def get_sorted_words(self):
        words = sorted(self.word_counts.items(), key=lambda x: x[1], reverse=True)
        logger.info(f"Retornando {len(words)} palavras ordenadas")
        return words
    
    def get_word_occurrences(self, word):
        return self.word_occurrences[word.lower()]

# Criação do app Flask
app = Flask(__name__)

# Instância global do processador (será inicializada mais tarde)
subtitle_processor = None

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>English Learning from Subtitles</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 20px;
            padding: 20px;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }
        th, td {
            padding: 12px;
            text-align: left;
            border: 1px solid #ddd;
        }
        th {
            background-color: #4CAF50;
            color: white;
        }
        tr:nth-child(even) {
            background-color: #f2f2f2;
        }
        .occurrences {
            display: none;
            margin-top: 10px;
            padding: 15px;
            background-color: #f9f9f9;
            border-radius: 5px;
        }
        .occurrence-item {
            margin-bottom: 10px;
            padding: 10px;
            border-bottom: 1px solid #eee;
            line-height: 1.4;
        }
        button {
            padding: 5px 10px;
            margin: 0 5px;
            cursor: pointer;
            border: none;
            border-radius: 3px;
        }
        button:first-child {
            background-color: #4CAF50;
            color: white;
        }
        button:last-child {
            background-color: #f44336;
            color: white;
        }
        .stats {
            margin-bottom: 20px;
            padding: 10px;
            background-color: #e7f3ff;
            border-radius: 5px;
        }
    </style>
    <script>
        function toggleOccurrences(word) {
            const occurrencesDiv = document.getElementById('occurrences-' + word);
            if (occurrencesDiv.style.display === 'none') {
                fetch('/get_occurrences/' + word)
                    .then(response => response.json())
                    .then(data => {
                        let html = '';
                        data.forEach(occurrence => {
                            html += `<div class="occurrence-item">
                                <strong>File:</strong> ${occurrence.file}<br>
                                <strong>Line:</strong> ${occurrence.line}
                            </div>`;
                        });
                        occurrencesDiv.innerHTML = html;
                        occurrencesDiv.style.display = 'block';
                    });
            } else {
                occurrencesDiv.style.display = 'none';
            }
        }
        
        function removeWord(word) {
            fetch('/remove_word/' + word, { method: 'POST' })
                .then(() => {
                    const row = document.getElementById('row-' + word);
                    const occurrencesRow = row.nextElementSibling;
                    row.remove();
                    occurrencesRow.remove();
                });
        }
    </script>
</head>
<body>
    <h1>English Learning from Subtitles</h1>
    <div class="stats">
        <h3>Statistics:</h3>
        <p>Total unique words: {{ total_words }}</p>
    </div>
    <table>
        <tr>
            <th>Word</th>
            <th>Occurrences</th>
            <th>Actions</th>
        </tr>
        {% for word, count in words %}
        <tr id="row-{{ word }}">
            <td>{{ word }}</td>
            <td>{{ count }}</td>
            <td>
                <button onclick="toggleOccurrences('{{ word }}')">Show Phrases</button>
                <button onclick="removeWord('{{ word }}')">Remove</button>
            </td>
        </tr>
        <tr>
            <td colspan="3">
                <div id="occurrences-{{ word }}" class="occurrences" style="display: none;">
                </div>
            </td>
        </tr>
        {% endfor %}
    </table>
</body>
</html>
'''

@app.route('/')
def index():
    if subtitle_processor is None:
        return "Erro: Nenhum diretório processado"
    words = subtitle_processor.get_sorted_words()
    total_words = len(words)
    return render_template_string(HTML_TEMPLATE, words=words, total_words=total_words)

@app.route('/get_occurrences/<word>')
def get_occurrences(word):
    return jsonify(subtitle_processor.get_word_occurrences(word))

@app.route('/remove_word/<word>', methods=['POST'])
def remove_word(word):
    if word in subtitle_processor.word_counts:
        del subtitle_processor.word_counts[word]
        del subtitle_processor.word_occurrences[word]
    return jsonify({'status': 'success'})

def validate_directory(directory_path):
    path = Path(directory_path)
    if not path.exists():
        return False
    if not path.is_dir():
        return False
    srt_files = list(path.glob('*.srt'))
    if not srt_files:
        return False
    logger.info(f"Encontrados {len(srt_files)} arquivos .srt no diretório")
    return True

if __name__ == '__main__':
    while True:
        directory = input("\nDigite o caminho do diretório com os arquivos .srt: ").strip()
        
        if validate_directory(directory):
            print(f"\nProcessando arquivos do diretório: {directory}")
            
            # Inicializa o processador com o diretório
            subtitle_processor = SubtitleProcessor(directory)
            
            if len(subtitle_processor.word_counts) > 0:
                print("\nProcessamento concluído com sucesso!")
                print(f"Total de palavras únicas encontradas: {len(subtitle_processor.word_counts)}")
                print("\nIniciando servidor web...")
                print("Acesse http://localhost:5000 no seu navegador")
                app.run(debug=False, host='0.0.0.0')
                break
            else:
                print("\nERRO: Nenhuma palavra foi processada dos arquivos.")
        else:
            print("\nERRO: Diretório inválido ou não contém arquivos .srt")
            retry = input("Deseja tentar novamente? (s/n): ").lower()
            if retry != 's':
                print("Programa encerrado.")
                break
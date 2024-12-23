# main.py
from pathlib import Path
import re
from collections import defaultdict
from flask import Flask, render_template, request, jsonify
import logging
from urllib.parse import unquote

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SubtitleProcessor:
    def __init__(self, directory_path=None):
        self.word_occurrences = defaultdict(list)
        self.word_counts = defaultdict(int)
        self.exceptions = self.load_exceptions()
        self.exception_stats = {
            'total_exceptions': len(self.exceptions),
            'total_exception_occurrences': 0,
            'exception_word_counts': defaultdict(int)
        }
        if directory_path:
            self.process_directory(directory_path)
    
    def load_exceptions(self):
        try:
            exceptions_file = Path(__file__).parent / 'exceptions.txt'
            if exceptions_file.exists():
                with open(exceptions_file, 'r', encoding='utf-8') as f:
                    return {word.strip().lower() for word in f if word.strip()}
            logger.info("Arquivo exceptions.txt não encontrado. Criando arquivo vazio.")
            exceptions_file.touch()
            return set()
        except Exception as e:
            logger.error(f"Erro ao carregar exceções: {str(e)}")
            return set()
        
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
                words = re.findall(r"\b[a-zA-Z]+(?:'[a-zA-Z]+)?(?=\s|$)", line.lower())
                
                for word in words:
                    if len(word) > 1:
                        if word in self.exceptions:
                            self.exception_stats['exception_word_counts'][word] += 1
                            self.exception_stats['total_exception_occurrences'] += 1
                        else:
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
    
    def get_stats(self):
        return {
            'total_words': len(self.word_counts),
            'total_occurrences': sum(self.word_counts.values()),
            'total_exceptions': len(self.exceptions),
            'total_exception_occurrences': self.exception_stats['total_exception_occurrences'],
            'unique_exception_words': len(self.exception_stats['exception_word_counts'])
        }

app = Flask(__name__)
subtitle_processor = None

@app.route('/')
def index():
    if subtitle_processor is None:
        return "Erro: Nenhum diretório processado"
    words = subtitle_processor.get_sorted_words()
    stats = subtitle_processor.get_stats()
    
    formatted_stats = {
        'total_words': "{:,}".format(stats['total_words']).replace(",", "."),
        'total_occurrences': "{:,}".format(stats['total_occurrences']).replace(",", "."),
        'total_exceptions': "{:,}".format(stats['total_exceptions']).replace(",", "."),
        'total_exception_occurrences': "{:,}".format(stats['total_exception_occurrences']).replace(",", "."),
        'unique_exception_words': "{:,}".format(stats['unique_exception_words']).replace(",", ".")
    }
    
    return render_template('index.html', words=words, stats=formatted_stats)

@app.route('/get_stats')
def get_stats():
    stats = subtitle_processor.get_stats()
    formatted_stats = {
        'total_words': "{:,}".format(stats['total_words']).replace(",", "."),
        'total_occurrences': "{:,}".format(stats['total_occurrences']).replace(",", "."),
        'total_exceptions': "{:,}".format(stats['total_exceptions']).replace(",", "."),
        'total_exception_occurrences': "{:,}".format(stats['total_exception_occurrences']).replace(",", "."),
        'unique_exception_words': "{:,}".format(stats['unique_exception_words']).replace(",", ".")
    }
    return jsonify(formatted_stats)

@app.route('/get_occurrences/<word>')
def get_occurrences(word):
    decoded_word = unquote(word)
    return jsonify(subtitle_processor.get_word_occurrences(decoded_word))

@app.route('/remove_word/<word>', methods=['POST'])
def remove_word(word):
    decoded_word = unquote(word)
    
    exceptions_file = Path(__file__).parent / 'exceptions.txt'
    
    with open(exceptions_file, 'a', encoding='utf-8') as f:
        f.write(decoded_word.lower() + '\n')
    
    # Atualiza as exceções no subtitle_processor
    subtitle_processor.exceptions.add(decoded_word.lower())
    subtitle_processor.exception_stats['total_exceptions'] = len(subtitle_processor.exceptions)
    
    if decoded_word in subtitle_processor.word_counts:
        del subtitle_processor.word_counts[decoded_word]
        del subtitle_processor.word_occurrences[decoded_word]
    
    return jsonify(subtitle_processor.get_stats())

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
    print("\nVerificando arquivo de exceções...")
    exceptions_file = Path('exceptions.txt')
    if not exceptions_file.exists():
        print("Arquivo exceptions.txt não encontrado. Criando arquivo vazio.")
        exceptions_file.touch()
    else:
        print("Arquivo exceptions.txt encontrado.")
    
    while True:
        directory = input("\nDigite o caminho do diretório com os arquivos .srt: ").strip()
        
        if validate_directory(directory):
            print(f"\nProcessando arquivos do diretório: {directory}")
            
            subtitle_processor = SubtitleProcessor(directory)
            
            if len(subtitle_processor.word_counts) > 0:
                print("\nProcessamento concluído com sucesso!")
                stats = subtitle_processor.get_stats()
                print(f"Total de palavras únicas encontradas: {stats['total_words']}")
                print(f"Total de ocorrências: {stats['total_occurrences']}")
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
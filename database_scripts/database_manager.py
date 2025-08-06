import sqlite3
# import pandas as pd # Não é mais necessário para ler o arquivo de entrada
import os
import glob
import logging
import re 
import json # Adicionar import json
from datetime import datetime

# Configuração do Logging (igual)
log_format = '%(asctime)s - %(levelname)s - %(message)s'
logging.basicConfig(level=logging.INFO, format=log_format)
logger = logging.getLogger(__name__)

# --- Constantes ---
DATABASE_FILE = os.path.join(os.path.dirname(__file__), '..', 'shopping_app.db')
# Renomear para refletir que pode ser JSON ou outros, ou manter se a pasta é a mesma
DATA_FILES_DIR = os.path.join(os.path.dirname(__file__), '..', 'dados_coletados') 
SUPERMERCADO_ATUAL = 'Pingo Doce'

# --- Função criar_conexao_e_tabela --- (Permanece igual à versão anterior com o schema atualizado)
def criar_conexao_e_tabela():
    conn = None
    try:
        db_path = os.path.abspath(DATABASE_FILE)
        logger.info(f"Conectando/Criando banco de dados em: {db_path}")
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        cursor.execute("DROP TABLE IF EXISTS Produtos") 
        logger.info("Tabela 'Produtos' antiga removida (se existia) para recriação com novo schema.")
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS Produtos (
            id_produto TEXT PRIMARY KEY, nome_produto TEXT NOT NULL, marca TEXT,
            preco REAL, unidade_info_original TEXT, quantidade_embalagem REAL,
            unidade_embalagem TEXT, preco_unidade_ref REAL, unidade_ref TEXT,
            categoria_principal TEXT, sub_categorias TEXT, data_coleta TEXT NOT NULL,
            supermercado TEXT NOT NULL
        )''')
        conn.commit()
        logger.info("Tabela 'Produtos' (novo schema) verificada/criada com sucesso.")
    except sqlite3.Error as e: logger.error(f"Erro DB: {e}")
    finally:
        if conn: conn.close()

# --- Função parse_unidade_info --- (Permanece igual à versão anterior)
def parse_unidade_info(texto_unidade, preco_item):
    if not texto_unidade or not isinstance(texto_unidade, str):
        return None, None, None, None
    texto_unidade_norm = texto_unidade.lower().replace(',', '.')
    qtd_embalagem, und_embalagem, preco_ref, und_ref = None, None, None, None
    match_completo = re.search(r'([\d.]+)\s*([a-zç]+)\s*\|\s*([\d.]+)\s*€\s*/\s*([\d.]*[a-zç]+)', texto_unidade_norm)
    if match_completo:
        try:
            qtd_embalagem = float(match_completo.group(1)); und_embalagem = match_completo.group(2)
            preco_ref = float(match_completo.group(3)); und_ref = match_completo.group(4)
            if und_embalagem in ['un', 'uni', 'unid']: und_embalagem = 'unidade'
            if und_ref in ['un', 'uni', 'unid']: und_ref = 'unidade'
            return qtd_embalagem, und_embalagem, preco_ref, und_ref
        except ValueError: logger.warning(f"ValueError parse completo: '{texto_unidade}' grupos: {match_completo.groups()}")
    match_simples = re.search(r'([\d.]+)\s*([a-zç]+)', texto_unidade_norm)
    if match_simples:
        try:
            qtd_embalagem = float(match_simples.group(1)); und_embalagem = match_simples.group(2)
            if und_embalagem in ['un', 'uni', 'unid']: und_embalagem = 'unidade'
            if preco_item is not None and qtd_embalagem > 0:
                if und_embalagem == 'g': preco_ref = round((preco_item / qtd_embalagem) * 1000, 2); und_ref = 'kg'
                elif und_embalagem == 'ml': preco_ref = round((preco_item / qtd_embalagem) * 1000, 2); und_ref = 'l'
                elif und_embalagem == 'cl': preco_ref = round((preco_item / qtd_embalagem) * 100, 2); und_ref = 'l'
                elif und_embalagem == 'unidade': preco_ref = round(preco_item / qtd_embalagem, 2); und_ref = 'unidade'
            return qtd_embalagem, und_embalagem, preco_ref, und_ref
        except ValueError: logger.warning(f"ValueError parse simples: '{texto_unidade}' grupos: {match_simples.groups()}")
    match_aprox = re.search(r'aprox\.?\s*([\d.]+)\s*([a-zç]+)', texto_unidade_norm)
    if match_aprox:
        try:
            qtd_embalagem = float(match_aprox.group(1)); und_embalagem = match_aprox.group(2)
            if und_embalagem in ['un', 'uni', 'unid']: und_embalagem = 'unidade'
            return qtd_embalagem, und_embalagem, preco_ref, und_ref 
        except ValueError: logger.warning(f"ValueError parse aprox: '{texto_unidade}' grupos: {match_aprox.groups()}")
    logger.debug(f"Não foi possível parsear estruturadamente: '{texto_unidade}'.")
    return None, None, None, None


# MODIFICADA: Função para encontrar o arquivo JSON mais recente
def encontrar_json_mais_recente():
    """Encontra o arquivo JSON mais recente na pasta de dados."""
    try:
        data_dir_abs_path = os.path.abspath(DATA_FILES_DIR) # Usar DATA_FILES_DIR
        # Procurar por arquivos .json
        list_of_files = glob.glob(os.path.join(data_dir_abs_path, 'precos_pingodoce_*.json')) 
        if not list_of_files:
            logger.warning(f"Nenhum arquivo JSON encontrado em: {data_dir_abs_path}")
            return None
        latest_file = max(list_of_files, key=os.path.getmtime)
        logger.info(f"Arquivo JSON mais recente encontrado: {latest_file}")
        return latest_file
    except Exception as e:
        logger.error(f"Erro ao encontrar o arquivo JSON mais recente: {e}")
        return None

# MODIFICADA: Função para importar dados do JSON
def importar_dados_do_json(json_path):
    """Lê os dados do arquivo JSON, transforma-os e os insere no banco de dados."""
    if not json_path:
        logger.error("Caminho do arquivo JSON não fornecido para importação.")
        return

    conn = None
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            lista_de_produtos = json.load(f) # Carrega a lista de dicionários
        
        logger.info(f"Lidos {len(lista_de_produtos)} registros do arquivo JSON: {json_path}")

        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        # A tabela já foi limpa/recriada por criar_conexao_e_tabela()

        produtos_para_inserir = []
        for index, item in enumerate(lista_de_produtos): # 'item' é um dicionário de produto
            nome_produto = str(item.get('Nome', '')).strip()
            marca_raw = item.get('Marca')
            marca = str(marca_raw).strip() if marca_raw is not None and str(marca_raw).strip() else None
            
            preco_raw = item.get('Preco')
            preco = None
            if preco_raw is not None and preco_raw != 'N/A': # 'N/A' pode vir do scraper
                try:
                    preco = float(str(preco_raw).replace(',', '.'))
                    if preco < 0:
                        logger.warning(f"Preço negativo para '{nome_produto}' (pid: {item.get('ID_Produto')}): {preco_raw}. Será NULL.")
                        preco = None
                except (ValueError, TypeError):
                    logger.warning(f"Preço inválido para '{nome_produto}' (pid: {item.get('ID_Produto')}): '{preco_raw}'. Será NULL.")
                    preco = None
            
            unidade_info_original_raw = item.get('Unidade_Info')
            unidade_info_original = str(unidade_info_original_raw).strip() if unidade_info_original_raw is not None and str(unidade_info_original_raw).strip() else None
            qtd_emb, und_emb, prc_ref, und_ref = parse_unidade_info(unidade_info_original, preco)

            data_coleta_raw = item.get('Data_Coleta') # O scraper já deve salvar no formato correto
            data_coleta = data_coleta_raw if isinstance(data_coleta_raw, str) else datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            produto_tupla = (
                str(item.get('ID_Produto', f'SEM_ID_{index}')),
                nome_produto, marca, preco, unidade_info_original,
                qtd_emb, und_emb, prc_ref, und_ref,
                str(item.get('Categoria_Scraping', '')).strip() if item.get('Categoria_Scraping') is not None and str(item.get('Categoria_Scraping','')).strip() else None,
                str(item.get('Categorias_GTM', '')).strip() if item.get('Categorias_GTM') is not None and str(item.get('Categorias_GTM','')).strip() else None,
                data_coleta, SUPERMERCADO_ATUAL
            )
            produtos_para_inserir.append(produto_tupla)
        
        if produtos_para_inserir:
            cursor.executemany('''
            INSERT OR REPLACE INTO Produtos (id_produto, nome_produto, marca, preco, unidade_info_original,
                                 quantidade_embalagem, unidade_embalagem, preco_unidade_ref, unidade_ref,
                                 categoria_principal, sub_categorias, data_coleta, supermercado)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', produtos_para_inserir)
            conn.commit()
            logger.info(f"{cursor.rowcount} novos registros inseridos na tabela Produtos.")
        else:
            logger.info("Nenhum produto para inserir na tabela Produtos.")

    except FileNotFoundError: 
        logger.error(f"Arquivo JSON não encontrado: {json_path}")
    except json.JSONDecodeError as e: # Erro específico para JSON malformado ou vazio
        logger.error(f"Erro ao decodificar JSON do arquivo '{json_path}': {e}")
    except sqlite3.Error as e:
        logger.error(f"Erro SQLite ao importar dados: {e}")
        if conn: conn.rollback()
    except Exception as e:
        logger.error(f"Erro inesperado ao importar dados do JSON: {e}", exc_info=True)
        if conn: conn.rollback()
    finally:
        if conn:
            conn.close()
            logger.info("Conexão com o banco de dados fechada.")

if __name__ == "__main__":
    logger.info("Iniciando gerenciador do banco de dados (JSON input)...")
    criar_conexao_e_tabela()
    
    caminho_json = encontrar_json_mais_recente() # Chama a função renomeada
    
    if caminho_json:
        importar_dados_do_json(caminho_json) # Chama a função renomeada
    else:
        logger.warning("Nenhum arquivo JSON para processar.")
    
    logger.info("Processo do gerenciador do banco de dados concluído.")
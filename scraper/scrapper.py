import requests
from bs4 import BeautifulSoup
import pandas as pd
import logging
import time
from datetime import datetime
import json
import os

from datetime import datetime # Já deve estar lá
import logging # Já deve estar lá

from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, ElementNotInteractableException, TimeoutException, StaleElementReferenceException, ElementClickInterceptedException

# --- Configuração do Logging ---
log_format = '%(asctime)s - %(levelname)s - %(message)s'
logging.basicConfig(level=logging.INFO, format=log_format) 
logger = logging.getLogger(__name__)

# --- URLs para scraping ---
urls_categorias = {
    'mercearia': 'https://www.pingodoce.pt/home/mercearia?/',
    'talho': 'https://www.pingodoce.pt/home/talho?/',
    'peixaria': 'https://www.pingodoce.pt/home/peixaria?/',
    'promocoes' : 'https://www.pingodoce.pt/home/promocoes?',
    'frutas-e-vegetais' : 'https://www.pingodoce.pt/home/frutas-e-vegetais?',
    'padaria' : 'https://www.pingodoce.pt/home/padaria-e-pastelaria?',
    'charcutaria' : 'https://www.pingodoce.pt/home/charcutaria?',
    'congelados' : 'https://www.pingodoce.pt/home/congelados?',
    'leite-e-ovos' : 'https://www.pingodoce.pt/home/leite-natas-e-ovos?',
    'frigorificos' : 'https://www.pingodoce.pt/home/frigorifico?/',
    'bebidas' : 'https://www.pingodoce.pt/home/bebidas?',
    'infantil' : 'https://www.pingodoce.pt/home/infantil?',
    'higiene pessoal e beleza' : 'https://www.pingodoce.pt/home/higiene-pessoal-e-beleza?',
    'casa' : 'https://www.pingodoce.pt/home/casa?',
    'animais' : 'https://www.pingodoce.pt/home/animais?',
    'bazar' : 'https://www.pingodoce.pt/home/bazar?',


    # Adicione mais URLs de categorias conforme necessário
}

SELENIUM_USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'

# --- Função setup_driver --- (igual à anterior)
def setup_driver():
    options = webdriver.ChromeOptions()
    options.add_argument(f"user-agent={SELENIUM_USER_AGENT}")
    # options.add_argument("--headless") # Descomente para produção
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage") 
    options.add_argument("start-maximized") 
    options.add_argument("disable-infobars")
    options.add_argument("--disable-extensions")
    logger.info("Configurando o WebDriver para Chrome...")
    try:
        driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=options)
        logger.info("WebDriver configurado com sucesso.")
        return driver
    except Exception as e:
        logger.error(f"Erro ao configurar o WebDriver: {e}")
        return None

# --- Função extract_product_data_from_element --- (igual à anterior)
def extract_product_data_from_element(product_element, categoria):
    try:
        product_id = product_element.get('data-pid', 'N/A')
        nome = 'N/A'
        preco_float = 'N/A'
        marca = 'N/A'
        unidade_info = 'N/A'
        categorias_gtm = []

        gtm_info_str = product_element.get('data-gtm-info')
        if gtm_info_str:
            try:
                gtm_data = json.loads(gtm_info_str)
                if 'items' in gtm_data and len(gtm_data['items']) > 0:
                    item_details = gtm_data['items'][0]
                    nome = item_details.get('item_name', 'N/A')
                    preco_float = item_details.get('price', gtm_data.get('value', 'N/A'))
                    marca = item_details.get('item_brand', 'N/A')
                    for i in range(1, 6): 
                        cat_key = f'item_category{"" if i == 1 else i}'
                        if item_details.get(cat_key): categorias_gtm.append(item_details.get(cat_key))
                elif 'value' in gtm_data and gtm_data.get('items') and 'item_name' in gtm_data['items'][0]:
                     item_details = gtm_data['items'][0]
                     nome = item_details.get('item_name', 'N/A')
                     preco_float = gtm_data.get('value', 'N/A') 
                     marca = item_details.get('item_brand', 'N/A')
                     for i in range(1, 6):
                        cat_key = f'item_category{"" if i == 1 else i}'
                        if item_details.get(cat_key): categorias_gtm.append(item_details.get(cat_key))
            except json.JSONDecodeError as je: logger.error(f"JSONDecodeError para pid {product_id}: {je} - GTM: {gtm_info_str[:100]}")
            except Exception as ex: logger.error(f"Erro GTM para pid {product_id}: {ex} - GTM: {gtm_info_str[:100]}")
        
        if nome == 'N/A':
            name_tag = product_element.select_one('div.product-name-link > a')
            nome = name_tag.get_text(strip=True) if name_tag else 'N/A'
        if preco_float == 'N/A' or not isinstance(preco_float, (int, float)): # Verifica se não é número
            price_sales_tag = product_element.select_one('div.product-price span.sales')
            if price_sales_tag:
                preco_texto = price_sales_tag.get_text(strip=True).replace('€', '').replace(',', '.').strip()
                try: preco_float = float(preco_texto)
                except ValueError: preco_float = 'N/A'
            else:
                price_value_tag = product_element.select_one('div.product-price span.value[content]')
                if price_value_tag:
                    try: preco_float = float(price_value_tag['content'])
                    except ValueError: preco_float = 'N/A'
        if marca == 'N/A':
            brand_tag = product_element.select_one('div.product-brand-name')
            marca = brand_tag.get_text(strip=True) if brand_tag else 'N/A'

        unit_tag = product_element.select_one('div.product-unit')
        unidade_info = unit_tag.get_text(strip=True).replace('\n', ' ').replace('\r', ' ').strip() if unit_tag else 'N/A'

        if nome != 'N/A' and nome.strip() != '' and isinstance(preco_float, (int, float)):
            return {
                'ID_Produto': product_id, 'Categoria_Scraping': categoria, 'Nome': nome,
                'Marca': marca, 'Preco': preco_float, 'Unidade_Info': unidade_info,
                'Categorias_GTM': ', '.join(categorias_gtm) if categorias_gtm else 'N/A',
                'Data_Coleta': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        # logger.debug(f"Produto pid {product_id} descartado. Nome: '{nome}', Preço: {preco_float}")
        return None
    except Exception as e:
        logger.error(f"Erro extract_product_data (pid {product_element.get('data-pid', 'DESCONHECIDO')}): {e}")
        return None

# --- Função para raspar uma categoria com a nova estratégia HÍBRIDA ---
def scrape_category_with_selenium(driver, url, categoria_nome):
    logger.info(f"Acessando URL com Selenium: {url}")
    produtos_coletados_categoria = []
    seen_product_ids_in_category = set()

    try:
        driver.get(url)
        logger.info("Aguardando carregamento inicial da página (10s)...")
        time.sleep(10)

        # --- Fase 1: Extrair produtos iniciais ---
        logger.info("Extraindo produtos carregados inicialmente...")
        initial_soup = BeautifulSoup(driver.page_source, 'html.parser')
        product_elements_initial = initial_soup.select('div.product-tile-pd')
        novos_nesta_fase = 0
        for element in product_elements_initial:
            product_data = extract_product_data_from_element(element, categoria_nome)
            if product_data and product_data['ID_Produto'] != 'N/A' and product_data['ID_Produto'] not in seen_product_ids_in_category:
                produtos_coletados_categoria.append(product_data)
                seen_product_ids_in_category.add(product_data['ID_Produto'])
                novos_nesta_fase += 1
        logger.info(f"Extraídos {novos_nesta_fase} produtos iniciais únicos.")

        # --- Fase 2: Tentar clicar no botão "Ver mais" UMA VEZ ---
        ver_mais_button_clicked_successfully = False
        try:
            button_xpath = "//div[contains(@class, 'show-more')]//button[contains(@class, 'more') and contains(normalize-space(.), 'Ver mais')]"
            logger.info(f"Tentando encontrar botão 'Ver mais' (clique único) com XPath: {button_xpath}")
            wait = WebDriverWait(driver, 10) # Espera mais curta, pois pode não existir

            # Espera que o botão esteja presente e depois clicável
            ver_mais_button_initial_ref = wait.until(EC.presence_of_element_located((By.XPATH, button_xpath)))
            logger.debug("Botão 'Ver mais' (clique único) presente no DOM.")
            ver_mais_button_clickable = wait.until(EC.element_to_be_clickable((By.XPATH, button_xpath)))
            
            logger.info(f"Botão 'Ver mais' ({ver_mais_button_clickable.text.strip()}) encontrado para clique único.")

            if ver_mais_button_clickable.is_displayed():
                driver.execute_script("arguments[0].scrollIntoView({behavior: 'auto', block: 'center', inline: 'nearest'});", ver_mais_button_clickable)
                time.sleep(1) # Pausa para scroll

                # Re-localizar o botão ANTES de clicar para evitar StaleElementReferenceException
                logger.debug("Re-localizando botão 'Ver mais' antes do clique...")
                ver_mais_button_fresh = driver.find_element(By.XPATH, button_xpath)
                
                try:
                    ver_mais_button_fresh.click()
                    logger.info("Botão 'Ver mais' clicado (método normal) uma vez.")
                except ElementClickInterceptedException:
                    logger.warning("Clique normal interceptado. Tentando clique com JavaScript...")
                    driver.execute_script("arguments[0].click();", ver_mais_button_fresh)
                    logger.info("Clique com JavaScript no 'Ver mais' realizado uma vez.")
                
                ver_mais_button_clicked_successfully = True
                logger.info("Aguardando carregamento após clique único no 'Ver mais' (12s)...")
                time.sleep(12) # Tempo para carregar produtos após o clique

                # Extrair produtos após o clique no botão
                logger.info("Extraindo produtos após clique no 'Ver mais'...")
                soup_after_click = BeautifulSoup(driver.page_source, 'html.parser')
                product_elements_after_click = soup_after_click.select('div.product-tile-pd')
                novos_nesta_fase_pos_click = 0
                for element in product_elements_after_click:
                    product_data = extract_product_data_from_element(element, categoria_nome)
                    if product_data and product_data['ID_Produto'] != 'N/A' and product_data['ID_Produto'] not in seen_product_ids_in_category:
                        produtos_coletados_categoria.append(product_data)
                        seen_product_ids_in_category.add(product_data['ID_Produto'])
                        novos_nesta_fase_pos_click += 1
                logger.info(f"Extraídos {novos_nesta_fase_pos_click} produtos únicos após clique no 'Ver mais'.")
            else:
                logger.info("Botão 'Ver mais' (clique único) encontrado mas não visível.")

        except TimeoutException:
            logger.info("Botão 'Ver mais' (clique único) não encontrado ou não clicável a tempo.")
        except (NoSuchElementException, ElementNotInteractableException):
            logger.info("Botão 'Ver mais' (clique único) não encontrado/interagível.")
        except StaleElementReferenceException: # Captura StaleElementReference durante a tentativa de clique único
            logger.warning("Botão 'Ver mais' ficou obsoleto durante a tentativa de clique único. O clique pode ter ocorrido. Prosseguindo...")
            ver_mais_button_clicked_successfully = True # Assume que o clique pode ter acontecido se o botão sumiu rápido
            time.sleep(10) # Dar um tempo caso o clique tenha ocorrido e a página esteja carregando
        except Exception as e_button_click:
            logger.error(f"Erro inesperado ao tentar clique único no 'Ver mais': {e_button_click}")

        # --- Fase 3: Lógica de Scroll Infinito ---
        logger.info("Iniciando lógica de scroll infinito...")
        last_height = driver.execute_script("return document.body.scrollHeight")
        scroll_attempts_no_change = 0
        max_scroll_retries_no_change = 3 
        max_total_scrolls = 50 # Limite de segurança para scrolls totais
        scrolls_done = 0

        while scrolls_done < max_total_scrolls:
            scrolls_done += 1
            logger.info(f"Scroll infinito: Tentativa {scrolls_done}/{max_total_scrolls}")
            
            # Scroll para baixo
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(5) # Esperar carregar após scroll. Ajustar se necessário.

            soup_after_scroll = BeautifulSoup(driver.page_source, 'html.parser')
            product_elements_after_scroll = soup_after_scroll.select('div.product-tile-pd')
            
            novos_nesta_fase_pos_scroll = 0
            for element in product_elements_after_scroll:
                product_data = extract_product_data_from_element(element, categoria_nome)
                if product_data and product_data['ID_Produto'] != 'N/A' and product_data['ID_Produto'] not in seen_product_ids_in_category:
                    produtos_coletados_categoria.append(product_data)
                    seen_product_ids_in_category.add(product_data['ID_Produto'])
                    novos_nesta_fase_pos_scroll += 1
            
            if novos_nesta_fase_pos_scroll > 0:
                logger.info(f"Extraídos {novos_nesta_fase_pos_scroll} produtos únicos após scroll.")
            else:
                logger.info("Nenhum produto novo único encontrado após este scroll.")

            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                # Se não houve scroll E não houve novos produtos, pode ser o fim
                if novos_nesta_fase_pos_scroll == 0:
                    scroll_attempts_no_change += 1
                    logger.info(f"Altura da página e contagem de produtos não mudou. Tentativas sem mudança: {scroll_attempts_no_change}/{max_scroll_retries_no_change}.")
                    if scroll_attempts_no_change >= max_scroll_retries_no_change:
                        logger.info("Altura da página e contagem de produtos estáveis após várias tentativas. Assumindo fim do scroll.")
                        break 
                else: # Houve novos produtos, então resetamos mesmo que a altura não tenha mudado (carregamento AJAX no mesmo lugar)
                    scroll_attempts_no_change = 0

            else: # Altura mudou, então resetamos
                last_height = new_height
                scroll_attempts_no_change = 0
        
        if scrolls_done >= max_total_scrolls:
            logger.warning(f"Atingido o limite máximo de scrolls ({max_total_scrolls}) para a categoria {categoria_nome}.")

    except Exception as e:
        logger.error(f"Erro GERAL em scrape_category_with_selenium para {categoria_nome} ({url}): {e}")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        screenshot_path = f"error_screenshot_geral_{categoria_nome}_{timestamp}.png"
        try:
            driver.save_screenshot(screenshot_path)
            logger.info(f"Screenshot de erro geral salva em: {screenshot_path}")
        except Exception as sc_error: logger.error(f"Falha ao salvar screenshot geral: {sc_error}")
            
    logger.info(f"Coletados {len(produtos_coletados_categoria)} produtos únicos da categoria '{categoria_nome}'.")
    return produtos_coletados_categoria

# --- Função main --- (igual à anterior)
# Na função main() do pingo_doce_scraper.py, substitua a parte de salvar em Excel:
def main():
    logger.info("Iniciando o web scraper de preços do Pingo Doce com Selenium.")
    todos_os_produtos = []
    
    driver = setup_driver()
    if not driver:
        logger.error("Falha ao iniciar o WebDriver. Encerrando o script.")
        return

    for categoria_nome, url_base in urls_categorias.items():
        logger.info(f"--- Iniciando scraping da categoria: {categoria_nome} ---")
        produtos_da_categoria = scrape_category_with_selenium(driver, url_base, categoria_nome)
        todos_os_produtos.extend(produtos_da_categoria)
        
        logger.info(f"--- Fim do scraping da categoria: {categoria_nome} ---")
        if len(urls_categorias) > 1 and categoria_nome != list(urls_categorias.keys())[-1]:
            logger.info(f"Aguardando 10 segundos antes da próxima categoria...")
            time.sleep(10) # Mantenha seus tempos de espera

    if driver:
        logger.info("Fechando o WebDriver.")
        driver.quit()

    # ----- NOVA PARTE PARA SALVAR EM JSON -----
    if todos_os_produtos:
        logger.info(f"Total de {len(todos_os_produtos)} produtos coletados de todas as categorias.")
        
        # Define o diretório de saída (assumindo que está na raiz do projeto)
        # O scraper deve estar na pasta 'scraper/', então '..' volta para a raiz
        # e depois entra em 'dados_coletados/'
        # Se o seu scraper estiver na raiz, apenas 'dados_coletados' é suficiente.
        # Ajuste conforme a localização do seu script scraper.
        # Assumindo que o scraper está em 'scraper/' e 'dados_coletados' está na raiz:
        # output_dir = os.path.join(os.path.dirname(__file__), "..", "dados_coletados")

        # Se o script scraper e a pasta dados_coletados estão no mesmo nível (raiz do projeto):
        output_dir = "dados_coletados"


        if not os.path.exists(output_dir):
            try:
                os.makedirs(output_dir)
                logger.info(f"Diretório '{output_dir}' criado com sucesso.")
            except OSError as e:
                logger.error(f"Erro ao criar o diretório '{output_dir}': {e}")
                # Decide se quer parar ou tentar salvar na pasta atual
                # Por simplicidade, vamos tentar salvar na pasta atual do script se a criação falhar
                output_dir = "." 

        # Gera o nome do arquivo JSON com timestamp
        timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
        nome_arquivo_json = os.path.join(output_dir, f"precos_pingodoce_{timestamp_str}.json")
        
        try:
            with open(nome_arquivo_json, 'w', encoding='utf-8') as f:
                json.dump(todos_os_produtos, f, ensure_ascii=False, indent=4)
            logger.info(f"Dados salvos com sucesso em '{nome_arquivo_json}'")
        except IOError as e:
            logger.error(f"Erro de I/O ao salvar o arquivo JSON '{nome_arquivo_json}': {e}")
        except Exception as e:
            logger.error(f"Erro inesperado ao salvar o arquivo JSON: {e}")
    else:
        logger.warning("Nenhum produto foi coletado. O arquivo JSON não será gerado.")

    logger.info("Scraping concluído.")

if __name__ == '__main__':
    main()
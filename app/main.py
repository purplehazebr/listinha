from flask import Flask, jsonify, request, render_template
import sqlite3
import os
import uuid # Para gerar IDs únicos

# Inicializa a aplicação Flask
app = Flask(__name__)

# Define o caminho para o banco de dados
DATABASE_PATH = os.path.join(os.path.dirname(__file__), '..', 'shopping_app.db')

# Função para criar as tabelas se não existirem
def initialize_database():
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    sql_create_shopping_lists_table = """
    CREATE TABLE IF NOT EXISTS ShoppingLists (
        list_id TEXT PRIMARY KEY,
        list_name TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );"""

    sql_create_list_items_table = """
    CREATE TABLE IF NOT EXISTS ListItems (
        item_id TEXT PRIMARY KEY,
        list_id_fk TEXT NOT NULL,
        product_id_fk TEXT,
        manual_item_name TEXT,
        manual_item_brand TEXT,
        manual_item_unit_info TEXT,
        price_at_add REAL NOT NULL,
        quantity INTEGER NOT NULL DEFAULT 1,
        purchased INTEGER NOT NULL DEFAULT 0, -- 0 for false, 1 for true
        added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (list_id_fk) REFERENCES ShoppingLists (list_id) ON DELETE CASCADE,
        FOREIGN KEY (product_id_fk) REFERENCES Produtos (id_produto) ON DELETE SET NULL
    );"""

    try:
        print("Verificando/Criando tabela ShoppingLists...")
        cursor.execute(sql_create_shopping_lists_table)
        print("Tabela ShoppingLists OK.")

        print("Verificando/Criando tabela ListItems...")
        cursor.execute(sql_create_list_items_table)
        print("Tabela ListItems OK.")
        
        conn.commit()
        print("Banco de dados inicializado/verificado com sucesso.")
    except sqlite3.Error as e:
        print(f"Erro ao inicializar o banco de dados: {e}")
    finally:
        if conn:
            conn.close()

# Função para obter conexão com o DB
def get_db_connection():
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row 
        conn.execute("PRAGMA foreign_keys = ON;") # Habilita constraints de chave estrangeira
        return conn
    except sqlite3.Error as e:
        print(f"Erro ao conectar ao banco de dados: {e}")
        return None

# Helper para gerar IDs únicos
def generate_unique_id(prefix="id_"):
    return f"{prefix}{uuid.uuid4().hex[:12]}" # ID mais curto

# Helper para transformar dados do item para o frontend
def transform_list_item_for_frontend(item_row, conn_for_product_lookup=None):
    item_data = {
        "item_id": item_row["item_id"],
        "list_id_fk": item_row["list_id_fk"], # Adicionado para consistência
        "id": item_row["product_id_fk"] if item_row["product_id_fk"] else f"manual_{item_row['item_id']}",
        "name": item_row["manual_item_name"],
        "brand": item_row["manual_item_brand"],
        "price": item_row["price_at_add"],
        "unitInfo": item_row["manual_item_unit_info"],
        "quantity": item_row["quantity"],
        "purchased": bool(item_row["purchased"])
    }
    if item_row["product_id_fk"] and conn_for_product_lookup:
        product_cursor = conn_for_product_lookup.cursor()
        product_cursor.execute(
            "SELECT nome_produto, marca, unidade_info_original FROM Produtos WHERE id_produto = ?",
            (item_row["product_id_fk"],)
        )
        product_details = product_cursor.fetchone()
        if product_details:
            item_data['name'] = product_details['nome_produto']
            item_data['brand'] = product_details['marca']
            item_data['unitInfo'] = product_details['unidade_info_original']
    return item_data

# --- Rota Principal ---
@app.route('/')
def index():
    return render_template('index.html', title="Minhas Listas de Compras") # Título genérico

# --- API Endpoint para Buscar Produtos (EXISTENTE) ---
@app.route('/api/produtos/buscar', methods=['GET'])
def buscar_produtos():
    termo_busca = request.args.get('termo', '').strip()
    if not termo_busca or len(termo_busca) < 2:
        return jsonify({'erro': 'Termo de busca deve ter pelo menos 2 caracteres.'}), 400
    conn = get_db_connection()
    if not conn:
        return jsonify({'erro': 'Falha ao conectar ao banco de dados.'}), 500
    cursor = conn.cursor()
    query = """
        SELECT id_produto, nome_produto, marca, preco, unidade_info_original,
               quantidade_embalagem, unidade_embalagem, preco_unidade_ref, unidade_ref
        FROM Produtos 
        WHERE nome_produto LIKE ? 
        ORDER BY nome_produto 
        LIMIT 20 
    """
    try:
        parametro_like = f"%{termo_busca}%"
        cursor.execute(query, (parametro_like,))
        produtos_encontrados = [dict(row) for row in cursor.fetchall()]
        return jsonify(produtos_encontrados)
    except sqlite3.Error as e:
        return jsonify({'erro': f'Erro ao buscar produtos: {str(e)}'}), 500
    finally:
        if conn: conn.close()

# --- API Endpoints para Listas de Compras (NOVOS) ---
@app.route('/api/shoppinglists', methods=['GET'])
def get_all_lists_api():
    conn = get_db_connection()
    if not conn: return jsonify({'erro': 'DB connection error.'}), 500
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT list_id, list_name, created_at FROM ShoppingLists ORDER BY created_at DESC")
        lists = [dict(row) for row in cursor.fetchall()]
        return jsonify(lists)
    except sqlite3.Error as e:
        return jsonify({'erro': str(e)}), 500
    finally:
        if conn: conn.close()

@app.route('/api/shoppinglists', methods=['POST'])
def create_list_api():
    data = request.get_json()
    list_name = data.get('list_name')
    if not list_name: return jsonify({'erro': 'List name is required.'}), 400
    new_list_id = generate_unique_id("list_")
    conn = get_db_connection()
    if not conn: return jsonify({'erro': 'DB connection error.'}), 500
    try:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO ShoppingLists (list_id, list_name) VALUES (?, ?)", (new_list_id, list_name))
        conn.commit()
        cursor.execute("SELECT list_id, list_name, created_at FROM ShoppingLists WHERE list_id = ?", (new_list_id,))
        created_list = dict(cursor.fetchone())
        return jsonify(created_list), 201
    except sqlite3.Error as e:
        return jsonify({'erro': str(e)}), 500
    finally:
        if conn: conn.close()

@app.route('/api/shoppinglists/<list_id>', methods=['DELETE'])
def delete_list_api(list_id):
    conn = get_db_connection()
    if not conn: return jsonify({'erro': 'DB connection error.'}), 500
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM ShoppingLists WHERE list_id = ?", (list_id,)) # ON DELETE CASCADE handles items
        conn.commit()
        if cursor.rowcount == 0: return jsonify({'erro': 'List not found.'}), 404
        return jsonify({'message': 'List deleted successfully.'}), 200
    except sqlite3.Error as e:
        return jsonify({'erro': str(e)}), 500
    finally:
        if conn: conn.close()

# --- API Endpoints para Itens da Lista (NOVOS) ---
@app.route('/api/shoppinglists/<list_id>/items', methods=['GET'])
def get_list_items_api(list_id):
    conn = get_db_connection()
    if not conn: return jsonify({'erro': 'DB connection error.'}), 500
    try:
        list_cursor = conn.cursor() # Check if list exists
        list_cursor.execute("SELECT list_id FROM ShoppingLists WHERE list_id = ?", (list_id,))
        if not list_cursor.fetchone(): return jsonify({'erro': 'List not found.'}), 404
        
        items_cursor = conn.cursor()
        items_cursor.execute("""
            SELECT item_id, list_id_fk, product_id_fk, manual_item_name, manual_item_brand,
                   manual_item_unit_info, price_at_add, quantity, purchased
            FROM ListItems WHERE list_id_fk = ? ORDER BY added_at ASC
        """, (list_id,))
        items_raw = items_cursor.fetchall()
        items_transformed = [transform_list_item_for_frontend(dict(row), conn) for row in items_raw]
        return jsonify(items_transformed)
    except sqlite3.Error as e:
        return jsonify({'erro': str(e)}), 500
    finally:
        if conn: conn.close()

@app.route('/api/shoppinglists/<list_id>/items', methods=['POST'])
def add_item_to_list_api(list_id):
    data = request.get_json()
    if not data: return jsonify({'erro': 'No data provided.'}), 400
    conn = get_db_connection()
    if not conn: return jsonify({'erro': 'DB connection error.'}), 500
    try:
        list_cursor = conn.cursor() # Check if list exists
        list_cursor.execute("SELECT list_id FROM ShoppingLists WHERE list_id = ?", (list_id,))
        if not list_cursor.fetchone(): return jsonify({'erro': 'List not found.'}), 404
        
        prod_id_original = data.get('id') # Original ID from product search or "manual_..."
        prod_name = data.get('name')
        prod_brand = data.get('brand', '')
        prod_price = data.get('price', 0.0)
        prod_unit_info = data.get('unitInfo', '')
        quantity = data.get('quantity', 1)
        product_id_fk = None
        if prod_id_original and not str(prod_id_original).startswith('manual_'):
            product_id_fk = prod_id_original

        item_cursor = conn.cursor()
        # Try to group if item from catalog and not purchased yet
        if product_id_fk:
            item_cursor.execute("""
                SELECT item_id, quantity FROM ListItems
                WHERE list_id_fk = ? AND product_id_fk = ? AND purchased = 0
            """, (list_id, product_id_fk))
            existing_item = item_cursor.fetchone()
            if existing_item:
                new_quantity = existing_item['quantity'] + quantity
                item_cursor.execute("UPDATE ListItems SET quantity = ? WHERE item_id = ?",
                                   (new_quantity, existing_item['item_id']))
                conn.commit()
                item_cursor.execute("SELECT * FROM ListItems WHERE item_id = ?", (existing_item['item_id'],))
                updated_item_data = transform_list_item_for_frontend(dict(item_cursor.fetchone()), conn)
                return jsonify(updated_item_data), 200 # OK for update

        # Insert new item
        new_item_id = generate_unique_id("item_")
        item_cursor.execute("""
            INSERT INTO ListItems (item_id, list_id_fk, product_id_fk, manual_item_name, 
                                 manual_item_brand, manual_item_unit_info, price_at_add, quantity, purchased)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (new_item_id, list_id, product_id_fk, prod_name, prod_brand, 
              prod_unit_info, prod_price, quantity, 0))
        conn.commit()
        item_cursor.execute("SELECT * FROM ListItems WHERE item_id = ?", (new_item_id,))
        created_item_data = transform_list_item_for_frontend(dict(item_cursor.fetchone()), conn)
        return jsonify(created_item_data), 201 # Created
    except sqlite3.Error as e:
        if conn: conn.rollback()
        return jsonify({'erro': str(e)}), 500
    finally:
        if conn: conn.close()

@app.route('/api/shoppinglists/<list_id>/items/<item_id>', methods=['PUT'])
def update_list_item_api(list_id, item_id):
    data = request.get_json()
    if not data: return jsonify({'erro': 'No data provided.'}), 400
    quantity_val = data.get('quantity')
    purchased_val = data.get('purchased') # boolean true/false
    if quantity_val is None and purchased_val is None:
        return jsonify({'erro': 'No fields to update (quantity or purchased).'}), 400
    conn = get_db_connection()
    if not conn: return jsonify({'erro': 'DB connection error.'}), 500
    try:
        cursor = conn.cursor()
        set_clauses, params = [], []
        if quantity_val is not None:
            set_clauses.append("quantity = ?")
            params.append(int(quantity_val))
        if purchased_val is not None:
            set_clauses.append("purchased = ?")
            params.append(1 if purchased_val else 0)
        
        params.extend([item_id, list_id])
        sql = f"UPDATE ListItems SET {', '.join(set_clauses)} WHERE item_id = ? AND list_id_fk = ?"
        cursor.execute(sql, tuple(params))
        conn.commit()
        if cursor.rowcount == 0: return jsonify({'erro': 'Item not found or not in list.'}), 404
        
        cursor.execute("SELECT * FROM ListItems WHERE item_id = ?", (item_id,))
        updated_item_data = transform_list_item_for_frontend(dict(cursor.fetchone()), conn)
        return jsonify(updated_item_data), 200
    except (sqlite3.Error, ValueError) as e: # ValueError for int conversion
        if conn: conn.rollback()
        return jsonify({'erro': str(e)}), 500
    finally:
        if conn: conn.close()

@app.route('/api/shoppinglists/<list_id>/items/<item_id>', methods=['DELETE'])
def delete_list_item_api(list_id, item_id):
    conn = get_db_connection()
    if not conn: return jsonify({'erro': 'DB connection error.'}), 500
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM ListItems WHERE item_id = ? AND list_id_fk = ?", (item_id, list_id))
        conn.commit()
        if cursor.rowcount == 0: return jsonify({'erro': 'Item not found or not in list.'}), 404
        return jsonify({'message': 'Item deleted successfully.'}), 200
    except sqlite3.Error as e:
        return jsonify({'erro': str(e)}), 500
    finally:
        if conn: conn.close()

if __name__ == '__main__':
    initialize_database() # Garante que as tabelas existam ao iniciar
    app.run(debug=True, use_reloader=False)
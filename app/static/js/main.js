// Função para remover tags HTML de uma string (EXISTENTE)
function stripHtml(html) {
    const tempDiv = document.createElement("div");
    tempDiv.innerHTML = html;
    return tempDiv.textContent || tempDiv.innerText || "";
}

document.addEventListener('DOMContentLoaded', () => {
    // --- Seletores de Elementos Globais ---
    const initialScreen = document.getElementById('initial-screen');
    const listDetailScreen = document.getElementById('list-detail-screen');

    // --- Seletores Tela Inicial ---
    const newListNameInput = document.getElementById('new-list-name');
    const createListBtn = document.getElementById('create-list-btn');
    const savedListsUl = document.getElementById('saved-lists-ul');

    // --- Seletores Tela Detalhes da Lista ---
    const backToListsBtn = document.getElementById('back-to-lists-btn');
    const currentListTitleEl = document.getElementById('current-list-title');
    const itemNameInput = document.getElementById('item-name');
    const productSuggestionsDiv = document.getElementById('product-suggestions');
    const itemQuantityInput = document.getElementById('item-quantity');
    const addItemBtn = document.getElementById('add-item-btn');
    const shoppingListUl = document.getElementById('shopping-list');
    const totalCostSpan = document.getElementById('total-cost');
    const itemsListHeader = document.getElementById('items-list-header');


    // --- Variáveis de Estado do Cliente ---
    let allClientLists = []; // Cache das listas vindas do servidor [{list_id, list_name, created_at, items:[]}]
    let currentActiveListId = null;
    let selectedProductFromSuggestion = null; // Guarda o objeto do produto selecionado das sugestões
    let debounceTimer;

    // --- Funções de UI ---
    function showScreen(screenName) {
        initialScreen.style.display = (screenName === 'initial') ? 'block' : 'none';
        listDetailScreen.style.display = (screenName === 'detail') ? 'block' : 'none';
        if (screenName === 'initial') {
            document.title = "Minhas Listas de Compras";
            currentActiveListId = null; // Reseta ao voltar para tela inicial
            sessionStorage.removeItem('currentActiveListId');
        }
    }

    // --- Funções de API (Async) ---
    async function fetchAllLists() {
        try {
            const response = await fetch('/api/shoppinglists');
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            allClientLists = await response.json();
            renderSavedListsOnUI();
        } catch (error) {
            console.error("Erro ao buscar listas:", error);
            savedListsUl.innerHTML = `<p style="color:red;">Falha ao carregar listas.</p>`;
        }
    }

    async function createNewList(listName) {
        try {
            const response = await fetch('/api/shoppinglists', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ list_name: listName })
            });
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            const newList = await response.json();
            allClientLists.push(newList); // Adiciona ao cache local
            allClientLists.sort((a, b) => new Date(b.created_at) - new Date(a.created_at)); // Reordena
            renderSavedListsOnUI();
            newListNameInput.value = '';
            openListDetailView(newList.list_id); // Abre a lista recém-criada
        } catch (error) {
            console.error("Erro ao criar lista:", error);
            alert("Falha ao criar lista.");
        }
    }

    async function deleteListFromServer(listId) {
        try {
            const response = await fetch(`/api/shoppinglists/${listId}`, { method: 'DELETE' });
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            allClientLists = allClientLists.filter(list => list.list_id !== listId);
            renderSavedListsOnUI();
        } catch (error) {
            console.error("Erro ao excluir lista:", error);
            alert("Falha ao excluir lista.");
        }
    }

    async function fetchItemsForList(listId) {
        const list = allClientLists.find(l => l.list_id === listId);
        if (!list) {
            console.error("Lista não encontrada no cache do cliente:", listId);
            showScreen('initial'); // Volta para tela inicial se algo der errado
            return;
        }
        try {
            const response = await fetch(`/api/shoppinglists/${listId}/items`);
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            list.items = await response.json(); // Armazena os itens no cache da lista
            renderShoppingListUI();
            updateTotalCostUI();
        } catch (error) {
            console.error("Erro ao buscar itens da lista:", error);
            // Tratar erro na UI, talvez mostrar mensagem na lista de itens
        }
    }

    async function addItemToListOnServer(listId, itemData) {
        try {
            const response = await fetch(`/api/shoppinglists/${listId}/items`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(itemData)
            });
            if (!response.ok) {
                 const errorData = await response.json().catch(() => ({erro: "Erro desconhecido"}));
                 throw new Error(errorData.erro || `HTTP error! status: ${response.status}`);
            }
            const addedOrUpdatedItem = await response.json();
            
            const list = allClientLists.find(l => l.list_id === listId);
            if (list && list.items) {
                const existingItemIndex = list.items.findIndex(i => i.item_id === addedOrUpdatedItem.item_id);
                if (existingItemIndex > -1) { // Item foi atualizado (quantidade)
                    list.items[existingItemIndex] = addedOrUpdatedItem;
                } else { // Novo item
                    list.items.push(addedOrUpdatedItem);
                }
            } else if (list) { // Lista existe mas itens não foram carregados ou está vazia
                list.items = [addedOrUpdatedItem];
            }
            
            renderShoppingListUI();
            updateTotalCostUI();
            // Limpar campos de input
            itemNameInput.value = '';
            itemQuantityInput.value = '1';
            selectedProductFromSuggestion = null;
            productSuggestionsDiv.innerHTML = '';
            productSuggestionsDiv.style.display = 'none';
            itemNameInput.focus();

        } catch (error) {
            console.error("Erro ao adicionar item:", error);
            alert(`Falha ao adicionar item: ${error.message}`);
        }
    }
    
    async function updateItemOnServer(listId, itemId, updateData) { // updateData = { quantity: X, purchased: Y }
        try {
            const response = await fetch(`/api/shoppinglists/${listId}/items/${itemId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(updateData)
            });
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            const updatedItem = await response.json();

            const list = allClientLists.find(l => l.list_id === listId);
            if (list && list.items) {
                const itemIndex = list.items.findIndex(i => i.item_id === itemId);
                if (itemIndex > -1) {
                    list.items[itemIndex] = updatedItem;
                }
            }
            renderShoppingListUI();
            updateTotalCostUI(); // O total pode ou não mudar dependendo da sua lógica de itens comprados
        } catch (error) {
            console.error("Erro ao atualizar item:", error);
            alert("Falha ao atualizar item.");
        }
    }

    async function deleteItemFromServer(listId, itemId) {
        try {
            const response = await fetch(`/api/shoppinglists/${listId}/items/${itemId}`, { method: 'DELETE' });
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            
            const list = allClientLists.find(l => l.list_id === listId);
            if (list && list.items) {
                list.items = list.items.filter(i => i.item_id !== itemId);
            }
            renderShoppingListUI();
            updateTotalCostUI();
        } catch (error) {
            console.error("Erro ao excluir item:", error);
            alert("Falha ao excluir item.");
        }
    }


    // --- Renderização UI ---
    function renderSavedListsOnUI() {
        savedListsUl.innerHTML = '';
        if (allClientLists.length === 0) {
            savedListsUl.innerHTML = '<li>Nenhuma lista salva ainda.</li>';
            return;
        }
        allClientLists.forEach(list => {
            const li = document.createElement('li');
            li.innerHTML = `
                <a href="#" data-list-id="${list.list_id}">${stripHtml(list.list_name)}</a>
                <span class="list-actions">
                    <small>Criada em: ${new Date(list.created_at).toLocaleDateString()}</small>
                    <button class="delete-list-btn" data-list-id="${list.list_id}" title="Excluir lista">Excluir</button>
                </span>
            `;
            li.querySelector('a').addEventListener('click', (e) => {
                e.preventDefault();
                openListDetailView(list.list_id);
            });
            li.querySelector('.delete-list-btn').addEventListener('click', () => {
                if (confirm(`Tem certeza que deseja excluir a lista "${stripHtml(list.list_name)}"?`)) {
                    deleteListFromServer(list.list_id);
                }
            });
            savedListsUl.appendChild(li);
        });
    }
    
    function getCurrentActiveListItems() {
        if (!currentActiveListId) return [];
        const list = allClientLists.find(l => l.list_id === currentActiveListId);
        return (list && list.items) ? list.items : [];
    }

    function renderShoppingListUI() {
        shoppingListUl.innerHTML = '';
        const items = getCurrentActiveListItems();

        if (items.length === 0) {
            shoppingListUl.innerHTML = '<li>Nenhum item nesta lista. Adicione alguns!</li>';
            updateTotalCostUI();
            return;
        }

        items.forEach((item) => { // Não precisamos mais do index aqui para data-index
            const listItem = document.createElement('li');
            if (item.purchased) {
                listItem.classList.add('item-is-purchased');
            }
            
            let itemPriceText = 'Preço Indisp.';
            if (item.price && typeof item.price === 'number' && item.price > 0) {
                itemPriceText = `${(item.price * item.quantity).toFixed(2)}€ (${item.quantity} x ${item.price.toFixed(2)}€)`;
            } else if (String(item.id).startsWith('manual_')) { // item.id é o product_id_fk ou manual_item_id
                itemPriceText = '(manual, sem preço)';
            }

            const cleanItemName = stripHtml(item.name || '');
            const cleanItemBrand = stripHtml(item.brand || '');
            const cleanItemUnitInfo = stripHtml(item.unitInfo || '');

            listItem.innerHTML = `
                <input type="checkbox" class="item-purchase-checkbox" data-item-id="${item.item_id}" ${item.purchased ? 'checked' : ''} title="Marcar como comprado">
                <div class="item-details">
                    <span class="item-name ${item.purchased ? 'strikethrough' : ''}">${cleanItemName}</span>
                    ${cleanItemBrand ? `<span class="item-brand">(${cleanItemBrand})</span>` : ''}
                    ${cleanItemUnitInfo ? `<span class="item-unit-info">[${cleanItemUnitInfo}]</span>` : ''}
                </div>
                <div class="item-price-quantity">${itemPriceText}</div>
                <span class="remove-item" data-item-id="${item.item_id}" title="Remover item">X</span>
            `;
            shoppingListUl.appendChild(listItem);

            // Event listeners para checkbox e botão de remover de cada item
            listItem.querySelector('.item-purchase-checkbox').addEventListener('change', (e) => {
                const itemId = e.target.dataset.itemId;
                updateItemOnServer(currentActiveListId, itemId, { purchased: e.target.checked });
            });
            listItem.querySelector('.remove-item').addEventListener('click', (e) => {
                if (confirm(`Remover "${cleanItemName}" da lista?`)) {
                    const itemId = e.target.dataset.itemId;
                    deleteItemFromServer(currentActiveListId, itemId);
                }
            });
        });
        updateTotalCostUI();
    }

    function updateTotalCostUI() {
        const items = getCurrentActiveListItems();
        const total = items.reduce((acc, item) => {
            // Você pode decidir se itens comprados entram no total
            // if (item.purchased) return acc; 
            if (item.price && typeof item.price === 'number' && item.price > 0) {
                return acc + (item.price * item.quantity);
            }
            return acc;
        }, 0);
        totalCostSpan.textContent = total.toFixed(2) + ' €';
    }

    function openListDetailView(listId) {
        currentActiveListId = listId;
        sessionStorage.setItem('currentActiveListId', listId); // Lembra para recarregar a página
        const list = allClientLists.find(l => l.list_id === listId);
        if (list) {
            currentListTitleEl.textContent = stripHtml(list.list_name);
            document.title = stripHtml(list.list_name) + " | Lista de Compras";
            itemsListHeader.textContent = `Itens em "${stripHtml(list.list_name)}":`;
            if (!list.items) { // Se os itens ainda não foram carregados para esta lista
                fetchItemsForList(listId);
            } else {
                renderShoppingListUI(); // Renderiza com itens do cache
                updateTotalCostUI();
            }
        } else {
            console.error("Tentando abrir lista não encontrada no cache:", listId);
            fetchAllLists().then(() => { // Tenta recarregar todas as listas
                const freshList = allClientLists.find(l => l.list_id === listId);
                if(freshList) openListDetailView(listId); // Tenta abrir novamente
                else showScreen('initial'); // Se ainda não encontrar, volta para o início
            });
            return; // Evita mostrar tela de detalhes vazia
        }
        showScreen('detail');
        itemNameInput.focus();
    }

    // --- Lógica de Sugestões de Produtos (adaptada) ---
    itemNameInput.addEventListener('input', () => {
        clearTimeout(debounceTimer);
        const searchTerm = itemNameInput.value.trim();
        
        productSuggestionsDiv.innerHTML = '';
        selectedProductFromSuggestion = null;
        productSuggestionsDiv.style.display = 'none';

        if (searchTerm.length < 2) return;

        debounceTimer = setTimeout(async () => {
            try {
                const response = await fetch(`/api/produtos/buscar?termo=${encodeURIComponent(searchTerm)}`);
                if (!response.ok) {
                    const errorData = await response.json().catch(() => ({}));
                    console.error('Erro ao buscar sugestões:', errorData.erro || response.statusText);
                    productSuggestionsDiv.innerHTML = `<p style="color: red;">Erro ao buscar.</p>`;
                    productSuggestionsDiv.style.display = 'block';
                    return;
                }
                const suggestions = await response.json();
                if (suggestions.length > 0) {
                    suggestions.forEach(product => {
                        const suggestionDiv = document.createElement('div');
                        const cleanNomeProduto = stripHtml(product.nome_produto || '');
                        const cleanMarca = stripHtml(product.marca || 'Sem marca');
                        const cleanUnidadeInfo = stripHtml(product.unidade_info_original || '');
                        const precoDisplay = product.preco ? product.preco.toFixed(2) + '€' : 'Preço Indisp.';
                        suggestionDiv.textContent = `${cleanNomeProduto} (${cleanMarca}) - ${precoDisplay} (${cleanUnidadeInfo})`;
                        
                        suggestionDiv.addEventListener('click', () => {
                            itemNameInput.value = cleanNomeProduto;
                            selectedProductFromSuggestion = product; // Guarda o objeto original completo
                            productSuggestionsDiv.innerHTML = ''; 
                            productSuggestionsDiv.style.display = 'none';
                            itemQuantityInput.focus(); // Foco na quantidade após selecionar
                        });
                        productSuggestionsDiv.appendChild(suggestionDiv);
                    });
                    productSuggestionsDiv.style.display = 'block';
                } else {
                    productSuggestionsDiv.innerHTML = '<p>Nenhum produto encontrado.</p>';
                    productSuggestionsDiv.style.display = 'block';
                }
            } catch (error) {
                console.error('Falha na requisição de sugestões:', error);
                productSuggestionsDiv.innerHTML = `<p style="color: red;">Falha ao conectar à API.</p>`;
                productSuggestionsDiv.style.display = 'block';
            }
        }, 300);
    });
    
    // Esconder sugestões se clicar fora
    document.addEventListener('click', function(event) {
        if (!productSuggestionsDiv.contains(event.target) && event.target !== itemNameInput) {
            productSuggestionsDiv.style.display = 'none';
        }
    });

    // --- Event Listeners ---
    createListBtn.addEventListener('click', () => {
        const listName = newListNameInput.value.trim();
        if (listName) {
            createNewList(listName);
        } else {
            alert("Por favor, insira um nome para a lista.");
        }
    });

    backToListsBtn.addEventListener('click', () => {
        showScreen('initial');
    });

    addItemBtn.addEventListener('click', () => {
        if (!currentActiveListId) {
            alert("Nenhuma lista ativa selecionada.");
            return;
        }
        const quantity = parseInt(itemQuantityInput.value) || 1;
        let itemData;

        if (selectedProductFromSuggestion && stripHtml(selectedProductFromSuggestion.nome_produto || '') === itemNameInput.value) {
            itemData = {
                id: selectedProductFromSuggestion.id_produto, // ID do produto do catálogo
                name: selectedProductFromSuggestion.nome_produto, // Nome original (backend pode usar este ou o do catálogo)
                brand: selectedProductFromSuggestion.marca,
                price: parseFloat(selectedProductFromSuggestion.preco),
                unitInfo: selectedProductFromSuggestion.unidade_info_original,
                quantity: quantity
            };
        } else {
            const manualName = itemNameInput.value.trim();
            if (!manualName) {
                alert("Por favor, digite o nome do produto.");
                return;
            }
            itemData = {
                id: `manual_${Date.now()}`, // ID temporário para indicar entrada manual
                name: manualName,
                brand: '', 
                price: 0, // Preço desconhecido
                unitInfo: '',
                quantity: quantity
            };
        }
        addItemToListOnServer(currentActiveListId, itemData);
    });

    // --- Inicialização da Aplicação ---
    async function initializeApp() {
        await fetchAllLists(); // Carrega todas as listas do servidor
        const rememberedListId = sessionStorage.getItem('currentActiveListId');
        if (rememberedListId && allClientLists.some(list => list.list_id === rememberedListId)) {
            openListDetailView(rememberedListId);
        } else {
            showScreen('initial');
        }
    }

    initializeApp();
});
import os
import streamlit as st
from dotenv import load_dotenv
from supabase import create_client, Client

# Carrega as variáveis do .env
load_dotenv()
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")

if not url or not key:
    st.error("Erro: Credenciais do Supabase não encontradas no arquivo .env!")
    st.stop()

supabase: Client = create_client(url, key)

# Configuração da página do Streamlit
st.set_page_config(page_title="Controle de Hostel", page_icon="🏨", layout="wide")

# Estilos CSS personalizados para deixar com carinha de app profissional
st.markdown("""
    <style>
        .main {
            background-color: #f8f9fa;
        }
        .stButton>button {
            width: 100%;
            border-radius: 8px;
            font-weight: bold;
        }
    </style>
""", unsafe_allow_html=True)

# --- MENU LATERAL COM LOGOTIPO ---
st.sidebar.markdown("### 🏨 Hostel Manager")

# Tenta carregar o logotipo considerando variações de extensão
if os.path.exists("logo.png"):
    st.sidebar.image("logo.png", use_column_width=True)
elif os.path.exists("logo.jpg"):
    st.sidebar.image("logo.jpg", use_column_width=True)
elif os.path.exists("logo.jpeg"):
    st.sidebar.image("logo.jpeg", use_container_width=True)
else:
    st.sidebar.info("Dica: Coloque uma imagem de logotipo na pasta do projeto.")

st.sidebar.markdown("---")
menu = st.sidebar.radio("Navegação", [
    "Listar Quartos", 
    "Cadastrar Quarto", 
    "Cadastrar Hóspede", 
    "Criar Reserva", 
    "Ver Reservas"
])

# --- 1. LISTAR QUARTOS ---
if menu == "Listar Quartos":
    st.header("🛏️ Quartos do Hostel")
    
    response = supabase.table("quartos").select("*").execute()
    quartos = response.data

    if not quartos:
        st.info("Nenhum quarto cadastrado ainda.")
    else:
        st.dataframe(quartos, use_container_width=True)

# --- 2. CADASTRAR QUARTO ---
elif menu == "Cadastrar Quarto":
    st.header("➕ Cadastrar Novo Quarto")
    
    with st.form("form_quarto", clear_on_submit=True):
        numero = st.number_input("Número do Quarto", min_value=1, step=1)
        tipo = st.text_input("Tipo (ex: Compartilhado 6 leitos, Privativo)")
        capacidade = st.number_input("Capacidade de Pessoas", min_value=1, step=1)
        preco_diaria = st.number_input("Preço da Diária (R$)", min_value=0.0, format="%.2f")
        
        submitted = st.form_submit_button("Salvar Quarto")
        
        if submitted:
            if not tipo:
                st.warning("Por favor, preencha o tipo do quarto.")
            else:
                data = {
                    "numero": int(numero),
                    "tipo": tipo,
                    "capacidade": int(capacidade),
                    "preco_diaria": float(preco_diaria),
                    "disponivel": True
                }
                try:
                    supabase.table("quartos").insert(data).execute()
                    st.success(f"Quarto {numero} cadastrado com sucesso!")
                except Exception as e:
                    st.error(f"Erro ao cadastrar (número já existe?): {e}")

# --- 3. CADASTRAR HÓSPEDE ---
elif menu == "Cadastrar Hóspede":
    st.header("👤 Cadastrar Hóspede")
    
    with st.form("form_hospede", clear_on_submit=True):
        nome = st.text_input("Nome Completo")
        documento = st.text_input("Documento (CPF / RG / Passaporte)")
        telefone = st.text_input("Telefone")
        
        submitted = st.form_submit_button("Salvar Hóspede")
        
        if submitted:
            if not nome or not documento:
                st.warning("Nome e Documento são obrigatórios!")
            else:
                data = {
                    "nome": nome,
                    "documento": documento,
                    "telefone": telefone
                }
                try:
                    supabase.table("hospedes").insert(data).execute()
                    st.success(f"Hóspede {nome} cadastrado com sucesso!")
                except Exception as e:
                    st.error(f"Erro ao cadastrar (talvez o documento já exista): {e}")

# --- 4. CRIAR RESERVA ---
elif menu == "Criar Reserva":
    st.header("📅 Nova Reserva")
    
    h_resp = supabase.table("hospedes").select("id, nome, documento").execute()
    hospedes = h_resp.data
    
    q_resp = supabase.table("quartos").select("*").eq("disponivel", True).execute()
    quartos_disp = q_resp.data

    if not hospedes:
        st.warning("Nenhum hóspede cadastrado. Cadastre um hóspede primeiro na aba lateral.")
    elif not quartos_disp:
        st.warning("Não há quartos disponíveis no momento.")
    else:
        hospede_dict = {f"{h['nome']} (Doc: {h['documento']})": h['id'] for h in hospedes}
        quarto_dict = {f"Quarto {q['numero']} - {q['tipo']} (R$ {q['preco_diaria']}/dia)": q for q in quartos_disp}

        with st.form("form_reserva"):
            selected_hospede_str = st.selectbox("Selecione o Hóspede", list(hospede_dict.keys()))
            selected_quarto_str = st.selectbox("Selecione o Quarto Disponível", list(quarto_dict.keys()))
            dias = st.number_input("Quantidade de Dias", min_value=1, step=1)
            
            submitted = st.form_submit_button("Confirmar Reserva")
            
            if submitted:
                hospede_id = hospede_dict[selected_hospede_str]
                quarto_selecionado = quarto_dict[selected_quarto_str]
                quarto_id = quarto_selecionado['id']
                preco_diaria = quarto_selecionado['preco_diaria']
                
                valor_total = preco_diaria * dias

                reserva_data = {
                    "hospede_id": hospede_id,
                    "quarto_id": quarto_id,
                    "dias": int(dias),
                    "valor_total": float(valor_total)
                }
                supabase.table("reservas").insert(reserva_data).execute()
                supabase.table("quartos").update({"disponivel": False}).eq("id", quarto_id).execute()

                st.success(f"Reserva criada com sucesso! Valor Total: R$ {valor_total:.2f}")

# --- 5. VER RESERVAS ---
elif menu == "Ver Reservas":
    st.header("📋 Histórico de Reservas")
    
    response = supabase.table("reservas").select("id, dias, valor_total, criado_em, hospedes(nome, documento), quartos(numero, tipo)").execute()
    reservas = response.data

    if not reservas:
        st.info("Nenhuma reserva registrada.")
    else:
        st.dataframe(reservas, use_container_width=True)
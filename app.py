import streamlit as st
import secrets
from datetime import datetime
import database as db

# Importação dos módulos do sistema
from modulos.cadastros import (
    renderizar_hospedes,
    renderizar_quartos,
    renderizar_colaboradores
)
from modulos.usuarios import renderizar_gestao_usuarios

# Importações protegidas de outros módulos (caso já existam na sua estrutura)
try:
    from modulos.reservas import renderizar_reservas
except ImportError:
    renderizar_reservas = None

try:
    from modulos.financeiro import renderizar_financeiro
except ImportError:
    renderizar_financeiro = None

# ==========================================
# 1. CONFIGURAÇÃO DA PÁGINA
# ==========================================
st.set_page_config(
    page_title="Hostel PMS - Sistema de Gestão",
    page_icon="🏨",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilização básica para Web e Dispositivos Móveis
st.markdown("""
    <style>
        .block-container {
            padding-top: 1.5rem;
            padding-bottom: 2rem;
        }
        [data-testid="stSidebarNav"] {
            display: none;
        }
    </style>
""", unsafe_allow_html=True)


# ==========================================
# 2. CONTROLE DE SESSÃO PERSISTENTE E LOGIN
# ==========================================
if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False
    st.session_state["usuario_email"] = None
    st.session_state["usuario_nome"] = None
    st.session_state["usuario_perfil"] = None

# Recuperação automática de login via token persistente (URL / App Mobile)
token_param = st.query_params.get("session")

if not st.session_state["autenticado"] and token_param:
    dados_token = db.validar_token_sessao(token_param)
    if dados_token:
        # Checa se o horário atual ainda permite o uso
        autorizado, msg_erro_horario = db.validar_horario_acesso(
            dados_token["email"], 
            dados_token.get("perfil", "Recepção")
        )
        if autorizado:
            st.session_state["autenticado"] = True
            st.session_state["usuario_email"] = dados_token["email"]
            st.session_state["usuario_nome"] = dados_token["nome"]
            st.session_state["usuario_perfil"] = dados_token.get("perfil", "Recepção")
        else:
            st.query_params.clear()
            st.error(f"⛔ Turno encerrado: {msg_erro_horario}")


# ==========================================
# 3. TELA DE LOGIN (QUANDO NÃO AUTENTICADO)
# ==========================================
if not st.session_state["autenticado"]:
    col_vazia1, col_login, col_vazia2 = st.columns([1, 1.8, 1])

    with col_login:
        logo_url = db.obter_logo()
        if logo_url:
            st.image(logo_url, width=220)

        st.markdown("## 🏨 Sistema de Gestão de Hostel")
        st.caption("Acesso restrito para colaboradores autorizados.")

        tab_entrar, tab_esqueci = st.tabs(["🔑 Entrar no Painel", "❓ Esqueci Minha Senha"])

        with tab_entrar:
            with st.form("form_login"):
                email_input = st.text_input("E-mail Cadastrado").strip().lower()
                senha_input = st.text_input("Senha de Acesso", type="password")
                lembrar_login = st.checkbox("Mantenha-me conectado neste dispositivo", value=True)
                btn_acessar = st.form_submit_button("Acessar Painel", use_container_width=True)

                if btn_acessar:
                    if not email_input or not senha_input:
                        st.error("Informe seu e-mail e senha.")
                    else:
                        try:
                            auth_resp = db.supabase.auth.sign_in_with_password({
                                "email": email_input, 
                                "password": senha_input
                            })

                            if auth_resp.user:
                                perfil_user, nome_user = db.obter_perfil_usuario(email_input, auth_resp.user)

                                if perfil_user == "Suspenso":
                                    st.error("Este usuário está suspenso. Procure a Administração.")
                                else:
                                    # Validação da janela de horário
                                    autorizado, msg_horario = db.validar_horario_acesso(email_input, perfil_user)
                                    if not autorizado:
                                        st.error(f"⛔ Acesso Bloqueado: {msg_horario}")
                                    else:
                                        st.session_state["autenticado"] = True
                                        st.session_state["usuario_email"] = email_input
                                        st.session_state["usuario_nome"] = nome_user
                                        st.session_state["usuario_perfil"] = perfil_user

                                        # Salva o token na URL para persistência
                                        if lembrar_login:
                                            novo_token = db.gerar_token_sessao(email_input)
                                            if novo_token:
                                                st.query_params["session"] = novo_token

                                        db.notificar_sucesso(f"Bem-vindo(a), {nome_user}!")
                                        st.rerun()
                            else:
                                st.error("Credenciais inválidas. Verifique seu e-mail e senha.")
                        except Exception as e:
                            st.error(f"Falha na autenticação: {e}")

        with tab_esqueci:
            st.markdown("##### 📩 Recuperação de Senha por E-mail")
            with st.form("form_recuperacao"):
                email_recup = st.text_input("E-mail Cadastrado:").strip().lower()
                if st.form_submit_button("Enviar E-mail de Recuperação", use_container_width=True):
                    if not email_recup:
                        st.error("Informe o e-mail cadastrado.")
                    else:
                        ok, msg = db.solicitar_recuperacao_senha(email_recup)
                        if ok:
                            st.success(msg)
                        else:
                            st.error(msg)

    st.stop()


# ==========================================
# 4. BARRA LATERAL (MENU E NAVEGAÇÃO)
# ==========================================
with st.sidebar:
    logo_menu = db.obter_logo()
    if logo_menu:
        st.image(logo_menu, width=150)

    st.markdown(f"### Olá, **{st.session_state['usuario_nome']}**")
    st.caption(f"Cargo / Nível: **{st.session_state['usuario_perfil']}**")
    st.markdown("---")

    # Opções do menu com base nas permissões
    opcoes_menu = [
        "🛏️ Mapa de Ocupação",
        "📁 Cadastros",
        "💰 Financeiro",
        "👥 Gestão de Usuários"
    ]

    menu_selecionado = st.radio("Navegação:", opcoes_menu)

    st.markdown("---")

    # Botão de Logout seguro
    if st.button("🚪 Sair do Sistema", use_container_width=True):
        if st.session_state.get("usuario_email"):
            db.revogar_token_sessao(st.session_state["usuario_email"])
        try:
            db.supabase.auth.sign_out()
        except Exception:
            pass
        st.query_params.clear()
        st.session_state.clear()
        st.rerun()


# ==========================================
# 5. ROTEAMENTO DAS TELAS DO SISTEMA
# ==========================================

# 1. Mapa de Ocupação / Reservas
if menu_selecionado == "🛏️ Mapa de Ocupação":
    if renderizar_reservas:
        renderizar_reservas()
    else:
        st.markdown("### 🛏️ Mapa de Ocupação e Reservas")
        st.info("Módulo de reservas ativo. Conecte o arquivo correspondente caso esteja em outro submódulo.")

# 2. Cadastros Gerais (Hóspedes, Quartos, Colaboradores)
elif menu_selecionado == "📁 Cadastros":
    st.markdown("## 📁 Central de Cadastros")
    sub_cadastros = st.radio(
        "Selecione o que deseja cadastrar:",
        ["Hóspedes", "Quartos e Camas", "Equipe (Colaboradores)"],
        horizontal=True
    )
    st.markdown("---")

    if sub_cadastros == "Hóspedes":
        renderizar_hospedes()
    elif sub_cadastros == "Quartos e Camas":
        renderizar_quartos()
    elif sub_cadastros == "Equipe (Colaboradores)":
        renderizar_colaboradores()

# 3. Financeiro
elif menu_selecionado == "💰 Financeiro":
    if renderizar_financeiro:
        renderizar_financeiro()
    else:
        st.markdown("### 💰 Controle Financeiro")
        st.info("Módulo financeiro ativo.")

# 4. Gestão de Usuários (Módulo Dedicado com Exclusão)
elif menu_selecionado == "👥 Gestão de Usuários":
    if st.session_state["usuario_perfil"] not in ["Administrador", "Gerente"]:
        st.warning("🔒 Acesso restrito. Somente administradores e gerentes podem gerenciar contas de usuários.")
    else:
        renderizar_gestao_usuarios()
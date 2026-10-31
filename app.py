import streamlit as st
import secrets
import inspect
import traceback
from datetime import datetime
import database as db

# ----------------------------------------------------
# IMPORTAÇÃO SEGURA DOS MÓDULOS DO SISTEMA
# ----------------------------------------------------
from modulos.cadastros import (
    renderizar_hospedes,
    renderizar_quartos,
    renderizar_colaboradores
)
from modulos.usuarios import renderizar_gestao_usuarios

try:
    import modulos.hospedagem as mod_hosp
except ImportError:
    mod_hosp = None

try:
    import modulos.financeiro as mod_fin
except ImportError:
    mod_fin = None

try:
    import modulos.manutencao as mod_manut
except ImportError:
    mod_manut = None

try:
    import modulos.eventos as mod_eventos
except ImportError:
    mod_eventos = None


# ----------------------------------------------------
# EXECUTOR INTELIGENTE DE MÓDULOS (EVITA TYPEERROR)
# ----------------------------------------------------
def executar_funcao_modulo(modulo, nomes_possiveis):
    """
    Localiza a função correta dentro do módulo, verifica se ela exige
    argumentos obrigatórios e executa com tratamento detalhado de erros.
    """
    if not modulo:
        st.warning("Módulo não encontrado na pasta 'modulos/'.")
        return

    func_alvo = None
    for nome in nomes_possiveis:
        if hasattr(modulo, nome) and callable(getattr(modulo, nome)):
            func_alvo = getattr(modulo, nome)
            break

    # Se não achar pelos nomes padrão, busca qualquer função iniciada por 'renderizar_'
    if not func_alvo:
        for attr_name in dir(modulo):
            if attr_name.startswith("renderizar_"):
                candidata = getattr(modulo, attr_name)
                if callable(candidata):
                    func_alvo = candidata
                    break

    if not func_alvo:
        st.error(f"Nenhuma função de renderização encontrada no módulo {modulo.__name__}.")
        return

    try:
        assinatura = inspect.signature(func_alvo)
        parametros = assinatura.parameters
        args_para_enviar = []

        for nome_param, param in parametros.items():
            # Se o parâmetro não tem valor padrão (é obrigatório)
            if param.default is inspect.Parameter.empty and param.kind in (
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD
            ):
                nome_p = nome_param.lower()
                if "perfil" in nome_p or "cargo" in nome_p:
                    args_para_enviar.append(st.session_state.get("usuario_perfil", "Administrador"))
                elif "email" in nome_p:
                    args_para_enviar.append(st.session_state.get("usuario_email", ""))
                elif "user" in nome_p or "usuario" in nome_p or "nome" in nome_p:
                    args_para_enviar.append(st.session_state.get("usuario_nome", "Administrador"))
                else:
                    args_para_enviar.append(None)

        func_alvo(*args_para_enviar)

    except Exception as e:
        st.error(f"⚠️ Detalhe técnico do erro em `{func_alvo.__name__}`: **{type(e).__name__}: {e}**")
        with st.expander("🔍 Ver rastreamento completo da linha do erro (Traceback)"):
            st.code(traceback.format_exc(), language="python")


# ==========================================
# 1. CONFIGURAÇÃO DA PÁGINA
# ==========================================
st.set_page_config(
    page_title="Hostel PMS - Sistema de Gestão",
    page_icon="🏨",
    layout="wide",
    initial_sidebar_state="expanded"
)

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

# Exibição de notificações salvas na sessão (Toast)
if "toast_msg" in st.session_state and st.session_state["toast_msg"]:
    st.toast(st.session_state["toast_msg"], icon=st.session_state.get("toast_icon", "✅"))
    st.session_state["toast_msg"] = None


# ==========================================
# 2. CONTROLE DE SESSÃO PERSISTENTE E LOGIN
# ==========================================
if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False
    st.session_state["usuario_email"] = None
    st.session_state["usuario_nome"] = None
    st.session_state["usuario_perfil"] = None

token_param = st.query_params.get("session")

if not st.session_state["autenticado"] and token_param:
    dados_token = db.validar_token_sessao(token_param)
    if dados_token:
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
                                    autorizado, msg_horario = db.validar_horario_acesso(email_input, perfil_user)
                                    if not autorizado:
                                        st.error(f"⛔ Acesso Bloqueado: {msg_horario}")
                                    else:
                                        st.session_state["autenticado"] = True
                                        st.session_state["usuario_email"] = email_input
                                        st.session_state["usuario_nome"] = nome_user
                                        st.session_state["usuario_perfil"] = perfil_user

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

    opcoes_menu = [
        "🛏️ Hospedagem e Reservas",
        "📁 Cadastros",
        "💰 Financeiro e Vendas",
        "🛠️ Manutenção",
        "🎉 Eventos",
        "👥 Gestão de Usuários"
    ]

    menu_selecionado = st.radio("Navegação:", opcoes_menu)

    st.markdown("---")

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

# 1. Hospedagem / Mapa de Ocupação / Reservas
if menu_selecionado == "🛏️ Hospedagem e Reservas":
    executar_funcao_modulo(
        mod_hosp, 
        ["renderizar_hospedagem", "renderizar_mapa", "renderizar_reservas", "renderizar_tela"]
    )

# 2. Cadastros Gerais (Hóspedes, Quartos, Colaboradores)
elif menu_selecionado == "📁 Cadastros":
    st.markdown("## 📁 Central de Cadastros")
    sub_cadastros = st.radio(
        "Selecione o que deseja gerenciar:",
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

# 3. Financeiro e Vendas
elif menu_selecionado == "💰 Financeiro e Vendas":
    if mod_fin:
        executar_funcao_modulo(
            mod_fin, 
            ["renderizar_financeiro", "renderizar_vendas", "renderizar_caixa"]
        )
    else:
        st.info("Módulo financeiro não localizado.")

# 4. Manutenção
elif menu_selecionado == "🛠️ Manutenção":
    if mod_manut:
        executar_funcao_modulo(
            mod_manut, 
            ["renderizar_manutencao", "renderizar_manutencoes"]
        )
    else:
        st.info("Módulo de manutenção não localizado.")

# 5. Eventos
elif menu_selecionado == "🎉 Eventos":
    if mod_eventos:
        executar_funcao_modulo(
            mod_eventos, 
            ["renderizar_eventos", "renderizar_evento"]
        )
    else:
        st.info("Módulo de eventos não localizado.")

# 6. Gestão de Usuários
elif menu_selecionado == "👥 Gestão de Usuários":
    if st.session_state["usuario_perfil"] not in ["Administrador", "Gerente"]:
        st.warning("🔒 Acesso restrito. Somente administradores e gerentes podem gerenciar contas de usuários.")
    else:
        renderizar_gestao_usuarios()
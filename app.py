import importlib
import streamlit as st
import database as db
from utils import formatadores, exportadores
from modulos import (
    dashboard,
    hospedagem,
    operacoes,
    cadastros,
    gestao,
    manutencao,
    configuracoes,
    fiscal,
    ajuda_lgpd
)

# Força o recarregamento em tempo real de todos os módulos
importlib.reload(formatadores)
importlib.reload(exportadores)
importlib.reload(db)
importlib.reload(dashboard)
importlib.reload(hospedagem)
importlib.reload(operacoes)
importlib.reload(cadastros)
importlib.reload(gestao)
importlib.reload(manutencao)
importlib.reload(configuracoes)
importlib.reload(fiscal)
importlib.reload(ajuda_lgpd)

# ==========================================
# 1. CONFIGURAÇÃO, TEMA, PWA E CSS
# ==========================================
st.set_page_config(
    page_title="Sistema de Gestão de Hostel",
    page_icon="https://unmyzwkinjvexxanknku.supabase.co/storage/v1/object/public/publico/icone.png",
    layout="wide",
)

# Notificações flutuantes de ação (toast persistente)
if "toast_msg" in st.session_state:
    st.toast(st.session_state["toast_msg"], icon=st.session_state.get("toast_icon", "✅"))
    del st.session_state["toast_msg"]
    if "toast_icon" in st.session_state:
        del st.session_state["toast_icon"]

# Recuperação de preferência de tema (Claro / Escuro)
if "tema_sistema" not in st.session_state:
    try:
        res_t = db.supabase.table("configuracoes").select("valor").eq("chave", "tema_sistema").execute()
        st.session_state["tema_sistema"] = res_t.data[0]["valor"] if (res_t.data and res_t.data[0].get("valor")) else "Claro"
    except Exception:
        st.session_state["tema_sistema"] = "Claro"

tema_atual = st.session_state.get("tema_sistema", "Claro")

if tema_atual == "Escuro":
    css_tema = """
        html, body, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
            background-color: #0b1120 !important;
            color: #f1f5f9 !important;
        }
        [data-testid="stSidebar"] {
            background-color: #0f172a !important;
            border-right: 1px solid #1e293b !important;
        }
        .user-profile-badge {
            background-color: #1e293b !important;
            border: 1px solid #334155 !important;
            color: #f8fafc !important;
        }
        .recibo-card {
            background-color: #1e293b !important;
            border: 2px dashed #475569 !important;
            color: #f8fafc !important;
        }
        div[data-testid="stMetricValue"] {
            color: #60a5fa !important;
        }
        div[data-testid="stExpander"] {
            background-color: #0f172a !important;
            border-color: #334155 !important;
        }
        input, select, textarea {
            background-color: #1e293b !important;
            color: #f8fafc !important;
        }
    """
else:
    css_tema = """
        html, body, [data-testid="stAppViewContainer"] {
            background-color: #ffffff !important;
            color: #0f172a !important;
        }
        [data-testid="stSidebar"] {
            background-color: #f8fafc !important;
            border-right: 1px solid #e2e8f0 !important;
        }
        .user-profile-badge {
            background-color: #f1f5f9 !important;
            border: 1px solid #cbd5e1 !important;
            color: #0f172a !important;
        }
        .recibo-card {
            background-color: #ffffff !important;
            border: 2px dashed #94a3b8 !important;
            color: #0f172a !important;
        }
    """

# Injeção unificada de PWA com ícone oficial hospedado no Supabase
st.markdown(
    f"""
    <html lang="pt-BR">
    <head>
        <meta name="apple-mobile-web-app-capable" content="yes">
        <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
        <meta name="apple-mobile-web-app-title" content="Hostel PMS">
        <meta name="mobile-web-app-capable" content="yes">
        <meta name="theme-color" content="#2563eb">
        <link rel="icon" type="image/png" href="https://unmyzwkinjvexxanknku.supabase.co/storage/v1/object/public/publico/icone.png">
        <link rel="apple-touch-icon" href="https://unmyzwkinjvexxanknku.supabase.co/storage/v1/object/public/publico/icone.png">
        <link rel="manifest" href="data:application/manifest+json;charset=utf-8,%7B%22name%22%3A%22Sistema%20de%20Gestao%20de%20Hostel%22%2C%22short_name%22%3A%22Hostel%20PMS%22%2C%22start_url%22%3A%22%2F%22%2C%22display%22%3A%22standalone%22%2C%22background_color%22%3A%22%23ffffff%22%2C%22theme_color%22%3A%22%232563eb%22%2C%22icons%22%3A%5B%7B%22src%22%3A%22https%3A%2F%2Funmyzwkinjvexxanknku.supabase.co%2Fstorage%2Fv1%2Fobject%2Fpublic%2Fpublico%2Ficone.png%22%2C%22sizes%22%3A%22512x512%22%2C%22type%22%3A%22image%2Fpng%22%7D%5D%7D">
        <meta name="google" content="notranslate">
    </head>
    <style>
        html, body, [class*="css"], [class*="st-"] {{
            translate: no !important;
        }}
        .alerta-badge-card {{
            padding: 8px 12px;
            border-radius: 6px;
            margin-bottom: 4px;
            font-size: 0.88rem;
        }}
        .user-profile-badge {{
            padding: 10px 12px;
            border-radius: 8px;
            margin-bottom: 12px;
        }}
        .recibo-card {{
            padding: 20px;
            border-radius: 8px;
            font-family: monospace;
            line-height: 1.4;
        }}
        {css_tema}
    </style>
    </html>
    """,
    unsafe_allow_html=True
)

def renderizar_cabecalho(titulo_menu: str, indice_menu: int):
    for _ in range(indice_menu):
        st.empty()
    cor_texto = "#93c5fd" if tema_atual == "Escuro" else "#1e293b"
    with st.container():
        st.markdown(
            f"""
            <meta name="google" content="notranslate">
            <div id="cabecalho-hostel-{indice_menu}" class="notranslate" translate="no" 
                 style="padding-bottom: 10px; margin-bottom: 20px; border-bottom: 2px solid {'#334155' if tema_atual == 'Escuro' else '#e2e8f0'};">
                <span style="color: {'#94a3b8' if tema_atual == 'Escuro' else '#64748b'}; font-size: 0.9rem; font-weight: 600; text-transform: uppercase; letter-spacing: 1px;">
                    🏨 Sistema Integrado de Gestão Hoteleira
                </span>
                <h1 style="margin: 4px 0 0 0; padding: 0; font-size: 2rem; font-weight: 700; color: {cor_texto};">
                    {titulo_menu}
                </h1>
            </div>
            """,
            unsafe_allow_html=True,
        )

# ==========================================
# 2. TELA PRIVADA DE LOGIN
# ==========================================
if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False
    st.session_state["usuario_email"] = None
    st.session_state["usuario_nome"] = None
    st.session_state["usuario_perfil"] = None

if not st.session_state["autenticado"]:
    col_c1, col_c2, col_c3 = st.columns([1, 1.8, 1])
    with col_c2:
        logo_login = db.obter_logo()
        if logo_login:
            st.image(logo_login, width=220)
        
        st.markdown("## 🏨 Sistema de Gestão de Hostel")
        st.caption("Acesso restrito para colaboradores autorizados.")

        tab_login, tab_recuperar = st.tabs(["🔑 Entrar no Sistema", "❓ Esqueci Minha Senha"])

        with tab_login:
            with st.form("form_login"):
                email_login = st.text_input("E-mail Cadastrado").strip()
                senha_login = st.text_input("Senha de Acesso", type="password")
                btn_entrar = st.form_submit_button("Acessar Painel", use_container_width=True)

                if btn_entrar:
                    if not email_login or not senha_login:
                        st.error("Preencha o e-mail e a senha.")
                    else:
                        try:
                            auth_resp = db.supabase.auth.sign_in_with_password({"email": email_login, "password": senha_login})
                            if auth_resp.user:
                                perfil_user, nome_user = db.obter_perfil_usuario(email_login, auth_resp.user)
                                if perfil_user == "Suspenso":
                                    st.error("Este usuário está suspenso. Procure a Administração.")
                                else:
                                    st.session_state["autenticado"] = True
                                    st.session_state["usuario_email"] = email_login
                                    st.session_state["usuario_nome"] = nome_user
                                    st.session_state["usuario_perfil"] = perfil_user
                                    db.notificar_sucesso(f"Bem-vindo(a), {nome_user}!")
                                    st.rerun()
                            else:
                                st.error("E-mail ou senha incorretos.")
                        except Exception as e:
                            st.error(f"Falha na autenticação: {e}")

        with tab_recuperar:
            st.markdown("##### 📩 Recuperação de Senha por E-mail")
            st.caption("Digite seu e-mail cadastrado para receber o link de redefinição de senha diretamente na sua caixa de entrada.")
            with st.form("form_recuperar_senha"):
                email_recup = st.text_input("E-mail Cadastrado:").strip()
                if st.form_submit_button("Enviar Instruções de Recuperação", use_container_width=True):
                    if not email_recup:
                        st.error("Informe seu e-mail.")
                    else:
                        ok, msg = db.solicitar_recuperacao_senha(email_recup)
                        if ok:
                            st.success(msg)
                        else:
                            st.error(msg)
    st.stop()


# ==========================================
# 3. INTERFACE E MENU CATEGORIZADO
# ==========================================
usuario_atual_nome = st.session_state.get("usuario_nome", "Usuário")
usuario_atual_email = st.session_state.get("usuario_email", "")
usuario_atual_perfil = st.session_state.get("usuario_perfil", "Administrador")

categorias_menu = {
    "📌 OPERAÇÃO": [
        "🏠 Painel Geral (Dashboard)",
        "📊 Mapa de Ocupação & Leitos",
        "🔔 Central de Alertas",
        "🧹 Painel de Limpeza",
        "🔧 Gestão de Manutenção"
    ],
    "🏨 HOSPEDAGEM & BALCÃO": [
        "📅 Nova Reserva & Edição",
        "📋 Check-out & Histórico",
        "🛒 Loja & Conveniência (PDV)",
        "🎉 Eventos & Experiências"
    ],
    "📁 CADASTROS": [
        "👤 Cadastro de Hóspedes",
        "🏢 Empresas Parceiras",
        "🚪 Quartos & Alas",
        "🛏️ Camas & Preços por Leito",
        "🧑‍💼 Equipe (Colaboradores)",
        "🛠️ Prestadores de Serviços"
    ],
    "⚙️ ADMINISTRAÇÃO & GESTÃO": [
        "👥 Gestão de Usuários & Acessos",
        "🏛️ Integração Fiscal (NFS-e)",
        "🛡️ Governança LGPD & Termos",
        "❓ Central de Ajuda & Manual",
        "📈 Relatórios & Faturamento",
        "⚙️ Configurações & Temas"
    ]
}

menu_plano = []
for cat_nome, itens in categorias_menu.items():
    for item in itens:
        if usuario_atual_perfil == "Administrador":
            menu_plano.append(item)
        elif usuario_atual_perfil == "Recepção":
            if item not in [
                "🚪 Quartos & Alas",
                "🛏️ Camas & Preços por Leito",
                "🧑‍💼 Equipe (Colaboradores)",
                "🛠️ Prestadores de Serviços",
                "👥 Gestão de Usuários & Acessos",
                "🏛️ Integração Fiscal (NFS-e)",
                "📈 Relatórios & Faturamento",
                "⚙️ Configurações & Temas"
            ]:
                menu_plano.append(item)
        else:  # Perfil Limpeza
            if item in ["🧹 Painel de Limpeza", "🔧 Gestão de Manutenção", "📊 Mapa de Ocupação & Leitos", "❓ Central de Ajuda & Manual"]:
                menu_plano.append(item)

if "redirecionar_menu" in st.session_state:
    destino = st.session_state.pop("redirecionar_menu")
    for m in menu_plano:
        if destino.lower() in m.lower() or m.lower() in destino.lower():
            st.session_state["menu_selecionado"] = m
            break

if "menu_selecionado" not in st.session_state or st.session_state["menu_selecionado"] not in menu_plano:
    st.session_state["menu_selecionado"] = menu_plano[0]

# Barra Lateral: Identificação do Hostel e Usuário
logo_atual = db.obter_logo()
if logo_atual:
    st.sidebar.image(logo_atual, use_container_width=True)

st.sidebar.markdown(
    f"""
    <div class="user-profile-badge">
        <div style="font-weight: 700; font-size: 0.95rem;">👤 {usuario_atual_nome}</div>
        <div style="font-size: 0.8rem; opacity: 0.8;">{usuario_atual_email}</div>
        <div style="margin-top: 4px; display: inline-block; background-color: {'#334155' if tema_atual == 'Escuro' else '#e2e8f0'}; font-size: 0.75rem; font-weight: 600; padding: 2px 8px; border-radius: 4px;">
            Perfil: {usuario_atual_perfil}
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

if st.sidebar.button("🚪 Sair do Sistema (Logout)", use_container_width=True):
    try:
        db.supabase.auth.sign_out()
    except Exception:
        pass
    st.session_state.clear()
    st.rerun()

st.sidebar.markdown("---")

# ----------------------------------------------------
# 🔍 BUSCA RÁPIDA GLOBAL NO MENU LATERAL
# ----------------------------------------------------
with st.sidebar.expander("🔎 Busca Rápida no Sistema"):
    busca_query = st.text_input("Buscar Hóspede, Localizador ou Quarto:", placeholder="Digite 2+ caracteres").strip()
    if busca_query:
        resultados_busca = db.busca_rapida_global(busca_query)
        achou_algo = False

        if resultados_busca["reservas"]:
            achou_algo = True
            st.markdown("##### 📅 Reservas Ativas:")
            for rb in resultados_busca["reservas"]:
                h_n = rb.get("hospedes", {}).get("nome", "Hóspede")
                loc = rb.get("codigo_localizador", "S/CÓD")
                if st.button(f"[{loc}] {h_n}", key=f"b_res_{rb['id']}", use_container_width=True):
                    st.session_state["redirecionar_menu"] = "📋 Check-out & Histórico"
                    st.session_state["destaque_reserva_id"] = rb["id"]
                    st.rerun()

        if resultados_busca["hospedes"]:
            achou_algo = True
            st.markdown("##### 👤 Hóspedes:")
            for hb in resultados_busca["hospedes"]:
                tel_limpo = "".join(filter(str.isdigit, str(hb.get("telefone", ""))))
                col_hb1, col_hb2 = st.columns([2, 1])
                with col_hb1:
                    st.write(f"• **{hb['nome']}**")
                with col_hb2:
                    if tel_limpo:
                        st.link_button("📲 WPP", f"https://wa.me/55{tel_limpo}")

        if resultados_busca["manutencoes"]:
            achou_algo = True
            st.markdown("##### 🔧 Manutenções:")
            for mb in resultados_busca["manutencoes"]:
                st.write(f"• **{mb['titulo']}** ({mb.get('status')})")

        if not achou_algo:
            st.caption("Nenhum resultado encontrado.")

st.sidebar.markdown("---")

# MENU PRINCIPAL LATERAL
st.sidebar.markdown("### 🧭 Menu do Sistema")
escolha = st.sidebar.selectbox("Navegue pelas funcionalidades:", menu_plano, key="menu_selecionado")
st.sidebar.markdown("---")

# Avisos na Barra Lateral
dados_alertas = db.obter_resumo_alertas()
tot_overstay = len(dados_alertas["overstay"])
tot_checkout = len(dados_alertas["checkout_hoje"])
tot_devedores = len(dados_alertas["inadimplencia_vendas"]) + len(dados_alertas["inadimplencia_eventos"])
tot_limpeza = len(dados_alertas["limpeza_pendente"])
tot_manut = len(dados_alertas.get("manutencoes_urgentes", []))

with st.sidebar.container():
    st.markdown("### 🔔 Avisos Operacionais")
    if tot_overstay > 0:
        st.markdown(f"<div class='alerta-badge-card' style='background-color:#ffe3e3; color:#c92a2a; border-left:4px solid #f03e3e;'>🚨 <b>{tot_overstay}</b> estadia(s) vencida(s)!</div>", unsafe_allow_html=True)
        if st.button("👉 Resolver Overstay", key="btn_nav_overstay", use_container_width=True):
            st.session_state["redirecionar_menu"] = "🔔 Central de Alertas"
            st.rerun()

    if tot_checkout > 0:
        st.markdown(f"<div class='alerta-badge-card' style='background-color:#fff4e6; color:#d9480f; border-left:4px solid #fd7e14;'>⏰ <b>{tot_checkout}</b> saída(s) hoje (11h)</div>", unsafe_allow_html=True)
        if st.button("👉 Ir p/ Check-outs", key="btn_nav_checkout", use_container_width=True):
            st.session_state["redirecionar_menu"] = "📋 Check-out & Histórico"
            st.rerun()

    if tot_devedores > 0 and usuario_atual_perfil in ["Administrador", "Recepção"]:
        st.markdown(f"<div class='alerta-badge-card' style='background-color:#fff9db; color:#e67700; border-left:4px solid #fcc419;'>💸 <b>{tot_devedores}</b> conta(s) pendente(s)</div>", unsafe_allow_html=True)
        if st.button("👉 Cobrar Inadimplentes", key="btn_nav_devedores", use_container_width=True):
            st.session_state["redirecionar_menu"] = "🔔 Central de Alertas"
            st.rerun()

    if tot_limpeza > 0:
        st.markdown(f"<div class='alerta-badge-card' style='background-color:#f1f3f5; color:#495057; border-left:4px solid #adb5bd;'>🧹 <b>{tot_limpeza}</b> leito(s) para limpeza</div>", unsafe_allow_html=True)
        if st.button("👉 Ir p/ Limpeza", key="btn_nav_limpeza", use_container_width=True):
            st.session_state["redirecionar_menu"] = "🧹 Painel de Limpeza"
            st.rerun()

    if tot_manut > 0:
        st.markdown(f"<div class='alerta-badge-card' style='background-color:#fef2f2; color:#991b1b; border-left:4px solid #ef4444;'>🔧 <b>{tot_manut}</b> manutenção(ões) urgente(s)!</div>", unsafe_allow_html=True)
        if st.button("👉 Resolver Manutenções", key="btn_nav_manut", use_container_width=True):
            st.session_state["redirecionar_menu"] = "🔧 Gestão de Manutenção"
            st.rerun()

    if tot_overstay == 0 and tot_checkout == 0 and tot_devedores == 0 and tot_limpeza == 0 and tot_manut == 0:
        st.markdown("<div class='alerta-badge-card' style='background-color:#ebfbee; color:#2b8a3e; border-left:4px solid #40c057;'>✅ Nenhuma pendência no momento</div>", unsafe_allow_html=True)

indice_atual = menu_plano.index(escolha)
renderizar_cabecalho(escolha, indice_atual)

# ==========================================
# 4. ROTEAMENTO DE MÓDULOS
# ==========================================
if escolha == "🏠 Painel Geral (Dashboard)":
    dashboard.renderizar_dashboard(usuario_atual_perfil)
elif escolha == "📊 Mapa de Ocupação & Leitos":
    hospedagem.renderizar_mapa(usuario_atual_perfil)
elif escolha == "🔔 Central de Alertas":
    operacoes.renderizar_alertas(usuario_atual_perfil)
elif escolha == "🧹 Painel de Limpeza":
    hospedagem.renderizar_limpeza()
elif escolha == "🔧 Gestão de Manutenção":
    manutencao.renderizar_manutencao(usuario_atual_perfil)

elif escolha == "📅 Nova Reserva & Edição":
    hospedagem.renderizar_reservas()
elif escolha == "📋 Check-out & Histórico":
    hospedagem.renderizar_checkout()
elif escolha == "🛒 Loja & Conveniência (PDV)":
    operacoes.renderizar_pdv(usuario_atual_email, usuario_atual_nome)
elif escolha == "🎉 Eventos & Experiências":
    operacoes.renderizar_eventos()

elif escolha == "👤 Cadastro de Hóspedes":
    cadastros.renderizar_hospedes()
elif escolha == "🏢 Empresas Parceiras":
    cadastros.renderizar_empresas()
elif escolha == "🚪 Quartos & Alas":
    cadastros.renderizar_quartos()
elif escolha == "🛏️ Camas & Preços por Leito":
    cadastros.renderizar_camas()
elif escolha == "🧑‍💼 Equipe (Colaboradores)":
    cadastros.renderizar_colaboradores()
elif escolha == "🛠️ Prestadores de Serviços":
    cadastros.renderizar_prestadores()

elif escolha == "👥 Gestão de Usuários & Acessos":
    gestao.renderizar_gestao_acessos(usuario_atual_email, usuario_atual_nome)
elif escolha == "🏛️ Integração Fiscal (NFS-e)":
    fiscal.renderizar_fiscal(usuario_atual_perfil)
elif escolha == "🛡️ Governança LGPD & Termos":
    ajuda_lgpd.renderizar_ajuda_lgpd(usuario_atual_perfil)
elif escolha == "❓ Central de Ajuda & Manual":
    ajuda_lgpd.renderizar_ajuda_lgpd(usuario_atual_perfil)
elif escolha == "📈 Relatórios & Faturamento":
    gestao.renderizar_relatorios()
elif escolha == "⚙️ Configurações & Temas":
    configuracoes.renderizar_configuracoes(usuario_atual_perfil)
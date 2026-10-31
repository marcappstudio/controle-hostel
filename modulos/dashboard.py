from datetime import datetime, timedelta
import pandas as pd
import streamlit as st
import database as db
from utils.formatadores import formatar_data_br, extrair_data

def ir_para_menu(nome_menu):
    st.session_state["redirecionar_menu"] = nome_menu
    st.rerun()

def renderizar_dashboard(usuario_perfil):
    hoje = datetime.today().date()
    primeiro_dia_mes = hoje.replace(day=1)

    # Coleta de dados operacionais
    camas = db.buscar_camas_com_quartos()
    reservas_todas = db.buscar_reservas_completas()
    manutencoes = db.buscar_manutencoes()
    alertas = db.obter_resumo_alertas()

    # Cálculos operacionais imediatos
    total_leitos = len(camas)
    leitos_ocupados = len([c for c in camas if c.get("status") == "Ocupado"])
    leitos_livres = len([c for c in camas if c.get("status") == "Disponível"])
    leitos_limpeza = len([c for c in camas if c.get("status") == "Limpeza Pendente"])
    taxa_ocupacao = (leitos_ocupados / total_leitos * 100) if total_leitos > 0 else 0.0

    # Entradas e Saídas do Dia
    checkins_hoje = []
    checkouts_hoje = []
    
    for r in reservas_todas:
        dt_ini = extrair_data(r.get("data_inicio"))
        dt_fim = extrair_data(r.get("data_fim"))
        
        if dt_ini == hoje and r.get("status") in ["Ativa", "Pendente"]:
            checkins_hoje.append(r)
        if dt_fim == hoje and r.get("status") == "Ativa":
            checkouts_hoje.append(r)

    # Manutenções Críticas / Urgentes
    manut_abertas = [m for m in manutencoes if m.get("status") in ["Pendente", "Em Andamento"]]
    manut_criticas = [m for m in manut_abertas if m.get("prioridade") in ["Alta", "Crítica"]]

    # Faturamento do Mês Atual
    faturamento_mes = sum(
        float(r.get("valor_total") or 0.0) 
        for r in reservas_todas 
        if r.get("status") == "Concluída" and extrair_data(r.get("data_fim")) and extrair_data(r.get("data_fim")) >= primeiro_dia_mes
    )

    # =========================================================================
    # 1. CARDS DE METAS E INDICADORES (COCKPIT DO DIA)
    # =========================================================================
    st.markdown("#### ⚡ Visão Executiva do Dia")
    
    col_kpi1, col_kpi2, col_kpi3, col_kpi4, col_kpi5 = st.columns(5)
    
    with col_kpi1:
        st.metric(
            label="Taxa de Ocupação",
            value=f"{taxa_ocupacao:.1f}%",
            delta=f"{leitos_ocupados}/{total_leitos} leitos"
        )
    with col_kpi2:
        st.metric(
            label="Chegadas Hoje (Check-in)",
            value=len(checkins_hoje),
            delta="Novos Hóspedes" if checkins_hoje else "Sem chegadas",
            delta_color="normal" if checkins_hoje else "off"
        )
    with col_kpi3:
        st.metric(
            label="Saídas Hoje (Check-out)",
            value=len(checkouts_hoje),
            delta="Encerramentos às 11h" if checkouts_hoje else "Sem saídas",
            delta_color="inverse" if checkouts_hoje else "off"
        )
    with col_kpi4:
        st.metric(
            label="Limpeza & Higienização",
            value=leitos_limpeza,
            delta="Leito(s) aguardando" if leitos_limpeza > 0 else "Tudo limpo",
            delta_color="inverse" if leitos_limpeza > 0 else "normal"
        )
    with col_kpi5:
        if usuario_perfil in ["Administrador", "Gerente"]:
            st.metric(
                label=f"Receita Mês ({datetime.now().strftime('%b/%Y')})",
                value=f"R$ {faturamento_mes:.2f}",
                delta="Faturamento Realizado"
            )
        else:
            st.metric(
                label="Manutenções em Aberto",
                value=len(manut_abertas),
                delta=f"{len(manut_criticas)} crítica(s)" if manut_criticas else "Em dia",
                delta_color="inverse" if manut_criticas else "normal"
            )

    st.markdown("---")

    # =========================================================================
    # 2. BARRA DE ATALHOS RÁPIDOS OPERACIONAIS (1 CLIQUE)
    # =========================================================================
    st.markdown("#### 🚀 Ações Rápidas de Balcão")
    
    btn_c1, btn_c2, btn_c3, btn_c4, btn_c5 = st.columns(5)
    with btn_c1:
        if st.button("➕ Nova Reserva", use_container_width=True, key="dash_btn_res"):
            ir_para_menu("📅 Nova Reserva / Hospedagem")
    with btn_c2:
        if st.button("🛒 Balcão / PDV", use_container_width=True, key="dash_btn_pdv"):
            ir_para_menu("🛒 Loja & Conveniência (PDV)")
    with btn_c3:
        if st.button("🧹 Painel de Limpeza", use_container_width=True, key="dash_btn_limp"):
            ir_para_menu("🧹 Painel de Limpeza")
    with btn_c4:
        if st.button("🔧 Abrir Chamado", use_container_width=True, key="dash_btn_manut"):
            ir_para_menu("🔧 Gestão de Manutenção")
    with btn_c5:
        if st.button("📊 Mapa Completo", use_container_width=True, key="dash_btn_mapa"):
            ir_para_menu("📊 Mapa Visual de Ocupação")

    st.markdown("---")

    # =========================================================================
    # 3. PAINEL DE MOVIMENTAÇÃO DE HÓSPEDES DO DIA (ENTRADAS VS SAÍDAS)
    # =========================================================================
    col_mov1, col_mov2 = st.columns(2)

    with col_mov1:
        st.markdown(f"##### 🧳 Entradas Previstas para Hoje ({len(checkins_hoje)})")
        if not checkins_hoje:
            st.info("Nenhum check-in programado para a data de hoje.")
        else:
            for cin in checkins_hoje:
                h_nome = cin.get("hospedes", {}).get("nome", "Hóspede") if cin.get("hospedes") else "Hóspede"
                h_tel = cin.get("hospedes", {}).get("telefone", "Sem telefone") if cin.get("hospedes") else ""
                q_nome = cin.get("camas", {}).get("quartos", {}).get("nome", "?") if cin.get("camas") and cin["camas"].get("quartos") else "?"
                c_num = cin.get("camas", {}).get("numero", "?") if cin.get("camas") else "?"
                loc = cin.get("codigo_localizador", "S/CÓD")
                canal = cin.get("origem_canal", "Balcão")
                total = float(cin.get("valor_total") or 0.0)

                st.markdown(
                    f"""
                    <div style='background-color: #f0fdf4; border: 1px solid #bbf7d0; border-left: 5px solid #22c55e; border-radius: 6px; padding: 10px; margin-bottom: 8px;'>
                        <div style='display: flex; justify-content: space-between;'>
                            <b>🟢 {h_nome}</b>
                            <code>{loc}</code>
                        </div>
                        <div style='font-size: 0.85rem; color: #166534; margin-top: 2px;'>
                            Quarto {q_nome} — Cama {c_num} &nbsp;|&nbsp; Tel: {h_tel} &nbsp;|&nbsp; Canal: {canal}<br>
                            <b>Valor Contratado:</b> R$ {total:.2f}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

    with col_mov2:
        st.markdown(f"##### ⏰ Saídas Previstas para Hoje ({len(checkouts_hoje)})")
        if not checkouts_hoje:
            st.success("Nenhum check-out pendente para o dia de hoje!")
        else:
            for cout in checkouts_hoje:
                cout_id = cout["id"]
                h_nome = cout.get("hospedes", {}).get("nome", "Hóspede") if cout.get("hospedes") else "Hóspede"
                q_nome = cout.get("camas", {}).get("quartos", {}).get("nome", "?") if cout.get("camas") and cout["camas"].get("quartos") else "?"
                c_num = cout.get("camas", {}).get("numero", "?") if cout.get("camas") else "?"
                loc = cout.get("codigo_localizador", "S/CÓD")
                
                c_sub1, c_sub2 = st.columns([3, 1.2])
                with c_sub1:
                    st.markdown(
                        f"""
                        <div style='background-color: #fff7ed; border: 1px solid #fed7aa; border-left: 5px solid #f97316; border-radius: 6px; padding: 10px;'>
                            <b>🟠 {h_nome}</b> [<code>{loc}</code>]<br>
                            <span style='font-size: 0.85rem; color: #9a3412;'>
                                Quarto {q_nome} — Cama {c_num} | Limite: <b>11:00</b>
                            </span>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                with c_sub2:
                    if st.button("🧾 Fechar", key=f"btn_dash_chk_{cout_id}", use_container_width=True):
                        st.session_state["redirecionar_menu"] = "📋 Histórico & Check-out"
                        st.session_state["destaque_reserva_id"] = cout_id
                        st.rerun()

    st.markdown("---")

    # =========================================================================
    # 4. QUADRO RÁPIDO DE OCUPAÇÃO POR ALA
    # =========================================================================
    st.markdown("#### 🛏️ Status Físico dos Leitos por Ala")
    
    alas = sorted(list(set(c.get("quartos", {}).get("ala", "Geral") for c in camas if c.get("quartos"))))
    if not alas:
        alas = ["Geral"]

    cols_ala = st.columns(len(alas))
    for idx, ala_nome in enumerate(alas):
        camas_ala = [c for c in camas if c.get("quartos", {}).get("ala", "Geral") == ala_nome]
        tot_ala = len(camas_ala)
        livres_ala = len([c for c in camas_ala if c.get("status") == "Disponível"])
        ocupadas_ala = len([c for c in camas_ala if c.get("status") == "Ocupado"])
        limp_ala = len([c for c in camas_ala if c.get("status") == "Limpeza Pendente"])
        
        with cols_ala[idx]:
            st.markdown(
                f"""
                <div style='background-color: #f8fafc; border: 1px solid #cbd5e1; border-radius: 8px; padding: 12px;'>
                    <b style='font-size: 1rem; color: #1e293b;'>Ala: {ala_nome}</b><br>
                    <small style='color: #64748b;'>Total: {tot_ala} leito(s)</small>
                    <div style='margin-top: 8px; font-size: 0.88rem;'>
                        🟢 Livres: <b>{livres_ala}</b><br>
                        🔴 Ocupados: <b>{ocupadas_ala}</b><br>
                        🟡 Limpeza: <b>{limp_ala}</b>
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )
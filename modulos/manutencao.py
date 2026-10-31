from datetime import datetime, timedelta
import pandas as pd
import streamlit as st
import database as db
from utils.formatadores import formatar_data_br, extrair_data
from utils.exportadores import gerar_csv, gerar_pdf_tabela

def renderizar_manutencao(usuario_perfil):
    aba_painel, aba_nova, aba_preventivas = st.tabs([
        "📋 Painel de Chamados & Ocorrências",
        "➕ Registrar Chamado / Manutenção",
        "⚙️ Programação Preventiva Periódica"
    ])

    hoje = datetime.today().date()

    # =========================================================================
    # ABA 1: PAINEL DE CHAMADOS
    # =========================================================================
    with aba_painel:
        manutencoes = db.buscar_manutencoes(ordem_data=True)

        # Métricas no topo
        tot_pendentes = len([m for m in manutencoes if m.get("status") == "Pendente"])
        tot_andamento = len([m for m in manutencoes if m.get("status") == "Em Andamento"])
        tot_criticas = len([m for m in manutencoes if m.get("prioridade") in ["Alta", "Crítica"] and m.get("status") != "Concluída"])
        tot_concluidas = len([m for m in manutencoes if m.get("status") == "Concluída"])

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Pendentes", tot_pendentes)
        m2.metric("Em Andamento", tot_andamento)
        m3.metric("Críticas / Altas", tot_criticas, delta="- Atenção" if tot_criticas > 0 else "Estável", delta_color="inverse")
        m4.metric("Concluídas", tot_concluidas)
        st.markdown("---")

        col_f1, col_f2, col_f3 = st.columns([1.5, 1, 1])
        with col_f1:
            filtro_status = st.selectbox("Filtrar por Status:", ["Todos", "Pendentes & Em Andamento", "Pendente", "Em Andamento", "Concluída"])
        with col_f2:
            filtro_tipo = st.selectbox("Filtrar por Tipo:", ["Todos", "Corretiva", "Preventiva"])
        with col_f3:
            filtro_prioridade = st.selectbox("Filtrar por Prioridade:", ["Todas", "Crítica", "Alta", "Média", "Baixa"])

        # Aplica filtros
        lista_exibicao = manutencoes
        if filtro_status == "Pendentes & Em Andamento":
            lista_exibicao = [m for m in lista_exibicao if m.get("status") in ["Pendente", "Em Andamento"]]
        elif filtro_status != "Todos":
            lista_exibicao = [m for m in lista_exibicao if m.get("status") == filtro_status]

        if filtro_tipo != "Todos":
            lista_exibicao = [m for m in lista_exibicao if m.get("tipo") == filtro_tipo]

        if filtro_prioridade != "Todas":
            lista_exibicao = [m for m in lista_exibicao if m.get("prioridade") == filtro_prioridade]

        # Barra de Exportação
        if lista_exibicao:
            col_exp1, col_exp2, col_exp3 = st.columns([2, 1, 1])
            with col_exp1:
                st.caption(f"🔧 Exibindo **{len(lista_exibicao)}** ocorrência(s)")
            with col_exp2:
                df_exp = pd.DataFrame([{
                    "Título": item["titulo"], "Tipo": item["tipo"], "Prioridade": item["prioridade"],
                    "Status": item["status"], "Local": item.get("local_detalhe") or item.get("local_tipo"),
                    "Data Limite": formatar_data_br(item.get("data_agendada")).split()[0],
                    "Custo Estimado (R$)": f"{float(item.get('custo_estimado') or 0):.2f}",
                    "Custo Real (R$)": f"{float(item.get('custo_real') or 0):.2f}"
                } for item in lista_exibicao])
                st.download_button("📥 Baixar CSV", gerar_csv(df_exp), f"manutencoes_{hoje}.csv", "text/csv", use_container_width=True)
            with col_exp3:
                cols_pdf = ["Título", "Tipo", "Prioridade", "Status", "Local", "Data Limite"]
                pdf_bytes = gerar_pdf_tabela("Relatório de Manutenções e Ocorrências", cols_pdf, df_exp.to_dict(orient="records"), "L")
                st.download_button("📕 Baixar PDF", pdf_bytes, f"manutencoes_{hoje}.pdf", "application/pdf", use_container_width=True)
            st.markdown("---")

        if not lista_exibicao:
            st.info("Nenhuma ocorrência encontrada para os filtros selecionados.")
        else:
            for m in lista_exibicao:
                m_id = m["id"]
                tit = m.get("titulo", "Sem título")
                tipo = m.get("tipo", "Corretiva")
                prio = m.get("prioridade", "Média")
                status = m.get("status", "Pendente")
                dt_ag = extrair_data(m.get("data_agendada"))
                atrasada = bool(dt_ag and dt_ag < hoje and status != "Concluída")

                # Monta identificação do local
                loc_tipo = m.get("local_tipo", "Geral")
                detalhe_loc = m.get("local_detalhe", "")
                if loc_tipo == "Quarto" and m.get("quartos"):
                    local_str = f"🚪 Quarto {m['quartos'].get('nome')} ({m['quartos'].get('ala', 'Geral')})"
                elif loc_tipo == "Leito/Cama" and m.get("camas"):
                    quarto_c = m.get("quartos", {}).get("nome", "?") if m.get("quartos") else "?"
                    local_str = f"🛏️ Cama {m['camas'].get('numero')} (Quarto {quarto_c})"
                else:
                    local_str = f"🏢 {loc_tipo}: {detalhe_loc}" if detalhe_loc else f"🏢 {loc_tipo}"

                # Estilos visuais por prioridade
                if prio == "Crítica":
                    cor_prio = "#dc2626"
                elif prio == "Alta":
                    cor_prio = "#ea580c"
                elif prio == "Média":
                    cor_prio = "#d97706"
                else:
                    cor_prio = "#16a34a"

                badge_atraso = " <span style='background-color: #fee2e2; color: #b91c1c; padding: 2px 8px; border-radius: 4px; font-weight: bold;'>⚠️ Atrasada!</span>" if atrasada else ""
                badge_status = f"<span style='background-color: #e2e8f0; color: #1e293b; padding: 2px 8px; border-radius: 4px; font-size: 0.85rem;'>{status}</span>"

                st.markdown(
                    f"""
                    <div style='background-color: #f8fafc; border: 1px solid #cbd5e1; border-left: 6px solid {cor_prio}; border-radius: 6px; padding: 12px; margin-bottom: 8px;'>
                        <div style='display: flex; justify-content: space-between; align-items: center;'>
                            <b style='font-size: 1.05rem; color: #0f172a;'>🔧 {tit}</b>
                            <div>{badge_status} {badge_atraso}</div>
                        </div>
                        <div style='font-size: 0.88rem; color: #475569; margin-top: 4px;'>
                            <b>Local:</b> {local_str} &nbsp;|&nbsp; 
                            <b>Tipo:</b> {tipo} &nbsp;|&nbsp; 
                            <b>Prioridade:</b> <span style='color: {cor_prio}; font-weight: bold;'>{prio}</span> &nbsp;|&nbsp; 
                            <b>Data Limite:</b> {dt_ag.strftime('%d/%m/%Y') if dt_ag else 'Não informada'}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

                with st.expander(f"⚙️ Detalhes e Ações do Chamado #{m_id}"):
                    c_det1, c_det2 = st.columns(2)
                    with c_det1:
                        st.write(f"**Descrição / Ocorrência:** {m.get('descricao') or 'Sem descrição adicional'}")
                        prest_info = m.get("prestadores", {}).get("nome_razao") if m.get("prestadores") else m.get("responsavel_nome", "Equipe interna")
                        st.write(f"**Responsável / Prestador:** {prest_info}")
                        st.write(f"**Custo Estimado:** R$ {float(m.get('custo_estimado') or 0):.2f}")
                        if m.get("custo_real"):
                            st.write(f"**Custo Real Efetivado:** R$ {float(m.get('custo_real') or 0):.2f}")

                    with c_det2:
                        if status == "Pendente":
                            if st.button("▶️ Iniciar Reparo (Em Andamento)", key=f"btn_ini_{m_id}", use_container_width=True):
                                db.supabase.table("manutencoes").update({"status": "Em Andamento"}).eq("id", m_id).execute()
                                st.success("Chamado colocado em andamento!")
                                st.rerun()

                        if status in ["Pendente", "Em Andamento"]:
                            with st.popover("✅ Concluir Manutenção"):
                                custo_f = st.number_input("Custo Final Efetivado (R$)", min_value=0.0, value=float(m.get("custo_estimado") or 0.0), format="%.2f", key=f"cf_{m_id}")
                                obs_concl = st.text_area("Observações da Conclusão", placeholder="Ex: Peça substituída, testado e funcionando.", key=f"obs_c_{m_id}")
                                if st.button("Confirmar Conclusão", key=f"btn_concl_{m_id}"):
                                    db.supabase.table("manutencoes").update({
                                        "status": "Concluída",
                                        "custo_real": custo_f,
                                        "observacoes_conclusao": obs_concl,
                                        "data_conclusao": datetime.now().isoformat()
                                    }).eq("id", m_id).execute()
                                    st.success("Manutenção concluída e arquivada!")
                                    st.rerun()

                        if usuario_perfil == "Administrador":
                            if st.button("🗑️ Excluir Chamado", key=f"btn_del_manut_{m_id}", use_container_width=True):
                                db.supabase.table("manutencoes").delete().eq("id", m_id).execute()
                                st.success("Registro removido!")
                                st.rerun()
                st.markdown("---")

    # =========================================================================
    # ABA 2: REGISTRAR CHAMADO
    # =========================================================================
    with aba_nova:
        st.subheader("➕ Abrir Ordem de Serviço ou Chamado")
        
        res_quartos = db.supabase.table("quartos").select("id, nome, ala").execute()
        quartos_lista = res_quartos.data or []
        camas_lista = db.buscar_camas_com_quartos()
        res_prest = db.supabase.table("prestadores").select("id, nome_razao, categoria_servico").execute()
        prestadores = res_prest.data or []

        with st.form("form_nova_manutencao"):
            col_t1, col_t2 = st.columns([2, 1])
            with col_t1:
                titulo = st.text_input("Título do Chamado (ex: Reparo no chuveiro elétrico, Troca do filtro)", placeholder="Identificação concisa da ocorrência")
            with col_t2:
                tipo = st.selectbox("Tipo de Manutenção:", ["Corretiva", "Preventiva"])

            col_p1, col_p2, col_p3 = st.columns(3)
            with col_p1:
                prioridade = st.selectbox("Nível de Prioridade:", ["Baixa", "Média", "Alta", "Crítica"])
            with col_p2:
                data_agendada = st.date_input("Data Limite / Execução:", value=hoje, format="DD/MM/YYYY")
            with col_p3:
                custo_estimado = st.number_input("Custo Estimado (R$):", min_value=0.0, value=0.0, step=10.0, format="%.2f")

            st.markdown("##### 📍 Local da Ocorrência")
            col_l1, col_l2 = st.columns(2)
            with col_l1:
                local_tipo = st.selectbox("Tipo de Local:", ["Quarto", "Leito/Cama", "Área Comum", "Equipamento Geral"])

            quarto_id_sel = None
            cama_id_sel = None
            local_detalhe = ""

            with col_l2:
                if local_tipo == "Quarto":
                    q_opcoes = {f"Quarto {q['nome']} ({q.get('ala', 'Geral')})": q["id"] for q in quartos_lista}
                    if q_opcoes:
                        q_sel = st.selectbox("Selecione o Quarto:", list(q_opcoes.keys()))
                        quarto_id_sel = q_opcoes[q_sel]
                    else:
                        st.caption("Nenhum quarto cadastrado.")
                elif local_tipo == "Leito/Cama":
                    c_opcoes = {f"Cama {c['numero']} — Quarto {c.get('quartos', {}).get('nome', '?')}": (c["id"], c["quarto_id"]) for c in camas_lista}
                    if c_opcoes:
                        c_sel = st.selectbox("Selecione a Cama:", list(c_opcoes.keys()))
                        cama_id_sel, quarto_id_sel = c_opcoes[c_sel]
                    else:
                        st.caption("Nenhuma cama cadastrada.")
                else:
                    local_detalhe = st.text_input("Nome do Local ou Equipamento:", placeholder="Ex: Bebedouro Recepção, Ar-condicionado Sala")

            st.markdown("##### 👤 Atribuição de Responsável")
            col_r1, col_r2 = st.columns(2)
            with col_r1:
                p_opcoes = {"-- Equipe Interna / Outro --": None}
                for p in prestadores:
                    p_opcoes[f"{p['nome_razao']} ({p.get('categoria_servico', 'Geral')})"] = p["id"]
                prest_escolhido = st.selectbox("Prestador Externo Cadastrado:", list(p_opcoes.keys()))
                prestador_id_sel = p_opcoes[prest_escolhido]
            with col_r2:
                responsavel_nome = st.text_input("Nome do Responsável Interno (se aplicável):", placeholder="Ex: João da Manutenção")

            descricao = st.text_area("Descrição Detalhada do Problema / Instruções:")

            if st.form_submit_button("Salvar Ordem de Serviço", type="primary", use_container_width=True):
                if not titulo:
                    st.error("Informe um título para o chamado.")
                else:
                    db.supabase.table("manutencoes").insert({
                        "titulo": titulo,
                        "descricao": descricao,
                        "tipo": tipo,
                        "prioridade": prioridade,
                        "status": "Pendente",
                        "local_tipo": local_tipo,
                        "quarto_id": quarto_id_sel,
                        "cama_id": cama_id_sel,
                        "local_detalhe": local_detalhe,
                        "data_agendada": data_agendada.isoformat(),
                        "custo_estimado": custo_estimado,
                        "prestador_id": prestador_id_sel,
                        "responsavel_nome": responsavel_nome
                    }).execute()
                    st.success("Chamado de manutenção cadastrado com sucesso!")
                    st.rerun()

    # =========================================================================
    # ABA 3: PROGRAMAÇÃO PREVENTIVA
    # =========================================================================
    with aba_preventivas:
        st.subheader("⚙️ Agendamento Rápido de Rotinas Preventivas")
        st.caption("Crie agendamentos de rotina com prazos pré-configurados:")

        rotinas_padrao = [
            {"titulo": "Troca de Filtro de Água (Bebedouro)", "meses": 6, "prioridade": "Alta", "local": "Equipamento Geral", "detalhe": "Filtro Central / Bebedouro"},
            {"titulo": "Higienização e Limpeza dos Filtros de Ar-Condicionado", "meses": 3, "prioridade": "Média", "local": "Área Comum", "detalhe": "Aparelhos de Ar-Condicionado"},
            {"titulo": "Dedetização e Controle de Pragas", "meses": 6, "prioridade": "Crítica", "local": "Área Comum", "detalhe": "Todo o Hostel"},
            {"titulo": "Revisão Elétrica e Quadros de Disjuntores", "meses": 12, "prioridade": "Alta", "local": "Equipamento Geral", "detalhe": "Quadro Geral de Energia"},
            {"titulo": "Inspeção e Recarga de Extintores de Incêndio", "meses": 12, "prioridade": "Crítica", "local": "Área Comum", "detalhe": "Extintores de Incêndio"}
        ]

        for rot in rotinas_padrao:
            c_r1, c_r2, c_r3 = st.columns([3, 2, 2])
            with c_r1:
                st.write(f"🔧 **{rot['titulo']}**")
                st.caption(f"Frequência sugerida: cada **{rot['meses']} meses** | Prioridade: **{rot['prioridade']}**")
            with c_r2:
                data_sugerida = hoje + timedelta(days=rot["meses"] * 30)
                st.write(f"📅 Sugestão: **{data_sugerida.strftime('%d/%m/%Y')}**")
            with c_r3:
                if st.button("Agendar Preventiva", key=f"btn_rot_{rot['titulo']}"):
                    db.supabase.table("manutencoes").insert({
                        "titulo": rot["titulo"],
                        "tipo": "Preventiva",
                        "prioridade": rot["prioridade"],
                        "status": "Pendente",
                        "local_tipo": rot["local"],
                        "local_detalhe": rot["detalhe"],
                        "data_agendada": data_sugerida.isoformat(),
                        "descricao": f"Rotina periódica preventiva com intervalo de {rot['meses']} meses."
                    }).execute()
                    st.success(f"Preventiva '{rot['titulo']}' agendada para {data_sugerida.strftime('%d/%m/%Y')}!")
                    st.rerun()
            st.markdown("---")
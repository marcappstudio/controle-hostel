import json
from datetime import datetime, timedelta
import pandas as pd
import streamlit as st
import database as db
from utils.formatadores import formatar_data_br, extrair_data
from utils.exportadores import gerar_csv, gerar_pdf_tabela

def renderizar_relatorios():
    aba_metricas, aba_exportacao = st.tabs(["📊 Painel Financeiro & Métricas", "📥 Exportação de Dados"])

    with aba_metricas:
        col_filtro1, col_filtro2 = st.columns(2)
        hoje = datetime.today().date()
        com_inicio_mes = hoje.replace(day=1)
        
        with col_filtro1:
            data_ini_rel = st.date_input("Data Inicial", value=com_inicio_mes - timedelta(days=30), format="DD/MM/YYYY")
        with col_filtro2:
            data_fim_rel = st.date_input("Data Final", value=hoje, format="DD/MM/YYYY")

        try:
            res_res = db.supabase.table("reservas").select("*").execute()
            todas_reservas = res_res.data or []
            todas_vendas = db.buscar_vendas_completas()
            todos_ev_part = db.buscar_participantes_eventos_completos()

            reservas_periodo = [r for r in todas_reservas if extrair_data(r.get("data_inicio")) and data_ini_rel <= extrair_data(r.get("data_inicio")) <= data_fim_rel]
            vendas_periodo = [v for v in todas_vendas if extrair_data(v.get("data_venda")) and data_ini_rel <= extrair_data(v.get("data_venda")) <= data_fim_rel]

            faturamento_hospedagem = sum(float(r.get("valor_total") or 0.0) for r in reservas_periodo if r.get("status") == "Concluída")
            faturamento_pdv_pago = sum(float(v.get("valor_total") or 0.0) for v in vendas_periodo if v.get("status_pagamento") == "Pago")
            faturamento_eventos_pago = sum(float(ep.get("eventos", {}).get("valor_participacao") or 0.0) for ep in todos_ev_part if ep.get("status_pagamento") == "Pago" and ep.get("eventos"))

            receita_total_realizada = faturamento_hospedagem + faturamento_pdv_pago + faturamento_eventos_pago
            pendente_pdv = sum(float(v.get("valor_total") or 0.0) for v in todas_vendas if v.get("status_pagamento") != "Pago")
            pendente_eventos = sum(float(ep.get("eventos", {}).get("valor_participacao") or 0.0) for ep in todos_ev_part if ep.get("status_pagamento") != "Pago" and ep.get("eventos"))
            total_pendente_aberto = pendente_pdv + pendente_eventos

            num_diarias = len([r for r in reservas_periodo if r.get("status") == "Concluída"])
            adr = (faturamento_hospedagem / num_diarias) if num_diarias > 0 else 0.0

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Receita Total Realizada", f"R$ {receita_total_realizada:.2f}")
            m2.metric("Saldo Pendente (A Receber)", f"R$ {total_pendente_aberto:.2f}", delta="- Pendências" if total_pendente_aberto > 0 else "Em dia", delta_color="inverse")
            m3.metric("Diária Média (ADR)", f"R$ {adr:.2f}")
            m4.metric("Check-outs Concluídos", num_diarias)

            st.markdown("---")
            col_g1, col_g2 = st.columns(2)
            with col_g1:
                st.subheader("📊 Composição do Faturamento")
                df_origem = pd.DataFrame({
                    "Origem": ["Hospedagem", "Loja (PDV)", "Eventos"],
                    "Total (R$)": [faturamento_hospedagem, faturamento_pdv_pago, faturamento_eventos_pago]
                }).set_index("Origem")
                st.bar_chart(df_origem)

            with col_g2:
                st.subheader("🛒 Vendas do PDV por Categoria")
                cat_totais = {}
                for v in vendas_periodo:
                    if v.get("status_pagamento") == "Pago":
                        cat_nome = v.get("produtos", {}).get("categoria") if v.get("produtos") else "Sem Categoria"
                        cat_totais[cat_nome] = cat_totais.get(cat_nome, 0.0) + float(v.get("valor_total") or 0.0)
                
                if cat_totais:
                    df_cat = pd.DataFrame(list(cat_totais.items()), columns=["Categoria", "Total (R$)"]).set_index("Categoria")
                    st.bar_chart(df_cat)
                else:
                    st.info("Nenhuma venda no período selecionado.")

            st.markdown("---")
            st.subheader("🌐 Desempenho por Canal de Aquisição")
            if reservas_periodo:
                canais_dados = {}
                for r in reservas_periodo:
                    canal = r.get("origem_canal") or "Balcão (Presencial)"
                    val_res = float(r.get("valor_total") or 0.0)
                    if canal not in canais_dados:
                        canais_dados[canal] = {"Reservas": 0, "Receita": 0.0}
                    canais_dados[canal]["Reservas"] += 1
                    canais_dados[canal]["Receita"] += val_res

                col_c_vol, col_c_rec = st.columns(2)
                with col_c_vol:
                    df_canal_vol = pd.DataFrame([{"Canal": c, "Qtd Reservas": dados["Reservas"]} for c, dados in canais_dados.items()]).set_index("Canal")
                    st.bar_chart(df_canal_vol)
                with col_c_rec:
                    df_canal_rec = pd.DataFrame([{"Canal": c, "Faturamento (R$)": dados["Receita"]} for c, dados in canais_dados.items()]).set_index("Canal")
                    st.bar_chart(df_canal_rec)

        except Exception as e:
            st.error(f"Erro ao compilar métricas: {e}")

    with aba_exportacao:
        st.subheader("📥 Central de Exportação de Dados (CSV e PDF)")
        hoje_str = datetime.today().date()
        exp_c1, exp_c2 = st.columns(2)
        
        with exp_c1:
            st.markdown("##### 👥 Cadastro Geral de Hóspedes")
            hosp_raw = db.supabase.table("hospedes").select("nome, email, telefone, nacionalidade, documento").execute().data or []
            if hosp_raw:
                df_h = pd.DataFrame(hosp_raw)
                c_h1, c_h2 = st.columns(2)
                with c_h1:
                    st.download_button("📄 Baixar CSV (Excel)", gerar_csv(df_h), f"hospedes_{hoje_str}.csv", "text/csv", use_container_width=True)
                with c_h2:
                    pdf_h = gerar_pdf_tabela("Cadastro Geral de Hóspedes", ["nome", "telefone", "email", "nacionalidade", "documento"], hosp_raw, "L")
                    st.download_button("📕 Baixar PDF", pdf_h, f"hospedes_{hoje_str}.pdf", "application/pdf", use_container_width=True)
            else:
                st.info("Nenhum hóspede cadastrado.")

            st.markdown("---")
            st.markdown("##### 🛒 Vendas da Loja / PDV")
            vendas_raw = db.buscar_vendas_completas()
            if vendas_raw:
                linhas_v = [{
                    "Produto": vr.get("produtos", {}).get("nome", "Item"),
                    "Quantidade": vr.get("quantidade", 1),
                    "Total (R$)": f"{float(vr.get('valor_total') or 0):.2f}",
                    "Comprador": vr.get("hospedes", {}).get("nome") if vr.get("hospedes") else (vr.get("comprador_nome") or "Avulso"),
                    "Status": vr.get("status_pagamento", "Pago"),
                    "Data": formatar_data_br(vr.get("data_venda"))
                } for vr in vendas_raw]
                df_v = pd.DataFrame(linhas_v)
                c_v1, c_v2 = st.columns(2)
                with c_v1:
                    st.download_button("📄 Baixar CSV (Excel)", gerar_csv(df_v), f"vendas_pdv_{hoje_str}.csv", "text/csv", use_container_width=True)
                with c_v2:
                    pdf_v = gerar_pdf_tabela("Vendas da Conveniência", ["Produto", "Quantidade", "Total (R$)", "Comprador", "Status", "Data"], linhas_v, "L")
                    st.download_button("📕 Baixar PDF", pdf_v, f"vendas_pdv_{hoje_str}.pdf", "application/pdf", use_container_width=True)

        with exp_c2:
            st.markdown("##### 🏨 Histórico de Reservas")
            res_raw = db.buscar_reservas_completas()
            if res_raw:
                linhas_r = [{
                    "Localizador": rr.get("codigo_localizador", "S/CÓD"),
                    "Hóspede": rr.get("hospedes", {}).get("nome", ""),
                    "Quarto": rr.get("camas", {}).get("quartos", {}).get("nome", "") if rr.get("camas") and rr.get("camas").get("quartos") else "",
                    "Cama": rr.get("camas", {}).get("numero", "") if rr.get("camas") else "",
                    "Canal de Origem": rr.get("origem_canal", "Balcão (Presencial)"),
                    "Entrada": formatar_data_br(rr.get("data_inicio")),
                    "Saída": formatar_data_br(rr.get("data_fim")),
                    "Total (R$)": f"{float(rr.get('valor_total') or 0):.2f}",
                    "Status": rr.get("status", "")
                } for rr in res_raw]
                df_r = pd.DataFrame(linhas_r)
                c_r1, c_r2 = st.columns(2)
                with c_r1:
                    st.download_button("📄 Baixar CSV (Excel)", gerar_csv(df_r), f"reservas_{hoje_str}.csv", "text/csv", use_container_width=True)
                with c_r2:
                    pdf_r = gerar_pdf_tabela("Histórico Geral de Reservas", ["Localizador", "Hóspede", "Quarto", "Cama", "Canal de Origem", "Entrada", "Saída", "Total (R$)", "Status"], linhas_r, "L")
                    st.download_button("📕 Baixar PDF", pdf_r, f"reservas_{hoje_str}.pdf", "application/pdf", use_container_width=True)

def renderizar_gestao_acessos(usuario_email, usuario_nome):
    aba_novo, aba_lista, aba_seeder = st.tabs([
        "➕ Cadastrar Novo Colaborador", "👥 Usuários Ativos & Suspensões", "🧪 Carga de Testes & Limpeza"
    ])

    with aba_novo:
        st.subheader("➕ Criar Conta para Novo Colaborador")
        st.caption("Apenas administradores logados podem criar novos operadores de sistema.")

        with st.form("form_cad_usuario"):
            u_nome = st.text_input("Nome Completo do Colaborador:")
            u_email = st.text_input("E-mail Institucional de Acesso:").strip()
            u_senha = st.text_input("Senha Inicial (mínimo 6 dígitos):", type="password")
            u_perfil = st.selectbox("Perfil de Acesso:", ["Recepção", "Limpeza", "Administrador"])

            if st.form_submit_button("Cadastrar e Liberar Acesso", type="primary", use_container_width=True):
                if len(u_senha) < 6:
                    st.error("A senha deve ter no mínimo 6 caracteres.")
                else:
                    try:
                        db.supabase.auth.sign_up({
                            "email": u_email, "password": u_senha, 
                            "options": {"data": {"nome": u_nome, "perfil": u_perfil}}
                        })
                        db.salvar_perfil_usuario(u_email, u_nome, u_perfil, ativo=True)
                        db.notificar_sucesso(f"Usuário '{u_nome}' cadastrado com sucesso!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao cadastrar usuário: {e}")

    with aba_lista:
        st.subheader("👥 Gestão de Colaboradores e Bloqueios")
        st.caption("Gerencie permissões ou suspenda temporariamente o acesso de operadores desligados.")

        usuarios = db.listar_todos_usuarios()
        for usr in usuarios:
            u_mail = usr.get("email", "")
            u_nome_exib = usr.get("nome", u_mail)
            u_perf_exib = usr.get("perfil", "Recepção")
            u_status = usr.get("status", "Ativo")

            c1, c2, c3, c4 = st.columns([2.5, 1.5, 1.2, 1.5])
            with c1:
                st.write(f"👤 **{u_nome_exib}**")
                st.caption(u_mail)
            with c2:
                st.write(f"Perfil: **{u_perf_exib}**")
            with c3:
                cor_st = "#16a34a" if u_status == "Ativo" else "#dc2626"
                st.markdown(f"<span style='color: {cor_st}; font-weight: bold;'>{u_status}</span>", unsafe_allow_html=True)
            with c4:
                with st.popover("Gerenciar"):
                    novo_p = st.selectbox("Perfil:", ["Recepção", "Limpeza", "Administrador"], index=["Recepção", "Limpeza", "Administrador"].index(u_perf_exib) if u_perf_exib in ["Recepção", "Limpeza", "Administrador"] else 0, key=f"sel_p_{u_mail}")
                    tornar_suspenso = st.checkbox("Suspender / Bloquear Acesso", value=(u_status == "Suspenso"), key=f"chk_susp_{u_mail}")
                    if st.button("Salvar Alterações", key=f"btn_salv_u_{u_mail}"):
                        db.salvar_perfil_usuario(u_mail, u_nome_exib, novo_p, ativo=(not tornar_suspenso))
                        db.notificar_sucesso(f"Acesso de {u_nome_exib} atualizado!")
                        st.rerun()
            st.markdown("---")

    with aba_seeder:
        st.subheader("🧪 Carga de Testes e Limpeza Operacional")
        col_s1, col_s2 = st.columns(2)
        with col_s1:
            st.markdown("##### 🚀 Popular Demonstração")
            chk_seed = st.checkbox("Confirmar carga de testes", key="chk_seed_modular")
            if st.button("Popular Dados de Teste", type="primary"):
                if not chk_seed:
                    st.error("Marque a confirmação.")
                else:
                    try:
                        for cat in ["Bebidas", "Snacks & Bomboniere"]:
                            if not db.supabase.table("categorias_produtos").select("nome").eq("nome", cat).execute().data:
                                db.supabase.table("categorias_produtos").insert({"nome": cat}).execute()
                        db.notificar_sucesso("Dados de teste carregados com sucesso!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro: {e}")

        with col_s2:
            st.markdown("##### 🗑️ Limpar Dados Operacionais")
            chk_clean = st.checkbox("Confirmar remoção dos dados operacionais", key="chk_clean_modular")
            if st.button("Limpar Banco"):
                if not chk_clean:
                    st.error("Marque a confirmação.")
                else:
                    for tb in ["manutencoes", "vendas", "eventos_participantes", "reservas", "camas", "quartos", "hospedes", "empresas", "produtos"]:
                        try:
                            db.supabase.table(tb).delete().neq("id", 0).execute()
                        except Exception:
                            pass
                    db.notificar_sucesso("Banco operacional resetado!")
                    st.rerun()
import json
from datetime import datetime, timedelta, time
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
        "➕ Cadastrar Novo Usuário", "👥 Gerenciar / Excluir Usuários", "🧪 Carga de Testes & Limpeza"
    ])

    # =========================================================================
    # ABA 1: CRIAR NOVA CONTA DE ACESSO
    # =========================================================================
    with aba_novo:
        st.subheader("➕ Criar Conta para Novo Colaborador")
        st.caption("Apenas administradores logados podem criar novos operadores de sistema.")

        with st.form("form_cad_usuario", clear_on_submit=True):
            u_nome = st.text_input("Nome Completo do Colaborador *")
            u_email = st.text_input("E-mail Institucional de Acesso *").strip().lower()
            u_senha = st.text_input("Senha Inicial (mínimo 6 dígitos) *", type="password")
            u_perfil = st.selectbox("Perfil de Acesso:", ["Recepção", "Limpeza", "Administrador"])

            st.markdown("---")
            st.markdown("##### ⏰ Janela de Acesso Permitido")
            u_restringir = st.checkbox("Restringir horário de login deste usuário?", value=False)
            col_uh1, col_uh2 = st.columns(2)
            with col_uh1:
                u_h_ini = st.time_input("Entrada Permitida", value=time(8, 0), step=1800)
            with col_uh2:
                u_h_fim = st.time_input("Saída Permitida", value=time(17, 0), step=1800)

            if st.form_submit_button("Cadastrar e Liberar Acesso", type="primary", use_container_width=True):
                if not u_nome or not u_email:
                    st.error("Informe o nome e o e-mail do colaborador.")
                elif len(u_senha) < 6:
                    st.error("A senha deve ter no mínimo 6 caracteres.")
                else:
                    try:
                        # 1. Registra no Supabase Auth
                        db.supabase.auth.sign_up({
                            "email": u_email, 
                            "password": u_senha, 
                            "options": {"data": {"nome": u_nome, "perfil": u_perfil}}
                        })
                        # 2. Salva perfil de acesso no sistema
                        db.salvar_perfil_usuario(u_email, u_nome, u_perfil, ativo=True)

                        # 3. Sincroniza na tabela colaboradores com os horários de turno
                        try:
                            res_col = db.supabase.table("colaboradores").select("id").eq("email", u_email).execute()
                            dados_col = {
                                "nome": u_nome,
                                "email": u_email,
                                "cargo": u_perfil,
                                "status": "Ativo",
                                "restringir_horario": u_restringir,
                                "horario_inicio": u_h_ini.strftime("%H:%M:%S"),
                                "horario_fim": u_h_fim.strftime("%H:%M:%S")
                            }
                            if res_col.data and len(res_col.data) > 0:
                                db.supabase.table("colaboradores").update(dados_col).eq("email", u_email).execute()
                            else:
                                db.supabase.table("colaboradores").insert(dados_col).execute()
                        except Exception:
                            pass

                        db.notificar_sucesso(f"Usuário '{u_nome}' cadastrado com sucesso!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao cadastrar usuário: {e}")

    # =========================================================================
    # ABA 2: GERENCIAR, EDITAR E EXCLUIR USUÁRIOS (COM DROPDOWN)
    # =========================================================================
    with aba_lista:
        st.subheader("👥 Gestão de Usuários, Permissões e Exclusão")
        st.caption("Selecione um usuário na lista suspensa abaixo para editar permissões, definir horários ou excluir a conta.")

        # Unifica usuários de usuarios_sistema/configuracoes e colaboradores com e-mail
        usuarios_base = db.listar_todos_usuarios() or []
        mapa_usuarios = {}

        for u in usuarios_base:
            mail = str(u.get("email") or "").strip().lower()
            if mail:
                mapa_usuarios[mail] = {
                    "email": mail,
                    "nome": u.get("nome") or mail,
                    "perfil": u.get("perfil") or "Recepção",
                    "status": u.get("status") or "Ativo",
                    "restringir_horario": False,
                    "horario_inicio": "08:00:00",
                    "horario_fim": "17:00:00"
                }

        try:
            res_c = db.supabase.table("colaboradores").select("*").execute()
            for c in (res_c.data or []):
                mail_c = str(c.get("email") or "").strip().lower()
                if mail_c:
                    if mail_c in mapa_usuarios:
                        mapa_usuarios[mail_c]["restringir_horario"] = bool(c.get("restringir_horario", False))
                        mapa_usuarios[mail_c]["horario_inicio"] = c.get("horario_inicio") or "08:00:00"
                        mapa_usuarios[mail_c]["horario_fim"] = c.get("horario_fim") or "17:00:00"
                    else:
                        cargo_c = c.get("cargo", "Recepção")
                        perfil_map = "Administrador" if cargo_c in ["Administrador", "Gerente"] else ("Limpeza" if cargo_c == "Limpeza" else "Recepção")
                        mapa_usuarios[mail_c] = {
                            "email": mail_c,
                            "nome": c.get("nome") or mail_c,
                            "perfil": perfil_map,
                            "status": "Suspenso" if c.get("status") in ["Suspenso", "Inativo"] else "Ativo",
                            "restringir_horario": bool(c.get("restringir_horario", False)),
                            "horario_inicio": c.get("horario_inicio") or "08:00:00",
                            "horario_fim": c.get("horario_fim") or "17:00:00"
                        }
        except Exception:
            pass

        lista_unificada = sorted(list(mapa_usuarios.values()), key=lambda x: x["nome"].lower())

        if not lista_unificada:
            st.info("Nenhum usuário cadastrado.")
        else:
            opcoes_usr = ["-- Selecione o Usuário para Editar ou Excluir --"] + [
                f"{u['nome']} ({u['perfil']}) — {u['email']} [{u['status']}]" for u in lista_unificada
            ]

            usr_escolhido_str = st.selectbox("Buscar Usuário:", opcoes_usr)

            if usr_escolhido_str != "-- Selecione o Usuário para Editar ou Excluir --":
                idx_u = opcoes_usr.index(usr_escolhido_str) - 1
                usr_sel = lista_unificada[idx_u]
                u_mail = usr_sel["email"]
                u_nome_atual = usr_sel["nome"]
                u_perf_atual = usr_sel["perfil"]
                u_status_atual = usr_sel["status"]

                st.markdown("---")
                with st.form(f"form_edit_usr_{u_mail}"):
                    st.markdown(f"#### ✏️ Editando Usuário: **{u_nome_atual}** (`{u_mail}`)")
                    
                    col_u1, col_u2 = st.columns(2)
                    with col_u1:
                        edit_nome = st.text_input("Nome Completo:", value=u_nome_atual)
                        perfis_lista = ["Recepção", "Limpeza", "Administrador"]
                        idx_p = perfis_lista.index(u_perf_atual) if u_perf_atual in perfis_lista else 0
                        edit_perfil = st.selectbox("Perfil de Acesso:", perfis_lista, index=idx_p)
                    with col_u2:
                        tornar_suspenso = st.checkbox("🚫 Suspender / Bloquear Acesso deste Usuário", value=(u_status_atual == "Suspenso"))
                        edit_restringir = st.checkbox("⏰ Restringir horário de login?", value=bool(usr_sel.get("restringir_horario", False)))

                    # Horários de turno
                    h_ini_v = time(8, 0)
                    if usr_sel.get("horario_inicio"):
                        try:
                            h_ini_v = datetime.strptime(str(usr_sel["horario_inicio"])[:8], "%H:%M:%S").time()
                        except Exception:
                            pass

                    h_fim_v = time(17, 0)
                    if usr_sel.get("horario_fim"):
                        try:
                            h_fim_v = datetime.strptime(str(usr_sel["horario_fim"])[:8], "%H:%M:%S").time()
                        except Exception:
                            pass

                    col_th1, col_th2 = st.columns(2)
                    with col_th1:
                        edit_h_ini = st.time_input("Entrada Permitida", value=h_ini_v, step=1800, key=f"u_ini_{u_mail}")
                    with col_th2:
                        edit_h_fim = st.time_input("Saída Permitida", value=h_fim_v, step=1800, key=f"u_fim_{u_mail}")

                    if st.form_submit_button("💾 Salvar Alterações do Usuário", type="primary", use_container_width=True):
                        db.salvar_perfil_usuario(u_mail, edit_nome, edit_perfil, ativo=(not tornar_suspenso))
                        try:
                            res_col_check = db.supabase.table("colaboradores").select("id").eq("email", u_mail).execute()
                            payload_col = {
                                "nome": edit_nome,
                                "cargo": edit_perfil,
                                "status": "Inativo" if tornar_suspenso else "Ativo",
                                "restringir_horario": edit_restringir,
                                "horario_inicio": edit_h_ini.strftime("%H:%M:%S"),
                                "horario_fim": edit_h_fim.strftime("%H:%M:%S")
                            }
                            if res_col_check.data and len(res_col_check.data) > 0:
                                db.supabase.table("colaboradores").update(payload_col).eq("email", u_mail).execute()
                            else:
                                payload_col["email"] = u_mail
                                db.supabase.table("colaboradores").insert(payload_col).execute()
                        except Exception:
                            pass

                        if tornar_suspenso:
                            db.revogar_token_sessao(u_mail)

                        db.notificar_sucesso(f"Acesso de {edit_nome} atualizado com sucesso!")
                        st.rerun()

                # Zona de Exclusão Definitiva
                st.markdown("---")
                with st.expander("🗑️ Zona de Perigo: Excluir este Usuário Permanentemente", expanded=False):
                    if u_mail.lower() == str(usuario_email or "").strip().lower():
                        st.info("🔒 Você não pode excluir a sua própria conta de Administrador enquanto estiver logado nela.")
                    else:
                        st.warning(f"Tem certeza de que deseja excluir permanentemente o acesso de **{u_nome_atual}** (`{u_mail}`)?")
                        confirma_del_u = st.checkbox("Sim, confirmo a exclusão definitiva deste usuário", key=f"chk_del_u_{u_mail}")
                        
                        if st.button("🗑️ Excluir Usuário Definitivamente", type="primary", use_container_width=True, key=f"btn_del_u_{u_mail}"):
                            if not confirma_del_u:
                                st.error("Marque a caixa de confirmação acima para autorizar a exclusão.")
                            else:
                                db.revogar_token_sessao(u_mail)
                                db.excluir_usuario_sistema(u_mail)
                                db.notificar_sucesso(f"Usuário {u_nome_atual} excluído permanentemente!")
                                st.rerun()

    # =========================================================================
    # ABA 3: CARGA DE TESTES E LIMPEZA OPERACIONAL
    # =========================================================================
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
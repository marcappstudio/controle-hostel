import json
import urllib.parse
from datetime import datetime, timedelta
import pandas as pd
import streamlit as st
import database as db
from utils.formatadores import formatar_data_br, extrair_data
from utils.exportadores import gerar_csv, gerar_pdf_tabela

def ir_para_menu(nome_menu, reserva_id=None):
    st.session_state["redirecionar_menu"] = nome_menu
    if reserva_id is not None:
        st.session_state["destaque_reserva_id"] = reserva_id
    st.rerun()

def renderizar_alertas(usuario_perfil):
    dados_alertas = db.obter_resumo_alertas()
    total_overstay = len(dados_alertas["overstay"])
    total_checkout_hoje = len(dados_alertas["checkout_hoje"])
    total_devedores = len(dados_alertas["inadimplencia_vendas"]) + len(dados_alertas["inadimplencia_eventos"])
    total_limpeza = len(dados_alertas["limpeza_pendente"])
    total_manut = len(dados_alertas.get("manutencoes_urgentes", []))

    aba_overstay, aba_saidas, aba_debitos, aba_limpeza_alerta, aba_manut_alerta = st.tabs([
        f"🚨 Estadias Excedidas ({total_overstay})",
        f"⏰ Saídas de Hoje ({total_checkout_hoje})",
        f"💸 Inadimplência ({total_devedores})",
        f"🧹 Limpeza ({total_limpeza})",
        f"🔧 Manutenção Crítica ({total_manut})"
    ])

    with aba_overstay:
        st.subheader("🚨 Estadias Excedidas (Overstay)")
        st.caption("Reservas ativas cuja data de saída expirou, mas o check-out não foi efetuado.")
        
        if not dados_alertas["overstay"]:
            st.success("Nenhuma estadia excedida. Todas as estadias estão no prazo.")
        else:
            hoje = datetime.today().date()
            for r in dados_alertas["overstay"]:
                r_id = r["id"]
                h_nome = r["hospedes"]["nome"] if r.get("hospedes") else "Hóspede"
                h_tel = r["hospedes"]["telefone"] if r.get("hospedes") else "Sem telefone"
                c_num = r["camas"]["numero"] if r.get("camas") else "?"
                q_nome = r["camas"]["quartos"]["nome"] if r.get("camas") and r["camas"].get("quartos") else "?"
                dt_fim = extrair_data(r.get("data_fim"))
                dias_atraso = (hoje - dt_fim).days if dt_fim else 0

                c1, c2, c3 = st.columns([3, 2, 2])
                with c1:
                    st.error(f"**Hóspede:** {h_nome} (Quarto {q_nome} - Cama {c_num})")
                    st.write(f"📞 Tel: {h_tel}")
                with c2:
                    st.write(f"📅 **Previsão:** {formatar_data_br(r.get('data_fim'))}")
                    st.write(f"⚠️ **Atraso:** {dias_atraso} dia(s)")
                with c3:
                    if st.button("👉 Ir p/ Fechar Conta", key=f"btn_chk_overstay_{r_id}", use_container_width=True):
                        ir_para_menu("📋 Histórico & Check-out", reserva_id=r_id)

                    with st.popover("Prorrogar Diárias"):
                        nova_saida = st.date_input("Nova Saída", min_value=hoje + timedelta(days=1), format="DD/MM/YYYY", key=f"prorr_{r_id}")
                        valor_adicional = st.number_input("Valor Adicional (R$)", min_value=0.0, format="%.2f", key=f"v_prorr_{r_id}")
                        if st.button("Confirmar Prorrogação", key=f"btn_prorr_{r_id}"):
                            dt_fim_completa = datetime.combine(nova_saida, datetime.strptime("11:00", "%H:%M").time()).isoformat()
                            novo_total = float(r.get("valor_total") or 0.0) + valor_adicional
                            db.supabase.table("reservas").update({"data_fim": dt_fim_completa, "valor_total": novo_total}).eq("id", r_id).execute()
                            st.success("Estadia prorrogada!")
                            st.rerun()
                st.markdown("---")

    with aba_saidas:
        st.subheader("⏰ Check-outs Previstos para Hoje (11:00)")
        if not dados_alertas["checkout_hoje"]:
            st.info("Nenhuma reserva programada para encerrar hoje.")
        else:
            for r in dados_alertas["checkout_hoje"]:
                r_id = r["id"]
                h_nome = r["hospedes"]["nome"] if r.get("hospedes") else "Hóspede"
                h_tel = r["hospedes"]["telefone"] if r.get("hospedes") else "Não informado"
                c_num = r["camas"]["numero"] if r.get("camas") else "?"
                q_nome = r["camas"]["quartos"]["nome"] if r.get("camas") and r["camas"].get("quartos") else "?"
                
                col_s1, col_s2 = st.columns([3, 2])
                with col_s1:
                    st.warning(f"🛏️ **Quarto {q_nome} — Cama {c_num}**: {h_nome}")
                    st.caption(f"📞 Telefone: {h_tel}")
                with col_s2:
                    if st.button("👉 Realizar Check-out", key=f"btn_act_hoje_{r_id}", use_container_width=True):
                        ir_para_menu("📋 Histórico & Check-out", reserva_id=r_id)
                st.markdown("---")

    with aba_debitos:
        st.subheader("💸 Inadimplência e Contas Pendentes")
        st.markdown("##### 🛒 Vendas da Conveniência / PDV Pendentes")
        if not dados_alertas["inadimplencia_vendas"]:
            st.success("Nenhuma venda pendente de quitação.")
        else:
            for v in dados_alertas["inadimplencia_vendas"]:
                v_id = v["id"]
                prod_nome = v["produtos"]["nome"] if v.get("produtos") else "Item"
                hosp_nome = v["hospedes"]["nome"] if v.get("hospedes") else (v.get("comprador_nome") or "Cliente Avulso")
                val_total = float(v.get("valor_total") or 0.0)

                cv1, cv2, cv3 = st.columns([3, 2, 2])
                with cv1:
                    st.write(f"**Devedor:** {hosp_nome}")
                    st.caption(f"Item: {v.get('quantidade', 1)}x {prod_nome}")
                with cv2:
                    st.write(f"**Valor Devido:** R$ {val_total:.2f}")
                with cv3:
                    col_b1, col_b2 = st.columns(2)
                    with col_b1:
                        if st.button("💰 Quitar", key=f"pag_alerta_v_{v_id}"):
                            db.supabase.table("vendas").update({"status_pagamento": "Pago"}).eq("id", v_id).execute()
                            st.success("Pagamento registrado!")
                            st.rerun()
                    with col_b2:
                        if st.button("👉 Ir ao PDV", key=f"nav_pdv_{v_id}"):
                            ir_para_menu("🛒 Loja & Conveniência (PDV)")
                st.markdown("---")

        st.markdown("##### 🎉 Eventos Pendentes de Pagamento")
        if not dados_alertas["inadimplencia_eventos"]:
            st.success("Não há inscrições de eventos com pagamento em aberto.")
        else:
            for ep in dados_alertas["inadimplencia_eventos"]:
                ep_id = ep["id"]
                ev_nome = ep["eventos"]["nome"] if ep.get("eventos") else "Evento"
                val_ev = float(ep["eventos"].get("valor_participacao") or 0.0) if ep.get("eventos") else 0.0
                part_nome = ep["hospedes"]["nome"] if ep.get("hospedes") else (ep.get("nome_visitante") or "Visitante")

                ce1, ce2, ce3 = st.columns([3, 2, 2])
                with ce1:
                    st.write(f"**Participante:** {part_nome}")
                    st.caption(f"Evento: {ev_nome}")
                with ce2:
                    st.write(f"**Valor:** R$ {val_ev:.2f}")
                with ce3:
                    col_be1, col_be2 = st.columns(2)
                    with col_be1:
                        if st.button("💰 Quitar", key=f"pag_alerta_ev_{ep_id}"):
                            db.supabase.table("eventos_participantes").update({"status_pagamento": "Pago"}).eq("id", ep_id).execute()
                            st.success("Taxa quitada!")
                            st.rerun()
                    with col_be2:
                        if st.button("👉 Ver Eventos", key=f"nav_ev_{ep_id}"):
                            ir_para_menu("🎉 Eventos & Experiências")
                st.markdown("---")

    with aba_limpeza_alerta:
        st.subheader("🧹 Leitos Aguardando Limpeza")
        if not dados_alertas["limpeza_pendente"]:
            st.success("Todos os leitos estão limpos e arrumados!")
        else:
            for cp in dados_alertas["limpeza_pendente"]:
                c_id = cp["id"]
                q_nome = cp["quartos"]["nome"] if cp.get("quartos") else "Quarto"
                c_num = cp.get("numero", "?")

                cl1, cl2, cl3 = st.columns([3, 2, 2])
                with cl1:
                    st.warning(f"🛏️ **Quarto {q_nome} — Cama {c_num}**")
                with cl2:
                    com_toalha = st.checkbox("Equipar com toalha", value=True, key=f"alerta_toalha_{c_id}")
                with cl3:
                    col_bl1, col_bl2 = st.columns(2)
                    with col_bl1:
                        if st.button("Liberar Leito", key=f"btn_libera_alerta_{c_id}"):
                            db.supabase.table("camas").update({"status": "Disponível", "toalha_colocada": com_toalha}).eq("id", c_id).execute()
                            st.success(f"Cama {c_num} liberada!")
                            st.rerun()
                    with col_bl2:
                        if st.button("👉 Ir p/ Limpeza", key=f"btn_go_limp_{c_id}"):
                            ir_para_menu("🧹 Painel de Limpeza")
                st.markdown("---")

    with aba_manut_alerta:
        st.subheader("🔧 Manutenções Críticas ou Vencidas")
        st.caption("Ordens de serviço com prazo expirado ou classificadas com prioridade Alta/Crítica.")
        
        manut_urgentes = dados_alertas.get("manutencoes_urgentes", [])
        if not manut_urgentes:
            st.success("Nenhuma manutenção crítica ou atrasada no momento!")
        else:
            for mu in manut_urgentes:
                mu_id = mu["id"]
                tit = mu.get("titulo", "Manutenção")
                prio = mu.get("prioridade", "Alta")
                dt_ag = extrair_data(mu.get("data_agendada"))
                is_venc = mu.get("vencida", False)

                col_m1, col_m2, col_m3 = st.columns([3, 2, 2])
                with col_m1:
                    st.error(f"**{tit}**")
                    st.caption(f"Local: {mu.get('local_detalhe') or mu.get('local_tipo')} | Prioridade: {prio}")
                with col_m2:
                    dt_str = dt_ag.strftime('%d/%m/%Y') if dt_ag else 'Sem data'
                    if is_venc:
                        st.markdown(f"📅 Prazo: **{dt_str}** <b style='color:#dc2626;'>(Atrasada!)</b>", unsafe_allow_html=True)
                    else:
                        st.write(f"📅 Prazo: **{dt_str}**")
                with col_m3:
                    col_bm1, col_bm2 = st.columns(2)
                    with col_bm1:
                        if st.button("✅ Concluir", key=f"btn_concl_alerta_{mu_id}"):
                            db.supabase.table("manutencoes").update({
                                "status": "Concluída",
                                "data_conclusao": datetime.now().isoformat()
                            }).eq("id", mu_id).execute()
                            st.success("Manutenção concluída!")
                            st.rerun()
                    with col_bm2:
                        if st.button("👉 Abrir Módulo", key=f"btn_goto_manut_{mu_id}"):
                            ir_para_menu("🔧 Gestão de Manutenção")
                st.markdown("---")

def renderizar_pdv(usuario_email, usuario_nome):
    res_cat_prod = db.supabase.table("categorias_produtos").select("nome").order("nome").execute()
    cat_produtos_lista = [c["nome"] for c in res_cat_prod.data] if res_cat_prod.data else ["Sem categoria"]
    
    aba_pdv, aba_caixa, aba_cad_prod, aba_cat_prod, aba_hist_vendas = st.tabs([
        "Frente de Caixa (PDV)", "💼 Caixa & Turno", "Gestão de Produtos", "Configurar Categorias", "Histórico de Vendas"
    ])

    with aba_pdv:
        try:
            res_produtos = db.supabase.table("produtos").select("*").execute()
            produtos_disponiveis = [p for p in (res_produtos.data or []) if p.get("estoque", 0) > 0]
            res_hospedes = db.supabase.table("hospedes").select("id, nome").execute()
            hospedes_lista = res_hospedes.data or []

            if not produtos_disponiveis:
                st.warning("O estoque está vazio. Cadastre novos produtos na aba ao lado.")
            else:
                with st.form("form_pdv"):
                    st.subheader("Lançar Venda")
                    prod_labels = ["-- Selecione o Produto --"] + [f"{p['nome']} (Estoque: {p['estoque']}) — R$ {float(p.get('preco', 0)):.2f}" for p in produtos_disponiveis]
                    prod_escolhido = st.selectbox("Produto", prod_labels)
                    qtde_venda = st.number_input("Quantidade", min_value=1, value=1, step=1)
                    
                    st.markdown("##### Identificação do Comprador")
                    tipo_comprador = st.radio("Comprador:", ["Hóspede", "Cliente Avulso (Não Hospedado)"], horizontal=True)
                    hospede_id_venda = None
                    comprador_nome_venda = None
                    
                    if tipo_comprador == "Hóspede":
                        if not hospedes_lista:
                            st.error("Nenhum hóspede cadastrado.")
                        else:
                            hosp_labels = ["-- Selecione o Hóspede --"] + [h['nome'] for h in hospedes_lista]
                            hosp_escolhido = st.selectbox("Hóspede", hosp_labels)
                    else:
                        comprador_nome_venda = st.text_input("Nome do Cliente Avulso")
                        
                    st.markdown("##### Forma de Acerto")
                    status_pagamento = st.selectbox("Situação do Pagamento", ["Pago", "Pendente (Lançar na Conta)"])
                    
                    if st.form_submit_button("Finalizar Venda", use_container_width=True):
                        if prod_escolhido == "-- Selecione o Produto --":
                            st.error("Selecione um produto.")
                        elif tipo_comprador == "Hóspede" and (not hospedes_lista or hosp_escolhido == "-- Selecione o Hóspede --"):
                            st.error("Selecione o hóspede.")
                        elif tipo_comprador == "Cliente Avulso (Não Hospedado)" and not comprador_nome_venda:
                            st.error("Informe o nome do cliente avulso.")
                        else:
                            idx_prod = prod_labels.index(prod_escolhido) - 1
                            produto_obj = produtos_disponiveis[idx_prod]
                            
                            if qtde_venda > produto_obj["estoque"]:
                                st.error(f"Estoque insuficiente! Apenas {produto_obj['estoque']} unidades disponíveis.")
                            else:
                                if tipo_comprador == "Hóspede":
                                    idx_hosp = hosp_labels.index(hosp_escolhido) - 1
                                    hospede_id_venda = hospedes_lista[idx_hosp]["id"]
                                
                                valor_total_venda = float(produto_obj["preco"]) * qtde_venda
                                db.supabase.table("vendas").insert({
                                    "produto_id": produto_obj["id"], "quantidade": qtde_venda, "valor_total": valor_total_venda,
                                    "hospede_id": hospede_id_venda, "comprador_nome": comprador_nome_venda,
                                    "status_pagamento": status_pagamento
                                }).execute()
                                
                                novo_estoque = int(produto_obj["estoque"]) - qtde_venda
                                db.supabase.table("produtos").update({"estoque": novo_estoque}).eq("id", produto_obj["id"]).execute()
                                st.success(f"Venda concluída! Total: R$ {valor_total_venda:.2f}")
                                st.rerun()
        except Exception as e:
            st.error(f"Erro ao abrir PDV: {e}")

    with aba_caixa:
        st.subheader("💼 Controle de Caixa por Turno")
        chave_caixa_aberto = f"caixa_aberto_{usuario_email}"
        res_caixa = db.supabase.table("configuracoes").select("valor").eq("chave", chave_caixa_aberto).execute()
        dados_caixa_atual = json.loads(res_caixa.data[0]["valor"]) if (res_caixa.data and len(res_caixa.data) > 0 and res_caixa.data[0].get("valor")) else None

        if not dados_caixa_atual:
            st.info("Nenhum turno aberto no momento.")
            with st.form("form_abrir_caixa"):
                fundo_troco = st.number_input("Fundo de Troco Inicial (R$)", min_value=0.0, format="%.2f", step=10.0)
                obs_abertura = st.text_input("Observações de Abertura")
                if st.form_submit_button("Abrir Turno de Caixa"):
                    novo_caixa = {
                        "operador_nome": usuario_nome, "operador_email": usuario_email,
                        "data_abertura": datetime.now().isoformat(), "fundo_troco": fundo_troco,
                        "sangrias": 0.0, "suprimentos": 0.0,
                        "historico_movimentacoes": [{"tipo": "Abertura", "valor": fundo_troco, "motivo": obs_abertura or "Fundo inicial", "hora": datetime.now().strftime("%H:%M")}]
                    }
                    db.supabase.table("configuracoes").upsert({"chave": chave_caixa_aberto, "valor": json.dumps(novo_caixa)}).execute()
                    st.success("Turno aberto com sucesso!")
                    st.rerun()
        else:
            col_cx1, col_cx2, col_cx3 = st.columns(3)
            col_cx1.metric("Fundo de Troco", f"R$ {dados_caixa_atual.get('fundo_troco', 0.0):.2f}")
            col_cx2.metric("Suprimentos (+)", f"R$ {dados_caixa_atual.get('suprimentos', 0.0):.2f}")
            col_cx3.metric("Sangrias (-)", f"R$ {dados_caixa_atual.get('sangrias', 0.0):.2f}")
            
            st.write(f"Turno aberto em: **{formatar_data_br(dados_caixa_atual.get('data_abertura'))}** por **{dados_caixa_atual.get('operador_nome')}**")
            st.markdown("---")

            col_mov, col_fechar = st.columns(2)
            with col_mov:
                st.markdown("##### ➕ Movimentação Avulsa")
                tipo_mov = st.selectbox("Tipo:", ["Sangria (Retirada)", "Suprimento (Reforço)"])
                valor_mov = st.number_input("Valor (R$)", min_value=0.0, format="%.2f", key="val_mov_caixa")
                motivo_mov = st.text_input("Motivo", key="motivo_mov_caixa")
                
                if st.button("Confirmar Movimentação"):
                    if valor_mov <= 0 or not motivo_mov:
                        st.error("Informe um valor e um motivo válido.")
                    else:
                        nome_t = "Sangria" if tipo_mov.startswith("Sangria") else "Suprimento"
                        if nome_t == "Sangria":
                            dados_caixa_atual["sangrias"] = dados_caixa_atual.get("sangrias", 0.0) + valor_mov
                        else:
                            dados_caixa_atual["suprimentos"] = dados_caixa_atual.get("suprimentos", 0.0) + valor_mov

                        dados_caixa_atual["historico_movimentacoes"].append({"tipo": nome_t, "valor": valor_mov, "motivo": motivo_mov, "hora": datetime.now().strftime("%H:%M")})
                        db.supabase.table("configuracoes").update({"valor": json.dumps(dados_caixa_atual)}).eq("chave", chave_caixa_aberto).execute()
                        st.success(f"{nome_t} registrada!")
                        st.rerun()

            with col_fechar:
                st.markdown("##### 🔒 Fechamento de Caixa (Conferência Cega)")
                dinheiro_contado = st.number_input("Total em Dinheiro Físico Contado (R$)", min_value=0.0, format="%.2f", key="din_contado")

                if st.button("Encerrar Turno de Caixa", type="primary"):
                    saldo_esperado = dados_caixa_atual.get("fundo_troco", 0.0) + dados_caixa_atual.get("suprimentos", 0.0) - dados_caixa_atual.get("sangrias", 0.0)
                    diferenca = dinheiro_contado - saldo_esperado
                    
                    dados_caixa_atual["data_fechamento"] = datetime.now().isoformat()
                    dados_caixa_atual["valor_declarado"] = dinheiro_contado
                    dados_caixa_atual["diferenca"] = diferenca
                    
                    chave_hist = f"caixa_hist_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{usuario_email}"
                    db.supabase.table("configuracoes").insert({"chave": chave_hist, "valor": json.dumps(dados_caixa_atual)}).execute()
                    db.supabase.table("configuracoes").delete().eq("chave", chave_caixa_aberto).execute()
                    st.success(f"Caixa encerrado! Saldo apurado: R$ {dinheiro_contado:.2f} (Diferença: R$ {diferenca:.2f})")
                    st.rerun()

    with aba_cad_prod:
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Cadastrar Produto")
            pr_nome = st.text_input("Nome do Produto")
            pr_cat = st.selectbox("Categoria", cat_produtos_lista)
            res_sub = db.supabase.table("subcategorias_produtos").select("nome").eq("categoria_nome", pr_cat).execute()
            lista_sub = [s["nome"] for s in res_sub.data] if res_sub.data else ["Geral"]
            pr_subcat = st.selectbox("Subcategoria", lista_sub)
            pr_preco = st.number_input("Preço de Venda (R$)", min_value=0.0, format="%.2f")
            pr_estoque = st.number_input("Estoque Inicial", min_value=0, step=1)
            
            if st.button("Salvar Produto"):
                if not pr_nome or pr_preco <= 0:
                    st.error("Preencha nome e preço válido.")
                else:
                    db.supabase.table("produtos").insert({
                        "nome": pr_nome, "categoria": pr_cat, "subcategoria": pr_subcat,
                        "preco": pr_preco, "estoque": pr_estoque
                    }).execute()
                    st.success("Produto cadastrado!")
                    st.rerun()
                        
        with col2:
            st.subheader("Atualizar Estoque/Preço")
            res_produtos = db.supabase.table("produtos").select("*").execute()
            todos_produtos = res_produtos.data or []
            if todos_produtos:
                p_labels = ["-- Selecione --"] + [f"{p['nome']} (Estoque: {p['estoque']})" for p in todos_produtos]
                p_sel = st.selectbox("Buscar Produto:", p_labels)
                if p_sel != "-- Selecione --":
                    p_obj = todos_produtos[p_labels.index(p_sel) - 1]
                    e_preco = st.number_input("Preço", value=float(p_obj.get("preco", 0.0)), format="%.2f")
                    e_estoque = st.number_input("Estoque", value=int(p_obj.get("estoque", 0)), step=1)
                    if st.button("Atualizar"):
                        db.supabase.table("produtos").update({"preco": e_preco, "estoque": e_estoque}).eq("id", p_obj["id"]).execute()
                        st.success("Atualizado!")
                        st.rerun()

    with aba_cat_prod:
        st.subheader("Categorias de Produtos")
        nova_cat = st.text_input("Nova Categoria Mestre")
        if st.button("Adicionar Categoria"):
            if nova_cat:
                db.supabase.table("categorias_produtos").upsert({"nome": nova_cat}).execute()
                st.success("Categoria criada!")
                st.rerun()

    with aba_hist_vendas:
        st.subheader("Histórico de Vendas da Conveniência")
        vendas = db.buscar_vendas_completas(ordem_desc=True)
        if not vendas:
            st.info("Nenhuma venda registrada.")
        else:
            dados_vendas_tabela = []
            for v in vendas:
                p_nome = v["produtos"]["nome"] if v.get("produtos") else "Item"
                c_nome = v["hospedes"]["nome"] if v.get("hospedes") else (v.get("comprador_nome") or "Avulso")
                dados_vendas_tabela.append({
                    "Produto": p_nome,
                    "Quantidade": v.get("quantidade", 1),
                    "Total (R$)": f"{float(v.get('valor_total') or 0):.2f}",
                    "Comprador": c_nome,
                    "Status": v.get("status_pagamento", "Pago"),
                    "Data": formatar_data_br(v.get("data_venda"))
                })

            col_exp_v1, col_exp_v2, col_exp_v3 = st.columns([2, 1, 1])
            with col_exp_v1:
                st.caption(f"🛒 Total de vendas registradas: **{len(dados_vendas_tabela)}**")
            with col_exp_v2:
                df_v_exp = pd.DataFrame(dados_vendas_tabela)
                st.download_button(
                    label="📥 Baixar Vendas (CSV)",
                    data=gerar_csv(df_v_exp),
                    file_name=f"vendas_pdv_{datetime.today().date()}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            with col_exp_v3:
                cols_v_pdf = ["Produto", "Quantidade", "Total (R$)", "Comprador", "Status", "Data"]
                pdf_v_bytes = gerar_pdf_tabela("Histórico de Vendas da Conveniência", cols_v_pdf, dados_vendas_tabela, orientacao="L")
                st.download_button(
                    label="📕 Baixar Vendas (PDF)",
                    data=pdf_v_bytes,
                    file_name=f"vendas_pdv_{datetime.today().date()}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
            st.markdown("---")

            for v in vendas:
                p_nome = v["produtos"]["nome"] if v.get("produtos") else "Item"
                c_nome = v["hospedes"]["nome"] if v.get("hospedes") else (v.get("comprador_nome") or "Avulso")
                st.write(f"• **{v.get('quantidade')}x {p_nome}** — R$ {float(v.get('valor_total') or 0):.2f} ({c_nome}) — [{v.get('status_pagamento')}]")

def renderizar_eventos():
    aba_cad_ev, aba_part_ev, aba_fotos_ev, aba_qr_ev = st.tabs([
        "Cadastrar / Gerenciar Evento", "Lista de Participantes", "Mural de Fotos", "Gerador de QR Code PIX"
    ])

    with aba_cad_ev:
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Novo Evento")
            with st.form("form_novo_evento"):
                ev_nome = st.text_input("Nome do Evento (ex: Noite da Pizza)")
                ev_desc = st.text_area("Descrição")
                ev_data = st.date_input("Data do Evento", min_value=datetime.today().date(), format="DD/MM/YYYY")
                ev_valor = st.number_input("Valor de Participação (R$)", min_value=0.0, format="%.2f")
                if st.form_submit_button("Agendar Evento"):
                    if not ev_nome:
                        st.error("Nome obrigatório.")
                    else:
                        db.supabase.table("eventos").insert({"nome": ev_nome, "descricao": ev_desc, "data_inicio": ev_data.isoformat(), "valor_participacao": ev_valor}).execute()
                        st.success("Evento agendado!")
                        st.rerun()
        with col2:
            st.subheader("Eventos Registrados")
            res_ev = db.supabase.table("eventos").select("*").order("data_inicio", desc=True).execute()
            for ev in (res_ev.data or []):
                st.write(f"🗓️ **{formatar_data_br(ev['data_inicio']).split()[0]}** — {ev['nome']} (R$ {float(ev.get('valor_participacao') or 0):.2f})")
                if st.button("Excluir", key=f"del_ev_{ev['id']}"):
                    db.supabase.table("eventos").delete().eq("id", ev["id"]).execute()
                    st.rerun()

    with aba_part_ev:
        res_ev = db.supabase.table("eventos").select("*").order("data_inicio", desc=True).execute()
        eventos = res_ev.data or []
        if not eventos:
            st.warning("Cadastre um evento primeiro.")
        else:
            ev_labels = {f"{e['nome']} ({formatar_data_br(e['data_inicio']).split()[0]})": e for e in eventos}
            ev_sel = ev_labels[st.selectbox("Selecione o Evento:", list(ev_labels.keys()))]
            
            with st.form("form_add_part"):
                nome_visitante = st.text_input("Nome do Participante")
                status_pag = st.selectbox("Pagamento:", ["Pendente", "Pago"])
                if st.form_submit_button("Confirmar Presença"):
                    if nome_visitante:
                        db.supabase.table("eventos_participantes").insert({"evento_id": ev_sel["id"], "nome_visitante": nome_visitante, "status_pagamento": status_pag}).execute()
                        st.success("Participante adicionado!")
                        st.rerun()

            st.markdown("##### Confirmados:")
            parts = db.buscar_participantes_eventos_completos(evento_id_filtro=ev_sel["id"])
            for p in parts:
                p_nome = p["hospedes"]["nome"] if p.get("hospedes") else p.get("nome_visitante")
                st.write(f"• 👤 {p_nome} — [{p['status_pagamento']}]")

    with aba_fotos_ev:
        st.subheader("Mural de Fotos")
        st.info("Cole o link direto da imagem para adicionar ao álbum do evento.")

    with aba_qr_ev:
        st.subheader("Gerador de QR Code PIX")
        pix_copia_cola = st.text_input("Cole o código PIX Copia e Cola:")
        if pix_copia_cola:
            pix_encoded = urllib.parse.quote(pix_copia_cola)
            url_qr = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={pix_encoded}"
            st.image(url_qr, caption="Aponte a câmera para pagar", width=250)
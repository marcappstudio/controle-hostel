import re
import json
import uuid
import urllib.parse
from datetime import datetime, timedelta
import pandas as pd
import streamlit as st
import database as db
from utils.formatadores import (
    formatar_data_br, extrair_data, ordenar_natural
)
from utils.exportadores import gerar_csv, gerar_pdf_tabela, gerar_pdf_recibo

def sanitizar_html(html_str: str) -> str:
    """Remove quebras de linha e indentação para impedir que o Markdown trate 4 espaços como bloco de código."""
    return " ".join(line.strip() for line in html_str.splitlines() if line.strip())

def renderizar_mapa(usuario_perfil):
    try:
        res_quartos = db.supabase.table("quartos").select("*").execute()
        res_camas = db.supabase.table("camas").select("*").execute()
        
        quartos = res_quartos.data or []
        camas = res_camas.data or []
        reservas_ativas = db.buscar_reservas_completas(status_filtro="Ativa", incluir_foto=True)

        hoje = datetime.today().date()
        alertas_checkout = []

        for r in reservas_ativas:
            dt_fim = extrair_data(r.get("data_fim"))
            if dt_fim == hoje:
                num_cama = r.get("camas", {}).get("numero", "?") if r.get("camas") else "?"
                nome_quarto = r.get("camas", {}).get("quartos", {}).get("nome", "?") if r.get("camas") and r.get("camas").get("quartos") else "?"
                nome_hospede = r.get("hospedes", {}).get("nome", "Hóspede") if r.get("hospedes") else "Hóspede"
                alertas_checkout.append(f"A Cama **{num_cama}** do Quarto **{nome_quarto}** ({nome_hospede}) vence hoje às **11:00**.")

        if alertas_checkout:
            st.warning("### ⚠️ Atenção: Leitos com Check-out Previsto para Hoje (11:00):\n" + "\n".join([f"- {a}" for a in alertas_checkout]))
            if st.button("👉 Ir para todos os Check-outs de Hoje", key="btn_top_chk_hoje"):
                st.session_state["redirecionar_menu"] = "📋 Check-out & Histórico"
                st.rerun()

        total_camas = len(camas)
        ocupadas = len([c for c in camas if c.get("status") == "Ocupado"])
        limpeza = len([c for c in camas if c.get("status") == "Limpeza Pendente"])
        disponiveis = len([c for c in camas if c.get("status") == "Disponível"])
        taxa_ocupacao = (ocupadas / total_camas * 100) if total_camas > 0 else 0

        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Total de Leitos", total_camas)
        col2.metric("Livres", disponiveis)
        col3.metric("Ocupadas", ocupadas)
        col4.metric("Limpeza Pendente", limpeza)
        col5.metric("Taxa de Ocupação", f"{taxa_ocupacao:.1f}%")
        st.markdown("---")

        alas_disponiveis = sorted(list(set(q.get("ala", "Geral") for q in quartos if q.get("ala"))))
        ala_selecionada = st.selectbox("Filtrar por Ala:", ["-- Todas as Alas --"] + alas_disponiveis)

        quartos_filtrados = quartos if ala_selecionada == "-- Todas as Alas --" else [q for q in quartos if q.get("ala") == ala_selecionada]
        quartos_ordenados = ordenar_natural(quartos_filtrados, "nome")
        camas_vagas_geral = [c for c in camas if c.get("status") == "Disponível"]

        for quarto in quartos_ordenados:
            q_id = quarto["id"]
            q_nome = quarto["nome"]
            q_perfil = quarto.get("perfil", "Misto")
            q_pcd = " ♿ PCD" if quarto.get("pcd") else ""
            tem_ar = bool(quarto.get("ar_condicionado", False))
            
            badge_clima_quarto = (
                "<span style='background:#e0f2fe; color:#0369a1; padding:3px 8px; border-radius:6px; font-weight:600; font-size:0.85rem; border:1px solid #bae6fd;'>❄️ Ar-Condicionado</span>"
                if tem_ar else
                "<span style='background:#f1f5f9; color:#475569; padding:3px 8px; border-radius:6px; font-weight:600; font-size:0.85rem; border:1px solid #cbd5e1;'>🌀 Ventilador</span>"
            )

            q_ala = f" (Ala: {quarto.get('ala')})" if quarto.get("ala") else ""

            header_quarto_html = sanitizar_html(f"""
                <div style='display:flex; align-items:center; justify-content:space-between; margin-top:16px; margin-bottom:8px;'>
                    <h3 style='margin:0; font-size:1.3rem; color:#1e293b;'>🚪 {q_nome}{q_ala} <span style='font-size:0.95rem; font-weight:normal; color:#64748b;'>— {q_perfil}{q_pcd}</span></h3>
                    <div>{badge_clima_quarto}</div>
                </div>
            """)
            st.markdown(header_quarto_html, unsafe_allow_html=True)

            camas_quarto = [c for c in camas if c.get("quarto_id") == q_id]
            camas_quarto_ordenadas = ordenar_natural(camas_quarto, "numero")

            if not camas_quarto_ordenadas:
                st.info("Nenhuma cama cadastrada neste quarto.")
                continue

            cols = st.columns(4)
            for idx, cama in enumerate(camas_quarto_ordenadas):
                c_id = cama["id"]
                c_status = cama.get("status", "Disponível")
                c_num = cama.get("numero")
                c_tipo = cama.get("tipo_leito", "Leito")
                toalha_colocada = cama.get("toalha_colocada", False)
                toalha_badge = "<span style='font-size:0.75rem; background:#dcfce7; color:#15803d; padding:2px 6px; border-radius:4px;'>🧺 Toalha</span>" if toalha_colocada else "<span style='font-size:0.75rem; background:#f1f5f9; color:#94a3b8; padding:2px 6px; border-radius:4px;'>Sem toalha</span>"
                
                detalhes_hospede = ""
                foto_html = ""
                checkout_hoje = False
                reserva_cama = None
                tel_hosp_wpp = None
                nome_hospede_txt = ""

                preco_leito = float(cama.get("preco_diaria") or quarto.get("preco_base") or 80.0)

                if c_status == "Ocupado":
                    reserva_cama = next((r for r in reservas_ativas if r.get("cama_id") == c_id), None)
                    if reserva_cama:
                        dt_saida = extrair_data(reserva_cama.get("data_fim"))
                        if dt_saida == hoje:
                            checkout_hoje = True

                        if reserva_cama.get("hospedes"):
                            nome_hospede_txt = reserva_cama["hospedes"].get("nome", "Hóspede")
                            h_tel = reserva_cama["hospedes"].get("telefone", "Não informado")
                            h_foto = reserva_cama["hospedes"].get("foto")
                            f_fim = formatar_data_br(reserva_cama.get("data_fim"))
                            cod_loc = reserva_cama.get("codigo_localizador", "S/CÓD")
                            canal_res = reserva_cama.get("origem_canal", "Balcão")
                            tel_hosp_wpp = re.sub(r'\D', '', str(h_tel))
                            
                            nome_empresa = reserva_cama.get("empresas", {}).get("razao_social") if reserva_cama.get("empresas") else None
                            info_empresa = f"<div style='font-size:0.75rem; color:#6366f1; margin-top:2px;'>🏢 Faturado: {nome_empresa}</div>" if reserva_cama.get("faturar_empresa") and nome_empresa else ""
                            
                            if h_foto:
                                foto_html = f"<img src='{h_foto}' style='width:42px; height:42px; border-radius:50%; object-fit:cover; border:2px solid #cbd5e1; margin-right:8px;'>"
                            
                            aviso_saida = "<div style='color:#dc2626; font-weight:700; font-size:0.78rem; margin-top:3px;'>⚠️ Saída hoje às 11:00!</div>" if checkout_hoje else ""
                            
                            detalhes_hospede = (
                                f"<div style='display:flex; align-items:center; margin-top:8px;'>"
                                f"{foto_html}"
                                f"<div style='line-height:1.2;'>"
                                f"<div style='font-weight:700; color:#0f172a; font-size:0.92rem;'>{nome_hospede_txt}</div>"
                                f"<div style='font-size:0.75rem; color:#64748b;'>Loc: <code>{cod_loc}</code> • {canal_res}</div>"
                                f"</div></div>"
                                f"<div style='font-size:0.78rem; color:#475569; margin-top:6px;'>"
                                f"📅 <b>Saída:</b> {f_fim}"
                                f"{aviso_saida}"
                                f"{info_empresa}"
                                f"</div>"
                            )

                if c_status == "Disponível":
                    bg_color, border_cor = "#f0fdf4", "#86efac"
                    status_badge = f"<span style='background:#dcfce7; color:#15803d; font-weight:700; font-size:0.78rem; padding:2px 8px; border-radius:4px;'>🟢 Livre • R$ {preco_leito:.2f}</span>"
                elif c_status == "Ocupado" and checkout_hoje:
                    bg_color, border_cor = "#fff7ed", "#fdba74"
                    status_badge = "<span style='background:#ffedd5; color:#c2410c; font-weight:700; font-size:0.78rem; padding:2px 8px; border-radius:4px;'>⏰ Saída Hoje (11h)</span>"
                elif c_status == "Ocupado":
                    bg_color, border_cor = "#fef2f2", "#fca5a5"
                    status_badge = f"<span style='background:#fee2e2; color:#b91c1c; font-weight:700; font-size:0.78rem; padding:2px 8px; border-radius:4px;'>🔴 Ocupado • R$ {preco_leito:.2f}</span>"
                else: 
                    bg_color, border_cor = "#fffbeb", "#fde68a"
                    status_badge = "<span style='background:#fef3c7; color:#b45309; font-weight:700; font-size:0.78rem; padding:2px 8px; border-radius:4px;'>🟡 Limpeza Pendente</span>"

                bloco_wpp_html = ""
                if tel_hosp_wpp:
                    msg_saudacao = urllib.parse.quote(f"Olá {nome_hospede_txt}! Aqui é da recepção do hostel. Como podemos ajudar?")
                    wpp_url = f"https://wa.me/55{tel_hosp_wpp}?text={msg_saudacao}"
                    bloco_wpp_html = (
                        f"<div style='margin-top:6px;'>"
                        f"<a href='{wpp_url}' target='_blank' style='display:inline-flex; align-items:center; gap:5px; background-color:#25D366; color:white; text-decoration:none; font-size:0.78rem; font-weight:700; padding:4px 10px; border-radius:5px; box-shadow:0 1px 2px rgba(0,0,0,0.1);'>"
                        f"<svg width='14' height='14' viewBox='0 0 24 24' fill='white'><path d='M.057 24l1.687-6.163c-1.041-1.804-1.588-3.849-1.587-5.946.003-6.556 5.338-11.891 11.893-11.891 3.181.001 6.167 1.24 8.413 3.488 2.245 2.248 3.481 5.236 3.48 8.414-.003 6.557-5.338 11.892-11.893 11.892-1.99-.001-3.951-.5-5.688-1.448l-6.305 1.654zm6.597-3.807c1.676.995 3.276 1.591 5.392 1.592 5.448 0 9.886-4.434 9.889-9.885.002-5.462-4.415-9.89-9.881-9.892-5.452 0-9.887 4.434-9.889 9.884-.001 2.225.651 3.891 1.746 5.634l-.999 3.648 3.742-.981zm11.387-5.464c-.074-.124-.272-.198-.57-.347-.297-.149-1.758-.868-2.031-.967-.272-.099-.47-.149-.669.149-.198.297-.768.967-.941 1.165-.173.198-.347.223-.644.074-.297-.149-1.255-.462-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.297-.347.446-.521.151-.172.2-.296.3-.495.099-.198.05-.372-.025-.521-.075-.148-.669-1.611-.916-2.206-.242-.579-.487-.501-.669-.51l-.57-.01c-.198 0-.52.074-.792.372s-1.04 1.016-1.04 2.479 1.065 2.876 1.213 3.074c.149.198 2.095 3.2 5.076 4.487.709.306 1.263.489 1.694.626.712.226 1.36.194 1.872.118.571-.085 1.758-.719 2.006-1.413.248-.695.248-1.29.173-1.414z'/></svg>"
                        f" WhatsApp"
                        f"</a>"
                        f"</div>"
                    )

                card_html = (
                    f"<div style='background-color:{bg_color}; border:1.5px solid {border_cor}; border-radius:10px; padding:12px; margin-bottom:8px; box-shadow:0 1px 3px rgba(0,0,0,0.05);'>"
                    f"<div style='display:flex; justify-content:space-between; align-items:center;'>"
                    f"<b style='font-size:1.05rem; color:#1e293b;'>🛏️ Cama {c_num}</b>"
                    f"<div>{toalha_badge}</div>"
                    f"</div>"
                    f"<div style='font-size:0.75rem; color:#64748b; margin-bottom:4px;'>{c_tipo}</div>"
                    f"<div style='margin-bottom:4px;'>{status_badge}</div>"
                    f"{detalhes_hospede}"
                    f"{bloco_wpp_html}"
                    f"</div>"
                )

                with cols[idx % 4]:
                    st.markdown(sanitizar_html(card_html), unsafe_allow_html=True)

                    if usuario_perfil in ["Administrador", "Recepção"] and c_status == "Ocupado" and reserva_cama:
                        btn_c1, btn_c2 = st.columns(2)
                        with btn_c1:
                            if st.button("🧾 Fechar", key=f"btn_chk_card_{c_id}", use_container_width=True):
                                st.session_state["redirecionar_menu"] = "📋 Check-out & Histórico"
                                st.session_state["destaque_reserva_id"] = reserva_cama["id"]
                                st.rerun()

                        with btn_c2:
                            outras_vagas = [cv for cv in camas_vagas_geral if cv["id"] != c_id]
                            if outras_vagas:
                                with st.popover("🔄 Trocar"):
                                    st.caption(f"Transferir **{nome_hospede_txt}**:")
                                    mapa_vagas = {f"Q.{cv.get('quartos', {}).get('nome', '?')} - C.{cv.get('numero')}": cv["id"] for cv in outras_vagas}
                                    destino_sel = st.selectbox("Novo Leito:", list(mapa_vagas.keys()), key=f"sel_move_{c_id}")
                                    if st.button("Confirmar Transferência", key=f"btn_move_{c_id}", type="primary"):
                                        nova_cama_id = mapa_vagas[destino_sel]
                                        db.supabase.table("reservas").update({"cama_id": nova_cama_id}).eq("id", reserva_cama["id"]).execute()
                                        db.supabase.table("camas").update({"status": "Limpeza Pendente", "toalha_colocada": False}).eq("id", c_id).execute()
                                        db.supabase.table("camas").update({"status": "Ocupado"}).eq("id", nova_cama_id).execute()
                                        db.notificar_sucesso(f"{nome_hospede_txt} transferido com sucesso! Leito anterior enviado para limpeza.")
                                        st.rerun()
                            else:
                                st.caption("Lotado")

                    elif c_status == "Limpeza Pendente":
                        if st.button("🧹 Liberar Leito", key=f"btn_limp_card_{c_id}", use_container_width=True):
                            db.supabase.table("camas").update({"status": "Disponível", "toalha_colocada": True}).eq("id", c_id).execute()
                            db.notificar_sucesso(f"Cama {c_num} liberada!")
                            st.rerun()

        st.markdown("---")
    except Exception as e:
        st.error(f"Erro ao carregar o mapa de ocupação: {e}")


def renderizar_reservas():
    tab_nova, tab_editar = st.tabs(["📅 Lançar Nova Reserva", "✏️ Consultar & Editar Reserva"])

    with tab_nova:
        try:
            res_hosp = db.supabase.table("hospedes").select("id, nome, nacionalidade, cpf, passaporte_rne, documento").execute()
            hospedes = res_hosp.data or []
            camas_disp = db.buscar_camas_com_quartos(status_filtro="Disponível")
            res_empresas = db.supabase.table("empresas").select("*").execute()
            empresas = res_empresas.data or []
            precos_cfg = db.obter_precos_padrao()

            if not hospedes:
                st.warning("Cadastre ao menos um hóspede antes de lançar uma nova reserva.")
                return
            if not camas_disp:
                st.warning("Não há leitos disponíveis para ocupação no momento.")
                return

            st.markdown("#### 1. Identificação, Leito e Canal de Aquisição")
            col_sel1, col_sel2, col_sel3 = st.columns([1.5, 1.8, 1.2])
            
            with col_sel1:
                hosp_labels = ["-- Selecione o Hóspede --"]
                for h in hospedes:
                    doc_exib = h.get('cpf') or h.get('documento') if h.get('nacionalidade') == "Brasileira" else h.get('passaporte_rne') or h.get('documento') or 'Não informado'
                    hosp_labels.append(f"{h['nome']} (Doc: {doc_exib})")
                hospede_escolhido = st.selectbox("Hóspede Responsável:", hosp_labels, key="sel_nova_hosp")

            cama_detalhes_map = {}
            lista_camas = ["-- Selecione a Cama Disponível --"]
            for c in camas_disp:
                q_obj = c.get("quartos", {})
                q_nome = q_obj.get("nome", "?")
                ar_txt = "❄️ Ar" if q_obj.get("ar_condicionado") else "🌀 Vent"
                tipo_l = c.get("tipo_leito") or "Leito"
                preco_leito_padrao = float(c.get("preco_diaria") or q_obj.get("preco_base") or precos_cfg.get("diaria", 80.0))
                
                rotulo_cama = f"Quarto {q_nome} ({ar_txt}) — Cama {c['numero']} [{tipo_l} | R$ {preco_leito_padrao:.2f}]"
                lista_camas.append(rotulo_cama)
                cama_detalhes_map[rotulo_cama] = {
                    "id": c["id"],
                    "preco_sugerido": preco_leito_padrao,
                    "quarto_nome": q_nome,
                    "ar": bool(q_obj.get("ar_condicionado")),
                    "tipo_leito": tipo_l
                }

            with col_sel2:
                cama_escolhida = st.selectbox("Leito Disponível:", lista_camas, key="sel_nova_cama")

            with col_sel3:
                canais_opcoes = ["Balcão (Presencial)", "WhatsApp", "Booking.com", "Airbnb", "Site Próprio", "Indicação / Outro"]
                origem_canal = st.selectbox("Canal de Origem:", canais_opcoes, key="sel_nova_origem")

            preco_sugerido_leito = float(precos_cfg.get("diaria", 80.0))
            if cama_escolhida != "-- Selecione a Cama Disponível --":
                dados_leito_sel = cama_detalhes_map[cama_escolhida]
                preco_sugerido_leito = dados_leito_sel["preco_sugerido"]
                st.caption(f"💡 **Preço deste leito:** R$ {preco_sugerido_leito:.2f} ({'Com Ar' if dados_leito_sel['ar'] else 'Sem Ar'}) — {dados_leito_sel['tipo_leito']}")

            st.markdown("#### 2. Período da Estadia")
            col_p1, col_p2, col_p3 = st.columns(3)
            with col_p1:
                tipo_estadia = st.selectbox("Modalidade:", ["Diária", "Plano Mensal (Longo Prazo)"], key="sel_nova_tipo")
            with col_p2:
                data_inicio = st.date_input("Data de Entrada (Check-in 14:00):", value=datetime.today(), format="DD/MM/YYYY", key="nova_dt_ini")
            with col_p3:
                if tipo_estadia == "Diária":
                    data_fim = st.date_input("Data de Saída (Check-out 11:00):", value=datetime.today() + timedelta(days=1), format="DD/MM/YYYY", key="nova_dt_fim")
                else:
                    dias_longos = st.number_input("Duração em Dias:", min_value=30, max_value=365, value=30, key="nova_dias_longos")
                    data_fim = data_inicio + timedelta(days=int(dias_longos))

            num_noites = max(1, (data_fim - data_inicio).days)

            st.markdown("#### 3. Orçamento Detalhado")
            col_v1, col_v2, col_v3 = st.columns(3)
            with col_v1:
                valor_diaria = st.number_input("Valor da Diária (R$):", min_value=0.0, value=float(preco_sugerido_leito), step=5.0, format="%.2f", key=f"nova_vd_{cama_escolhida}")
            with col_v2:
                st.number_input("Qtd. Noites Calculada:", value=int(num_noites), disabled=True, key=f"nova_noites_{num_noites}")
            with col_v3:
                subtotal_diarias = float(num_noites * valor_diaria)
                st.number_input("Total Diárias (R$):", value=subtotal_diarias, format="%.2f", disabled=True, key=f"nova_sub_diarias_{subtotal_diarias:.2f}")

            st.markdown("##### ☕ Adicionais e Descontos")
            col_ad1, col_ad2, col_ad3 = st.columns(3)
            with col_ad1:
                preco_cafe_un = float(precos_cfg.get("cafe", 25.0))
                qtd_cafes = st.number_input(f"Cafés (R$ {preco_cafe_un:.2f}/un):", min_value=0, value=0, step=1, key="nova_qtd_cafes")
                subtotal_cafes = qtd_cafes * preco_cafe_un
            with col_ad2:
                preco_toalha_un = float(precos_cfg.get("toalha", 10.0))
                qtd_toalhas = st.number_input(f"Toalhas (R$ {preco_toalha_un:.2f}/un):", min_value=0, value=0, step=1, key="nova_qtd_toalhas")
                subtotal_toalhas = qtd_toalhas * preco_toalha_un
            with col_ad3:
                desconto = st.number_input("Desconto (R$):", min_value=0.0, value=0.0, step=5.0, format="%.2f", key="nova_desconto")

            total_bruto = subtotal_diarias + subtotal_cafes + subtotal_toalhas
            total_liquido = max(0.0, total_bruto - desconto)

            st.markdown("#### 4. Acerto no Check-in (Entrada / Sinal)")
            c_pag1, c_pag2, c_pag3 = st.columns([1.6, 1.2, 1.2])
            with c_pag1:
                tipo_adiantamento = st.radio("Condição no Check-in:", ["Sem adiantamento (pagar tudo no check-out)", "Pagar 50% agora (Sinal)", "Quitar 100% no Check-in", "Digitar outro valor parcial"], key="nova_tipo_adiantamento")

            with c_pag2:
                if tipo_adiantamento == "Sem adiantamento (pagar tudo no check-out)":
                    valor_pago_checkin = st.number_input("Valor Pago no Check-in (R$):", value=0.0, format="%.2f", disabled=True, key=f"adin_0_{total_liquido:.2f}")
                elif tipo_adiantamento == "Pagar 50% agora (Sinal)":
                    valor_pago_checkin = st.number_input("Valor Pago no Check-in (50% - R$):", value=float(round(total_liquido * 0.5, 2)), format="%.2f", disabled=True, key=f"adin_50_{total_liquido:.2f}")
                elif tipo_adiantamento == "Quitar 100% no Check-in":
                    valor_pago_checkin = st.number_input("Valor Pago no Check-in (100% - R$):", value=float(total_liquido), format="%.2f", disabled=True, key=f"adin_100_{total_liquido:.2f}")
                else:
                    valor_pago_checkin = st.number_input("Digite o Valor na Entrada (R$):", min_value=0.0, max_value=float(max(0.0, total_liquido)), value=0.0, step=10.0, format="%.2f", key="nova_adin_custom")

            forma_pag_checkin = "Não aplicável"
            with c_pag3:
                if valor_pago_checkin > 0:
                    forma_pag_checkin = st.selectbox("Forma de Pagamento:", ["PIX", "Dinheiro em Espécie", "Cartão de Crédito", "Cartão de Débito"], key="nova_forma_pag_adin")
                else:
                    st.info("Nenhuma entrada cobrada.")

            saldo_restante_estadia = max(0.0, total_liquido - valor_pago_checkin)

            st.markdown(
                f"""
                <div style='background-color:#f8fafc; border:2px solid #cbd5e1; border-radius:8px; padding:14px; margin-top:8px;'>
                    <div style='font-size:0.98rem; color:#1e293b;'>
                        • <b>Canal:</b> {origem_canal} &nbsp;|&nbsp;
                        <b>Diárias:</b> R$ {subtotal_diarias:.2f} &nbsp;|&nbsp;
                        <b>Cafés:</b> R$ {subtotal_cafes:.2f} &nbsp;|&nbsp;
                        <b>Toalhas:</b> R$ {subtotal_toalhas:.2f} &nbsp;|&nbsp;
                        <b>Desconto:</b> -R$ {desconto:.2f}<br>
                        • <b>Valor Total Contratado:</b> <b>R$ {total_liquido:.2f}</b><br>
                        • <b>(-) Pago no Check-in:</b> <span style='color:#15803d; font-weight:bold;'>R$ {valor_pago_checkin:.2f}</span> ({forma_pag_checkin})
                    </div>
                    <div style='font-size:1.3rem; font-weight:800; color:{'#15803d' if saldo_restante_estadia == 0 else '#b91c1c'}; margin-top:8px;'>
                        (=) Saldo Restante a Cobrar no Check-out: R$ {saldo_restante_estadia:.2f}
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

            st.markdown("#### 5. Faturamento Corporativo (B2B)")
            faturar_empresa = st.checkbox("Esta estadia será faturada para uma Empresa parceira", key="nova_chk_fat_emp")
            empresa_id = None
            if faturar_empresa:
                if not empresas:
                    st.warning("Nenhuma empresa cadastrada no sistema.")
                else:
                    emp_labels = ["-- Selecione a Empresa --"] + [f"{e['razao_social']} (CNPJ: {e['cnpj']})" for e in empresas]
                    emp_sel = st.selectbox("Empresa Pagadora:", emp_labels, key="nova_sel_emp")
                    if emp_sel != "-- Selecione a Empresa --":
                        empresa_id = empresas[emp_labels.index(emp_sel) - 1]["id"]

            st.markdown("---")
            if st.button("🏁 Confirmar e Efetivar Reserva", type="primary", use_container_width=True, key="btn_confirmar_nova_res"):
                if hospede_escolhido == "-- Selecione o Hóspede --":
                    st.error("Selecione um hóspede válido.")
                elif cama_escolhida == "-- Selecione a Cama Disponível --":
                    st.error("Selecione um leito disponível.")
                elif data_fim <= data_inicio:
                    st.error("A data de saída deve ser posterior à data de entrada.")
                elif faturar_empresa and not empresa_id:
                    st.error("Selecione a empresa pagadora.")
                else:
                    hospede_id = hospedes[hosp_labels.index(hospede_escolhido) - 1]["id"]
                    cama_id = cama_detalhes_map[cama_escolhida]["id"]

                    dt_inicio_completa = datetime.combine(data_inicio, datetime.strptime("14:00", "%H:%M").time()).isoformat()
                    dt_fim_completa = datetime.combine(data_fim, datetime.strptime("11:00", "%H:%M").time()).isoformat()
                    codigo_localizador = f"HST-{uuid.uuid4().hex[:6].upper()}"

                    dados_reserva = {
                        "hospede_id": hospede_id, "cama_id": cama_id, "empresa_id": empresa_id,
                        "codigo_localizador": codigo_localizador, "origem_canal": origem_canal,
                        "tipo_estadia": tipo_estadia, "data_inicio": dt_inicio_completa,
                        "data_fim": dt_fim_completa, "cafe_manha": (qtd_cafes > 0),
                        "toalhas": (qtd_toalhas > 0), "valor_total": total_liquido,
                        "faturar_empresa": faturar_empresa, "status": "Ativa"
                    }

                    res_ins = db.supabase.table("reservas").insert(dados_reserva).execute()
                    if res_ins.data:
                        reserva_id = res_ins.data[0]["id"]
                        detalhes_dict = {
                            "codigo_localizador": codigo_localizador, "origem_canal": origem_canal,
                            "noites": num_noites, "valor_diaria": valor_diaria, "subtotal_diarias": subtotal_diarias,
                            "qtd_cafes": qtd_cafes, "preco_cafe": preco_cafe_un, "subtotal_cafes": subtotal_cafes,
                            "qtd_toalhas": qtd_toalhas, "preco_toalha": preco_toalha_un, "subtotal_toalhas": subtotal_toalhas,
                            "desconto": desconto, "total": total_liquido,
                            "adiantamento": valor_pago_checkin, "forma_adiantamento": forma_pag_checkin,
                            "saldo_restante": saldo_restante_estadia, "estorno_credito": 0.0
                        }
                        db.supabase.table("configuracoes").upsert({
                            "chave": f"reserva_det_{reserva_id}", "valor": json.dumps(detalhes_dict)
                        }).execute()

                    db.supabase.table("camas").update({"status": "Ocupado", "toalha_colocada": (qtd_toalhas > 0)}).eq("id", cama_id).execute()
                    db.notificar_sucesso(f"Reserva confirmada! Localizador: {codigo_localizador}")
                    st.rerun()

        except Exception as e:
            st.error(f"Erro ao processar nova reserva: {e}")

    with tab_editar:
        st.subheader("🔍 Localizar e Editar Reserva Ativa")
        st.caption("Altere leitos, datas, adicionais e realize o reequilíbrio financeiro.")

        try:
            reservas_ativas = db.buscar_reservas_completas(status_filtro="Ativa", incluir_foto=False)
            if not reservas_ativas:
                st.info("Nenhuma reserva ativa no momento para edição.")
            else:
                filtro_busca = st.text_input("Filtrar por Hóspede, Quarto, Cama ou Código Localizador:", placeholder="Ex: HST-A1B2 ou João").strip().lower()

                reservas_filtradas = []
                for r in reservas_ativas:
                    h_nome = r["hospedes"]["nome"].lower() if r.get("hospedes") else ""
                    q_nome = str(r.get("camas", {}).get("quartos", {}).get("nome", "")).lower() if r.get("camas") and r["camas"].get("quartos") else ""
                    c_num = str(r.get("camas", {}).get("numero", "")).lower() if r.get("camas") else ""
                    c_loc = str(r.get("codigo_localizador") or "").lower()

                    if (not filtro_busca) or (filtro_busca in h_nome) or (filtro_busca in q_nome) or (filtro_busca in c_num) or (filtro_busca in c_loc):
                        reservas_filtradas.append(r)

                if not reservas_filtradas:
                    st.warning("Nenhuma reserva encontrada.")
                else:
                    opcoes_edit = {}
                    for rf in reservas_filtradas:
                        loc = rf.get("codigo_localizador") or f"ID-{rf['id']}"
                        h_n = rf["hospedes"]["nome"] if rf.get("hospedes") else "Desconhecido"
                        q_n = rf["camas"]["quartos"]["nome"] if rf.get("camas") and rf["camas"].get("quartos") else "?"
                        c_n = rf["camas"]["numero"] if rf.get("camas") else "?"
                        canal = rf.get("origem_canal", "Balcão")
                        rotulo = f"[{loc}] {h_n} — Quarto {q_n}, Cama {c_n} ({canal})"
                        opcoes_edit[rotulo] = rf

                    reserva_sel_rotulo = st.selectbox("Selecione a Reserva:", list(opcoes_edit.keys()), key="sel_reserva_edit")
                    res_edit = opcoes_edit[reserva_sel_rotulo]
                    r_id = res_edit["id"]
                    cama_atual_id = res_edit.get("cama_id")

                    res_det_db = db.supabase.table("configuracoes").select("valor").eq("chave", f"reserva_det_{r_id}").execute()
                    det_orig = json.loads(res_det_db.data[0]["valor"]) if (res_det_db.data and len(res_det_db.data) > 0 and res_det_db.data[0].get("valor")) else {}

                    adiantamento_pago = float(det_orig.get("adiantamento", 0.0))
                    forma_adiantamento = det_orig.get("forma_adiantamento", "Não informado")
                    codigo_loc_atual = res_edit.get("codigo_localizador") or det_orig.get("codigo_localizador") or f"HST-{uuid.uuid4().hex[:6].upper()}"

                    tel_edit_wpp = re.sub(r'\D', '', str(res_edit.get("hospedes", {}).get("telefone", "")))
                    if tel_edit_wpp:
                        msg_edit = urllib.parse.quote(f"Olá {res_edit.get('hospedes', {}).get('nome')}, sobre sua reserva {codigo_loc_atual}:")
                        st.link_button("📲 Chamar Hóspede no WhatsApp", f"https://wa.me/55{tel_edit_wpp}?text={msg_edit}")

                    st.markdown("---")
                    st.markdown(f"#### ✏️ Editando: **{res_edit.get('hospedes', {}).get('nome', 'Hóspede')}** (`{codigo_loc_atual}`)")

                    col_ed1, col_ed2 = st.columns(2)
                    with col_ed1:
                        canais_lista = ["Balcão (Presencial)", "WhatsApp", "Booking.com", "Airbnb", "Site Próprio", "Indicação / Outro"]
                        canal_atual = res_edit.get("origem_canal") or "Balcão (Presencial)"
                        idx_canal = canais_lista.index(canal_atual) if canal_atual in canais_lista else 0
                        novo_canal = st.selectbox("Canal de Origem:", canais_lista, index=idx_canal, key=f"edit_canal_{r_id}")

                    with col_ed2:
                        camas_vagas = db.buscar_camas_com_quartos(status_filtro="Disponível")
                        opcoes_camas_edit = {}
                        
                        cama_obj_atual = res_edit.get("camas")
                        if cama_obj_atual:
                            q_atual_nome = cama_obj_atual.get("quartos", {}).get("nome", "?")
                            rot_atual = f"(Atual) Quarto {q_atual_nome} — Cama {cama_obj_atual.get('numero')}"
                            opcoes_camas_edit[rot_atual] = cama_atual_id

                        for cv in camas_vagas:
                            if cv["id"] != cama_atual_id:
                                q_v_nome = cv.get("quartos", {}).get("nome", "?")
                                p_v = float(cv.get("preco_diaria") or cv.get("quartos", {}).get("preco_base") or 80.0)
                                opcoes_camas_edit[f"Quarto {q_v_nome} — Cama {cv.get('numero')} (R$ {p_v:.2f})"] = cv["id"]

                        nova_cama_sel = st.selectbox("Acomodação / Leito:", list(opcoes_camas_edit.keys()), key=f"edit_cama_{r_id}")
                        nova_cama_id = opcoes_camas_edit[nova_cama_sel]

                    st.markdown("##### 📅 Datas da Estadia")
                    col_dt1, col_dt2 = st.columns(2)
                    dt_ini_orig = extrair_data(res_edit.get("data_inicio")) or datetime.today().date()
                    dt_fim_orig = extrair_data(res_edit.get("data_fim")) or (datetime.today().date() + timedelta(days=1))

                    with col_dt1:
                        nova_dt_ini = st.date_input("Data de Entrada:", value=dt_ini_orig, format="DD/MM/YYYY", key=f"edit_ini_{r_id}")
                    with col_dt2:
                        nova_dt_fim = st.date_input("Data de Saída:", value=dt_fim_orig, format="DD/MM/YYYY", key=f"edit_fim_{r_id}")

                    novas_noites = max(1, (nova_dt_fim - nova_dt_ini).days)

                    st.markdown("##### 💵 Valores, Adicionais e Descontos")
                    col_ev1, col_ev2, col_ev3, col_ev4 = st.columns(4)
                    
                    val_diaria_padrao = float(det_orig.get("valor_diaria") or (float(res_edit.get("valor_total") or 80.0) / max(1, novas_noites)))
                    with col_ev1:
                        novo_val_diaria = st.number_input("Valor Diária (R$):", min_value=0.0, value=val_diaria_padrao, step=5.0, format="%.2f", key=f"edit_vd_{r_id}")
                    with col_ev2:
                        qtd_cafes_orig = int(det_orig.get("qtd_cafes", 0)) if det_orig else (1 if res_edit.get("cafe_manha") else 0)
                        novo_qtd_cafes = st.number_input("Qtd. Cafés:", min_value=0, value=qtd_cafes_orig, step=1, key=f"edit_caf_{r_id}")
                    with col_ev3:
                        qtd_toalhas_orig = int(det_orig.get("qtd_toalhas", 0)) if det_orig else (1 if res_edit.get("toalhas") else 0)
                        novo_qtd_toalhas = st.number_input("Qtd. Toalhas:", min_value=0, value=qtd_toalhas_orig, step=1, key=f"edit_toa_{r_id}")
                    with col_ev4:
                        desc_orig = float(det_orig.get("desconto", 0.0))
                        novo_desconto = st.number_input("Desconto (R$):", min_value=0.0, value=desc_orig, step=5.0, format="%.2f", key=f"edit_desc_{r_id}")

                    precos_cfg = db.obter_precos_padrao()
                    preco_cafe_un = float(det_orig.get("preco_cafe", precos_cfg.get("cafe", 25.0)))
                    preco_toalha_un = float(det_orig.get("preco_toalha", precos_cfg.get("toalha", 10.0)))

                    novo_subtotal_diarias = novas_noites * novo_val_diaria
                    novo_subtotal_cafes = novo_qtd_cafes * preco_cafe_un
                    novo_subtotal_toalhas = novo_qtd_toalhas * preco_toalha_un
                    novo_total_bruto = novo_subtotal_diarias + novo_subtotal_cafes + novo_subtotal_toalhas
                    novo_total_liquido = max(0.0, novo_total_bruto - novo_desconto)

                    st.markdown("##### ⚖️ Balanço Financeiro Reajustado")
                    col_b1, col_b2, col_b3 = st.columns(3)
                    col_b1.metric("Novo Total da Estadia", f"R$ {novo_total_liquido:.2f}")
                    col_b2.metric("Valor Pago no Check-in", f"R$ {adiantamento_pago:.2f}")

                    estorno_devolver = 0.0
                    saldo_restante_novo = 0.0

                    if novo_total_liquido >= adiantamento_pago:
                        saldo_restante_novo = novo_total_liquido - adiantamento_pago
                        col_b3.metric("Saldo Restante na Saída", f"R$ {saldo_restante_novo:.2f}")
                    else:
                        estorno_devolver = adiantamento_pago - novo_total_liquido
                        col_b3.metric("Crédito / Estorno", f"R$ {estorno_devolver:.2f}", delta="- Devolver", delta_color="inverse")
                        st.warning(f"⚠️ Estadia reduzida: O hostel deve estornar ou creditar **R$ {estorno_devolver:.2f}** ao hóspede.")

                    st.markdown("---")
                    if st.button("💾 Salvar Alterações da Reserva", type="primary", use_container_width=True, key=f"btn_salvar_edit_{r_id}"):
                        if nova_dt_fim <= nova_dt_ini:
                            st.error("A data de saída deve ser posterior à data de entrada.")
                        else:
                            if nova_cama_id != cama_atual_id:
                                db.supabase.table("camas").update({"status": "Limpeza Pendente", "toalha_colocada": False}).eq("id", cama_atual_id).execute()
                                db.supabase.table("camas").update({"status": "Ocupado", "toalha_colocada": (novo_qtd_toalhas > 0)}).eq("id", nova_cama_id).execute()

                            dt_ini_iso = datetime.combine(nova_dt_ini, datetime.strptime("14:00", "%H:%M").time()).isoformat()
                            dt_fim_iso = datetime.combine(nova_dt_fim, datetime.strptime("11:00", "%H:%M").time()).isoformat()

                            db.supabase.table("reservas").update({
                                "cama_id": nova_cama_id,
                                "origem_canal": novo_canal,
                                "codigo_localizador": codigo_loc_atual,
                                "data_inicio": dt_ini_iso,
                                "data_fim": dt_fim_iso,
                                "cafe_manha": (novo_qtd_cafes > 0),
                                "toalhas": (novo_qtd_toalhas > 0),
                                "valor_total": novo_total_liquido
                            }).eq("id", r_id).execute()

                            det_atualizado = {
                                "codigo_localizador": codigo_loc_atual,
                                "origem_canal": novo_canal,
                                "noites": novas_noites,
                                "valor_diaria": novo_val_diaria,
                                "subtotal_diarias": novo_subtotal_diarias,
                                "qtd_cafes": novo_qtd_cafes,
                                "preco_cafe": preco_cafe_un,
                                "subtotal_cafes": novo_subtotal_cafes,
                                "qtd_toalhas": novo_qtd_toalhas,
                                "preco_toalha": preco_toalha_un,
                                "subtotal_toalhas": novo_subtotal_toalhas,
                                "desconto": novo_desconto,
                                "total": novo_total_liquido,
                                "adiantamento": adiantamento_pago,
                                "forma_adiantamento": forma_adiantamento,
                                "saldo_restante": saldo_restante_novo,
                                "estorno_credito": estorno_devolver
                            }
                            db.supabase.table("configuracoes").upsert({
                                "chave": f"reserva_det_{r_id}",
                                "valor": json.dumps(det_atualizado)
                            }).execute()

                            db.notificar_sucesso(f"Reserva {codigo_loc_atual} atualizada com sucesso!")
                            st.rerun()

        except Exception as e:
            st.error(f"Erro ao carregar edição: {e}")


def renderizar_checkout():
    try:
        reservas_ativas = db.buscar_reservas_completas(status_filtro="Ativa", incluir_foto=False)
        st.subheader("🟢 Reservas Ativas — Fechamento de Conta & Check-out")
        
        if not reservas_ativas:
            st.info("Não há reservas ativas no hostel no momento.")
        else:
            hoje = datetime.today().date()
            reserva_focada = st.session_state.pop("destaque_reserva_id", None)

            for r in reservas_ativas:
                r_id = r["id"]
                h_id = r.get("hospede_id")
                h_nome = r["hospedes"]["nome"] if r.get("hospedes") else "Desconhecido"
                h_tel = r["hospedes"]["telefone"] if r.get("hospedes") else ""
                c_num = r["camas"]["numero"] if r.get("camas") else "?"
                q_nome = r["camas"]["quartos"]["nome"] if r.get("camas") and r["camas"].get("quartos") else "?"
                cama_id = r["camas"]["id"] if r.get("camas") else None
                d_ini = formatar_data_br(r.get("data_inicio"))
                d_fim = formatar_data_br(r.get("data_fim"))
                dt_fim = extrair_data(r.get("data_fim"))
                checkout_hoje = (dt_fim == hoje)
                deve_expandir = (reserva_focada == r_id)

                cod_loc = r.get("codigo_localizador", "S/CÓD")
                canal = r.get("origem_canal", "Balcão")

                nome_empresa = r.get("empresas", {}).get("razao_social") if r.get("empresas") else None
                empresa_tag = f" (Faturado para: {nome_empresa})" if r.get('faturar_empresa') and nome_empresa else ""

                vendas_pendentes = db.buscar_vendas_completas(hospede_id_filtro=h_id, apenas_pendentes=True)
                eventos_pendentes = db.buscar_participantes_eventos_completos(hospede_id_filtro=h_id, apenas_pendentes=True)

                subtotal_hospedagem = float(r.get("valor_total") or 0.0)
                subtotal_pdv = sum(float(v.get("valor_total") or 0.0) for v in vendas_pendentes)
                subtotal_eventos = sum(float(ep.get("eventos", {}).get("valor_participacao") or 0.0) for ep in eventos_pendentes if ep.get("eventos"))

                res_det = db.supabase.table("configuracoes").select("valor").eq("chave", f"reserva_det_{r_id}").execute()
                detalhes_res = json.loads(res_det.data[0]["valor"]) if (res_det.data and len(res_det.data) > 0 and res_det.data[0].get("valor")) else None

                adiantamento = float(detalhes_res.get("adiantamento", 0.0)) if detalhes_res else 0.0
                forma_adiantamento = detalhes_res.get("forma_adiantamento", "") if detalhes_res else ""
                estorno_credito = float(detalhes_res.get("estorno_credito", 0.0)) if detalhes_res else 0.0
                
                saldo_estadia_pendente = max(0.0, subtotal_hospedagem - adiantamento)
                total_inicial_estada = saldo_estadia_pendente + subtotal_pdv + subtotal_eventos - estorno_credito
                tem_pendencias_extras = (len(vendas_pendentes) > 0 or len(eventos_pendentes) > 0)

                badge_saida = " <span style='background-color:#ffe8cc; color:#d9480f; padding:2px 8px; border-radius:4px; font-weight:bold;'>⏰ Check-out Hoje (11:00)</span>" if checkout_hoje else ""
                badge_pendencia = " <span style='background-color:#fff3cd; color:#856404; padding:2px 8px; border-radius:4px;'>🛒 Consumo Pendente</span>" if tem_pendencias_extras else ""
                badge_adiant = f" <span style='background-color:#dcfce7; color:#166534; padding:2px 8px; border-radius:4px;'>💵 Entrada: R$ {adiantamento:.2f}</span>" if adiantamento > 0 else ""

                st.markdown(
                    f"""
                    <div style="border:1px solid #dee2e6; border-radius:8px; padding:14px; margin-bottom:10px; background-color:#f8f9fa;">
                        <h4 style="margin:0 0 6px 0;">👤 {h_nome} &nbsp;<small style='color:#475569;'>[Localizador: <b>{cod_loc}</b> | {canal}]</small> {badge_saida} {badge_adiant} {badge_pendencia}</h4>
                        <div style="font-size:0.95rem; color:#495057;">
                            <b>Quarto:</b> {q_nome} | <b>Cama:</b> {c_num} | <b>Período:</b> {d_ini} até {d_fim} {empresa_tag}<br>
                            <b>Total Estadia:</b> R$ {subtotal_hospedagem:.2f} | <b>Pago no Check-in:</b> - R$ {adiantamento:.2f} | <b>PDV:</b> R$ {subtotal_pdv:.2f} | <b>Eventos:</b> R$ {subtotal_eventos:.2f} | <b style="color:#2b8a3e; font-size:1.05rem;">Saldo a Pagar: R$ {max(0.0, total_inicial_estada):.2f}</b>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

                with st.expander(f"🧾 Fechamento de Conta & Pagamento: {h_nome} (Cama {c_num})", expanded=deve_expandir):
                    if deve_expandir:
                        st.info("📍 Acesso rápido acionado: leito selecionado automaticamente para fechamento.")

                    col_extrato, col_pagamento = st.columns([1, 1])

                    with col_extrato:
                        st.markdown("##### 📋 Extrato Discriminado")
                        if detalhes_res:
                            st.write(f"🏨 **Diárias ({detalhes_res.get('origem_canal', 'Balcão')}):** {detalhes_res.get('noites', 1)} noite(s) × R$ {detalhes_res.get('valor_diaria', 0.0):.2f} = **R$ {detalhes_res.get('subtotal_diarias', 0.0):.2f}**")
                            if detalhes_res.get("qtd_cafes", 0) > 0:
                                st.write(f"☕ **Café da Manhã:** {detalhes_res['qtd_cafes']} un × R$ {detalhes_res['preco_cafe']:.2f} = **R$ {detalhes_res['subtotal_cafes']:.2f}**")
                            if detalhes_res.get("qtd_toalhas", 0) > 0:
                                st.write(f"🧺 **Kits de Toalha:** {detalhes_res['qtd_toalhas']} un × R$ {detalhes_res['preco_toalha']:.2f} = **R$ {detalhes_res['subtotal_toalhas']:.2f}**")
                            if detalhes_res.get("desconto", 0) > 0:
                                st.write(f"🏷️ **Desconto Concedido:** - R$ {detalhes_res['desconto']:.2f}")
                            st.write(f"**Total Contratado da Estadia:** R$ {subtotal_hospedagem:.2f}")
                            if adiantamento > 0:
                                st.write(f"🟢 **(-) Valor Pago no Check-in:** R$ {adiantamento:.2f} ({forma_adiantamento})")
                            if estorno_credito > 0:
                                st.write(f"🔴 **Crédito/Estorno devido ao hóspede:** R$ {estorno_credito:.2f}")
                            st.write(f"➡️ **Saldo Restante da Estadia:** R$ {saldo_estadia_pendente:.2f}")
                        else:
                            st.write(f"🏨 **Total da Estadia:** R$ {subtotal_hospedagem:.2f}")

                        if vendas_pendentes:
                            st.write("🛒 **Consumo na Conveniência (PDV):**")
                            for vp in vendas_pendentes:
                                nome_prod = vp["produtos"]["nome"] if vp.get("produtos") else "Item da Loja"
                                qtd_v = vp.get("quantidade", 1)
                                tot_v = float(vp.get("valor_total") or 0.0)
                                st.write(f"  * {qtd_v}x {nome_prod} — R$ {tot_v:.2f}")
                        else:
                            st.write("🛒 **Consumo na Conveniência:** Nenhum item pendente.")

                        if eventos_pendentes:
                            st.write("🎉 **Inscrições em Eventos:**")
                            for ep in eventos_pendentes:
                                nome_ev = ep["eventos"]["nome"] if ep.get("eventos") else "Evento"
                                val_ev = float(ep["eventos"].get("valor_participacao") or 0.0) if ep.get("eventos") else 0.0
                                st.write(f"  * {nome_ev} — R$ {val_ev:.2f}")
                        else:
                            st.write("🎉 **Eventos:** Nenhuma taxa pendente.")

                        st.markdown("---")
                        st.markdown("##### ➕ Ajustes de Saída")
                        col_adj1, col_adj2 = st.columns(2)
                        val_extra = col_adj1.number_input("Acréscimos / Multas (R$)", min_value=0.0, format="%.2f", key=f"extra_{r_id}")
                        val_desc = col_adj2.number_input("Desconto de Saída (R$)", min_value=0.0, format="%.2f", key=f"desc_{r_id}")

                        total_final_devido = max(0.0, total_inicial_estada + val_extra - val_desc)
                        st.markdown(
                            f"""
                            <div style="background-color:#e7f5ff; border:1px solid #a5d8ff; padding:10px; border-radius:6px; margin-top:10px;">
                                <span style="font-size:1.15rem; color:#1864ab; font-weight:bold;">Total Final a Pagar na Saída: R$ {total_final_devido:.2f}</span>
                            </div>
                            """,
                            unsafe_allow_html=True
                        )

                    with col_pagamento:
                        st.markdown("##### 💳 Quitação da Conta")
                        faturar_empresa_marcado = r.get("faturar_empresa", False)
                        is_b2b = False
                        if faturar_empresa_marcado and nome_empresa:
                            is_b2b = st.checkbox(f"Faturar saldo integral para a empresa ({nome_empresa})", value=True, key=f"fat_check_{r_id}")

                        if not is_b2b:
                            if total_final_devido <= 0.01:
                                st.success("✅ **Conta 100% quitada!** O hóspede não possui saldo pendente.")
                                total_pago = 0.0
                            else:
                                st.caption("Distribua o saldo restante entre os métodos de pagamento:")
                                cp1, cp2 = st.columns(2)
                                p_pix = cp1.number_input("PIX (R$)", min_value=0.0, format="%.2f", key=f"pix_{r_id}")
                                p_din = cp2.number_input("Dinheiro em Espécie (R$)", min_value=0.0, format="%.2f", key=f"din_{r_id}")
                                cp3, cp4 = st.columns(2)
                                p_cred = cp3.number_input("Cartão de Crédito (R$)", min_value=0.0, format="%.2f", key=f"cred_{r_id}")
                                p_deb = cp4.number_input("Cartão de Débito (R$)", min_value=0.0, format="%.2f", key=f"deb_{r_id}")

                                total_pago = p_pix + p_din + p_cred + p_deb
                                saldo_diferenca = total_pago - total_final_devido
                                st.write(f"**Total Informado Agora:** R$ {total_pago:.2f}")

                                if total_final_devido > 0:
                                    if saldo_diferenca < -0.01:
                                        st.warning(f"⚠️ Falta Receber: R$ {abs(saldo_diferenca):.2f}")
                                    elif saldo_diferenca > 0.01 and p_din > 0:
                                        st.info(f"💵 Troco para o hóspede: R$ {saldo_diferenca:.2f}")
                                    else:
                                        st.success("✅ Valor exato!")
                        else:
                            total_pago = total_final_devido
                            st.info(f"O saldo de R$ {total_final_devido:.2f} será lançado no faturamento corporativo de **{nome_empresa}**.")

                        st.markdown("---")
                        if st.button("🏁 Concluir Check-out e Quitar Conta", key=f"btn_chk_{r_id}", use_container_width=True):
                            if not is_b2b and total_final_devido > 0.01 and total_pago < (total_final_devido - 0.01):
                                st.error(f"O total informado (R$ {total_pago:.2f}) não cobre o saldo pendente (R$ {total_final_devido:.2f}).")
                            else:
                                for v in vendas_pendentes:
                                    db.supabase.table("vendas").update({"status_pagamento": "Pago"}).eq("id", v["id"]).execute()
                                for ep in eventos_pendentes:
                                    db.supabase.table("eventos_participantes").update({"status_pagamento": "Pago"}).eq("id", ep["id"]).execute()

                                db.supabase.table("reservas").update({"status": "Concluída"}).eq("id", r_id).execute()
                                if cama_id:
                                    db.supabase.table("camas").update({"status": "Limpeza Pendente", "toalha_colocada": False}).eq("id", cama_id).execute()

                                db.notificar_sucesso(f"Check-out de {h_nome} concluído com sucesso!")
                                st.rerun()

                st.markdown("---")

        st.subheader("📚 Histórico Geral de Reservas Concluídas")
        todas_reservas = db.buscar_reservas_completas(incluir_foto=False, ordem_desc=True)

        if todas_reservas:
            dados_tabela = []
            for tr in todas_reservas:
                empresa_hist = tr.get("empresas", {}).get("razao_social") if tr.get("empresas") else "Próprio Hóspede"
                if not tr.get("faturar_empresa"):
                    empresa_hist = "Próprio Hóspede"
                    
                dados_tabela.append({
                    "ID": tr.get("id"),
                    "Localizador": tr.get("codigo_localizador", "S/CÓD"),
                    "Origem": tr.get("origem_canal", "Balcão"),
                    "Hóspede": tr["hospedes"]["nome"] if tr.get("hospedes") else "",
                    "Telefone": tr["hospedes"]["telefone"] if tr.get("hospedes") else "",
                    "Quarto": tr["camas"]["quartos"]["nome"] if tr.get("camas") and tr["camas"].get("quartos") else "",
                    "Cama": tr["camas"]["numero"] if tr.get("camas") else "",
                    "Entrada": formatar_data_br(tr.get("data_inicio")),
                    "Saída": formatar_data_br(tr.get("data_fim")),
                    "Responsável Financeiro": empresa_hist,
                    "Valor Total (R$)": tr.get("valor_total"),
                    "Situação": tr.get("status")
                })
            
            col_exp_h1, col_exp_h2, col_exp_h3 = st.columns([2, 1, 1])
            with col_exp_h1:
                st.caption(f"📋 Total de registros: **{len(dados_tabela)} estadia(s)**")
            with col_exp_h2:
                df_res_exp = pd.DataFrame(dados_tabela).drop(columns=["ID", "Telefone"], errors="ignore")
                st.download_button(
                    label="📥 Baixar Histórico (CSV)",
                    data=gerar_csv(df_res_exp),
                    file_name="historico_reservas.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            with col_exp_h3:
                cols_pdf_res = ["Localizador", "Hóspede", "Quarto", "Cama", "Entrada", "Saída", "Origem", "Valor Total (R$)", "Situação"]
                pdf_res_bytes = gerar_pdf_tabela("Histórico Geral de Reservas", cols_pdf_res, dados_tabela, orientacao="L")
                st.download_button(
                    label="📕 Baixar Histórico (PDF)",
                    data=pdf_res_bytes,
                    file_name="historico_reservas.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )

            df_hist = pd.DataFrame(dados_tabela)
            st.dataframe(df_hist.drop(columns=["ID", "Telefone"]), use_container_width=True)

            with st.expander("🧾 Emitir / Visualizar Recibo de Check-out Finalizado"):
                opcoes_res_rec = {f"[{d['Localizador']}] Hóspede: {d['Hóspede']} | Quarto {d['Quarto']} Cama {d['Cama']}": d for d in dados_tabela}
                sel_rec = st.selectbox("Selecione a Estadia:", list(opcoes_res_rec.keys()))
                d_rec = opcoes_res_rec[sel_rec]

                res_rec_det = db.supabase.table("configuracoes").select("valor").eq("chave", f"reserva_det_{d_rec['ID']}").execute()
                det_rec = json.loads(res_rec_det.data[0]["valor"]) if (res_rec_det.data and len(res_rec_det.data) > 0 and res_rec_det.data[0].get("valor")) else None

                itens_recibo_txt = ""
                if det_rec:
                    itens_recibo_txt = (
                        f"Localizador: {det_rec.get('codigo_localizador', d_rec['Localizador'])}\n"
                        f"Canal de Origem: {det_rec.get('origem_canal', d_rec['Origem'])}\n"
                        f"Diárias: {det_rec.get('noites')} noites × R$ {det_rec.get('valor_diaria', 0):.2f} = R$ {det_rec.get('subtotal_diarias', 0):.2f}\n"
                        f"Café da Manhã: {det_rec.get('qtd_cafes', 0)} un = R$ {det_rec.get('subtotal_cafes', 0):.2f}\n"
                        f"Kits de Toalha: {det_rec.get('qtd_toalhas', 0)} un = R$ {det_rec.get('subtotal_toalhas', 0):.2f}\n"
                        f"Desconto Concedido: - R$ {det_rec.get('desconto', 0):.2f}\n"
                        f"--------------------------------------------------\n"
                        f"Entrada Paga no Check-in: R$ {det_rec.get('adiantamento', 0):.2f} ({det_rec.get('forma_adiantamento', 'N/D')})\n"
                    )

                texto_recibo = f"""
==================================================
              🏨 COMPROVANTE DE HOSPEDAGEM
==================================================
Localizador: {d_rec['Localizador']}
Hóspede: {d_rec['Hóspede']}
Acomodação: Quarto {d_rec['Quarto']} — Cama {d_rec['Cama']}
Período: {d_rec['Entrada']} até {d_rec['Saída']}
Canal de Venda: {d_rec['Origem']}
Responsável Financeiro: {d_rec['Responsável Financeiro']}
--------------------------------------------------
{itens_recibo_txt}VALOR TOTAL DA HOSPEDAGEM: R$ {float(d_rec['Valor Total (R$)'] or 0):.2f}
Status: {d_rec['Situação']} e Quitado
Data de Emissão: {datetime.now().strftime('%d/%m/%Y às %H:%M')}
==================================================
Obrigado por se hospedar conosco! Volte sempre!
==================================================
"""
                st.markdown(f"<div class='recibo-card'><pre>{texto_recibo}</pre></div>", unsafe_allow_html=True)
                
                tel_hosp_limpo = re.sub(r'\D', '', str(d_rec.get("Telefone", "")))
                msg_whats = urllib.parse.quote(
                    f"Olá {d_rec['Hóspede']}! Segue o comprovante da sua estadia:\n"
                    f"🔖 Localizador: {d_rec['Localizador']}\n"
                    f"🛏️ Quarto {d_rec['Quarto']}, Cama {d_rec['Cama']}\n"
                    f"📅 Período: {d_rec['Entrada']} até {d_rec['Saída']}\n"
                    f"💰 Total Quitado: R$ {float(d_rec['Valor Total (R$)'] or 0):.2f}\n"
                    f"Agradecemos pela sua visita e esperamos revê-lo(a) em breve!"
                )
                link_whatsapp = f"https://api.whatsapp.com/send?phone=55{tel_hosp_limpo}&text={msg_whats}" if tel_hosp_limpo else None

                col_rec1, col_rec2, col_rec3 = st.columns(3)
                with col_rec1:
                    if link_whatsapp:
                        st.link_button("📲 Enviar WhatsApp", link_whatsapp, use_container_width=True)
                    else:
                        st.caption("Cadastre o telefone para envio WhatsApp.")
                with col_rec2:
                    st.download_button(
                        label="📄 Baixar Texto (.txt)",
                        data=texto_recibo,
                        file_name=f"recibo_hostel_{d_rec['Localizador']}.txt",
                        mime="text/plain",
                        use_container_width=True
                    )
                with col_rec3:
                    pdf_recibo_bytes = gerar_pdf_recibo(
                        hospede=f"{d_rec['Hóspede']} (Cód: {d_rec['Localizador']})",
                        quarto=d_rec['Quarto'],
                        cama=d_rec['Cama'],
                        periodo=f"{d_rec['Entrada']} até {d_rec['Saída']}",
                        responsavel=d_rec['Responsável Financeiro'],
                        total_geral=float(d_rec['Valor Total (R$)'] or 0.0),
                        detalhes_texto=itens_recibo_txt
                    )
                    st.download_button(
                        label="📕 Baixar Recibo Oficial (PDF)",
                        data=pdf_recibo_bytes,
                        file_name=f"recibo_hostel_{d_rec['Localizador']}.pdf",
                        mime="application/pdf",
                        use_container_width=True
                    )
        else:
            st.info("Nenhuma reserva arquivada no histórico.")
    except Exception as e:
        st.error(f"Erro ao processar histórico: {e}")

def renderizar_limpeza():
    try:
        res_colabs = db.supabase.table("colaboradores").select("*").eq("status", "Ativo").execute()
        colaboradores = res_colabs.data or []
        camas_pendentes = db.buscar_camas_com_quartos(status_filtro="Limpeza Pendente")

        if not camas_pendentes:
            st.success("🎉 Todos os leitos estão higienizados e prontos para uso!")
            return

        colab_labels = ["-- Selecione o Responsável pela Higienização --"] + [f"{c['nome']} ({c['cargo']})" for c in colaboradores]
        responsavel_limpeza = st.selectbox("Colaborador Responsável:", colab_labels)
        
        st.write("### 🟡 Quartos e Camas Aguardando Limpeza:")
        quartos_pendentes = {}
        for cama in camas_pendentes:
            q_id = cama.get("quarto_id")
            q_nome = cama["quartos"]["nome"] if cama.get("quartos") else "Desconhecido"
            if q_id not in quartos_pendentes:
                quartos_pendentes[q_id] = {"nome": q_nome, "camas": []}
            quartos_pendentes[q_id]["camas"].append(cama)
            
        for q_id, dados_quarto in quartos_pendentes.items():
            st.markdown(f"#### 🚪 Quarto {dados_quarto['nome']}")
            c_btn_q, c_chk_q = st.columns([3, 2])
            with c_chk_q:
                toalha_quarto_todo = st.checkbox("Equipar todas as camas com toalhas", value=False, key=f"chk_toalha_q_{q_id}")
            with c_btn_q:
                if st.button(f"🧹 Concluir Higienização do Quarto {dados_quarto['nome']}", key=f"limp_q_{q_id}"):
                    if responsavel_limpeza == "-- Selecione o Responsável pela Higienização --" and len(colaboradores) > 0:
                        st.error("Por favor, selecione seu nome acima antes de confirmar.")
                    else:
                        db.supabase.table("camas").update({
                            "status": "Disponível",
                            "toalha_colocada": toalha_quarto_todo
                        }).eq("quarto_id", q_id).eq("status", "Limpeza Pendente").execute()
                        db.notificar_sucesso(f"Quarto {dados_quarto['nome']} completamente liberado!")
                        st.rerun()
            
            for cama in dados_quarto["camas"]:
                c_id = cama["id"]
                c_num = cama["numero"]
                col1, col2, col3 = st.columns([3, 2, 2])
                with col1:
                    st.warning(f"🛏️ Cama {c_num}")
                with col2:
                    colocar_toalha_indiv = st.checkbox("Equipar com toalha", value=False, key=f"toalha_c_{c_id}")
                with col3:
                    if st.button("✅ Concluir Leito", key=f"limp_{c_id}"):
                        if responsavel_limpeza == "-- Selecione o Responsável pela Higienização --" and len(colaboradores) > 0:
                            st.error("Selecione seu nome acima antes de confirmar.")
                        else:
                            db.supabase.table("camas").update({
                                "status": "Disponível",
                                "toalha_colocada": colocar_toalha_indiv
                            }).eq("id", c_id).execute()
                            db.notificar_sucesso(f"Cama {c_num} liberada!")
                            st.rerun()
            st.markdown("---")
    except Exception as e:
        st.error(f"Erro ao carregar o painel de limpeza: {e}")
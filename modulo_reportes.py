import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import datetime
import calendar
from io import BytesIO
import numpy as np

COLOR_ROJO = "#d51b5d"
COLOR_PICTON = "#2bbcee"
COLOR_CETACEAN = "#10004F"
COLOR_BG_LIGHT = "#F2F3F7"
COLOR_WARNING = "#ffb74d"
COLOR_SUCCESS = "#4caf50"
COLOR_CYAN = "#00acc1"
COLOR_PURPLE = "#8e24aa"

def render_tab_reportes(db_manager):
    query = """
        SELECT 
            c.id, c.consecutivo_num, c.estado, c.afectacion,
            c.fecha_creacion, c.fecha_envio, c.escalado,
            c.requiere_aprobacion, c.solucion_aplicada,
            p.nombre AS plataforma,
            tc.nombre AS tipo_comunicado,
            s.nombre AS servicio,
            CONCAT(a.nombre, " ", a.apellido) AS analista,
            (SELECT t.nombre FROM comunicado_destinatario cd 
             JOIN tercero t ON cd.tercero_id = t.id 
             WHERE cd.comunicado_id = c.id LIMIT 1) AS tercero_nombre
        FROM comunicado c
        LEFT JOIN plataforma p ON c.plataforma_id = p.id
        LEFT JOIN tipo_comunicado tc ON c.tipo_comunicado_id = tc.id
        LEFT JOIN servicio s ON c.servicio_id = s.id
        LEFT JOIN analista a ON c.analista_id = a.id
    """
    conn = db_manager.get_conn()
    try:
        df = pd.read_sql(query, conn)
    finally:
        conn.close()

    if df.empty:
        st.info("No hay datos disponibles para generar el informe.")
        return

    # Preprocess
    df["fecha_creacion"] = pd.to_datetime(df["fecha_creacion"])
    df["fecha_envio"] = pd.to_datetime(df["fecha_envio"])
    df["tercero_nombre"] = df["tercero_nombre"].fillna("N/A")
    df["minutos_caida"] = (df["fecha_envio"] - df["fecha_creacion"]).dt.total_seconds() / 60.0
    df["minutos_caida"] = df["minutos_caida"].fillna(0).apply(lambda x: max(x, 0))
    df["escalado"] = df["escalado"].fillna(0).astype(int)
    df["hora_creacion"] = df["fecha_creacion"].dt.hour
    df["dia_semana"] = df["fecha_creacion"].dt.day_name()
    df["dia"] = df["fecha_creacion"].dt.date
    df["semana"] = df["fecha_creacion"].dt.to_period("W").apply(lambda r: r.start_time)
    df["mes"] = df["fecha_creacion"].dt.to_period("M").apply(lambda r: r.start_time)
    df["mes_str"] = df["fecha_creacion"].dt.strftime("%Y-%m")
    df["año_mes"] = df["fecha_creacion"].dt.strftime("%b %Y")
    df["hora_consumida_str"] = df["minutos_caida"].apply(
        lambda x: f"{int(x//60)}h {int(x%60)}m" if x > 0 else "N/A"
    )

    # ========== FILTROS MEJORADOS ==========
    st.markdown(
        f"<h2 style='color:{COLOR_CETACEAN}; margin-bottom:0;'>"
        f"📊 Centro de Analítica e Informes TI</h2>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<p style='color:rgba(16,0,79,0.6); margin-top:0;'>"
        "Métricas operativas, SLA, tendencias y exportación avanzada</p>",
        unsafe_allow_html=True,
    )

    with st.expander("🔍 Filtros Avanzados", expanded=True):
        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1:
            rango = st.date_input(
                "Rango de Fecha",
                [df["fecha_creacion"].min().date(), datetime.date.today()],
                key="rep_fecha",
            )
            servs_list = sorted(df["servicio"].dropna().unique())
            servs_sel = st.multiselect("Servicios", servs_list, placeholder="Todos...")
        with col_f2:
            plats_list = sorted(df["plataforma"].dropna().unique())
            plats_sel = st.multiselect("Plataformas", plats_list, placeholder="Todas...")
            tipos_list = sorted(df["tipo_comunicado"].dropna().unique())
            tipos_sel = st.multiselect("Tipos de Evento", tipos_list, placeholder="Todos...")
        with col_f3:
            analistas_list = sorted(df["analista"].dropna().unique())
            analistas_sel = st.multiselect("Analistas", analistas_list, placeholder="Todos...")
            estados_list = sorted(df["estado"].dropna().unique())
            estados_sel = st.multiselect("Estados", estados_list, placeholder="Todos...")

    # Apply filters
    mask = pd.Series(True, index=df.index)
    if plats_sel: mask &= df["plataforma"].isin(plats_sel)
    if tipos_sel: mask &= df["tipo_comunicado"].isin(tipos_sel)
    if servs_sel: mask &= df["servicio"].isin(servs_sel)
    if analistas_sel: mask &= df["analista"].isin(analistas_sel)
    if estados_sel: mask &= df["estado"].isin(estados_sel)
    if len(rango) == 2:
        mask &= (df["fecha_creacion"].dt.date >= rango[0]) & (df["fecha_creacion"].dt.date <= rango[1])
    df_f = df[mask]
    if df_f.empty:
        st.warning("Sin resultados para los filtros seleccionados.")
        return

    # ========== MÉTRICAS GLOBALES ==========
    total = len(df_f)
    cerrados = len(df_f[df_f["estado"] == "Cerrado"])
    df_cerrados = df_f[df_f["minutos_caida"] > 0]
    mttr = df_cerrados["minutos_caida"].mean() if not df_cerrados.empty else 0
    escalados = int(df_f["escalado"].sum())
    sla_pct = ((total - escalados) / total * 100) if total > 0 else 100
    pct_cierre = (cerrados / total * 100) if total > 0 else 0
    total_minutos = df_f["minutos_caida"].sum()
    dias_periodo = max(1, (df_f["fecha_creacion"].max() - df_f["fecha_creacion"].min()).days)
    mtbf = (dias_periodo * 24) / total if total > 0 else 0
    aprob_pend = len(df_f[df_f["estado"].astype(str).str.contains("Pendiente", case=False, na=False)])

    # Tab navigator
    tabs = st.tabs([
        "📈 Vista Management", "⚙️ KPIs Operación", "👥 KPIs Gestión",
        "📊 Tendencias", "🔥 Mapas de Calor", "⏰ Horario Crítico",
        "📋 Datos Detallados", "📥 Exportación"
    ])

    # ========== TAB 1: MANAGEMENT ==========
    with tabs[0]:
        st.markdown(f"<h3 style='color:{COLOR_CETACEAN};'>Resumen Ejecutivo</h3>", unsafe_allow_html=True)
        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        col_m1.metric("Disponibilidad SLA", f"{sla_pct:.1f}%",
                      help="% de incidentes resueltos dentro del SLA")
        col_m2.metric("Downtime Total", f"{total_minutos:,.0f} min",
                      f"{total_minutos/60:.1f} horas")
        col_m3.metric("MTTR (Media Reparación)", f"{mttr:.1f} min",
                      f"{mttr/60:.1f} horas")
        col_m4.metric("MTBF (Media entre Fallas)", f"{mtbf:.1f} hrs", "Entre incidentes")

        # Gauge de disponibilidad
        col_g1, col_g2 = st.columns([1, 1])
        with col_g1:
            fig_gauge = go.Figure(go.Indicator(
                mode="gauge+number+delta",
                value=sla_pct,
                title={"text": "SLA Global (%)"},
                delta={"reference": 95, "increasing": {"color": COLOR_SUCCESS}},
                gauge={"axis": {"range": [0, 100]},
                       "bar": {"color": COLOR_ROJO},
                       "steps": [
                           {"range": [0, 80], "color": "#ffebee"},
                           {"range": [80, 95], "color": "#fff8e1"},
                           {"range": [95, 100], "color": "#e8f5e9"},
                       ],
                       "threshold": {
                           "line": {"color": COLOR_CETACEAN, "width": 4},
                           "thickness": 0.75, "value": 95
                       }
                }
            ))
            fig_gauge.update_layout(height=250, margin=dict(t=30, b=0, l=0, r=0))
            st.plotly_chart(fig_gauge, use_container_width=True)

        with col_g2:
            # Disponibilidad mensual
            disp_mensual = df_f.groupby("mes_str")["minutos_caida"].sum().reset_index()
            disp_mensual["disponibilidad"] = 100 - ((disp_mensual["minutos_caida"] / 43200) * 100)
            disp_mensual["disponibilidad"] = disp_mensual["disponibilidad"].apply(
                lambda x: max(0, min(100, x)))
            fig_disp = go.Figure()
            fig_disp.add_trace(go.Scatter(
                x=disp_mensual["mes_str"], y=disp_mensual["disponibilidad"],
                mode="lines+markers", line=dict(color=COLOR_SUCCESS, width=3),
                fill="tozeroy", fillcolor=f"rgba(76, 175, 80, 0.15)",
                name="% Disponibilidad"
            ))
            fig_disp.add_hline(y=95, line_dash="dash", line_color=COLOR_CETACEAN,
                              annotation_text="Objetivo 95%")
            fig_disp.update_layout(
                yaxis_title="% Disponibilidad", yaxis=dict(range=[80, 100.5]),
                plot_bgcolor=COLOR_BG_LIGHT, paper_bgcolor="rgba(0,0,0,0)",
                height=250, margin=dict(t=20, b=0, l=0, r=0),
                title="Disponibilidad Global Mensual (%)"
            )
            st.plotly_chart(fig_disp, use_container_width=True)

        # Top fallas por servicio (horizontal)
        st.markdown(f"<h5 style='color:{COLOR_CETACEAN};'>Top Fallas por Servicio</h5>", unsafe_allow_html=True)
        top_fallas = df_f.groupby("servicio")["minutos_caida"].sum().nlargest(10).reset_index()
        fig_top = px.bar(
            top_fallas, x="minutos_caida", y="servicio", orientation="h",
            color="minutos_caida", color_continuous_scale=[COLOR_PICTON, COLOR_ROJO],
            text_auto=".0f"
        )
        fig_top.update_layout(
            xaxis_title="Downtime Total (min)", yaxis_title="",
            yaxis={"categoryorder": "total ascending"},
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            height=350
        )
        st.plotly_chart(fig_top, use_container_width=True)

    # ========== TAB 2: KPIs OPERACIÓN ==========
    with tabs[1]:
        st.markdown(f"<h3 style='color:{COLOR_CETACEAN};'>Métricas de Estabilidad y Resolución</h3>",
                    unsafe_allow_html=True)
        op1, op2, op3, op4 = st.columns(4)
        op1.metric("Total Eventos", total)
        op2.metric("Casos Cerrados", cerrados, f"{pct_cierre:.1f}%")
        op3.metric("Tasa de Cierre", f"{pct_cierre:.1f}%")
        op4.metric("SLA Incumplidos", escalados,
                   delta=f"{-escalados} fuera de SLA" if escalados > 0 else "0",
                   delta_color="inverse" if escalados > 0 else "normal")

        # Treemap de servicios
        st.markdown(f"<h5 style='color:{COLOR_CETACEAN};'>Distribución de Incidentes por Servicio (Treemap)</h5>",
                    unsafe_allow_html=True)
        treemap_data = df_f.groupby(["servicio", "plataforma"]).size().reset_index(name="cantidad")
        fig_tree = px.treemap(
            treemap_data, path=["plataforma", "servicio"], values="cantidad",
            color="cantidad", color_continuous_scale=[COLOR_BG_LIGHT, COLOR_PICTON, COLOR_ROJO],
        )
        fig_tree.update_layout(margin=dict(t=0, b=0, l=0, r=0), height=350)
        st.plotly_chart(fig_tree, use_container_width=True)

        col_o1, col_o2 = st.columns(2)
        with col_o1:
            st.markdown(f"<h5 style='color:{COLOR_CETACEAN};'>Incidentes por Proveedor</h5>",
                        unsafe_allow_html=True)
            prov = df_f["tercero_nombre"].value_counts().reset_index().head(10)
            prov.columns = ["Proveedor", "Incidentes"]
            fig_prov = px.bar(prov, x="Proveedor", y="Incidentes",
                             color_discrete_sequence=[COLOR_PICTON])
            fig_prov.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig_prov, use_container_width=True)

        with col_o2:
            st.markdown(f"<h5 style='color:{COLOR_CETACEAN};'>Incidentes por Tipo</h5>",
                        unsafe_allow_html=True)
            fig_tipo = px.pie(
                df_f, names="tipo_comunicado", hole=0.4,
                color_discrete_sequence=[COLOR_ROJO, COLOR_PICTON, COLOR_CETACEAN, COLOR_WARNING]
            )
            fig_tipo.update_layout(
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                margin=dict(t=0, b=0, l=0, r=0)
            )
            st.plotly_chart(fig_tipo, use_container_width=True)

    # ========== TAB 3: KPIs GESTIÓN ==========
    with tabs[2]:
        st.markdown(f"<h3 style='color:{COLOR_CETACEAN};'>Desempeño del Equipo y Procesos</h3>",
                    unsafe_allow_html=True)
        g1, g2, g3 = st.columns(3)
        g1.metric("Aprobaciones Pendientes", aprob_pend)
        g2.metric("Servicios Afectados", df_f["servicio"].nunique())
        g3.metric("Terceros Involucrados", df_f["tercero_nombre"].nunique())

        col_g1, col_g2 = st.columns(2)
        with col_g1:
            st.markdown(f"<h5 style='color:{COLOR_CETACEAN};'>Productividad por Analista</h5>",
                        unsafe_allow_html=True)
            if not df_cerrados.empty:
                prod = df_cerrados.groupby("analista").agg(
                    Casos=("id", "count"), MTTR=("minutos_caida", "mean")
                ).reset_index()
                fig_prod = px.scatter(
                    prod, x="Casos", y="MTTR", text="analista",
                    size="Casos", color="MTTR",
                    color_continuous_scale=[COLOR_SUCCESS, COLOR_WARNING, COLOR_ROJO]
                )
                fig_prod.update_traces(textposition="top center")
                fig_prod.update_layout(
                    plot_bgcolor=COLOR_BG_LIGHT, paper_bgcolor="rgba(0,0,0,0)",
                    height=350
                )
                st.plotly_chart(fig_prod, use_container_width=True)

        with col_g2:
            st.markdown(f"<h5 style='color:{COLOR_CETACEAN};'>MTTR por Severidad</h5>",
                        unsafe_allow_html=True)
            if not df_cerrados.empty:
                sev = df_cerrados.groupby("afectacion")["minutos_caida"].mean().reset_index()
                fig_sev = px.bar(
                    sev, x="afectacion", y="minutos_caida", text_auto=".1f",
                    color="afectacion",
                    color_discrete_map={
                        "Afecta Disponibilidad": COLOR_ROJO,
                        "Afectación Parcial": COLOR_WARNING,
                        "No Afecta": COLOR_CETACEAN
                    }
                )
                fig_sev.update_layout(
                    showlegend=False, plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)", height=350
                )
                st.plotly_chart(fig_sev, use_container_width=True)

    # ========== TAB 4: TENDENCIAS ==========
    with tabs[3]:
        st.markdown(f"<h3 style='color:{COLOR_CETACEAN};'>Análisis de Tendencias</h3>", unsafe_allow_html=True)
        agrupacion = st.radio("Agrupar por:", ["Día", "Semana", "Mes"], horizontal=True, key="rep_agrup")
        col_temp = {"Día": "dia", "Semana": "semana", "Mes": "mes"}[agrupacion]

        tendencia_vol = df_f.groupby(col_temp).size().reset_index(name="cantidad")
        tendencia_min = df_f.groupby(col_temp)["minutos_caida"].sum().reset_index()

        c_t1, c_t2 = st.columns(2)
        with c_t1:
            st.markdown(f"<h5 style='color:{COLOR_CETACEAN};'>Volumen de Eventos</h5>", unsafe_allow_html=True)
            fig_vol = px.bar(tendencia_vol, x=col_temp, y="cantidad",
                            color_discrete_sequence=[COLOR_CETACEAN])
            fig_vol.update_layout(plot_bgcolor=COLOR_BG_LIGHT, paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig_vol, use_container_width=True)

        with c_t2:
            st.markdown(f"<h5 style='color:{COLOR_CETACEAN};'>Downtime Total por Periodo</h5>",
                        unsafe_allow_html=True)
            fig_line = go.Figure()
            fig_line.add_trace(go.Scatter(
                x=tendencia_min[col_temp], y=tendencia_min["minutos_caida"],
                mode="lines+markers", name="Downtime (min)",
                line=dict(color=COLOR_ROJO, width=3),
                fill="tozeroy", fillcolor=f"rgba(213,27,93,0.1)"
            ))
            fig_line.update_layout(
                plot_bgcolor=COLOR_BG_LIGHT, paper_bgcolor="rgba(0,0,0,0)",
                yaxis_title="Minutos"
            )
            st.plotly_chart(fig_line, use_container_width=True)

        # Comparativa Mes a Mes
        st.markdown(f"<h5 style='color:{COLOR_CETACEAN};'>Comparativa Mensual (Volumen vs MTTR)</h5>",
                    unsafe_allow_html=True)
        comp_mensual = df_f.groupby("año_mes").agg(
            Volumen=("id", "count"),
            MTTR=("minutos_caida", "mean")
        ).reset_index()

        fig_comp = make_subplots(specs=[[{"secondary_y": True}]])
        fig_comp.add_trace(
            go.Bar(x=comp_mensual["año_mes"], y=comp_mensual["Volumen"],
                   name="Volumen", marker_color=COLOR_PICTON),
            secondary_y=False
        )
        fig_comp.add_trace(
            go.Scatter(x=comp_mensual["año_mes"], y=comp_mensual["MTTR"],
                       name="MTTR (min)", mode="lines+markers",
                       line=dict(color=COLOR_ROJO, width=3)),
            secondary_y=True
        )
        fig_comp.update_layout(
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            height=350
        )
        st.plotly_chart(fig_comp, use_container_width=True)

    # ========== TAB 5: HEATMAPS ==========
    with tabs[4]:
        st.markdown(f"<h3 style='color:{COLOR_CETACEAN};'>Mapas de Calor</h3>", unsafe_allow_html=True)
        hm_metrica = st.selectbox(
            "Métrica:", ["Frecuencia (Cantidad)", "Impacto (Minutos Downtime)"],
            key="rep_hm"
        )

        col_hm1, col_hm2 = st.columns(2)
        with col_hm1:
            st.markdown(f"<h5 style='color:{COLOR_CETACEAN};'>Servicio x Mes</h5>", unsafe_allow_html=True)
            if hm_metrica == "Impacto (Minutos Downtime)":
                hm_data = df_f.groupby(["servicio", "mes_str"])["minutos_caida"].sum().reset_index()
                z_col = "minutos_caida"
            else:
                hm_data = df_f.groupby(["servicio", "mes_str"]).size().reset_index(name="frecuencia")
                z_col = "frecuencia"

            if not hm_data.empty:
                fig_hm = px.density_heatmap(
                    hm_data, x="mes_str", y="servicio", z=z_col,
                    histfunc="sum",
                    color_continuous_scale=[COLOR_BG_LIGHT, COLOR_PICTON, COLOR_ROJO]
                )
                fig_hm.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fig_hm, use_container_width=True)

        with col_hm2:
            st.markdown(f"<h5 style='color:{COLOR_CETACEAN};'>Proveedor x Mes</h5>", unsafe_allow_html=True)
            hm_prov = df_f.groupby(["tercero_nombre", "mes_str"]).size().reset_index(name="frecuencia")
            if not hm_prov.empty:
                fig_prov_hm = px.density_heatmap(
                    hm_prov, x="mes_str", y="tercero_nombre", z="frecuencia",
                    color_continuous_scale=[COLOR_BG_LIGHT, COLOR_CYAN, COLOR_PURPLE]
                )
                fig_prov_hm.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fig_prov_hm, use_container_width=True)

    # ========== TAB 6: HORARIO CRÍTICO ==========
    with tabs[5]:
        st.markdown(f"<h3 style='color:{COLOR_CETACEAN};'>Análisis Horario de Incidentes</h3>",
                    unsafe_allow_html=True)
        col_h1, col_h2 = st.columns(2)
        with col_h1:
            st.markdown(f"<h5 style='color:{COLOR_CETACEAN};'>Incidentes por Hora del Día</h5>",
                        unsafe_allow_html=True)
            hora_dist = df_f.groupby("hora_creacion").size().reset_index(name="cantidad")
            fig_hora = px.bar(
                hora_dist, x="hora_creacion", y="cantidad",
                color="cantidad", color_continuous_scale=[COLOR_BG_LIGHT, COLOR_ROJO],
                labels={"hora_creacion": "Hora", "cantidad": "Incidentes"}
            )
            fig_hora.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig_hora, use_container_width=True)

        with col_h2:
            st.markdown(f"<h5 style='color:{COLOR_CETACEAN};'>Incidentes por Día de la Semana</h5>",
                        unsafe_allow_html=True)
            orden = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            dias_es = {
                "Monday": "Lun", "Tuesday": "Mar", "Wednesday": "Mié",
                "Thursday": "Jue", "Friday": "Vie", "Saturday": "Sáb", "Sunday": "Dom"
            }
            dia_dist = df_f.groupby("dia_semana").size().reset_index(name="cantidad")
            dia_dist["orden"] = dia_dist["dia_semana"].map(
                {d: i for i, d in enumerate(orden)})
            dia_dist = dia_dist.sort_values("orden")
            dia_dist["dia_label"] = dia_dist["dia_semana"].map(dias_es)
            fig_dia = px.bar(
                dia_dist, x="dia_label", y="cantidad",
                color="cantidad", color_continuous_scale=[COLOR_BG_LIGHT, COLOR_PICTON],
                labels={"cantidad": "Incidentes"}
            )
            fig_dia.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig_dia, use_container_width=True)

        # Sunburst: Jerarquía completa
        st.markdown(f"<h5 style='color:{COLOR_CETACEAN};'>Jerarquía de Incidentes (Sunburst)</h5>",
                    unsafe_allow_html=True)
        sun_data = (df_f.groupby(["plataforma", "servicio", "tercero_nombre"])
                     .size().reset_index(name="cantidad"))
        fig_sun = px.sunburst(
            sun_data, path=["plataforma", "servicio", "tercero_nombre"],
            values="cantidad", color="cantidad",
            color_continuous_scale=[COLOR_BG_LIGHT, COLOR_PICTON, COLOR_ROJO]
        )
        fig_sun.update_layout(margin=dict(t=0, b=0, l=0, r=0), height=450)
        st.plotly_chart(fig_sun, use_container_width=True)

    # ========== TAB 7: DATOS DETALLADOS ==========
    with tabs[6]:
        st.markdown(f"<h3 style='color:{COLOR_CETACEAN};'>Auditoría Detallada de Datos</h3>",
                    unsafe_allow_html=True)
        columnas_visibles = [
            "consecutivo_num", "plataforma", "servicio", "tercero_nombre",
            "analista", "estado", "afectacion", "escalado",
            "fecha_creacion", "fecha_envio", "minutos_caida",
        ]
        st.dataframe(
            df_f[columnas_visibles].sort_values("fecha_creacion", ascending=False),
            use_container_width=True, hide_index=True,
            column_config={
                "consecutivo_num": "ID",
                "minutos_caida": st.column_config.NumberColumn("Downtime", format="%.1f min"),
                "fecha_creacion": st.column_config.DatetimeColumn("Inicio", format="DD/MM/YYYY HH:mm"),
                "fecha_envio": st.column_config.DatetimeColumn("Cierre", format="DD/MM/YYYY HH:mm"),
                "escalado": st.column_config.CheckboxColumn("SLA Incumplido"),
            }
        )

    # ========== TAB 8: EXPORTACIÓN ==========
    with tabs[7]:
        st.markdown(f"<h3 style='color:{COLOR_CETACEAN};'>Exportación y Descargas</h3>", unsafe_allow_html=True)
        col_ex1, col_ex2 = st.columns(2)

        # Excel multi-sheet
        output = BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            # Sheet 1: Resumen
            df_resumen = pd.DataFrame({
                "Métrica": [
                    "Total Eventos", "Casos Cerrados", "Tasa Cierre (%)",
                    "Total Downtime (min)", "MTTR Promedio (min)",
                    "MTBF (Horas)", "SLA Cumplimiento (%)", "SLA Incumplidos",
                    "Servicios Afectados", "Terceros Involucrados",
                ],
                "Valor": [
                    total, cerrados, round(pct_cierre, 1),
                    round(total_minutos, 1), round(mttr, 1),
                    round(mtbf, 1), round(sla_pct, 1), escalados,
                    df_f["servicio"].nunique(), df_f["tercero_nombre"].nunique(),
                ]
            })
            df_resumen.to_excel(writer, sheet_name="Resumen_SLA", index=False)

            # Sheet 2: Detalle
            df_f[columnas_visibles].to_excel(
                writer, sheet_name="Auditoria_Detallada", index=False)

            # Sheet 3: Top servicios
            top_serv = (df_f.groupby("servicio").agg(
                Incidentes=("id", "count"),
                Downtime_Total=("minutos_caida", "sum"),
                MTTR=("minutos_caida", "mean")
            ).reset_index())
            top_serv.to_excel(writer, sheet_name="Top_Servicios", index=False)

            # Sheet 4: Por analista
            if not df_cerrados.empty:
                prod_analista = (df_cerrados.groupby("analista").agg(
                    Casos_Resueltos=("id", "count"),
                    MTTR_Promedio=("minutos_caida", "mean")
                ).reset_index())
                prod_analista.to_excel(writer, sheet_name="Productividad", index=False)

        with col_ex1:
            st.download_button(
                label="📊 Descargar Reporte Excel (.xlsx)",
                data=output.getvalue(),
                file_name=f"Reporte_TI_{datetime.date.today()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary", use_container_width=True
            )

        with col_ex2:
            # HTML ejecutivo
            html_content = f"""
            <html><head>
            <meta charset="utf-8">
            <style>
                * {{ font-family: Arial, sans-serif; margin: 0; padding: 0; box-sizing: border-box; }}
                body {{ color: {COLOR_CETACEAN}; padding: 30px; }}
                h1 {{ color: {COLOR_ROJO}; border-bottom: 3px solid {COLOR_PICTON}; padding-bottom: 10px; }}
                .grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin: 25px 0; }}
                .card {{ background: {COLOR_BG_LIGHT}; padding: 20px; border-radius: 8px; text-align: center; }}
                .card h2 {{ color: {COLOR_PICTON}; font-size: 28px; margin: 0; }}
                .card p {{ font-weight: bold; font-size: 11px; text-transform: uppercase; margin-top: 5px; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 20px; font-size: 11px; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background: {COLOR_CETACEAN}; color: white; }}
                .footer {{ margin-top: 30px; font-size: 11px; color: #888; text-align: center; }}
            </style>
            </head><body>
            <h1>Reporte Ejecutivo - Operaciones TI</h1>
            <p>Generado: {datetime.datetime.now().strftime("%d/%m/%Y %H:%M")} | Período: {rango[0]} al {rango[1] if len(rango)>1 else datetime.date.today()}</p>
            <div class="grid">
                <div class="card"><h2>{total}</h2><p>Incidentes</p></div>
                <div class="card"><h2>{sla_pct:.1f}%</h2><p>Disponibilidad SLA</p></div>
                <div class="card"><h2>{mttr:.1f}</h2><p>MTTR (min)</p></div>
                <div class="card"><h2>{mtbf:.1f}</h2><p>MTBF (hrs)</p></div>
            </div>
            <h2>Detalle de Incidentes Escalados</h2>
            {df_f[df_f["escalado"]==1][["consecutivo_num","servicio","tercero_nombre","afectacion"]].to_html(index=False) if escalados > 0 else "<p>No hay incidentes escalados en el período.</p>"}
            <div class="footer">Portal de Comunicados TI - Reporte generado automáticamente</div>
            </body></html>
            """
            st.download_button(
                label="📄 Descargar Informe Ejecutivo (.html)",
                data=html_content,
                file_name=f"Reporte_Management_{datetime.date.today()}.html",
                mime="text/html", use_container_width=True
            )

import streamlit as st
import pandas as pd
import requests
import matplotlib.pyplot as plt

st.set_page_config(page_title="Radioaficionados DMR Chile", layout="wide")

API_URL = "https://radioid.net/api/dmr/user/?country=Chile"

# -------------------------------
# Utilidades
# -------------------------------
@st.cache_data(ttl=15 * 60)  # cache 15 minutos
def fetch_data(url: str) -> pd.DataFrame:
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        js = r.json()
        results = js.get("results", [])
        df = pd.DataFrame(results)
        # columnas esperadas (dependen del API). Nos aseguramos de que existan:
        for col in ["state", "city", "callsign", "radio_id", "fname", "lname", "last_seen"]:
            if col not in df.columns:
                df[col] = pd.Series([None] * len(df))
        # Normalizaciones suaves
        df["state"] = df["state"].fillna("Sin Región").astype(str).str.strip()
        df["city"] = df["city"].fillna("Sin Ciudad").astype(str).str.strip()
        df["callsign"] = df["callsign"].astype(str).str.upper()
        # Orden sugerido
        df = df.sort_values(["state", "city", "callsign"], na_position="last").reset_index(drop=True)
        return df
    except requests.exceptions.RequestException as e:
        st.error(f"Error consultando la API: {e}")
        return pd.DataFrame()

def to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")

# -------------------------------
# Sidebar
# -------------------------------
st.sidebar.header("Opciones de Filtro")
with st.sidebar:
    st.write("### Configuración de Visualización")

    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        refresh = st.button("Actualizar")
    with col_btn2:
        clear_cache = st.button("Limpiar caché")

    if clear_cache:
        fetch_data.clear()  # invalida el cache

# -------------------------------
# Carga de datos
# -------------------------------
with st.spinner("Cargando datos…"):
    df = fetch_data(API_URL if not st.session_state.get("override_url") else st.session_state["override_url"])

if df.empty:
    st.error("No se pudieron cargar datos. Intenta nuevamente con 'Actualizar'.")
    st.stop()

if refresh:
    with st.spinner("Actualizando…"):
        fetch_data.clear()
        df = fetch_data(API_URL)

# -------------------------------
# Encabezado y descripción
# -------------------------------
st.title("Radioaficionados DMR en Chile")
st.caption("Fuente: radioid.net API – País: Chile")

st.write(
    "Esta aplicación muestra información actualizada de radioaficionados en Chile registrados para comunicación digital (DMR). "
    "Usa los filtros de la barra lateral para explorar por región, ciudad, o buscar por *callsign* y nombre."
)

# -------------------------------
# Filtros
# -------------------------------
regions = sorted(df["state"].dropna().unique().tolist())
selected_regions = st.sidebar.multiselect("Selecciona una o más Regiones", regions, default=regions)

# filtrar por región
df_filtered = df[df["state"].isin(selected_regions)].copy()

# filtro por ciudad (se rellena según regiones elegidas)
cities = sorted(df_filtered["city"].dropna().unique().tolist())
selected_cities = st.sidebar.multiselect("Filtrar por Ciudad (opcional)", cities)

if selected_cities:
    df_filtered = df_filtered[df_filtered["city"].isin(selected_cities)]

# búsqueda por texto
q = st.sidebar.text_input("Buscar (callsign, nombre, ciudad)", "").strip().upper()
if q:
    mask = (
        df_filtered["callsign"].astype(str).str.contains(q, na=False)
        | df_filtered["fname"].astype(str).str.upper().str.contains(q, na=False)
        | df_filtered["lname"].astype(str).str.upper().str.contains(q, na=False)
        | df_filtered["city"].astype(str).str.upper().str.contains(q, na=False)
        | df_filtered["state"].astype(str).str.upper().str.contains(q, na=False)
    )
    df_filtered = df_filtered[mask]

# columnas a mostrar
columns_to_show = ["callsign", "radio_id", "fname", "lname", "city", "state", "last_seen"]
missing_cols = [c for c in columns_to_show if c not in df_filtered.columns]
if missing_cols:
    # si faltan columnas, las creamos para evitar errores visuales
    for c in missing_cols:
        df_filtered[c] = None

# -------------------------------
# Descarga
# -------------------------------
st.download_button(
    "Descargar CSV (filtro aplicado)",
    data=to_csv_bytes(df_filtered),
    file_name="radioaficionados_chile_filtrado.csv",
    mime="text/csv",
)

# -------------------------------
# Tabla
# -------------------------------
st.write("### Datos de Radioaficionados en Chile (según filtros)")
st.dataframe(
    df_filtered[columns_to_show],
    use_container_width=True,
    hide_index=True,
)

# -------------------------------
# Gráficos
# -------------------------------
st.write("### Visualizaciones")

col1, col2 = st.columns(2)

# Gráfico de barras: cantidad por región
with col1:
    st.subheader("Cantidad de usuarios por Región")
    counts_region = df_filtered["state"].value_counts().sort_values(ascending=False)
    if counts_region.empty:
        st.info("No hay datos para graficar (revisa los filtros).")
    else:
        fig1, ax1 = plt.subplots()
        counts_region.plot(kind="bar", ax=ax1)
        ax1.set_title("Cantidad de usuarios por Región")
        ax1.set_xlabel("Región")
        ax1.set_ylabel("Cantidad")
        st.pyplot(fig1)

# Gráfico de torta: distribución por región
with col2:
    st.subheader("Distribución por Región")
    if counts_region.empty:
        st.info("No hay datos para graficar (revisa los filtros).")
    else:
        fig2, ax2 = plt.subplots()
        counts_region.plot(kind="pie", autopct="%1.1f%%", ax=ax2, ylabel="")
        ax2.set_title("Distribución por Región de Usuario")
        st.pyplot(fig2)

# -------------------------------
# Extras opcionales / diagnóstico
# -------------------------------
with st.expander("Ver primeras filas del DataFrame original (sin filtrar)"):
    st.dataframe(df.head(50), use_container_width=True, hide_index=True)

with st.expander("Ver esquema de columnas disponibles"):
    info_cols = pd.DataFrame(
        {
            "columna": df.columns,
            "nulos": df.isna().sum().values,
            "tipo": [str(t) for t in df.dtypes.values],
        }
    )
    st.dataframe(info_cols, use_container_width=True, hide_index=True)

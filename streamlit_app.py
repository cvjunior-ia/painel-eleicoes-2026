import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import streamlit as st
from streamlit_autorefresh import st_autorefresh

BASE = "https://resultados.tse.jus.br/oficial/ele2026"
ELEICAO_FEDERAL = "6257"
ELEICAO_ESTADUAL = "6259"

UFS = [
    "AC","AL","AP","AM","BA","CE","DF","ES","GO","MA","MT","MS","MG",
    "PA","PB","PR","PE","PI","RJ","RN","RS","RO","RR","SC","SP","SE","TO"
]

HEADERS = {
    "User-Agent": "Painel-Eleicoes-2026/1.1",
    "Accept": "application/json,text/plain,*/*",
}

# Cache compartilhado entre os visitantes do mesmo processo do Streamlit.
CACHE_TTL = 15 * 60

HIST = Path("historico")
HIST.mkdir(exist_ok=True)

TZ_BAHIA = ZoneInfo("America/Bahia")

st.set_page_config(
    page_title="Eleições 2026 - TSE",
    page_icon="🗳️",
    layout="wide"
)

# MOBILE RESPONSIVE
st.markdown(
    """
    <style>
    /* Mantém o painel confortável em Android e iOS */
    @media (max-width: 768px) {
        .block-container {
            padding-top: 1rem !important;
            padding-left: 0.65rem !important;
            padding-right: 0.65rem !important;
        }
        h1 {
            font-size: 1.65rem !important;
            line-height: 1.15 !important;
        }
        h2 { font-size: 1.35rem !important; }
        h3 { font-size: 1.15rem !important; }

        [data-testid="stMetricValue"] {
            font-size: 1.25rem !important;
        }
        [data-testid="stMetricLabel"] {
            font-size: 0.78rem !important;
        }

        /* Tabelas continuam roláveis na horizontal em telas estreitas */
        [data-testid="stDataFrame"] {
            overflow-x: auto !important;
        }

        /* Abas mais compactas no celular */
        button[data-baseweb="tab"] {
            padding-left: 0.45rem !important;
            padding-right: 0.45rem !important;
            font-size: 0.78rem !important;
        }
    }

    .motocred-ad {
        display: block;
        font-family: "Arial Narrow", "Roboto Condensed", "Helvetica Neue Condensed", Arial, sans-serif;
        text-decoration: none !important;
        border-radius: 16px;
        margin: 6px 0 12px 0;
        color: white !important;
        overflow: hidden;
        border: 1px solid rgba(255,255,255,0.14);
        background:
            radial-gradient(circle at 88% 16%, rgba(255,255,255,0.22), transparent 22%),
            linear-gradient(135deg, #0057B8 0%, #003399 52%, #001A70 100%);
        box-shadow: 0 14px 34px rgba(0,35,110,0.28);
        position: relative;
    }

    .motocred-ad:before {
        content: "";
        position: absolute;
        right: -55px;
        bottom: -90px;
        width: 260px;
        height: 260px;
        border-radius: 50%;
        background: rgba(255,255,255,0.07);
    }

    .motocred-ad:hover {
        transform: translateY(-2px);
        box-shadow: 0 18px 40px rgba(0,35,110,0.34);
        transition: 0.18s ease;
    }

    .motocred-wrap {
        position: relative;
        z-index: 2;
        display: grid;
        grid-template-columns: 1.75fr 0.65fr;
        gap: 14px;
        align-items: center;
        padding: 15px 18px;
    }

    .motocred-badge {
        display: inline-block;
        font-family: Arial, Helvetica, sans-serif;
        background: rgba(255,255,255,0.16);
        border: 1px solid rgba(255,255,255,0.24);
        padding: 4px 8px;
        border-radius: 999px;
        font-size: 0.68rem;
        font-weight: 700;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        margin-bottom: 6px;
    }

    .motocred-brand {
        font-family: "Arial Narrow", "Roboto Condensed", "Helvetica Neue Condensed", Arial, sans-serif;
        font-size: 1.72rem;
        font-weight: 900;
        line-height: 0.95;
        letter-spacing: 0.035em;
        text-transform: uppercase;
        margin-bottom: 5px;
    }

    .motocred-headline {
        font-family: Arial, Helvetica, sans-serif;
        font-size: 0.94rem;
        font-weight: 700;
        line-height: 1.24;
        letter-spacing: -0.01em;
        margin-bottom: 9px;
        max-width: 700px;
    }

    .motocred-benefits {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
        margin-bottom: 10px;
    }

    .motocred-benefit {
        font-family: Arial, Helvetica, sans-serif;
        background: rgba(255,255,255,0.12);
        border: 1px solid rgba(255,255,255,0.16);
        padding: 5px 8px;
        border-radius: 999px;
        font-size: 0.72rem;
        font-weight: 700;
    }

    .motocred-cta {
        display: inline-block;
        font-family: Arial, Helvetica, sans-serif;
        letter-spacing: 0.01em;
        background: #ffffff;
        color: #003399 !important;
        padding: 8px 12px;
        border-radius: 9px;
        font-weight: 900;
        font-size: 0.82rem;
        box-shadow: 0 5px 12px rgba(0,0,0,0.14);
    }

    .motocred-side {
        background: rgba(255,255,255,0.13);
        border: 1px solid rgba(255,255,255,0.18);
        border-radius: 12px;
        padding: 11px 12px;
        text-align: center;
        backdrop-filter: blur(4px);
    }

    .motocred-side-small {
        font-family: Arial, Helvetica, sans-serif;
        font-size: 0.70rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        opacity: 0.82;
        font-weight: 800;
        margin-bottom: 4px;
    }

    .motocred-side-big {
        font-family: "Arial Narrow", "Roboto Condensed", "Helvetica Neue Condensed", Arial, sans-serif;
        font-size: 1.05rem;
        font-weight: 900;
        line-height: 1.02;
        letter-spacing: 0.01em;
        text-transform: uppercase;
        margin-bottom: 7px;
    }

    .motocred-side-copy {
        font-family: Arial, Helvetica, sans-serif;
        font-size: 0.76rem;
        line-height: 1.2;
        opacity: 0.95;
    }

    .motocred-disclaimer {
        font-size: 0.70rem;
        opacity: 0.72;
        margin-top: -6px;
        margin-bottom: 8px;
    }

    @media (max-width: 768px) {
        .motocred-wrap {
            grid-template-columns: 1fr;
            padding: 12px 12px;
            gap: 9px;
        }

        .motocred-brand {
            font-size: 1.35rem;
        }

        .motocred-headline {
            font-size: 0.86rem;
        }

        .motocred-benefit {
            font-size: 0.74rem;
            padding: 6px 9px;
        }

        .motocred-side {
            display: none;
        }
    }

    </style>
    """,
    unsafe_allow_html=True,
)

st_autorefresh(interval=15 * 60 * 1000, key="auto_refresh_15min")

def to_int(v):
    if v is None:
        return 0
    try:
        if isinstance(v, int):
            return v
        s = str(v).strip().replace(".", "").replace(" ", "")
        return int(float(s.replace(",", ".")))
    except Exception:
        return 0

def to_float_br(v):
    if v is None:
        return 0.0
    try:
        if isinstance(v, (int, float)):
            return float(v)
        return float(str(v).replace("%", "").replace(".", "").replace(",", ".").strip())
    except Exception:
        return 0.0

@st.cache_resource
def http_session():
    """Uma única sessão HTTP compartilhada entre os usuários do painel."""
    session = requests.Session()
    session.headers.update(HEADERS)
    retry = Retry(
        total=2,
        connect=2,
        read=2,
        backoff_factor=0.4,
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=frozenset(["GET"]),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(pool_connections=20, pool_maxsize=20, max_retries=retry)
    session.mount("https://", adapter)
    return session


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def get_json(url):
    """Resultado fica em cache e é reutilizado por todos os visitantes."""
    r = http_session().get(url, timeout=20)
    r.raise_for_status()
    return r.json()

def codigo_eleicao_arquivo(eleicao):
    """O TSE usa o código da eleição com 6 dígitos no nome dos arquivos."""
    return str(eleicao).zfill(6)

def url_resultado(abrangencia, cargo, eleicao):
    a = abrangencia.lower()
    e = codigo_eleicao_arquivo(eleicao)
    return f"{BASE}/{eleicao}/dados/{a}/{a}-c{cargo}-e{e}-u.json"

def url_acompanhamento(abrangencia, eleicao):
    a = abrangencia.lower()
    e = codigo_eleicao_arquivo(eleicao)
    return f"{BASE}/{eleicao}/dados/{a}/{a}-e{e}-ab.json"

def safe_get(url):
    try:
        return get_json(url), None
    except requests.HTTPError as e:
        return None, f"HTTP {getattr(e.response, 'status_code', '?')}"
    except Exception as e:
        return None, str(e)

def collect_candidates(node, out, party_hint=""):
    """Percorre a estrutura TSE (carg > agr > par > cand) e coleta candidatos."""
    if isinstance(node, list):
        for item in node:
            collect_candidates(item, out, party_hint)
        return

    if not isinstance(node, dict):
        return

    # Tenta carregar a sigla partidária do nível atual para os filhos.
    hint = (
        node.get("sg")
        or node.get("sgp")
        or node.get("sigla")
        or party_hint
        or ""
    )

    cand = node.get("cand")
    if isinstance(cand, list):
        for candidato in cand:
            if isinstance(candidato, dict):
                item = dict(candidato)
                item["_party_hint"] = hint
                out.append(item)

    for k, v in node.items():
        if k != "cand":
            collect_candidates(v, out, hint)


def parse_candidates(data):
    if not data:
        return pd.DataFrame()

    rows = []
    collect_candidates(data, rows)

    out = []
    seen = set()

    for cand in rows:
        nome = cand.get("nmu") or cand.get("nm") or cand.get("nome") or "Não informado"
        numero = cand.get("n") or cand.get("nr") or cand.get("numero") or ""
        partido = (
            cand.get("cc")
            or cand.get("sg")
            or cand.get("sgp")
            or cand.get("partido")
            or cand.get("_party_hint")
            or ""
        )
        votos = cand.get("vap")
        if votos is None:
            votos = cand.get("votos")

        pct = cand.get("pvap")
        if pct is None:
            pct = cand.get("pvapn")
        if pct is None:
            pct = cand.get("percentual")

        status = (
            cand.get("st")
            or cand.get("sit")
            or cand.get("dvt")
            or cand.get("situacao")
            or ""
        )
        if not status and cand.get("e") == "s":
            status = "Eleito"

        seq = cand.get("sqcand") or cand.get("seq") or cand.get("sequencial") or ""
        key = (str(seq), str(nome), str(numero))
        if key in seen:
            continue
        seen.add(key)

        out.append({
            "Nome": nome,
            "Número": numero,
            "Partido/Coligação": partido,
            "Votos": to_int(votos),
            "% válidos": to_float_br(pct),
            "Status TSE": status,
            "Seq.": seq
        })

    df = pd.DataFrame(out)
    if not df.empty:
        df = df.sort_values(["Votos", "% válidos"], ascending=False).reset_index(drop=True)
    return df


def parse_totalizacao(data):
    if not isinstance(data, dict):
        return {}

    candidates = [data]
    for _, v in data.items():
        if isinstance(v, dict):
            candidates.append(v)

    keys_pct = ["pst", "pstr", "percentualSecoesTotalizadas", "percSecoes", "psa"]

    for d in candidates:
        pct = None
        for k in keys_pct:
            if k in d:
                pct = to_float_br(d.get(k))
                break
        if pct is not None:
            return {"percentual": pct, "raw": d}

    return {"percentual": 0.0, "raw": data}

def save_snapshot(df, nome, totalizacao=None):
    """
    No Community Cloud não gravamos um CSV novo a cada visita.
    Isso reduz I/O, memória e duplicação quando muitas pessoas acessam o painel.
    Os dados continuam sendo atualizados ao vivo pelo cache compartilhado.
    """
    return


def status_senado(df, pct_totalizada):
    if df.empty:
        return df

    out = df.copy()
    out["Chances/Status"] = "Em apuração"

    for i, row in out.iterrows():
        stt = str(row["Status TSE"]).lower()
        if any(x in stt for x in ["eleito", "eleita"]):
            out.at[i, "Chances/Status"] = "Eleito"
        elif any(x in stt for x in ["não eleito", "nao eleito", "suplente"]):
            out.at[i, "Chances/Status"] = "Não eleito"

    if len(out) < 3 or pct_totalizada <= 0:
        return out

    votos_apurados = int(out["Votos"].sum())
    frac = pct_totalizada / 100.0
    if frac <= 0:
        return out

    estimativa_total = votos_apurados / frac
    votos_restantes_est = max(0, estimativa_total - votos_apurados)

    v2 = int(out.iloc[1]["Votos"])
    v3 = int(out.iloc[2]["Votos"])
    vantagem = v2 - v3

    for pos in [0, 1]:
        if out.at[pos, "Chances/Status"] == "Em apuração":
            if vantagem > votos_restantes_est:
                out.at[pos, "Chances/Status"] = "Matematicamente eleito"
            elif pct_totalizada >= 95 and vantagem > max(1000, 0.002 * max(v2, 1)):
                out.at[pos, "Chances/Status"] = "Chance alta"
            else:
                out.at[pos, "Chances/Status"] = "Disputa acirrada"

    if out.at[2, "Chances/Status"] == "Em apuração":
        out.at[2, "Chances/Status"] = (
            "Não eleito" if vantagem > votos_restantes_est else "Disputa acirrada"
        )

    for i in range(3, len(out)):
        if out.at[i, "Chances/Status"] == "Em apuração":
            out.at[i, "Chances/Status"] = "Não eleito" if pct_totalizada >= 100 else "Em apuração"

    return out

def infer_party_status(status_tse):
    s = str(status_tse).lower()
    if "eleit" in s:
        return "Eleito"
    if "supl" in s:
        return "Suplente"
    return "Em apuração"

def top_por_partido(df, n=20):
    if df.empty:
        return {}
    col = "Partido/Coligação"
    grupos = {}
    for partido, g in df.groupby(col, dropna=False):
        gg = g.sort_values("Votos", ascending=False).head(n).copy()
        gg["Status"] = gg["Status TSE"].map(infer_party_status)
        grupos[str(partido) if str(partido) else "Sem identificação"] = gg
    return dict(sorted(grupos.items(), key=lambda kv: kv[0]))

st.title("🗳️ Painel Eleições 2026 — Dados oficiais do TSE")

st.markdown(
    """
    <a class="motocred-ad"
       href="https://motocredyamaha.com.br/"
       target="_blank"
       rel="noopener noreferrer">
        <div class="motocred-wrap">
            <div>
                <div class="motocred-badge">Publicidade</div>
                <div class="motocred-brand">YAMAHA MOTOCRED</div>
                <div class="motocred-headline">
                    Sua Yamaha no Recôncavo: motos, peças, acessórios e oficina especializada.
                </div>
                <div class="motocred-benefits">
                    <span class="motocred-benefit">🏍️ Motos Yamaha</span>
                    <span class="motocred-benefit">🔧 Peças e acessórios</span>
                    <span class="motocred-benefit">🛠️ Oficina especializada</span>
                    <span class="motocred-benefit">💬 Atendimento rápido</span>
                </div>
                <span class="motocred-cta">Ver ofertas e conhecer a Motocred →</span>
            </div>
            <div class="motocred-side">
                <div class="motocred-side-small">Destaque Yamaha</div>
                <div class="motocred-side-big">Escolha sua próxima Yamaha</div>
                <div class="motocred-side-copy">
                    Clique e confira modelos, serviços e novidades no site da Motocred.
                </div>
            </div>
        </div>
    </a>
    <div class="motocred-disclaimer">
        Conteúdo comercial da Yamaha Motocred. Não possui vínculo com o TSE.
    </div>
    """,
    unsafe_allow_html=True,
)

c1, c2, c3, c4 = st.columns([1.2, 0.8, 1, 0.9])
with c1:
    st.metric("Atualização local", datetime.now(TZ_BAHIA).strftime("%d/%m/%Y %H:%M"))
with c2:
    st.metric("Atualização", "15 min")
with c3:
    st.metric("Fonte", "TSE oficial")
with c4:
    st.metric("Cache", "Compartilhado")

st.caption(
    "O painel consulta diretamente os arquivos JSON públicos do TSE. "
    "Atualização automática a cada 15 minutos. Versão 1.8 — banner Yamaha Motocred compacto, tipografia Yamaha-inspired e interface móvel otimizada."
)

# Atualização manual com proteção contra cliques repetidos
if "ultima_atualizacao_manual" not in st.session_state:
    st.session_state.ultima_atualizacao_manual = None

col_refresh, col_status = st.columns([1, 3])

with col_refresh:
    if st.button("🔄 Atualizar agora", use_container_width=True):
        agora = datetime.now(TZ_BAHIA)
        ultima = st.session_state.ultima_atualizacao_manual

        if ultima is None or (agora - ultima) >= timedelta(seconds=30):
            st.session_state.ultima_atualizacao_manual = agora
            st.cache_data.clear()
            st.rerun()
        else:
            faltam = 30 - int((agora - ultima).total_seconds())
            st.warning(f"Aguarde {faltam}s para atualizar novamente.")

with col_status:
    st.caption("Atualização manual consulta novamente os dados do TSE e renova o cache compartilhado.")

tabs = st.tabs([
    "🇧🇷 Presidente",
    "🏛️ Senado — 27 UFs",
    "🏢 Deputados Federais",
    "🌴 ALBA — Bahia",
    "⚙️ Diagnóstico"
])

diagnostico = []

with tabs[0]:
    st.subheader("Presidente da República")

    escopos = {
        "Brasil + Exterior": "BR",
        "Bahia": "BA",
        "Exterior": "ZZ",
    }

    cols = st.columns(3)

    for (rotulo, abr), col in zip(escopos.items(), cols):
        with col:
            ures = url_resultado(abr, "0001", ELEICAO_FEDERAL)
            uac = url_acompanhamento(abr, ELEICAO_FEDERAL)
            data, err = safe_get(ures)
            acomp, err2 = safe_get(uac)

            diagnostico.append((rotulo, ures, err))
            diagnostico.append((rotulo + " acompanhamento", uac, err2))

            df = parse_candidates(data)
            tot = parse_totalizacao(data).get("percentual", 0.0)
            if tot <= 0:
                tot = parse_totalizacao(acomp).get("percentual", 0.0)

            st.markdown(f"### {rotulo}")
            st.progress(min(max(tot / 100, 0.0), 1.0), text=f"Seções totalizadas: {tot:.2f}%")

            if df.empty:
                st.info("Resultado ainda indisponível nesse arquivo.")
            else:
                st.dataframe(
                    df[["Nome","Partido/Coligação","Votos","% válidos","Status TSE"]].head(10),
                    use_container_width=True,
                    hide_index=True
                )
                save_snapshot(df, f"presidente_{abr.lower()}", tot)

with tabs[1]:
    st.subheader("Senado — todas as UFs")
    st.caption(
        "Duas vagas por UF. A classificação matemática é indicativa e usa "
        "percentual totalizado + diferença entre 2º e 3º."
    )

    uf_sel = st.selectbox("UF para detalhar", UFS, index=UFS.index("BA"))

    resumo = []
    for uf in UFS:
        ures = url_resultado(uf, "0005", ELEICAO_ESTADUAL)
        uac = url_acompanhamento(uf, ELEICAO_ESTADUAL)
        data, err = safe_get(ures)
        acomp, err2 = safe_get(uac)

        diagnostico.append((f"Senado {uf}", ures, err))
        diagnostico.append((f"Acompanhamento {uf}", uac, err2))

        df = parse_candidates(data)
        tot = parse_totalizacao(data).get("percentual", 0.0)
        if tot <= 0:
            tot = parse_totalizacao(acomp).get("percentual", 0.0)
        ds = status_senado(df, tot)

        if len(ds) >= 1:
            resumo.append({
                "UF": uf,
                "% totalizado": tot,
                "1º": ds.iloc[0]["Nome"],
                "Votos 1º": ds.iloc[0]["Votos"],
                "2º": ds.iloc[1]["Nome"] if len(ds) > 1 else "",
                "Votos 2º": ds.iloc[1]["Votos"] if len(ds) > 1 else 0,
                "3º": ds.iloc[2]["Nome"] if len(ds) > 2 else "",
                "Votos 3º": ds.iloc[2]["Votos"] if len(ds) > 2 else 0,
                "Dif. 2º-3º": (
                    ds.iloc[1]["Votos"] - ds.iloc[2]["Votos"]
                    if len(ds) > 2 else 0
                ),
            })

    if resumo:
        st.dataframe(pd.DataFrame(resumo), use_container_width=True, hide_index=True)

    st.markdown(f"### Detalhe — {uf_sel}")
    data, _ = safe_get(url_resultado(uf_sel, "0005", ELEICAO_ESTADUAL))
    acomp, _ = safe_get(url_acompanhamento(uf_sel, ELEICAO_ESTADUAL))
    df = parse_candidates(data)
    tot = parse_totalizacao(data).get("percentual", 0.0)
    if tot <= 0:
        tot = parse_totalizacao(acomp).get("percentual", 0.0)
    ds = status_senado(df, tot)

    st.progress(min(max(tot / 100, 0.0), 1.0), text=f"Seções totalizadas: {tot:.2f}%")
    if ds.empty:
        st.info("Resultado do Senado ainda indisponível para essa UF.")
    else:
        st.dataframe(
            ds[["Nome","Partido/Coligação","Votos","% válidos","Chances/Status"]],
            use_container_width=True,
            hide_index=True
        )
        save_snapshot(ds, f"senado_{uf_sel.lower()}", tot)

with tabs[2]:
    st.subheader("Deputados Federais — Top 20 por partido/federação")

    uf_df = st.selectbox(
        "UF para consultar os candidatos",
        UFS,
        index=UFS.index("BA"),
        key="uf_dep_fed"
    )

    data, err = safe_get(url_resultado(uf_df, "0006", ELEICAO_ESTADUAL))
    acomp, err2 = safe_get(url_acompanhamento(uf_df, ELEICAO_ESTADUAL))
    diagnostico.append((f"Deputado Federal {uf_df}", url_resultado(uf_df, "0006", ELEICAO_ESTADUAL), err))
    diagnostico.append((f"Acompanhamento DFed {uf_df}", url_acompanhamento(uf_df, ELEICAO_ESTADUAL), err2))

    df = parse_candidates(data)
    tot = parse_totalizacao(data).get("percentual", 0.0)
    if tot <= 0:
        tot = parse_totalizacao(acomp).get("percentual", 0.0)

    st.progress(min(max(tot / 100, 0.0), 1.0), text=f"Seções totalizadas: {tot:.2f}%")

    if df.empty:
        st.info("Resultado ainda indisponível.")
    else:
        grupos = top_por_partido(df, 20)
        for partido, g in grupos.items():
            with st.expander(f"{partido} — Top {min(20, len(g))}", expanded=False):
                st.dataframe(
                    g[["Nome","Partido/Coligação","Votos","Status"]],
                    use_container_width=True,
                    hide_index=True
                )
        save_snapshot(df, f"deputados_federais_{uf_df.lower()}", tot)

with tabs[3]:
    st.subheader("Deputados Estaduais — Bahia (ALBA)")

    data, err = safe_get(url_resultado("BA", "0007", ELEICAO_ESTADUAL))
    acomp, err2 = safe_get(url_acompanhamento("BA", ELEICAO_ESTADUAL))
    diagnostico.append(("ALBA", url_resultado("BA", "0007", ELEICAO_ESTADUAL), err))
    diagnostico.append(("Acompanhamento ALBA", url_acompanhamento("BA", ELEICAO_ESTADUAL), err2))

    df = parse_candidates(data)
    tot = parse_totalizacao(data).get("percentual", 0.0)
    if tot <= 0:
        tot = parse_totalizacao(acomp).get("percentual", 0.0)

    st.progress(min(max(tot / 100, 0.0), 1.0), text=f"Seções totalizadas: {tot:.2f}%")

    if df.empty:
        st.info("Resultado da ALBA ainda indisponível.")
    else:
        grupos = top_por_partido(df, 20)
        for partido, g in grupos.items():
            with st.expander(f"{partido} — Top {min(20, len(g))}", expanded=False):
                st.dataframe(
                    g[["Nome","Partido/Coligação","Votos","Status"]],
                    use_container_width=True,
                    hide_index=True
                )
        save_snapshot(df, "alba_bahia", tot)

with tabs[4]:
    st.subheader("Diagnóstico dos endpoints")
    st.write(
        "Use esta aba se algum quadro ficar vazio. Antes do início oficial da divulgação, "
        "é normal que alguns arquivos retornem 404."
    )
    if diagnostico:
        dd = pd.DataFrame(diagnostico, columns=["Consulta","URL","Erro"])
        dd["Situação"] = dd["Erro"].fillna("OK")
        st.dataframe(dd[["Consulta","Situação","URL"]], use_container_width=True, hide_index=True)

    st.markdown("#### Parâmetros oficiais configurados")
    st.code(
        "Base: https://resultados.tse.jus.br/oficial/ele2026\n"
        "Pleito: 3220\n"
        "Eleição Federal: 6257\n"
        "Eleição Estadual: 6259\n"
        "Atualização: 15 minutos"
    )

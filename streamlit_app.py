import time
import io
import zipfile
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

# Cadastro oficial de candidaturas (Portal de Dados Abertos do TSE)
CANDIDATOS_ZIP_URL = (
    "https://cdn.tse.jus.br/estatistica/sead/odsele/"
    "consulta_cand/consulta_cand_2026.zip"
)

ELEITORADO_ZIP_URL = (
    "https://cdn.tse.jus.br/estatistica/sead/odsele/"
    "perfil_eleitorado/perfil_eleitorado_2026.zip"
)

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


@st.cache_data(ttl=6 * 60 * 60, show_spinner=False)
def get_candidate_zip():
    """Baixa o cadastro oficial de candidatos do Portal de Dados Abertos do TSE."""
    r = http_session().get(
        CANDIDATOS_ZIP_URL,
        headers={"Accept": "application/zip,*/*"},
        timeout=90,
    )
    r.raise_for_status()
    return r.content


@st.cache_data(ttl=6 * 60 * 60, show_spinner=False)
def load_candidate_registry(uf, cargo):
    """
    Retorna cadastro oficial TSE para uma UF/cargo.
    Cargo: 1 presidente, 6 deputado federal, 7 deputado estadual.
    """
    try:
        raw = get_candidate_zip()
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            alvo = f"consulta_cand_2026_{uf.upper()}.csv"
            member = next(
                (n for n in zf.namelist() if n.endswith(alvo)),
                None
            )
            if not member:
                return pd.DataFrame()

            with zf.open(member) as fh:
                dados = pd.read_csv(
                    fh,
                    sep=";",
                    encoding="latin1",
                    dtype=str,
                    low_memory=False,
                )

        dados = dados[dados["CD_CARGO"].astype(str) == str(cargo)].copy()
        if dados.empty:
            return pd.DataFrame()

        def grupo(row):
            tp = str(row.get("TP_AGREMIACAO", "")).strip().upper()
            fed = str(row.get("NM_FEDERACAO", "")).strip()
            if tp == "FEDERAÇÃO" and fed and fed not in {"#NULO", "nan", "None"}:
                return fed
            p = str(row.get("SG_PARTIDO", "")).strip()
            return p if p not in {"", "#NULO", "nan", "None"} else "Sem identificação"

        nome_urna = dados["NM_URNA_CANDIDATO"].fillna("").astype(str).str.strip()
        nome_civil = dados["NM_CANDIDATO"].fillna("").astype(str).str.strip()

        out = pd.DataFrame({
            "Nome": nome_urna.where(nome_urna.ne(""), nome_civil),
            "Número": dados["NR_CANDIDATO"].fillna("").astype(str),
            "Partido/Coligação": dados.apply(grupo, axis=1),
            "Votos": 0,
            "% válidos": 0.0,
            "Status TSE": "Em apuração",
            "Seq.": dados["SQ_CANDIDATO"].fillna("").astype(str),
        })

        return (
            out.drop_duplicates(subset=["Seq.", "Número", "Nome"])
               .sort_values(["Partido/Coligação", "Número", "Nome"])
               .reset_index(drop=True)
        )
    except Exception:
        return pd.DataFrame()


def president_registry():
    """
    Doze chapas presidenciais validadas pelo TSE para o 1º turno de 2026.
    Mantém todos visíveis mesmo antes do primeiro boletim de votação.
    """
    rows = [
        ("LULA", "13", "PT"),
        ("FLÁVIO BOLSONARO", "22", "PL"),
        ("RONALDO CAIADO", "55", "PSD"),
        ("RUI COSTA PIMENTA", "29", "PCO"),
        ("SAMARA", "80", "UP"),
        ("ZEMA", "30", "NOVO"),
        ("HERTZ DIAS", "16", "PSTU"),
        ("EDMILSON COSTA", "21", "PCB"),
        ("RENAN SANTOS", "14", "MISSÃO"),
        ("VETERINÁRIO WILSON GRASSI", "35", "DEMOCRATA"),
        ("CLARIANA BARÃO", "27", "DC"),
        ("AUGUSTO CURY", "70", "AVANTE"),
    ]
    return pd.DataFrame([
        {
            "Nome": nome,
            "Número": numero,
            "Partido/Coligação": partido,
            "Votos": 0,
            "% válidos": 0.0,
            "Status TSE": "Em apuração",
            "Seq.": "",
        }
        for nome, numero, partido in rows
    ])


def merge_registry_results(registry, results):
    """Mescla cadastro oficial (base) com votos/status do arquivo de resultados."""
    if registry is None or registry.empty:
        return results.copy() if results is not None else pd.DataFrame()
    if results is None or results.empty:
        return registry.copy().sort_values(["Votos", "Nome"], ascending=[False, True]).reset_index(drop=True)

    base = registry.copy()
    res = results.copy()

    by_seq = {
        str(r["Seq."]): r
        for _, r in res.iterrows()
        if str(r.get("Seq.", "")).strip() not in {"", "nan", "None"}
    }
    by_num = {
        str(r["Número"]): r
        for _, r in res.iterrows()
        if str(r.get("Número", "")).strip() not in {"", "nan", "None"}
    }

    matched = set()
    for i, row in base.iterrows():
        hit = None
        seq = str(row.get("Seq.", "")).strip()
        num = str(row.get("Número", "")).strip()

        if seq in by_seq:
            hit = by_seq[seq]
        elif num in by_num:
            hit = by_num[num]

        if hit is not None:
            base.at[i, "Votos"] = to_int(hit.get("Votos", 0))
            base.at[i, "% válidos"] = to_float_br(hit.get("% válidos", 0))
            stt = str(hit.get("Status TSE", "")).strip()
            if stt:
                base.at[i, "Status TSE"] = stt
            matched.add((str(hit.get("Seq.", "")), str(hit.get("Número", ""))))

    extras = []
    for _, row in res.iterrows():
        key = (str(row.get("Seq.", "")), str(row.get("Número", "")))
        if key not in matched:
            extras.append(row.to_dict())

    if extras:
        base = pd.concat([base, pd.DataFrame(extras)], ignore_index=True)

    return (
        base.drop_duplicates(subset=["Seq.", "Número", "Nome"])
            .sort_values(["Votos", "Nome"], ascending=[False, True])
            .reset_index(drop=True)
    )

@st.cache_data(ttl=24 * 60 * 60, show_spinner=False)
def get_electorate_zip():
    """Baixa o perfil oficial do eleitorado 2026 do Portal de Dados Abertos do TSE."""
    r = http_session().get(
        ELEITORADO_ZIP_URL,
        headers={"Accept": "application/zip,*/*"},
        timeout=120,
    )
    r.raise_for_status()
    return r.content


@st.cache_data(ttl=24 * 60 * 60, show_spinner=False)
def load_top_ba_municipios(n=15):
    """
    Calcula os maiores colégios eleitorais da Bahia diretamente do arquivo
    oficial Perfil do Eleitorado 2026 do TSE.
    """
    try:
        raw = get_electorate_zip()
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            member = next(
                (
                    nome for nome in zf.namelist()
                    if nome.lower().endswith(".csv")
                    and "perfil_eleitorado" in nome.lower()
                ),
                None
            )
            if not member:
                return pd.DataFrame()

            with zf.open(member) as fh:
                dados = pd.read_csv(
                    fh,
                    sep=";",
                    encoding="latin1",
                    dtype=str,
                    usecols=[
                        "SG_UF",
                        "CD_MUNICIPIO",
                        "NM_MUNICIPIO",
                        "QT_ELEITORES_PERFIL",
                    ],
                    low_memory=False,
                )

        dados = dados[dados["SG_UF"].astype(str).str.upper() == "BA"].copy()
        if dados.empty:
            return pd.DataFrame()

        dados["Eleitores"] = pd.to_numeric(
            dados["QT_ELEITORES_PERFIL"],
            errors="coerce"
        ).fillna(0)

        agrupado = (
            dados.groupby(
                ["CD_MUNICIPIO", "NM_MUNICIPIO"],
                as_index=False
            )["Eleitores"]
            .sum()
            .sort_values("Eleitores", ascending=False)
            .head(n)
            .reset_index(drop=True)
        )

        agrupado["Código"] = (
            pd.to_numeric(agrupado["CD_MUNICIPIO"], errors="coerce")
              .fillna(0)
              .astype(int)
              .astype(str)
              .str.zfill(5)
        )
        agrupado["Município"] = agrupado["NM_MUNICIPIO"].astype(str)
        agrupado["Posição"] = range(1, len(agrupado) + 1)

        return agrupado[["Posição", "Município", "Código", "Eleitores"]]
    except Exception:
        return pd.DataFrame()


def top_municipal(df, n):
    """Top N municipal apenas quando já existem votos apurados."""
    if df is None or df.empty or int(df["Votos"].sum()) <= 0:
        return pd.DataFrame()
    return (
        df.sort_values(["Votos", "% válidos"], ascending=False)
          .head(n)
          .reset_index(drop=True)
    )


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


def url_resultado_municipio(uf, codigo_municipio, cargo, eleicao):
    """
    Resultado municipal EA20.
    O TSE exige código do município com 5 dígitos no nome do arquivo.
    """
    u = uf.lower()
    m = str(codigo_municipio).strip().zfill(5)
    e = codigo_eleicao_arquivo(eleicao)
    return f"{BASE}/{eleicao}/dados/{u}/{u}{m}-c{cargo}-e{e}-u.json"

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
    """
    Exibe somente fatos da apuração e status oficial do TSE.
    Não faz previsão própria de eleição.
    """
    if df.empty:
        return df

    out = df.copy().reset_index(drop=True)
    out["Posição atual"] = range(1, len(out) + 1)

    def oficial(stt):
        s = str(stt).lower()
        if "não eleito" in s or "nao eleito" in s:
            return "Não eleito"
        if "supl" in s:
            return "Suplente"
        if "eleit" in s:
            return "Eleito"
        return "Em apuração"

    out["Situação TSE"] = out["Status TSE"].map(oficial)
    return out


def infer_party_status(status_tse):
    s = str(status_tse).lower()
    if "não eleito" in s or "nao eleito" in s:
        return "Não eleito"
    if "supl" in s:
        return "Suplente"
    if "eleit" in s:
        return "Eleito"
    return "Em apuração"

def top_por_partido(df, n=20):
    if df.empty:
        return {}
    col = "Partido/Coligação"
    grupos = {}
    for partido, g in df.groupby(col, dropna=False):
        gg = g.sort_values(["Votos", "Nome"], ascending=[False, True]).head(n).copy()
        gg.insert(0, "Posição no grupo", range(1, len(gg) + 1))
        gg["Situação TSE"] = gg["Status TSE"].map(infer_party_status)
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
    "Atualização automática a cada 15 minutos. Versão 1.11 — resultados municipais das 15 maiores cidades da Bahia por eleitorado."
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
    "🏙️ 15 Maiores Cidades — BA",
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

            resultado_df = parse_candidates(data)
            df = merge_registry_results(president_registry(), resultado_df)
            tot = parse_totalizacao(data).get("percentual", 0.0)
            if tot <= 0:
                tot = parse_totalizacao(acomp).get("percentual", 0.0)

            st.markdown(f"### {rotulo}")
            st.progress(min(max(tot / 100, 0.0), 1.0), text=f"Seções totalizadas: {tot:.2f}%")

            if df.empty:
                st.info("Resultado ainda indisponível nesse arquivo.")
            else:
                st.dataframe(
                    df[["Nome","Número","Partido/Coligação","Votos","% válidos","Status TSE"]],
                    use_container_width=True,
                    hide_index=True
                )
                save_snapshot(df, f"presidente_{abr.lower()}", tot)

with tabs[1]:
    st.subheader("Senado — todas as UFs")
    st.caption(
        "Duas vagas por UF. O painel mostra posição atual, votos, diferença entre 2º e 3º "
        "e somente a situação oficial informada pelo TSE."
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
            ds[["Posição atual","Nome","Partido/Coligação","Votos","% válidos","Situação TSE"]],
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

    resultado_df = parse_candidates(data)
    cadastro_df = load_candidate_registry(uf_df, 6)
    df = merge_registry_results(cadastro_df, resultado_df)
    tot = parse_totalizacao(data).get("percentual", 0.0)
    if tot <= 0:
        tot = parse_totalizacao(acomp).get("percentual", 0.0)

    st.progress(min(max(tot / 100, 0.0), 1.0), text=f"Seções totalizadas: {tot:.2f}%")

    st.caption(
        "Cadastro de candidaturas: Portal de Dados Abertos do TSE. "
        "Antes da apuração, os votos aparecem zerados; depois, permanecem apenas os 20 mais votados de cada partido/federação."
    )

    if df.empty:
        st.info("Cadastro de candidaturas temporariamente indisponível.")
    else:
        grupos = top_por_partido(df, 20)
        for partido, g in grupos.items():
            with st.expander(f"{partido} — Top {min(20, len(g))}", expanded=False):
                st.dataframe(
                    g[["Posição no grupo","Nome","Número","Partido/Coligação","Votos","Situação TSE"]],
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

    resultado_df = parse_candidates(data)
    cadastro_df = load_candidate_registry("BA", 7)
    df = merge_registry_results(cadastro_df, resultado_df)
    tot = parse_totalizacao(data).get("percentual", 0.0)
    if tot <= 0:
        tot = parse_totalizacao(acomp).get("percentual", 0.0)

    st.progress(min(max(tot / 100, 0.0), 1.0), text=f"Seções totalizadas: {tot:.2f}%")

    st.caption(
        "Cadastro de candidaturas: Portal de Dados Abertos do TSE. "
        "Antes da apuração, os votos aparecem zerados; depois, permanecem apenas os 20 mais votados de cada partido/federação."
    )

    if df.empty:
        st.info("Cadastro de candidaturas da ALBA temporariamente indisponível.")
    else:
        grupos = top_por_partido(df, 20)
        for partido, g in grupos.items():
            with st.expander(f"{partido} — Top {min(20, len(g))}", expanded=False):
                st.dataframe(
                    g[["Posição no grupo","Nome","Número","Partido/Coligação","Votos","Situação TSE"]],
                    use_container_width=True,
                    hide_index=True
                )
        save_snapshot(df, "alba_bahia", tot)

with tabs[4]:
    st.subheader("15 maiores colégios eleitorais da Bahia")
    st.caption(
        "Ranking calculado pelo número de eleitores no arquivo oficial Perfil do Eleitorado 2026 do TSE. "
        "Escolha uma cidade para ver os candidatos mais votados no município."
    )

    municipios_ba = load_top_ba_municipios(15)

    if municipios_ba.empty:
        st.warning(
            "Não foi possível carregar o ranking municipal do eleitorado neste momento. "
            "Tente novamente em alguns minutos."
        )
    else:
        ranking_exibicao = municipios_ba[["Posição", "Município", "Eleitores"]].copy()
        ranking_exibicao["Eleitores"] = ranking_exibicao["Eleitores"].astype(int)
        st.dataframe(
            ranking_exibicao,
            use_container_width=True,
            hide_index=True
        )

        opcoes = municipios_ba["Município"].tolist()
        cidade_sel = st.selectbox(
            "Selecione uma das 15 cidades",
            opcoes,
            index=0,
            key="cidade_ba_top15"
        )

        cidade_row = municipios_ba[
            municipios_ba["Município"] == cidade_sel
        ].iloc[0]

        codigo_mun = cidade_row["Código"]
        eleitores_mun = int(cidade_row["Eleitores"])

        st.markdown(f"### {cidade_sel}")
        st.caption(
            f"Eleitorado: {eleitores_mun:,} eleitores • código TSE do município: {codigo_mun}"
            .replace(",", ".")
        )

        url_pres_mun = url_resultado_municipio(
            "BA", codigo_mun, "0001", ELEICAO_FEDERAL
        )
        url_dfed_mun = url_resultado_municipio(
            "BA", codigo_mun, "0006", ELEICAO_ESTADUAL
        )
        url_dest_mun = url_resultado_municipio(
            "BA", codigo_mun, "0007", ELEICAO_ESTADUAL
        )

        pres_data, pres_err = safe_get(url_pres_mun)
        dfed_data, dfed_err = safe_get(url_dfed_mun)
        dest_data, dest_err = safe_get(url_dest_mun)

        diagnostico.append((f"Presidente {cidade_sel}", url_pres_mun, pres_err))
        diagnostico.append((f"Deputado Federal {cidade_sel}", url_dfed_mun, dfed_err))
        diagnostico.append((f"Deputado Estadual {cidade_sel}", url_dest_mun, dest_err))

        pres_df = top_municipal(parse_candidates(pres_data), 3)
        dfed_df = top_municipal(parse_candidates(dfed_data), 10)
        dest_df = top_municipal(parse_candidates(dest_data), 10)

        t_pres, t_dfed, t_dest = st.tabs([
            "🇧🇷 Presidente — Top 3",
            "🏢 Federal — Top 10",
            "🌴 Estadual — Top 10",
        ])

        with t_pres:
            if pres_df.empty:
                st.info("Aguardando votos totalizados para Presidente neste município.")
            else:
                pres_show = pres_df[
                    ["Nome", "Número", "Partido/Coligação", "Votos", "% válidos"]
                ].copy()
                pres_show.insert(0, "Posição", range(1, len(pres_show) + 1))
                st.dataframe(
                    pres_show,
                    use_container_width=True,
                    hide_index=True
                )

        with t_dfed:
            if dfed_df.empty:
                st.info("Aguardando votos totalizados para Deputado Federal neste município.")
            else:
                dfed_show = dfed_df[
                    ["Nome", "Número", "Partido/Coligação", "Votos", "% válidos", "Status TSE"]
                ].copy()
                dfed_show.insert(0, "Posição", range(1, len(dfed_show) + 1))
                st.dataframe(
                    dfed_show,
                    use_container_width=True,
                    hide_index=True
                )

        with t_dest:
            if dest_df.empty:
                st.info("Aguardando votos totalizados para Deputado Estadual neste município.")
            else:
                dest_show = dest_df[
                    ["Nome", "Número", "Partido/Coligação", "Votos", "% válidos", "Status TSE"]
                ].copy()
                dest_show.insert(0, "Posição", range(1, len(dest_show) + 1))
                st.dataframe(
                    dest_show,
                    use_container_width=True,
                    hide_index=True
                )


with tabs[5]:
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

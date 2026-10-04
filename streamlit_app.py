import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests
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
    "User-Agent": "Painel-Eleicoes-2026/1.0",
    "Accept": "application/json,text/plain,*/*",
}

HIST = Path("historico")
HIST.mkdir(exist_ok=True)

st.set_page_config(
    page_title="Eleições 2026 - TSE",
    page_icon="🗳️",
    layout="wide"
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

@st.cache_data(ttl=14 * 60, show_spinner=False)
def get_json(url):
    r = requests.get(url, headers=HEADERS, timeout=20)
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
    if df.empty:
        return
    now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    cp = df.copy()
    cp.insert(0, "Atualização", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    if totalizacao is not None:
        cp.insert(1, "Seções totalizadas (%)", totalizacao)
    cp.to_csv(HIST / f"{nome}_{now}.csv", index=False, encoding="utf-8-sig")

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

c1, c2, c3 = st.columns([1.2, 1, 1])
with c1:
    st.metric("Atualização local", datetime.now().strftime("%d/%m/%Y %H:%M"))
with c2:
    st.metric("Intervalo automático", "15 min")
with c3:
    st.metric("Fonte", "TSE — resultados.tse.jus.br")

st.caption(
    "O painel consulta diretamente os arquivos JSON públicos do TSE. "
    "Atualização automática a cada 15 minutos. Versão 1.1 — endpoints oficiais 2026 corrigidos."
)

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

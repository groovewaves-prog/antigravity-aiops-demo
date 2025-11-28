import streamlit as st
import graphviz
import os
import google.generativeai as genai

# 既存のロジックをインポート
from data import TOPOLOGY, SOPS
from logic import CausalInferenceEngine, Alarm

st.set_page_config(page_title="AIOps Agent (Gemini Flash)", page_icon="⚡", layout="wide")

# --- 関数: トポロジー図の生成 ---
def render_topology(alarms, root_cause_node):
    graph = graphviz.Digraph()
    graph.attr(rankdir='TB')
    graph.attr('node', shape='box', style='rounded,filled', fontname='Helvetica')
    
    alarmed_ids = {a.device_id for a in alarms}
    
    for node_id, node in TOPOLOGY.items():
        color = "#e8f5e9" # Default Green
        penwidth = "1"
        fontcolor = "black"
        label = f"{node_id}\n({node.type})"
        
        if root_cause_node and node_id == root_cause_node.id:
            color = "#ffcdd2" # Root Cause Red
            penwidth = "3"
            label += "\n[ROOT CAUSE]"
        elif node_id in alarmed_ids:
            color = "#fff9c4" # Alarm Yellow
        
        graph.node(node_id, label=label, fillcolor=color, color='black', penwidth=penwidth, fontcolor=fontcolor)
    
    for node_id, node in TOPOLOGY.items():
        if node.parent_id:
            graph.edge(node.parent_id, node_id)
            
    return graph

# --- 関数: Gemini Flash レポート生成 (安定化設定済み) ---
def generate_gemini_response(inference_result, sop_text, api_key):
    if not api_key:
        return "⚠️ API Key not found."
    
    try:
        genai.configure(api_key=api_key)
        
        # 設定: 温度を0にして回答を固定化
        generation_config = {
            "temperature": 0.0,
            "max_output_tokens": 1000,
        }

        # モデル初期化 (Flashモデル)
        model = genai.GenerativeModel(
            model_name='gemini-2.0-flash',
            generation_config=generation_config
        )
        
        prompt = f"""
        あなたはAIOpsダッシュボードのAIオペレータです。
        以下の障害情報に基づき、運用チームへレポートしてください。
        
        **根本原因**: {inference_result.root_cause_reason}
        **推奨SOP**: {sop_text}
        
        要件:
        1. 緊急度を絵文字で表現 (🚨, ⚠️)。
        2. 状況を簡潔に要約。
        3. 「参照SOP」を明確に提示。
        4. Markdown形式。
        """
        
        response = model.generate_content(prompt)
        
        # 安全フィルター判定
        if response.parts:
            return response.text
        else:
            # ブロックされた場合のフォールバック
            return f"⚠️ Response blocked by safety filters. Reason: {response.prompt_feedback}"
            
    except Exception as e:
        return f"Gemini API Error: {e}"

# --- UI構築 ---
st.title("⚡ AIOps Agent (Gemini Flash Edition)")
st.markdown("Powered by **Metadata Inference** & **Google Gemini 2.0 Flash**")

# APIキー取得 (Secrets優先 -> 環境変数 -> 手動入力)
api_key = None
if "GOOGLE_API_KEY" in st.secrets:
    api_key = st.secrets["GOOGLE_API_KEY"]
else:
    api_key = os.environ.get("GOOGLE_API_KEY")

with st.sidebar:
    st.header("⚡ 障害注入テスト")
    scenario = st.radio("障害シナリオを選択:", ("正常稼働", "1. WAN全回線断", "2. FW片系障害", "3. L2SWサイレント障害"))
    
    st.markdown("---")
    if api_key:
        st.success("API Connected")
    else:
        st.warning("API Key Missing")
        user_key = st.text_input("Google API Key", type="password")
        if user_key: api_key = user_key

alarms = []
root_cause = None

# シナリオ分岐
if scenario == "1. WAN全回線断":
    alarms = [
        Alarm("WAN_ROUTER_01", "Interface Down", "CRITICAL"),
        Alarm("FW_01_PRIMARY", "Gateway Unreachable", "WARNING"),
        Alarm("FW_01_SECONDARY", "Gateway Unreachable", "WARNING"),
        Alarm("CORE_SW_01", "Uplink Down", "WARNING"),
        Alarm("AP_01", "Unreachable", "CRITICAL")
    ]
elif scenario == "2. FW片系障害":
    alarms = [
        Alarm("FW_01_PRIMARY", "Heartbeat Loss", "WARNING"),
        Alarm("FW_01_PRIMARY", "System Crash", "CRITICAL")
    ]
elif scenario == "3. L2SWサイレント障害":
    alarms = [
        Alarm("AP_01", "Connection Lost", "CRITICAL"),
        Alarm("AP_02", "Connection Lost", "CRITICAL")
    ]

# 推論エンジン実行
engine = CausalInferenceEngine(TOPOLOGY)
inference_result = engine.analyze_alarms(alarms)
root_cause = inference_result.root_cause_node
sop_text = SOPS.get(inference_result.sop_key, "")

# レイアウト描画
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("🌐 Network Topology")
    graph = render_topology(alarms, root_cause)
    st.graphviz_chart(graph, use_container_width=True)
    
    if root_cause:
        st.error(f"🚨 Root Cause: **{root_cause.id}**")
        st.caption(f"Reason: {inference_result.root_cause_reason}")
    else:
        st.success("✅ System Normal")

with col2:
    st.subheader("🤖 AI Analyst Report")
    if scenario != "Normal":
        with st.chat_message("assistant", avatar="⚡"):
            if api_key:
                with st.spinner("Gemini is analyzing causality..."):
                    report = generate_gemini_response(inference_result, sop_text, api_key)
                    st.markdown(report)
            else:
                st.error("Please set GOOGLE_API_KEY to see the AI report.")
    else:
        st.info("No active incidents. System is healthy.")

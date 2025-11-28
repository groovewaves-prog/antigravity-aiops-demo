import streamlit as st
import graphviz
import time
import os
import anthropic

# 既存のロジックをインポート
from data import TOPOLOGY, SOPS
from logic import CausalInferenceEngine, Alarm

# --- 設定 ---
st.set_page_config(
    page_title="Autonomous AIOps Agent",
    page_icon="🤖",
    layout="wide"
)

# --- 関数: トポロジー図の生成 (変更なし) ---
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
            color = "#ffcdd2" # Root Cause (Red)
            penwidth = "3"
            label += "\n[ROOT CAUSE]"
        elif node_id in alarmed_ids:
            color = "#fff9c4" # Alarm (Yellow)
        
        graph.node(node_id, label=label, fillcolor=color, color='black', penwidth=penwidth, fontcolor=fontcolor)
    
    for node_id, node in TOPOLOGY.items():
        if node.parent_id:
            graph.edge(node.parent_id, node_id)
            
    return graph

# --- 関数: AIレポート生成 (Claude対応版) ---
def generate_claude_response(inference_result, sop_text, api_key):
    if not api_key:
        return "⚠️ API Key not found. Please set ANTHROPIC_API_KEY."
    
    try:
        client = anthropic.Anthropic(api_key=api_key)
        
        prompt = f"""
        あなたは自律型AIOpsダッシュボードのAIオペレータです。
        以下の障害分析結果に基づき、運用チームへのチャットメッセージを作成してください。
        
        **根本原因**: {inference_result.root_cause_reason}
        **推奨SOP**: {sop_text}
        
        要件:
        1. 緊急度を絵文字で表現してください (🚨, ⚠️, 👻 など)。
        2. 状況を簡潔に説明してください。
        3. 「参照すべきSOP」を明確なリンク形式または太字で提示してください。
        4. マークダウンで見やすく整形してください。
        """
        
        message = client.messages.create(
            model="claude-4-5-sonnet-20250930", # 最新のSonnetを使用
            max_tokens=1000,
            temperature=0.7,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        return message.content[0].text
        
    except Exception as e:
        return f"Error connecting to Claude API: {e}"

# --- UI構築 ---

st.title("🤖 Autonomous AIOps Dashboard")
st.markdown("Metadata-Driven Causal Inference & Claude 3.5 Sonnet")

# APIキー取得ロジック (Secrets優先)
api_key = None
if "ANTHROPIC_API_KEY" in st.secrets:
    api_key = st.secrets["ANTHROPIC_API_KEY"]
else:
    api_key = os.environ.get("ANTHROPIC_API_KEY")

# サイドバー
with st.sidebar:
    st.header("⚡ Fault Injection (障害注入)")
    scenario = st.radio(
        "発生させる障害シナリオを選択:",
        ("正常稼働 (Normal)", "1. WAN全回線断", "2. FW片系障害", "3. L2SWサイレント障害")
    )
    st.markdown("---")
    if api_key:
        st.success("🟢 AI Core Connected")
    else:
        st.warning("🔴 API Key Missing")
        # ローカル動作確認用に手動入力欄を表示
        user_input_key = st.text_input("Enter Claude API Key", type="password")
        if user_input_key:
            api_key = user_input_key

# メインロジック
alarms = []
root_cause = None

if scenario == "1. WAN全回線断":
    alarms = [
        Alarm("WAN_ROUTER_01", "Interface Down", "CRITICAL"),
        Alarm("FW_01_PRIMARY", "Gateway Unreachable", "WARNING"),
        Alarm("FW_01_SECONDARY", "Gateway Unreachable", "WARNING"),
        Alarm("CORE_SW_01", "Uplink Down", "WARNING"),
        Alarm("AP_01", "Controller Unreachable", "CRITICAL")
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

# 推論実行
engine = CausalInferenceEngine(TOPOLOGY)
inference_result = engine.analyze_alarms(alarms)
root_cause = inference_result.root_cause_node
sop_key = inference_result.sop_key
sop_text = SOPS.get(sop_key, "")

# 画面レイアウト
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("🌐 Network Topology")
    graph = render_topology(alarms, root_cause)
    st.graphviz_chart(graph, use_container_width=True)
    
    if root_cause:
        st.error(f"🚨 Root Cause: **{root_cause.id}**")
        st.info(f"Reason: {inference_result.root_cause_reason}")
    else:
        st.success("✅ System Normal")

with col2:
    st.subheader("💬 AI Analyst Report")
    
    if "messages" not in st.session_state:
        st.session_state.messages = []
        st.session_state.messages.append({"role": "assistant", "content": "System monitoring started."})

    if scenario != "正常稼働 (Normal)":
        with st.chat_message("assistant", avatar="🤖"):
            with st.spinner("Claude is analyzing..."):
                if api_key:
                    response = generate_claude_response(inference_result, sop_text, api_key)
                    st.markdown(response)
                else:
                    st.error("API Keyが必要です。")
    else:
        st.info("No active incidents.")

import streamlit as st
import graphviz
import time
import os
import google.generativeai as genai

# 既存のロジックをインポート
from data import TOPOLOGY, SOPS, NetworkNode
from logic import CausalInferenceEngine, Alarm

# --- 設定 ---
st.set_page_config(
    page_title="Google Antigravity AIOps",
    page_icon="🤖",
    layout="wide"
)

# APIキーの取得 (環境変数 or サイドバー入力)
api_key = os.environ.get("GOOGLE_API_KEY")

# --- 関数: トポロジー図の生成 ---
def render_topology(alarms, root_cause_node):
    """
    Graphvizを使って現在のネットワーク状態を描画する
    """
    graph = graphviz.Digraph()
    graph.attr(rankdir='TB') # 上から下へ
    graph.attr('node', shape='box', style='rounded,filled', fontname='Helvetica')
    
    # アラームが出ている機器IDのセット
    alarmed_ids = {a.device_id for a in alarms}
    
    # ノードの描画
    for node_id, node in TOPOLOGY.items():
        color = "#e8f5e9" # Default Green (正常)
        penwidth = "1"
        fontcolor = "black"
        label = f"{node_id}\n({node.type})"
        
        # 状態による色分け
        if root_cause_node and node_id == root_cause_node.id:
            # 根本原因 (激しい赤)
            color = "#ffcdd2" 
            penwidth = "3"
            label += "\n[ROOT CAUSE]"
        elif node_id in alarmed_ids:
            # アラーム発報中 (オレンジ/黄色)
            color = "#fff9c4"
        
        graph.node(node_id, label=label, fillcolor=color, color='black', penwidth=penwidth, fontcolor=fontcolor)
    
    # エッジ（接続）の描画
    for node_id, node in TOPOLOGY.items():
        if node.parent_id:
            graph.edge(node.parent_id, node_id)
            
    return graph

# --- 関数: AIレポート生成 (main.pyから移植・調整) ---
def generate_gemini_response(inference_result, sop_text, api_key):
    if not api_key:
        return "⚠️ API Key not found. Please set GOOGLE_API_KEY."
    
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-pro')
    
    prompt = f"""
    あなたはGoogle Antigravity DashboardのAIオペレータです。
    以下の障害分析結果に基づき、運用チームへのチャットメッセージを作成してください。
    
    **根本原因**: {inference_result.root_cause_reason}
    **推奨SOP**: {sop_text}
    
    要件:
    1. 緊急度を絵文字で表現してください (🚨, ⚠️, 👻 など)。
    2. 状況を簡潔に説明してください。
    3. 「参照すべきSOP」を明確なリンク形式または太字で提示してください。
    4. マークダウンで見やすく整形してください。
    """
    
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Error connecting to Antigravity Core: {e}"

# --- UI構築 ---

# タイトルエリア
st.title("🤖 Google Antigravity AIOps Dashboard")
st.markdown("Metadata-Driven Causal Inference & Generative AI Operation")

# サイドバー: 障害注入シナリオ
with st.sidebar:
    st.header("⚡ Fault Injection (障害注入)")
    
    scenario = st.radio(
        "発生させる障害シナリオを選択:",
        ("正常稼働 (Normal)", "1. WAN全回線断", "2. FW片系障害", "3. L2SWサイレント障害")
    )
    
    st.markdown("---")
    st.markdown("**System Status**")
    if not api_key:
        api_key = st.text_input("Google API Key", type="password")
        if api_key:
            os.environ["GOOGLE_API_KEY"] = api_key
            st.success("API Key Set!")
        else:
            st.error("API Key Missing")
    else:
        st.success("🟢 Antigravity Core Connected")

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

# 推論エンジンの実行
engine = CausalInferenceEngine(TOPOLOGY)
inference_result = engine.analyze_alarms(alarms)
root_cause = inference_result.root_cause_node
sop_key = inference_result.sop_key
sop_text = SOPS.get(sop_key, "")

# --- 画面レイアウト ---
col1, col2 = st.columns([1, 1])

# 左カラム: トポロジー図
with col1:
    st.subheader("🌐 Network Topology (Real-time)")
    graph = render_topology(alarms, root_cause)
    st.graphviz_chart(graph, use_container_width=True)
    
    if root_cause:
        st.error(f"🚨 Detected Root Cause: **{root_cause.id}**")
        st.info(f"Reason: {inference_result.root_cause_reason}")
    else:
        st.success("✅ System All Green. No Anomalies Detected.")

# 右カラム: AIチャットボット
with col2:
    st.subheader("💬 Antigravity Agent Chat")
    
    # チャット履歴の初期化
    if "messages" not in st.session_state:
        st.session_state.messages = []
        # 初期挨拶
        st.session_state.messages.append({"role": "assistant", "content": "Antigravity Agent is online. Monitoring system telemetry..."})

    # シナリオが変更されたらAIが発言するトリガー
    # (簡易実装として、現在のアラーム状態に基づいて最新レポートを表示する)
    
    if scenario != "正常稼働 (Normal)":
        with st.chat_message("assistant", avatar="🤖"):
            with st.spinner("Analyzing telemetry & Thinking..."):
                # ここでGeminiを呼び出し
                if api_key:
                    ai_response = generate_gemini_response(inference_result, sop_text, api_key)
                else:
                    ai_response = "API Keyが必要です。"
                st.markdown(ai_response)
    else:
        with st.chat_message("assistant", avatar="🤖"):
            st.markdown("システムは正常です。アラームは検知されていません。")

    # ユーザーが追加で質問できる欄（オプション）
    if prompt := st.chat_input("Ask Antigravity about this incident..."):
        with st.chat_message("user"):
            st.markdown(prompt)
        # ここに対話ロジックを追加することも可能

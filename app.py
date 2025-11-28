import streamlit as st
import graphviz
import os
import google.generativeai as genai

# データとロジックのインポート
from data import TOPOLOGY
from logic import CausalInferenceEngine, Alarm

st.set_page_config(page_title="Antigravity Chat (Gemini 2.0 Flash)", page_icon="💬", layout="wide")

# --- 関数: トポロジー図 (冗長構成対応版) ---
def render_topology(alarms, root_cause_node):
    graph = graphviz.Digraph()
    graph.attr(rankdir='TB')
    graph.attr('node', shape='box', style='rounded,filled', fontname='Helvetica')
    
    alarmed_ids = {a.device_id for a in alarms}
    
    # ノード描画
    for node_id, node in TOPOLOGY.items():
        color = "#e8f5e9"
        penwidth = "1"
        if root_cause_node and node_id == root_cause_node.id:
            color = "#ffcdd2"
            penwidth = "3"
        elif node_id in alarmed_ids:
            color = "#fff9c4"
        graph.node(node_id, label=f"{node_id}\n({node.type})", fillcolor=color, color='black', penwidth=penwidth)
    
    # エッジ描画 (冗長構成対応)
    for node_id, node in TOPOLOGY.items():
        if node.parent_id:
            graph.edge(node.parent_id, node_id)
            
            # 親がHAグループの場合、相方からも線を引く
            parent_node = TOPOLOGY.get(node.parent_id)
            if parent_node and parent_node.redundancy_group:
                partners = [n.id for n in TOPOLOGY.values() 
                           if n.redundancy_group == parent_node.redundancy_group and n.id != parent_node.id]
                for partner_id in partners:
                    graph.edge(partner_id, node_id)
    return graph

# --- 関数: Config自動読み込み (IDベース) ---
def load_config_by_id(device_id):
    """
    configsフォルダから {device_id}.txt を探して読み込む
    """
    if not device_id:
        return None
        
    # 命名規則: configs/機器ID.txt
    config_path = f"configs/{device_id}.txt"
    
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception:
            return None
    return None

# --- UI & チャットロジック ---
st.title("💬 Antigravity AI Agent")

# APIキー設定
api_key = None
if "GOOGLE_API_KEY" in st.secrets:
    api_key = st.secrets["GOOGLE_API_KEY"]
else:
    api_key = os.environ.get("GOOGLE_API_KEY")

# サイドバー設定
with st.sidebar:
    st.header("⚡ 障害注入テスト")
    selected_scenario = st.radio("障害シナリオ:", ("正常稼働", "1. WAN全回線断", "2. FW片系障害", "3. L2SWサイレント障害"))
    
    st.markdown("---")
    if api_key:
        st.success("API Connected")
    else:
        st.warning("API Key Missing")
        user_key = st.text_input("Google API Key", type="password")
        if user_key: api_key = user_key

# セッション状態管理
if "current_scenario" not in st.session_state:
    st.session_state.current_scenario = "正常稼働"
    st.session_state.messages = []
    st.session_state.chat_session = None 

if st.session_state.current_scenario != selected_scenario:
    st.session_state.current_scenario = selected_scenario
    st.session_state.messages = []
    st.session_state.chat_session = None
    st.rerun()

# アラーム生成
alarms = []
root_cause = None
inference_result = None

if selected_scenario == "1. WAN全回線断":
    alarms = [
        Alarm("WAN_ROUTER_01", "Interface Down", "CRITICAL"),
        Alarm("FW_01_PRIMARY", "Gateway Unreachable", "WARNING"),
        Alarm("CORE_SW_01", "Uplink Down", "WARNING"),
        Alarm("AP_01", "Unreachable", "CRITICAL")
    ]
elif selected_scenario == "2. FW片系障害":
    alarms = [Alarm("FW_01_PRIMARY", "Heartbeat Loss", "WARNING")]
elif selected_scenario == "3. L2SWサイレント障害":
    alarms = [Alarm("AP_01", "Connection Lost", "CRITICAL"), Alarm("AP_02", "Connection Lost", "CRITICAL")]

# 推論実行
if alarms:
    engine = CausalInferenceEngine(TOPOLOGY)
    inference_result = engine.analyze_alarms(alarms)
    root_cause = inference_result.root_cause_node

# --- 画面レイアウト ---
col1, col2 = st.columns([1, 1])

# 左：トポロジー図
with col1:
    st.subheader("Network Topology")
    st.graphviz_chart(render_topology(alarms, root_cause), use_container_width=True)
    if root_cause:
        st.markdown(
            f'<div style="color: #d32f2f; font-weight: bold; font-size: 15px; background-color: #fdecea; padding: 10px; border-radius: 5px;">'
            f'🚨 緊急アラート：{root_cause.id} ダウン'
            f'</div>', 
            unsafe_allow_html=True
        )
        st.caption(f"理由: {inference_result.root_cause_reason}")

# 右：チャットインターフェース
with col2:
    st.subheader("AI Operator Chat")

    if not api_key:
        st.error("APIキーを設定してください")
        st.stop()

    if st.session_state.chat_session is None and selected_scenario != "正常稼働":
        genai.configure(api_key=api_key)
        
        # Gemini 2.0 Flash 設定 (安定出力)
        generation_config = {
            "temperature": 0.0,
            "max_output_tokens": 1000,
        }
        model = genai.GenerativeModel("gemini-2.0-flash", generation_config=generation_config)
        
        # Configファイルの自動読み込み (IDベース)
        device_id = root_cause.id
        config_content = load_config_by_id(device_id)
        
        # システムプロンプト構築
        system_prompt = f"""
        あなたはネットワーク運用のエキスパートAIです。
        現在、以下の障害が発生しています。Config情報がある場合はそれを踏まえて、エンジニアと対話しながら復旧を支援してください。

        【障害状況】
        - 根本原因機器: {device_id} ({root_cause.type})
        - 推論理由: {inference_result.root_cause_reason}
        """

        if config_content:
            system_prompt += f"""
            【Config情報あり (Source: configs/{device_id}.txt)】
            以下の設定内容に基づき、確認すべきプロトコル状態やコマンドを具体的に提案してください。
            ```text
            {config_content}
            ```
            """
        else:
            system_prompt += f"""
            【Config情報なし】
            設定ファイルが見つかりませんでした。一般的な {root_cause.type} のトラブルシューティング手順を提案してください。
            """

        system_prompt += "\n最初のメッセージとして、状況の要約と、Configの有無に基づいた具体的なネクストアクションを提示してください。"

        # チャット開始
        history = [{"role": "user", "parts": [system_prompt]}]
        chat = model.start_chat(history=history)
        
        try:
            response = chat.send_message("状況報告をお願いします。")
            st.session_state.chat_session = chat
            st.session_state.messages.append({"role": "assistant", "content": response.text})
        except Exception as e:
            st.error(f"Error: {e}")

    # チャット履歴表示
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # 入力エリア
    if prompt := st.chat_input("AIエージェントに指示..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        if st.session_state.chat_session:
            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    try:
                        response = st.session_state.chat_session.send_message(prompt)
                        st.markdown(response.text)
                        st.session_state.messages.append({"role": "assistant", "content": response.text})
                    except Exception as e:
                        st.error(f"Error: {e}")

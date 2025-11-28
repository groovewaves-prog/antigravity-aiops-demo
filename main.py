"""
AIOps Agent CLI - Main Module (Claude 4.5 Sonnet Edition)
"""

import os
import sys
import time
import anthropic
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich.markdown import Markdown
from rich.progress import Progress, SpinnerColumn, TextColumn

from data import TOPOLOGY, SOPS
from logic import CausalInferenceEngine, Alarm

# Richコンソールの初期化
console = Console()

def print_header():
    console.clear()
    console.print(Panel.fit(
        "[bold white]AUTONOMOUS AIOps AGENT[/bold white]\n[cyan]Powered by Claude 3.5 Sonnet[/cyan]",
        style="bold purple",
        subtitle="v2.0.0"
    ))

def get_api_key():
    """
    環境変数からAPIキーを取得します。
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        console.print("[bold red]エラー: 環境変数 ANTHROPIC_API_KEY が見つかりません。[/bold red]")
        console.print("続行するにはAPIキーを設定してください。")
        # デモ用に続行するか、終了するかを選択
        if Prompt.ask("APIキーなしでロジックのみ実行しますか？", choices=["y", "n"], default="y") == "n":
            sys.exit(1)
        return None
    return api_key

def generate_ai_report(inference_result, sop_content, api_key):
    """
    Claudeを使用して自然言語レポートを生成します。
    """
    if not api_key:
        return "⚠️ APIキーがないため、レポート生成をスキップしました。"

    client = anthropic.Anthropic(api_key=api_key)
    
    prompt = f"""
    あなたは熟練したAIOpsエンジニアです。
    以下の障害分析結果に基づき、運用チームへのインシデントレポートを作成してください。
    
    **根本原因**: {inference_result.root_cause_reason}
    **影響デバイス**: {inference_result.root_cause_node.id if inference_result.root_cause_node else "不明"}
    **推奨SOP**:
    {sop_content}
    
    **タスク**:
    日本語で簡潔かつプロフェッショナルなレポートを作成してください。
    1. 状況の要約
    2. 推論ロジックの解説（なぜその機器が原因か）
    3. 次のアクション（SOPへの誘導）を明確に記述
    4. 緊急度に応じた絵文字を使用
    """
    
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
        ) as progress:
            progress.add_task(description="[purple]Claude is thinking...[/purple]", total=None)
            
            message = client.messages.create(
                model="claude-4-5-sonnet-20250930",
                max_tokens=1000,
                temperature=0.7,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
        return message.content[0].text
    
    except Exception as e:
        return f"Claude API Error: {e}"

def run_scenario(scenario_id, api_key):
    engine = CausalInferenceEngine(TOPOLOGY)
    alarms = []
    
    if scenario_id == "1":
        # WAN 全断
        alarms = [
            Alarm("WAN_ROUTER_01", "Interface Down", "CRITICAL"),
            Alarm("FW_01_PRIMARY", "Gateway Unreachable", "WARNING"),
            Alarm("CORE_SW_01", "Uplink Down", "WARNING"),
            Alarm("AP_01", "Controller Unreachable", "CRITICAL")
        ]
    elif scenario_id == "2":
        # FW 片系障害
        alarms = [
            Alarm("FW_01_PRIMARY", "Heartbeat Loss", "WARNING"),
            Alarm("FW_01_PRIMARY", "System Crash", "CRITICAL")
        ]
    elif scenario_id == "3":
        # L2 サイレント障害
        alarms = [
            Alarm("AP_01", "Connection Lost", "CRITICAL"),
            Alarm("AP_02", "Connection Lost", "CRITICAL")
        ]
    else:
        console.print("[red]無効なシナリオです[/red]")
        return

    # アラーム表示
    table = Table(title="受信テレメトリ")
    table.add_column("デバイス", style="cyan")
    table.add_column("重要度", style="magenta")
    table.add_column("メッセージ", style="white")
    
    for alarm in alarms:
        table.add_row(alarm.device_id, alarm.severity, alarm.message)
    
    console.print(table)
    console.print("\n[bold yellow]因果推論エンジンを実行中...[/bold yellow]")
    time.sleep(1) 
    
    result = engine.analyze_alarms(alarms)
    
    console.print(f"[bold green]特定された根本原因:[/bold green] {result.root_cause_reason}")
    
    # SOP取得
    sop = SOPS.get(result.sop_key, SOPS["DEFAULT"])
    
    # AIレポート生成
    console.print("\n[bold purple]Claude レポート生成中...[/bold purple]")
    report = generate_ai_report(result, sop, api_key)
    console.print(Panel(Markdown(report), title="AI Incident Report", border_style="green"))

def main():
    print_header()
    api_key = get_api_key()

    while True:
        console.print("\n[bold]障害シミュレーションを選択してください:[/bold]")
        console.print("1. WAN 全断 (階層ルール)")
        console.print("2. FW 片系障害 (冗長性ルール)")
        console.print("3. L2スイッチ サイレント障害 (推論ルール)")
        console.print("q. 終了")
        
        choice = Prompt.ask("選択", choices=["1", "2", "3", "q"], default="1")
        
        if choice == "q":
            break
            
        run_scenario(choice, api_key)
        
        if Prompt.ask("\n別のシミュレーションを実行しますか？", choices=["y", "n"], default="y") == "n":
            break

if __name__ == "__main__":
    main()


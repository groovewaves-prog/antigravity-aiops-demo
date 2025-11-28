import os
import sys
import time
import google.generativeai as genai
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.markdown import Markdown

from data import TOPOLOGY, SOPS
from logic import CausalInferenceEngine, Alarm

console = Console()

def generate_report(inference_result, sop_text):
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return "⚠️ API Key not set."
    
    try:
        genai.configure(api_key=api_key)
        
        # 安定化設定
        generation_config = {
            "temperature": 0.0,
            "max_output_tokens": 1000,
        }
        
        model = genai.GenerativeModel(
            model_name='gemini-2.0-flash',
            generation_config=generation_config
        )
        
        prompt = f"""
        障害レポートを作成してください。
        根本原因: {inference_result.root_cause_reason}
        SOP: {sop_text}
        """
        
        response = model.generate_content(prompt)
        
        if response.parts:
            return response.text
        else:
            return f"⚠️ Blocked: {response.prompt_feedback}"
            
    except Exception as e:
        return f"Error: {e}"

def run_scenario(scenario_id):
    engine = CausalInferenceEngine(TOPOLOGY)
    alarms = []
    
    if scenario_id == "1":
        alarms = [Alarm("WAN_ROUTER_01", "Down", "CRITICAL")]
    elif scenario_id == "2":
        alarms = [Alarm("FW_01_PRIMARY", "Warning", "WARNING")]
    elif scenario_id == "3":
        alarms = [Alarm("AP_01", "Down", "CRITICAL"), Alarm("AP_02", "Down", "CRITICAL")]
    else:
        console.print("[red]Invalid Selection[/red]")
        return
        
    result = engine.analyze_alarms(alarms)
    sop = SOPS.get(result.sop_key, "")
    
    console.print(f"[green]Root Cause Identified: {result.root_cause_reason}[/green]")
    
    console.print("[yellow]Gemini Flash is generating report...[/yellow]")
    report = generate_report(result, sop)
    console.print(Panel(Markdown(report), title="Gemini 2.0 Flash Report", border_style="blue"))

def main():
    while True:
        console.print("\n1: WAN, 2: FW, 3: Silent L2, q: Quit")
        c = Prompt.ask("Select Scenario", default="1")
        if c == "q": break
        run_scenario(c)

if __name__ == "__main__":
    main()


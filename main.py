import os
import sys
import time
import google.generativeai as genai
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.markdown import Markdown

from data import TOPOLOGY
from logic import CausalInferenceEngine, Alarm

console = Console()

def load_config_by_id(device_id):
    path = f"configs/{device_id}.txt"
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return None

def generate_report(inference_result):
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return "⚠️ API Key not set."
    
    try:
        genai.configure(api_key=api_key)
        
        generation_config = {"temperature": 0.0, "max_output_tokens": 1000}
        model = genai.GenerativeModel('gemini-2.0-flash', generation_config=generation_config)
        
        root = inference_result.root_cause_node
        config = load_config_by_id(root.id)
        
        prompt = f"""
        障害レポートを作成してください。
        原因: {inference_result.root_cause_reason}
        機器: {root.id}
        """
        
        if config:
            prompt += f"\nConfig:\n{config}\nConfigに基づいた具体的な手順を提示してください。"
        else:
            prompt += "\n一般的な復旧手順を提示してください。"
            
        response = model.generate_content(prompt)
        return response.text
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
        return

    result = engine.analyze_alarms(alarms)
    console.print(f"[green]Root Cause: {result.root_cause_reason}[/green]")
    
    console.print("[yellow]Gemini 2.0 Flash Generating Report...[/yellow]")
    report = generate_report(result)
    console.print(Panel(Markdown(report), title="Gemini Report", border_style="blue"))

def main():
    while True:
        c = Prompt.ask("Select (1, 2, 3, q)", default="1")
        if c == "q": break
        run_scenario(c)

if __name__ == "__main__":
    main()

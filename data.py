"""
Google Antigravity AIOps Agent - データモジュール
ネットワーク構成（トポロジー）のメタデータを定義します。
Configファイルのパス指定は廃止し、IDベースの自動解決に移行しました。
"""

from typing import Dict, Optional
from dataclasses import dataclass

@dataclass
class NetworkNode:
    id: str
    layer: int
    type: str
    parent_id: Optional[str] = None
    redundancy_group: Optional[str] = None

# Antigravity ネットワークトポロジー定義
# 機器IDは configs/フォルダ内のファイル名(例: WAN_ROUTER_01.txt)と一致させる必要があります。

TOPOLOGY: Dict[str, NetworkNode] = {
    # Layer 1: WAN Edge
    "WAN_ROUTER_01": NetworkNode("WAN_ROUTER_01", 1, "ROUTER"),
    
    # Layer 2: Firewall HA Pair
    "FW_01_PRIMARY":   NetworkNode("FW_01_PRIMARY",   2, "FIREWALL", "WAN_ROUTER_01", "FW_HA_GROUP"),
    "FW_01_SECONDARY": NetworkNode("FW_01_SECONDARY", 2, "FIREWALL", "WAN_ROUTER_01", "FW_HA_GROUP"),
    
    # Layer 3: Core Switch
    "CORE_SW_01": NetworkNode("CORE_SW_01", 3, "SWITCH", "FW_01_PRIMARY"),
    
    # Layer 4: Floor Switches
    "L2_SW_01": NetworkNode("L2_SW_01", 4, "SWITCH", "CORE_SW_01"),
    "L2_SW_02": NetworkNode("L2_SW_02", 4, "SWITCH", "CORE_SW_01"),
    
    # Layer 5: Access Points
    "AP_01": NetworkNode("AP_01", 5, "ACCESS_POINT", "L2_SW_01"),
    "AP_02": NetworkNode("AP_02", 5, "ACCESS_POINT", "L2_SW_01"),
    "AP_03": NetworkNode("AP_03", 5, "ACCESS_POINT", "L2_SW_02"),
    "AP_04": NetworkNode("AP_04", 5, "ACCESS_POINT", "L2_SW_02"),
}

# SOPテンプレート定義（SOPテキストそのものではなく、AIへの指示書）
SOP_TEMPLATES = {} # 今回はConfig読み込みとAI生成に任せるため、明示的なテンプレートは必須ではありませんが互換性のため残します

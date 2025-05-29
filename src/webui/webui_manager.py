import json
from collections.abc import Generator
from typing import TYPE_CHECKING
import os
import gradio as gr
from datetime import datetime
from typing import Optional, Dict, List
import uuid
import asyncio

from gradio.components import Component
from browser_use.browser.browser import Browser
from browser_use.browser.context import BrowserContext
from browser_use.agent.service import Agent
from src.browser.custom_browser import CustomBrowser
from src.browser.custom_context import CustomBrowserContext
from src.controller.custom_controller import CustomController
from src.agent.deep_research.deep_research_agent import DeepResearchAgent


class WebuiManager:
    def __init__(self, settings_save_dir: str = "./tmp/webui_settings"):
        self.id_to_component: dict[str, Component] = {}
        self.component_to_id: dict[Component, str] = {}

        self.settings_save_dir = settings_save_dir
        os.makedirs(self.settings_save_dir, exist_ok=True)

        # Add mapping for session_id to unique task_id
        self.session_to_task_mapping: Dict[str, str] = {}
        self.mapping_file = os.path.join(self.settings_save_dir, "session_mapping.json")
        self._load_session_mapping()

    def _load_session_mapping(self):
        """Load session mapping from disk"""
        try:
            if os.path.exists(self.mapping_file):
                with open(self.mapping_file, 'r') as f:
                    self.session_to_task_mapping = json.load(f)
                print(f"📂 Loaded {len(self.session_to_task_mapping)} session mappings from disk")
        except Exception as e:
            print(f"❌ Error loading session mapping: {e}")
            self.session_to_task_mapping = {}
    
    def _save_session_mapping(self):
        """Save session mapping to disk"""
        try:
            with open(self.mapping_file, 'w') as f:
                json.dump(self.session_to_task_mapping, f, indent=2)
            print(f"💾 Saved {len(self.session_to_task_mapping)} session mappings to disk")
        except Exception as e:
            print(f"❌ Error saving session mapping: {e}")
    
    def add_session_mapping(self, session_id: str, task_id: str):
        """Add a session to task mapping and persist it"""
        self.session_to_task_mapping[session_id] = task_id
        self._save_session_mapping()
        print(f"🔗 Added mapping: {session_id} -> {task_id}")
    
    def remove_session_mapping(self, session_id: str):
        """Remove a session mapping and persist the change"""
        if session_id in self.session_to_task_mapping:
            del self.session_to_task_mapping[session_id]
            self._save_session_mapping()
            print(f"🗑️ Removed mapping for session: {session_id}")
    
    def get_task_id_for_session(self, session_id: str) -> Optional[str]:
        """Get the task ID for a given session ID"""
        return self.session_to_task_mapping.get(session_id)

    def init_browser_use_agent(self) -> None:
        """
        init browser use agent
        """
        self.bu_agent: Optional[Agent] = None
        self.bu_browser: Optional[CustomBrowser] = None
        self.bu_browser_context: Optional[CustomBrowserContext] = None
        self.bu_controller: Optional[CustomController] = None
        self.bu_chat_history: List[Dict[str, Optional[str]]] = []
        self.bu_response_event: Optional[asyncio.Event] = None
        self.bu_user_help_response: Optional[str] = None
        self.bu_current_task: Optional[asyncio.Task] = None
        self.bu_agent_task_id: Optional[str] = None

    def init_deep_research_agent(self) -> None:
        """
        init deep research agent
        """
        self.dr_agent: Optional[DeepResearchAgent] = None
        self.dr_current_task = None
        self.dr_agent_task_id: Optional[str] = None
        self.dr_save_dir: Optional[str] = None

    def add_components(self, tab_name: str, components_dict: dict[str, "Component"]) -> None:
        """
        Add tab components
        """
        for comp_name, component in components_dict.items():
            comp_id = f"{tab_name}.{comp_name}"
            self.id_to_component[comp_id] = component
            self.component_to_id[component] = comp_id

    def get_components(self) -> list["Component"]:
        """
        Get all components
        """
        return list(self.id_to_component.values())

    def get_component_by_id(self, comp_id: str) -> "Component":
        """
        Get component by id
        """
        return self.id_to_component[comp_id]

    def get_id_by_component(self, comp: "Component") -> str:
        """
        Get id by component
        """
        return self.component_to_id[comp]

    def save_config(self, components: Dict["Component", str]) -> str:
        """
        Save the current configuration to a JSON file.
        
        Args:
            components: Dictionary mapping components to their values
            
        Returns:
            str: Path to the saved configuration file
        """
        config_name = f"config_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        config_file = os.path.join(self.settings_save_dir, f"{config_name}.json")
        
        cur_settings = {}
        for comp, value in components.items():
            comp_id = self.get_id_by_component(comp)
            if comp_id:
                cur_settings[comp_id] = value

        with open(config_file, "w") as fw:
            json.dump(cur_settings, fw, indent=4)

        return os.path.join(self.settings_save_dir, f"{config_name}.json")

    def load_config(self, config_path: str):
        """
        Load configuration from a JSON file and return component updates.
        
        Args:
            config_path: Path to the configuration file
            
        Returns:
            Dict mapping components to their updated values
        """
        update_components = {}
        if os.path.exists(config_path):
            with open(config_path, "r") as fr:
                config_data = json.load(fr)
            
            for comp_id, comp_val in config_data.items():
                comp = self.id_to_component[comp_id]
                if comp.__class__.__name__ == "Chatbot":
                    update_components[comp] = comp.__class__(value=comp_val)
                else:
                    update_components[comp] = comp.__class__(value=comp_val)

        return update_components

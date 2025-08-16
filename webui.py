import os
import argparse
import asyncio
import threading
import json
import time
import random
import string
import uuid
from fastapi import FastAPI, Request, BackgroundTasks, Header, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from typing import Optional
from pydantic import BaseModel

load_dotenv()

from src.webui.interface import theme_map, create_ui
from src.webui.webui_manager import WebuiManager
from src.webui.components.browser_use_agent_tab import run_agent_task
from src.utils import llm_provider

# Create directories if they don't exist
os.makedirs("./tmp", exist_ok=True)
os.makedirs("./tmp/agent_history", exist_ok=True)
os.makedirs("./tmp/downloads", exist_ok=True)

# Get API key from environment variable
API_KEY = os.environ.get("BROWSER_SERVICE_API_KEY")
if not API_KEY:
    raise ValueError("BROWSER_SERVICE_API_KEY environment variable must be set. API cannot start without it.")

# Get allowed origins from environment variable
ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "https://6kfncr9i25.eu-central-1.awsapprunner.com")
if ALLOWED_ORIGINS:
    ALLOWED_ORIGINS = [origin.strip() for origin in ALLOWED_ORIGINS.split(",")]
else:
    # Fallback to AppRunner URL only
    ALLOWED_ORIGINS = ["https://6kfncr9i25.eu-central-1.awsapprunner.com"]

print(f"✅ CORS configured to allow requests only from: {ALLOWED_ORIGINS}")

# Create WebUI manager for agent state management
webui_manager = WebuiManager()

# Create FastAPI app for backend communication
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-API-Key"],
)

# Mount static files for agent history access
app.mount("/tmp", StaticFiles(directory="./tmp"), name="agent_files")

# API key verification dependency
async def verify_api_key(x_api_key: Optional[str] = Header(None)):
    if x_api_key is None:
        raise HTTPException(status_code=401, detail="API Key header is missing")
        
    if x_api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API Key")
        
    return True

@app.post("/execute-task")
async def execute_task(request: Request, background_tasks: BackgroundTasks, authorized: bool = Depends(verify_api_key)):
    """Execute a browser task using the existing WebUI agent infrastructure"""
    try:
        # Parse and validate the request data
        data = await request.json()
        task = data.get("task")
        
        if not task:
            return {"success": False, "error": "No task provided"}
        
        # Generate a session ID if one wasn't provided
        # Format: timestamp-random_string
        session_id = data.get("session_id")
        if not session_id:
            timestamp = int(time.time() * 1000)
            random_str = ''.join(
                random.choices(string.ascii_lowercase + string.digits, k=5)
            )
            session_id = f"{timestamp}-{random_str}"
        
        # print(f"Received task: {task}, session_id: {session_id}")
        
        # Check if there's an active task already running
        if hasattr(webui_manager, "bu_agent") and webui_manager.bu_agent:
            agent_state = webui_manager.bu_agent.state
            if (not agent_state.stopped and not agent_state.paused 
                and getattr(webui_manager, "bu_current_task", None)):
                return {
                    "success": False,
                    "error": "Another task is currently running. "
                            "Please wait for it to complete or stop it first.",
                    "current_session": getattr(webui_manager, "bu_agent_task_id", None)
                }
        
        # Initialize WebUI manager components if needed
        if not hasattr(webui_manager, "bu_chat_history"):
            webui_manager.init_browser_use_agent()
            
        # Add task to chat history (mimics user input)
        webui_manager.bu_chat_history.append({"role": "user", "content": task})
        
        # Start task execution in background
        background_tasks.add_task(process_agent_task, task, session_id)
        
        return {
            "success": True,
            "message": f"Task '{task}' has been queued with session ID {session_id}",
            "session_id": session_id
        }
    except ValueError as ve:
        # Handle validation errors
        print(f"Validation error in execute_task: {ve}")
        return {
            "success": False,
            "error": f"Validation error: {str(ve)}"
        }
    except Exception as e:
        # Handle unexpected errors
        print(f"Error in execute_task: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}"
        }

@app.get("/task-status/{session_id}")
async def task_status(session_id: str, request: Request, detailed: bool = False, minimal: bool = False, authorized: bool = Depends(verify_api_key)):
    """Get status of a browser automation task"""
    try:
        # Check if we have a mapping to the latest task for this session
        current_task_id = webui_manager.get_task_id_for_session(session_id)
        if current_task_id:
            print(f"✅ Found task mapping: {session_id} -> {current_task_id}")
        else:
            # Fallback to current agent task ID
            current_task_id = getattr(webui_manager, "bu_agent_task_id", None)
            if not current_task_id:
                # Final fallback: try to find the most recent task directory
                history_base = "./tmp/agent_history"
                if os.path.exists(history_base):
                    # Look for directories that contain the session_id or are recent
                    task_dirs = [d for d in os.listdir(history_base) 
                               if os.path.isdir(os.path.join(history_base, d))]
                    if task_dirs:
                        # Sort by modification time and get the most recent
                        task_dirs.sort(key=lambda x: os.path.getmtime(os.path.join(history_base, x)), reverse=True)
                        current_task_id = task_dirs[0]
                        print(f"🔄 Using fallback task ID: {current_task_id}")
        
        if not current_task_id:
            return {
                "success": False,
                "status": "not_found",
                "message": "No active task found"
            }
        
        # Check if agent is initialized
        agent = getattr(webui_manager, "bu_agent", None)
        if not agent:
            return {
                "success": False,
                "status": "error",
                "message": "Agent not initialized"
            }
        
        # Get agent state
        state = agent.state
        history = getattr(state, "history", None)
        
        # Determine task status
        task_is_done = history and history.is_done()
        is_stopped = state.stopped
        is_paused = state.paused
        
        # Check for files
        local_history_path = f"./tmp/agent_history/{current_task_id}/{current_task_id}.json"
        local_gif_path = f"./tmp/agent_history/{current_task_id}/{current_task_id}.gif"
        has_history = os.path.exists(local_history_path)
        has_gif = os.path.exists(local_gif_path)
        
        # Determine final status
        status = "running"
        if is_stopped:
            status = "stopped"
        elif is_paused:
            status = "paused"
        elif task_is_done:
            if has_history and has_gif:
                status = "completed"
            elif has_history or has_gif:
                status = "finishing"
            else:
                status = "completed"
        
        # Ultra-minimal response for backend integration
        if minimal:
            return {
                "status": status,
                "task_id": current_task_id,
                "has_files": has_history or has_gif
            }
        
        # Base output path using the current task ID
        output_base_path = f"/tmp/agent_history/{current_task_id}"
        server_base_url = f"{request.url.scheme}://{request.url.netloc}"
        
        # Get output paths using current task ID
        history_path = f"{output_base_path}/{current_task_id}.json"
        gif_path = f"{output_base_path}/{current_task_id}.gif"
        
        # For completed tasks, wait longer for files to be created
        if task_is_done and not detailed:
            print(f"🏁 Task {current_task_id} marked as done by agent, waiting for files...")
            wait_count = 0
            max_wait_attempts = 10
            
            while (wait_count < max_wait_attempts and 
                  not (os.path.exists(local_history_path) and os.path.exists(local_gif_path))):
                wait_count += 1
                await asyncio.sleep(0.5)
                print(f"   Waiting for files... attempt {wait_count}/{max_wait_attempts}")
                print(f"   History: {os.path.exists(local_history_path)}, GIF: {os.path.exists(local_gif_path)}")
        
        # Prepare basic response data
        final_result_text = ""
        duration_seconds = 0
        total_tokens = 0
        error_messages = []
        steps_data = []
        
        # Extract result information if available
        if history:
            # Get final result text
            final_result_text = history.final_result() or ""
            
            # Get duration and token usage
            duration_seconds = history.total_duration_seconds()
            total_tokens = history.total_input_tokens()
            
            # Get errors
            errors = history.errors()
            if errors and any(errors):
                error_messages = errors
                
            # Only get detailed steps if requested
            if detailed:
                steps = getattr(history, "steps", [])
                if steps:
                    for i, step in enumerate(steps):
                        step_data = {
                            "step_number": i + 1,
                            "action": getattr(step, "action", ""),
                            "status": "completed"
                        }
                        steps_data.append(step_data)
        
        # Basic lightweight response
        response = {
            "success": True,
            "status": status,
            "steps": state.n_steps,
            "session_id": current_task_id,  # Return the actual task ID being used
            "result": {
                "text": final_result_text,
                "success": status == "completed" and not error_messages,
                "duration_seconds": duration_seconds,
                "total_tokens": total_tokens,
                "has_errors": bool(error_messages)
            }
        }
        
        # Add basic URLs if files exist
        if os.path.exists(local_history_path):
            history_url = f"{server_base_url}{history_path}"
            response["historyUrl"] = history_url
            print(f"📄 History URL: {history_url}")
            
        if os.path.exists(local_gif_path):
            gif_url = f"{server_base_url}{gif_path}"
            response["gifUrl"] = gif_url
            print(f"🎬 GIF URL: {gif_url}")
            
        # Only include detailed data if requested
        if detailed:
            response["result"]["steps"] = steps_data
            response["result"]["errors"] = error_messages
            
            # Add full history content
            if os.path.exists(local_history_path):
                try:
                    with open(local_history_path, 'r') as f:
                        history_json_content = json.load(f)
                    response["historyContent"] = history_json_content
                except json.JSONDecodeError as e:
                    print(f"❌ Error parsing history JSON file: {e}")
            
            # Add resource paths
            resource_paths = {}
            
            if os.path.exists(local_history_path):
                resource_paths["history_json"] = {
                    "local_path": local_history_path,
                    "url": response["historyUrl"]
                }
            
            if os.path.exists(local_gif_path):
                resource_paths["recording_gif"] = {
                    "local_path": local_gif_path,
                    "url": response["gifUrl"]
                }
            
            # Add screenshots if available
            screenshots_dir = f"./tmp/agent_history/{current_task_id}"
            if os.path.exists(screenshots_dir):
                screenshot_files = [f for f in os.listdir(screenshots_dir) if f.startswith("step_") and f.endswith(".jpg")]
                if screenshot_files:
                    resource_paths["screenshots"] = []
                    for screenshot in screenshot_files:
                        step_num = screenshot.replace("step_", "").replace(".jpg", "")
                        screenshot_path = f"/tmp/agent_history/{current_task_id}/{screenshot}"
                        resource_paths["screenshots"].append({
                            "step": step_num,
                            "local_path": f"{screenshots_dir}/{screenshot}",
                            "url": f"{server_base_url}{screenshot_path}"
                        })
            
            response["resources"] = resource_paths
        
        # Enhanced logging
        available_resources = []
        if "historyUrl" in response:
            available_resources.append("history")
        if "gifUrl" in response:
            available_resources.append("gif")
            
        print(f"📊 Task {current_task_id} status: {status}")
        print(f"📁 Resources available: {', '.join(available_resources) if available_resources else 'none'}")
        
        return response
        
    except Exception as e:
        print(f"❌ Error in task_status: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "status": "error",
            "error": str(e)
        }

@app.post("/task-cancel/{session_id}")
async def cancel_task(session_id: str, authorized: bool = Depends(verify_api_key)):
    """Cancel a browser automation task by session ID"""
    try:
        # Get the current unique task ID for this session using the new method
        current_task_id = webui_manager.get_task_id_for_session(session_id)
        if not current_task_id:
            current_task_id = getattr(webui_manager, "bu_agent_task_id", None)
        
        agent = getattr(webui_manager, "bu_agent", None)
        
        if not current_task_id or not agent:
            return {
                "success": False,
                "error": "No active task found"
            }
        
        # Stop the agent
        agent.state.stopped = True
        
        # Also cancel any pending task if it exists
        current_task = getattr(webui_manager, "bu_current_task", None)
        if current_task and not current_task.done():
            current_task.cancel()
            
        # Remove the mapping for this session using the new method
        webui_manager.remove_session_mapping(session_id)
            
        return {
            "success": True,
            "message": f"Task with session ID {session_id} (task ID: {current_task_id}) has been cancelled"
        }
    except Exception as e:
        print(f"Error cancelling task: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": f"Error cancelling task: {str(e)}"
        }

# Helper function to process agent task
async def process_agent_task(task, session_id):
    """Process the agent task using the existing WebUI infrastructure"""
    print(f"Starting agent task: {task}")
    
    # Generate a unique task_id for this specific task execution
    # This ensures each task gets its own directory and files
    timestamp = int(time.time() * 1000)
    random_str = ''.join(
        random.choices(string.ascii_lowercase + string.digits, k=8)
    )
    unique_task_id = f"task-{timestamp}-{random_str}"
    
    print(f"Generated unique task ID: {unique_task_id} for session: {session_id}")
    
    # Initialize WebUI manager if needed
    if not hasattr(webui_manager, "bu_chat_history"):
        webui_manager.init_browser_use_agent()
    
    # Clear previous chat history and reset it for new task
    webui_manager.bu_chat_history = []
    webui_manager.bu_chat_history.append({"role": "user", "content": task})
    
    # Set the unique task ID instead of reusing session_id
    webui_manager.bu_agent_task_id = unique_task_id
    
    # Create required directories for output files
    os.makedirs("./tmp/agent_history", exist_ok=True)
    os.makedirs("./tmp/downloads", exist_ok=True)
    
    # Create task-specific directory using the unique task ID
    task_dir = f"./tmp/agent_history/{unique_task_id}"
    os.makedirs(task_dir, exist_ok=True)
    
    try:
        # Check if we should keep the browser open between tasks
        persistent_session = os.environ.get("CHROME_PERSISTENT_SESSION", "true").lower() in ["true", "1", "yes", "y"]
        
        # Initialize LLM
        from src.agent.browser_use.browser_use_agent import BrowserUseAgent
        from src.browser.custom_browser import CustomBrowser
        from src.browser.custom_context import CustomBrowserContextConfig
        from browser_use.browser.browser import BrowserConfig
        from browser_use.browser.context import BrowserContextWindowSize
        from browser_use.browser.views import BrowserState
        from browser_use.agent.views import AgentOutput, AgentHistoryList
        
        # Initialize the LLM - use appropriate provider and model
        default_provider = os.environ.get("DEFAULT_LLM_PROVIDER", "openai")
        default_model = os.environ.get("DEFAULT_LLM_MODEL", "gpt-4o")
        
        llm = llm_provider.get_llm_model(
            provider=default_provider,
            model_name=default_model,
            temperature=0.2
        )
        
        # Reuse existing browser if persistent_session is enabled and browser exists
        if persistent_session and hasattr(webui_manager, "bu_browser") and webui_manager.bu_browser:
            print("🔄 Reusing existing browser instance as CHROME_PERSISTENT_SESSION=true")
            # Clean up only the agent, not the browser
            if hasattr(webui_manager, "bu_agent") and webui_manager.bu_agent:
                try:
                    webui_manager.bu_agent.state.stopped = True
                    webui_manager.bu_agent = None
                except Exception as e:
                    print(f"⚠️ Warning during agent cleanup: {e}")
        else:
            # Create a fresh browser instance if we don't have one or persistence is disabled
            print("🌐 Creating new browser instance")
            
            # Clean up previous browser and agent if they exist
            if hasattr(webui_manager, "bu_agent") and webui_manager.bu_agent:
                try:
                    webui_manager.bu_agent.state.stopped = True
                    webui_manager.bu_agent = None
                except Exception as e:
                    print(f"⚠️ Warning during agent cleanup: {e}")
                    
            if hasattr(webui_manager, "bu_browser") and webui_manager.bu_browser:
                try:
                    await webui_manager.bu_browser.close()
                    webui_manager.bu_browser = None
                    webui_manager.bu_browser_context = None
                except Exception as e:
                    print(f"⚠️ Warning during browser cleanup: {e}")
            
            browser_config = BrowserConfig(
                headless=False,
                disable_security=True,
                extra_browser_args=[
                    "--disable-default-apps", 
                    "--start-maximized", 
                    "--kiosk", 
                    "--window-size=9999,9999", 
                    "--start-fullscreen",
                    "--ash-force-desktop"
                ]
            )
            
            webui_manager.bu_browser = CustomBrowser(config=browser_config)
            
            # Create browser context
            context_config = CustomBrowserContextConfig(
                browser_window_size=BrowserContextWindowSize(width=1920, height=1080),
                save_downloads_path="./tmp/downloads",
                force_new_context=True
            )
            webui_manager.bu_browser_context = await webui_manager.bu_browser.new_context(config=context_config)
            
            # Configure browser for full screen
            try:
                playwright_browser = webui_manager.bu_browser.playwright_browser
                if playwright_browser and hasattr(playwright_browser, "contexts") and len(playwright_browser.contexts) > 0:
                    context = playwright_browser.contexts[0]
                    pages = context.pages
                    if len(pages) == 0:
                        page = await context.new_page()
                    else:
                        page = pages[0]
                    
                    # Imposta la modalità schermo intero sia tramite JavaScript che tramite CSS
                    await page.evaluate("""() => {
                        document.documentElement.requestFullscreen().catch(e => console.error('Fullscreen error:', e));
                        if (window.screen) {
                            window.resizeTo(window.screen.availWidth, window.screen.availHeight);
                            window.moveTo(0, 0);
                        }
                        document.documentElement.style.overflow = 'hidden';
                        document.body.style.overflow = 'hidden';
                        document.documentElement.style.margin = '0';
                        document.body.style.margin = '0';
                        document.documentElement.style.padding = '0';
                        document.body.style.padding = '0';
                    }""")
                    
                    # Imposta le dimensioni della viewport al massimo possibile
                    viewport_size = await page.evaluate("""() => {
                        return {
                            width: window.screen ? window.screen.availWidth : 1920,
                            height: window.screen ? window.screen.availHeight : 1080
                        }
                    }""")
                    
                    await page.set_viewport_size(viewport_size)
                    print(f"✅ Browser configurato in modalità schermo intero: {viewport_size}")
            except Exception as e:
                print(f"❌ Error configuring browser for fullscreen: {e}")
        
        # Initialize controller if needed
        if not webui_manager.bu_controller:
            from src.controller.custom_controller import CustomController
            webui_manager.bu_controller = CustomController()
        
        # Define callback functions for step and completion tracking
        async def step_callback(state: BrowserState, output: AgentOutput, step_num: int):
            print(f"Step {step_num} completed for task {unique_task_id}")
            # Save screenshot to disk using the unique task ID
            screenshot_data = getattr(state, "screenshot", None)
            if screenshot_data and isinstance(screenshot_data, str) and len(screenshot_data) > 100:
                screenshot_dir = f"./tmp/agent_history/{unique_task_id}"
                os.makedirs(screenshot_dir, exist_ok=True)
                with open(f"{screenshot_dir}/step_{step_num}.jpg", "wb") as f:
                    import base64
                    f.write(base64.b64decode(screenshot_data))
        
        def done_callback(history: AgentHistoryList):
            print(f"Task {unique_task_id} completed. Duration: {history.total_duration_seconds():.2f}s")
            errors = history.errors()
            if errors and any(errors):
                print(f"Errors during execution: {errors}")
            else:
                print("Status: Success")
                
            final_result = history.final_result()
            if final_result:
                print(f"Final result: {final_result}")
        
        # Set up agent settings for GIF generation using unique task ID
        gif_path = f"{task_dir}/{unique_task_id}.gif"
        
        # Create agent instance
        print(f"🤖 Creating agent instance for task: {unique_task_id}")
        webui_manager.bu_agent = BrowserUseAgent(
            task=task,
            llm=llm,
            browser=webui_manager.bu_browser,
            browser_context=webui_manager.bu_browser_context,
            controller=webui_manager.bu_controller,
            register_new_step_callback=step_callback,
            register_done_callback=done_callback,
            use_vision=True,
            source="api"
        )
        
        # Set the GIF generation path for this specific task
        webui_manager.bu_agent.settings.generate_gif = gif_path
        
        # Set the agent ID to match the unique task ID for complete isolation
        webui_manager.bu_agent.state.agent_id = unique_task_id
        
        # Store the mapping between session_id and unique_task_id
        webui_manager.add_session_mapping(session_id, unique_task_id)
        
        # Legacy compatibility
        if not hasattr(webui_manager, "session_to_task_mapping"):
            webui_manager.session_to_task_mapping = {}
        webui_manager.session_to_task_mapping[session_id] = unique_task_id
        
        print(f"🚀 Running agent for task {unique_task_id}")
        
        # Run the agent with max 30 steps
        await webui_manager.bu_agent.run(max_steps=30)
        
        print(f"✅ Task {unique_task_id} execution completed")
        
        # Save history using unique task ID
        history_file = f"{task_dir}/{unique_task_id}.json"
        webui_manager.bu_agent.save_history(history_file)
        print(f"💾 History saved to: {history_file}")
        
    except Exception as e:
        print(f"❌ Error executing agent task {unique_task_id}: {e}")
        import traceback
        traceback.print_exc()

# Simple healthcheck endpoint - no auth required for this one
@app.get("/healthcheck")
async def healthcheck():
    return {"status": "ok", "message": "API server is running"}

@app.get("/health")
async def health():
    return {"status": "ok", "message": "API server is running"}

@app.get("/task-result/{session_id}")
async def task_result(session_id: str, request: Request, authorized: bool = Depends(verify_api_key)):
    """Get complete results of a finished browser automation task"""
    try:
        # Define paths
        history_dir = f"./tmp/agent_history/{session_id}"
        history_file = f"{history_dir}/{session_id}.json"
        gif_file = f"{history_dir}/{session_id}.gif"
        server_base_url = f"{request.url.scheme}://{request.url.netloc}"
        
        # Check if result exists
        if not os.path.exists(history_file):
            return {
                "success": False,
                "error": f"No results found for session ID: {session_id}"
            }
            
        # Load history data from JSON file
        with open(history_file, 'r') as f:
            try:
                history_data = json.load(f)
            except json.JSONDecodeError:
                return {
                    "success": False,
                    "error": f"Failed to parse history file for session {session_id}"
                }
        
        # Extract key information
        result = {
            "success": True,
            "session_id": session_id,
            "result": {
                "text": history_data.get("final_result", ""),
                "success": history_data.get("success", False),
                "duration_seconds": history_data.get("duration_seconds", 0),
                "steps_completed": len(history_data.get("steps", [])),
                "errors": history_data.get("errors", [])
            },
            "resources": {
                "history_json": {
                    "local_path": history_file,
                    "url": f"{server_base_url}/tmp/agent_history/{session_id}/{session_id}.json"
                }
            }
        }
        
        # Add GIF if it exists
        if os.path.exists(gif_file):
            result["resources"]["recording_gif"] = {
                "local_path": gif_file,
                "url": f"{server_base_url}/tmp/agent_history/{session_id}/{session_id}.gif"
            }
            
        # Add screenshots if available
        screenshot_files = [
            f for f in os.listdir(history_dir) 
            if f.startswith("step_") and f.endswith(".jpg")
        ]
        if screenshot_files:
            result["resources"]["screenshots"] = []
            for screenshot in sorted(screenshot_files):
                step_num = screenshot.replace("step_", "").replace(".jpg", "")
                result["resources"]["screenshots"].append({
                    "step": step_num,
                    "local_path": f"{history_dir}/{screenshot}",
                    "url": f"{server_base_url}/tmp/agent_history/{session_id}/{screenshot}"
                })
                
        # Include steps data if available
        if "steps" in history_data:
            result["steps"] = []
            for i, step in enumerate(history_data["steps"]):
                step_data = {
                    "step_number": i + 1,
                    "action": step.get("action", ""),
                    "result": step.get("result", ""),
                    "status": step.get("status", "completed")
                }
                result["steps"].append(step_data)
                
        return result
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": str(e)
        }

def run_api_server(host, port):
    """Run the FastAPI server in a separate thread"""
    print(f"Starting API server on {host}:{port}")
    uvicorn.run(app, host=host, port=port)

def main():
    parser = argparse.ArgumentParser(description="Web UI")
    parser.add_argument("--ip", type=str, default="localhost", help="IP address to serve on")
    parser.add_argument("--port", type=int, default=7788, help="Port to serve Gradio UI on")
    parser.add_argument("--api-port", type=int, default=7789, help="Port to serve API on")

    args = parser.parse_args()

    # Start API server in a separate thread
    api_thread = threading.Thread(target=run_api_server, args=(args.ip, args.api_port))
    api_thread.daemon = True
    api_thread.start()

    demo = create_ui(theme_name="Ocean")
    demo.queue().launch(server_name=args.ip, server_port=args.port)

if __name__ == '__main__':
    main()

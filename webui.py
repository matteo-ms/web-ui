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
async def task_status(session_id: str, request: Request, authorized: bool = Depends(verify_api_key)):
    """Get status of a browser automation task"""
    try:
        # Check if the agent has a task ID
        agent_task_id = getattr(webui_manager, "bu_agent_task_id", None)
        if not agent_task_id:
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
        
        # Base output path
        output_base_path = f"/tmp/agent_history/{agent_task_id}"
        server_base_url = f"{request.url.scheme}://{request.url.netloc}"
        
        # Get output paths
        history_path = f"{output_base_path}/{agent_task_id}.json"
        gif_path = f"{output_base_path}/{agent_task_id}.gif"
        local_history_path = f"./tmp/agent_history/{agent_task_id}/{agent_task_id}.json"
        local_gif_path = f"./tmp/agent_history/{agent_task_id}/{agent_task_id}.gif"
        
        # Prepare basic response
        status = "running"
        if state.stopped:
            status = "stopped"
        elif state.paused:
            status = "paused"
        elif history and history.is_done():
            # Only mark as completed if all output files exist
            # Wait up to 2 seconds for files to be created before responding
            wait_count = 0
            while (wait_count < 4 and 
                  not (os.path.exists(local_history_path) and 
                       os.path.exists(local_gif_path))):
                wait_count += 1
                time.sleep(0.5)  # Wait briefly for files to be created
                print(f"Waiting for output files to be created, attempt {wait_count}/4")
            
            if os.path.exists(local_history_path) and os.path.exists(local_gif_path):
                status = "completed"
                print(f"Task {agent_task_id} confirmed completed with all resources available")
            else:
                status = "finishing"  # New intermediate status
                print(f"Task {agent_task_id} is done but resources not ready yet. "
                      f"History: {os.path.exists(local_history_path)}, "
                      f"GIF: {os.path.exists(local_gif_path)}")
            
        # Prepare detailed results for Node.js
        steps_data = []
        error_messages = []
        final_result_text = ""
        duration_seconds = 0
        total_tokens = 0
        
        # Extract detailed result information if available
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
                
            # Get steps information if available
            steps = getattr(history, "steps", [])
            if steps:
                for i, step in enumerate(steps):
                    step_data = {
                        "step_number": i + 1,
                        "action": getattr(step, "action", ""),
                        "status": "completed"
                    }
                    steps_data.append(step_data)
        
        response = {
            "success": True,
            "status": status,
            "steps": state.n_steps,
            "session_id": agent_task_id,
            "result": {
                "text": final_result_text,
                "success": status == "completed" and not error_messages,
                "duration_seconds": duration_seconds,
                "total_tokens": total_tokens,
                "steps": steps_data,
                "errors": error_messages
            }
        }
        
        # Add paths if they exist
        resource_paths = {}
        
        # Add history JSON content if file exists
        history_json_content = None
        if os.path.exists(local_history_path):
            resource_paths["history_json"] = {
                "local_path": local_history_path,
                "url": f"{server_base_url}{history_path}"
            }
            response["historyUrl"] = f"{server_base_url}{history_path}"
            
            # Read and include the full history JSON content
            try:
                with open(local_history_path, 'r') as f:
                    history_json_content = json.load(f)
                response["historyContent"] = history_json_content
            except json.JSONDecodeError as e:
                print(f"Error parsing history JSON file: {e}")
        
        if os.path.exists(local_gif_path):
            resource_paths["recording_gif"] = {
                "local_path": local_gif_path,
                "url": f"{server_base_url}{gif_path}"
            }
            response["gifUrl"] = f"{server_base_url}{gif_path}"
            
        # Add screenshots if available
        screenshots_dir = f"./tmp/agent_history/{agent_task_id}"
        if os.path.exists(screenshots_dir):
            screenshot_files = [f for f in os.listdir(screenshots_dir) if f.startswith("step_") and f.endswith(".jpg")]
            if screenshot_files:
                resource_paths["screenshots"] = []
                for screenshot in screenshot_files:
                    step_num = screenshot.replace("step_", "").replace(".jpg", "")
                    screenshot_path = f"/tmp/agent_history/{agent_task_id}/{screenshot}"
                    resource_paths["screenshots"].append({
                        "step": step_num,
                        "local_path": f"{screenshots_dir}/{screenshot}",
                        "url": f"{server_base_url}{screenshot_path}"
                    })
        
        # Add all resource paths to the response
        response["resources"] = resource_paths
        
        # Log the full response to help with debugging
        print(f"Sending task status for {agent_task_id}: {status}, with resources: {list(resource_paths.keys()) if resource_paths else 'none'}")
        
        return response
        
    except Exception as e:
        print(f"Error in task_status: {e}")
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
        # Check if there's a matching task running
        agent_task_id = getattr(webui_manager, "bu_agent_task_id", None)
        agent = getattr(webui_manager, "bu_agent", None)
        
        if not agent_task_id or not agent:
            return {
                "success": False,
                "error": "No active task found"
            }
            
        if agent_task_id != session_id:
            return {
                "success": False, 
                "error": f"Session ID mismatch. Current session is {agent_task_id}, not {session_id}"
            }
        
        # Stop the agent
        agent.state.stopped = True
        
        # Also cancel any pending task if it exists
        current_task = getattr(webui_manager, "bu_current_task", None)
        if current_task and not current_task.done():
            current_task.cancel()
            
        return {
            "success": True,
            "message": f"Task with session ID {session_id} has been cancelled"
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
    
    # Initialize WebUI manager if needed
    if not hasattr(webui_manager, "bu_chat_history"):
        webui_manager.init_browser_use_agent()
    
    # Use the proper initialization methods from the webui_manager
    webui_manager.bu_chat_history.append({"role": "user", "content": task})
    
    # Generate a task ID that matches the session ID format
    webui_manager.bu_agent_task_id = session_id
    
    # Create required directories for output files
    os.makedirs("./tmp/agent_history", exist_ok=True)
    os.makedirs("./tmp/downloads", exist_ok=True)
    
    # Create session-specific directory
    session_dir = f"./tmp/agent_history/{session_id}"
    os.makedirs(session_dir, exist_ok=True)
    
    try:
        # Skip the run_agent_task function and use the agent directly
        if not webui_manager.bu_agent:
            # Initialize the agent if not already done
            from src.agent.browser_use.browser_use_agent import BrowserUseAgent
            from src.browser.custom_browser import CustomBrowser
            from src.browser.custom_context import CustomBrowserContextConfig
            from browser_use.browser.browser import BrowserConfig
            from browser_use.browser.context import BrowserContextWindowSize
            from browser_use.browser.views import BrowserState
            from browser_use.agent.views import AgentOutput, AgentHistoryList
            
            # Initialize the LLM - use appropriate provider and model
            # First check environment variables
            default_provider = os.environ.get("DEFAULT_LLM_PROVIDER", "openai")
            default_model = os.environ.get("DEFAULT_LLM_MODEL", "gpt-4o")
            
            # Initialize LLM
            llm = llm_provider.get_llm_model(
                provider=default_provider,
                model_name=default_model,
                temperature=0.2
            )
            
            # Check if we should connect to the persistent browser
            # Force always creating a new browser by overriding the environment variable
            use_persistent_browser = False  # Ignoriamo la variabile d'ambiente
            
            # Create a new browser instance (always)
            print("Creating new browser instance in incognito mode")
            browser_config = BrowserConfig(
                headless=False,
                disable_security=True,
                extra_browser_args=["--disable-default-apps", "--start-maximized", "--kiosk", "--window-size=1920,1080"]
            )
            
            webui_manager.bu_browser = CustomBrowser(config=browser_config)
            
            # Create browser context with force_new_context=False to use existing window
            context_config = CustomBrowserContextConfig(
                # Utilizziamo dimensioni esplicite a schermo intero
                browser_window_size=BrowserContextWindowSize(
                    width=1920, height=1080  # Dimensioni esplicite per schermo intero
                ),
                save_downloads_path="./tmp/downloads",
                force_new_context=False
            )
            webui_manager.bu_browser_context = await webui_manager.bu_browser.new_context(config=context_config)
            
            # Aggiungiamo configurazione per forzare il browser a schermo intero
            try:
                playwright_browser = webui_manager.bu_browser.playwright_browser
                if playwright_browser and hasattr(playwright_browser, "contexts") and len(playwright_browser.contexts) > 0:
                    context = playwright_browser.contexts[0]
                    # Create a page if none exists
                    pages = context.pages
                    if len(pages) == 0:
                        page = await context.new_page()
                    else:
                        page = pages[0]
                    
                    # Forziamo la modalità schermo intero via CDP
                    await page.evaluate("document.documentElement.requestFullscreen()")
                    await page.evaluate("window.resizeTo(screen.width, screen.height)")
                    print("✅ Browser configurato a risoluzione piena e modalità schermo intero")
            except Exception as e:
                print(f"❌ Error initializing browser context: {e}")
            
            # Initialize controller if needed
            if not webui_manager.bu_controller:
                from src.controller.custom_controller import CustomController
                webui_manager.bu_controller = CustomController()
            
            # Define simple callback functions for step and completion tracking
            async def step_callback(state: BrowserState, output: AgentOutput, step_num: int):
                print(f"Step {step_num} completed.")
                # Save screenshot to disk if available
                screenshot_data = getattr(state, "screenshot", None)
                if screenshot_data and isinstance(screenshot_data, str) and len(screenshot_data) > 100:
                    screenshot_dir = f"./tmp/agent_history/{session_id}"
                    os.makedirs(screenshot_dir, exist_ok=True)
                    with open(f"{screenshot_dir}/step_{step_num}.jpg", "wb") as f:
                        import base64
                        f.write(base64.b64decode(screenshot_data))
            
            def done_callback(history: AgentHistoryList):
                print(f"Task completed. Duration: {history.total_duration_seconds():.2f}s")
                # Check for errors
                errors = history.errors()
                if errors and any(errors):
                    print(f"Errors during execution: {errors}")
                else:
                    print("Status: Success")
                    
                # Save final result
                final_result = history.final_result()
                if final_result:
                    print(f"Final result: {final_result}")
            
            # Set up agent settings for GIF generation
            gif_path = f"{session_dir}/{session_id}.gif"
            
            # Initialize the agent with minimal settings
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
            
            # Set the GIF generation path
            webui_manager.bu_agent.settings.generate_gif = gif_path
        else:
            # If agent already exists, just add a new task
            webui_manager.bu_agent.add_new_task(task)
            
            # Update the GIF generation path for the new session
            gif_path = f"{session_dir}/{session_id}.gif"
            webui_manager.bu_agent.settings.generate_gif = gif_path
        
        # Set the agent ID to match the session ID
        webui_manager.bu_agent.state.agent_id = session_id
        
        # Run the agent directly (max 30 steps)
        await webui_manager.bu_agent.run(max_steps=30)
        
        print(f"Task {session_id} completed")
        
        # Save history
        history_file = f"{session_dir}/{session_id}.json"
        webui_manager.bu_agent.save_history(history_file)
        
    except Exception as e:
        print(f"Error executing agent task: {e}")
        # Add more detailed error logging
        import traceback
        traceback.print_exc()

# Simple healthcheck endpoint - no auth required for this one
@app.get("/healthcheck")
async def healthcheck():
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
    parser = argparse.ArgumentParser(description="Gradio WebUI for Browser Agent")
    
    # Check if running in AWS environment (ECS)
    default_ip = "0.0.0.0" if (os.environ.get("AWS_EXECUTION_ENV") or 
                               os.environ.get("ECS_CONTAINER_METADATA_URI")) else "127.0.0.1"
    
    parser.add_argument("--ip", type=str, default=default_ip, help="IP address to bind to")
    parser.add_argument("--port", type=int, default=7788, help="Port to listen on")
    parser.add_argument("--api-port", type=int, default=7789, help="Port for the API server")
    parser.add_argument("--theme", type=str, default="Ocean", 
                       choices=theme_map.keys(), help="Theme to use for the UI")
    parser.add_argument("--api-only", action="store_true", 
                       help="Run only the API server without the Gradio UI")
    args = parser.parse_args()

    # Always use 0.0.0.0 in production Docker containers for proper networking
    if (os.environ.get("DOCKER_CONTAINER") or os.environ.get("AWS_EXECUTION_ENV") or 
        os.environ.get("ECS_CONTAINER_METADATA_URI")):
        args.ip = "0.0.0.0"
        
    if args.api_only:
        print(f"Starting API server on {args.ip}:{args.port}")
        run_api_server(args.ip, args.port)
    else:
        # Initialize WebUI manager for agent functionality
        global webui_manager
        webui_manager = WebuiManager()
        
        # Start API server in a separate thread with a different port
        api_thread = threading.Thread(
            target=run_api_server,
            args=(args.ip, args.api_port),
            daemon=True
        )
        api_thread.start()
        print(f"API server started on {args.ip}:{args.api_port}")
        
        # Start Gradio UI
    print(f"Starting webui on {args.ip}:{args.port}")
    demo = create_ui(theme_name=args.theme)
    demo.queue().launch(server_name=args.ip, server_port=args.port)

if __name__ == '__main__':
    main()

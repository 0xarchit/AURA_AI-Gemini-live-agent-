from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import json

app = FastAPI(title="Gemini Live Agent API")

import re

class SafetyLayer:
    def __init__(self):
        # Basic heuristic blocklist for common injection patterns
        self.blocklist_patterns = [
            re.compile(r"(?i)\bignore\s+(all\s+)?(previous\s+)?instructions\b"),
            re.compile(r"(?i)\bforget\s+(all\s+)?(previous\s+)?instructions\b"),
            re.compile(r"(?i)\bsystem\s+prompt\b"),
            re.compile(r"(?i)\bdisregard\s+previous\b"),
            re.compile(r"(?i)\byou\s+are\s+now\b"),
            re.compile(r"(?i)\bbypass\b")
        ]

    def check_input(self, text):
        print(f"Safety Layer Shield running on: '{text}'")
        for pattern in self.blocklist_patterns:
            if pattern.search(text):
                print(f"Safety Layer Blocked input! Matched pattern: {pattern.pattern}")
                return False
        return True

# Multi-Agent Architecture (Worker Agents)
class MathAgent:
    def execute(self, task_content):
        print(f"MathAgent processing: {task_content}")
        try:
            allowed_chars = "0123456789+-*/(). "
            if all(c in allowed_chars for c in task_content):
                result = eval(task_content)
                return f"[MathAgent] The calculated result of {task_content} is {result}."
            else:
                return "[MathAgent Error] Invalid characters in math expression."
        except Exception as e:
            return f"[MathAgent Error] Calculation failed: {str(e)}"

class WebSearchAgent:
    def execute(self, task_content):
        print(f"WebSearchAgent processing: {task_content}")
        query_lower = task_content.lower()
        if "weather" in query_lower:
            return "[WebSearchAgent] Top result: The weather is currently sunny and 72 degrees."
        elif "gemini" in query_lower:
            return "[WebSearchAgent] Top result: Gemini is a multimodal AI developed by Google."
        else:
            return f"[WebSearchAgent] Synthesized information about '{task_content}' from multiple sources."

class KnowledgeRetriever:
    def retrieve(self, query, session_history):
        print(f"KnowledgeRetriever fetching context for: {query}")
        # In a real app, this would query a Vector DB. Here we just return recent session history.
        history_summary = " | ".join([f"{msg['role']}: {msg['content']}" for msg in session_history[-3:]])
        return f"Recent Conversation History: {history_summary}"

# Multi-Agent Architecture (Supervisor Agent)
class SupervisorAgent:
    def __init__(self):
        self.math_agent = MathAgent()
        self.search_agent = WebSearchAgent()
        self.retriever = KnowledgeRetriever()

    def process(self, user_input, session_history):
        print(f"Supervisor evaluating: '{user_input}'")
        
        # 1. Retrieve Context
        context = self.retriever.retrieve(user_input, session_history)
        print(f"Supervisor Context: {context}")
        
        # 2. Plan / Intent Recognition
        user_input_lower = user_input.lower()
        worker_response = None
        
        if any(word in user_input_lower for word in ["calculate", "math", "+", "-", "*", "/"]):
            print("Supervisor routing to MathAgent.")
            extracted = user_input_lower
            for word in ["calculate", "math", "what is"]:
                 extracted = extracted.replace(word, "")
            worker_response = self.math_agent.execute(extracted.strip())
            
        elif any(word in user_input_lower for word in ["search", "find", "who is", "what is"]):
            print("Supervisor routing to WebSearchAgent.")
            extracted = user_input.split("search for")[-1].strip() if "search for" in user_input_lower else user_input
            worker_response = self.search_agent.execute(extracted)
        
        else:
            print("Supervisor handling directly (General Chat).")
            
        return worker_response

class GeminiLiveAPI:
    def process(self, user_input, tool_result=None):
        # Simulating the Gemini API processing the input + tool results
        print(f"Gemini generating response for: {user_input}")
        
        if tool_result:
            return {"response": f"Based on my tools: {tool_result}"}
        else:
            return {"response": f"I heard you say: '{user_input}'. How else can I assist you today?"}

import uuid
import time

class FirestoreDatabase:
    def save_message(self, user_id, session_id, role, content, tool_calls=None):
        # Implement proper schema: users/{user_id}/sessions/{session_id}/messages/{message_id}
        message_id = str(uuid.uuid4())
        timestamp = int(time.time() * 1000)
        message_data = {
            "role": role,
            "content": content,
            "timestamp": timestamp,
            "tool_calls": tool_calls
        }
        print(f"Firestore stub: Saving to users/{user_id}/sessions/{session_id}/messages/{message_id}")
        print(f"Data: {message_data}")
        return True

# Initialize components
safety_layer = SafetyLayer()
supervisor = SupervisorAgent()
gemini_api = GeminiLiveAPI()
db = FirestoreDatabase()

# In-memory session store (for mockup purposes instead of constantly fetching from DB)
active_sessions = {}

@app.get("/")
async def root():
    return {"message": "Welcome to the Gemini Live Agent API"}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("Client connected to WebSocket")
    
    # 1. Authentication Phase
    try:
        auth_data_str = await websocket.receive_text()
        auth_data = json.loads(auth_data_str)
        if auth_data.get("type") != "auth" or not auth_data.get("token"):
            await websocket.send_text(json.dumps({"error": "Authentication required."}))
            await websocket.close(code=1008)
            return
            
        # Stub: Verify Firebase Token (In production, use firebase_admin.auth.verify_id_token)
        user_id = auth_data.get("user_id", "anonymous_user")
        session_id = auth_data.get("session_id", str(uuid.uuid4()))
        print(f"User {user_id} authenticated. Session: {session_id}")
        await websocket.send_text(json.dumps({"type": "system", "response": "Authentication successful."}))
        
    except Exception as e:
        print(f"Authentication failed: {e}")
        await websocket.close(code=1008)
        return

    # 2. Active Session Phase
    try:
        while True:
            data = await websocket.receive_text()
            print(f"Received data: {data}")
            
            try:
                message_json = json.loads(data)
                user_text = message_json.get("content", "")
                
                # Manage session history for context
                if session_id not in active_sessions:
                    active_sessions[session_id] = []
                
                session_history = active_sessions[session_id]
                session_history.append({"role": "user", "content": user_text})
                
                # Save user message to DB
                db.save_message(user_id, session_id, "user", user_text)
                
                # 3. Safety Layer Check
                if safety_layer.check_input(user_text):
                    
                    # 4. Supervisor Agent Processing (Routes to Worker Agents + gets context)
                    worker_result = supervisor.process(user_text, session_history)
                    
                    # 5. Gemini Live API Synthesis
                    gemini_response = gemini_api.process(user_text, worker_result)
                    agent_reply = gemini_response.get("response")
                    
                    session_history.append({"role": "agent", "content": agent_reply})
                    
                    # 6. Save agent response to DB
                    db.save_message(user_id, session_id, "agent", agent_reply, tool_calls=worker_result)
                    
                    # 7. Send response back to client
                    await websocket.send_text(json.dumps({"type": "message", "response": agent_reply}))
                else:
                    error_msg = "Input blocked by safety layer: Potential prompt injection detected."
                    db.save_message(user_id, session_id, "system", error_msg)
                    await websocket.send_text(json.dumps({"type": "error", "error": error_msg}))
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({"type": "error", "error": "Invalid JSON"}))
                
    except WebSocketDisconnect:
        print(f"Client {user_id} disconnected from session {session_id}")

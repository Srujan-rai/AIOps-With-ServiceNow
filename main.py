import json
import os
import re
import google.generativeai as genai
from supabase import create_client, Client
from dotenv import load_dotenv
import smtplib
from email.message import EmailMessage
import requests
from langchain_huggingface import HuggingFaceEmbeddings



load_dotenv()

try:
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    genai.configure(api_key=gemini_api_key)
    generation_model = genai.GenerativeModel("gemini-2.5-pro")
except Exception as e:
    print(f"Error configuring Gemini: {e}")
    
try:
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    supabase: Client = create_client(supabase_url, supabase_key)
except Exception as e:
    print(f"Error configuring Supabase: {e}")


def send_email(to_email, subject, content):
    
    msg = EmailMessage()
    msg.set_content(content)
    msg["Subject"] = subject
    msg["From"] = os.getenv("SMTP_FROM_EMAIL")
    msg["To"] = to_email

    smtp_server = os.getenv("SMTP_SERVER")
    smtp_port = int(os.getenv("SMTP_PORT"))
    smtp_user = os.getenv("SMTP_USERNAME")
    smtp_password = os.getenv("SMTP_PASSWORD")

    try:
        if smtp_port == 465:
            with smtplib.SMTP_SSL(smtp_server, smtp_port) as server:
                server.login(smtp_user, smtp_password)
                server.send_message(msg)
        elif smtp_port == 587:
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls()
                server.login(smtp_user, smtp_password)
                server.send_message(msg)
        else:
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.login(smtp_user, smtp_password)
                server.send_message(msg)
        print(f"Successfully sent email to {to_email}")
    except Exception as e:
        print(f"Failed to send email: {e}")
        raise

def find_relevant_sops(text_to_embed, match_threshold=0.75, match_count=5):
    """
    Embeds the input text using a local Hugging Face model and searches Supabase.
    """
    try:
        print(f"Embedding text for search: '{text_to_embed[:50]}...'")
        
        model_name = "sentence-transformers/all-MiniLM-L6-v2"
        embeddings = HuggingFaceEmbeddings(model_name=model_name)
        
        query_embedding = embeddings.embed_query(text_to_embed)

        print("Searching Supabase for relevant SOPs...")
        search_results = supabase.rpc('match_sop_chunks', {
            'query_embedding': query_embedding,
            'match_threshold': match_threshold,
            'match_count': match_count
        }).execute()

        if search_results.data:
            print(f"Found {len(search_results.data)} relevant SOP(s).")
            context_str = "\n".join([f"- {item['content']}" for item in search_results.data])
            return context_str
        else:
            print("No relevant SOPs found.")
            return "No specific SOPs found in the knowledge base for this issue."
    except Exception as e:
        print(f"Error finding relevant SOPs: {e}")
        return "Could not retrieve SOPs due to an error."


def generate_agent_assistance(data):
    
    caller_email = data.get("caller_email", "")
    caller_name = caller_email.split('@')[0].split('.')[0].capitalize() if caller_email else "User"
    
    search_query = f"{data.get('short_description', '')} {data.get('description', '')}"
    sop_context = find_relevant_sops(search_query)

    prompt = f"""
You are an advanced AI assistant for an IT Service Desk agent. Your role is to analyze a newly created incident and provide structured suggestions to help the agent resolve it faster.
You MUST prioritize and base your suggestions on the provided SOP context.

**Relevant SOPs from our Knowledge Base:**
{sop_context}

---
**Analyze the following incident:**
- **Caller Name:** {caller_name}
- **Short Description:** {data.get("short_description")}
- **Description:** {data.get("description", "No additional description provided.")}
- **Urgency:** {data.get("urgency")}
- **Impact:** {data.get("impact")}

**Your Task:**
Generate a JSON object with the following keys. Do NOT include any explanatory text, markdown formatting, or code blocks before or after the JSON object.

1.  `property_suggestion`: An object suggesting ticket properties (priority, category, severity, support_level).
2.  `solution_suggestion`: A string suggesting potential solutions. **Base this directly on the provided SOP context above.** Provide actionable, numbered steps. If no SOPs were found, provide general advice.
3.  `resolution_suggestion`: A string with a concise, resolution note for ticket closure, assuming the solution worked.
4.  `summary`: A brief, summary of the user's core problem.
5.  `email_draft`: A complete, empathetic, and helpful email draft to be sent to the user.
    * Address the user by their `Caller Name` ({caller_name}).
    * Acknowledge the issue clearly.
    * Provide the initial troubleshooting steps from the `solution_suggestion`.
    * End with a friendly closing.

**Important Formatting Rule:**
The entire output must be a single, valid JSON object.
"""
    try:
        use_local_llm = os.getenv("USE_LOCAL_LLM", 'false').lower() == 'true'
        llm_response_text = ""

        if use_local_llm:
            print("Using local Ollama model for generation.")
            ollama_host = os.getenv("OLLAMA_HOST")
            ollama_model = os.getenv("OLLAMA_MODEL")
            ollama_url = f"{ollama_host}/api/generate"
            
            payload = {
                "model": ollama_model,
                "prompt": prompt,
                "stream": False
            }
            
            response = requests.post(ollama_url, json=payload)
            response.raise_for_status() 
            llm_response_text = response.json().get('response', '')

        else:
            print("Using Google Gemini for generation.")
            response = generation_model.generate_content(prompt)
            llm_response_text = response.text

        clean_json_str = re.search(r'\{.*\}', llm_response_text, re.DOTALL).group(0)
        return json.loads(clean_json_str)

    except (json.JSONDecodeError, AttributeError, requests.exceptions.RequestException, Exception) as e:
        print(f"Error processing AI response: {e}")
        return {
            "property_suggestion": {},
            "solution_suggestion": "AI suggestion could not be generated.",
            "resolution_suggestion": "AI suggestion could not be generated.",
            "summary": "AI summary could not be generated.",
            "email_draft": "Could not generate an email draft."
        }

def webhook(request):
    """
    (This function remains unchanged)
    Main Cloud Function entry point. Handles CORS preflight requests and routes
    other requests based on the path.
    - /      -> Handles incident creation/enrichment.
    - /email -> Handles sending the drafted email.
    """
    if request.method == 'OPTIONS':
        headers = {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'POST, GET, OPTIONS',
            'Access-control-Allow-Headers': 'Content-Type',
            'Access-Control-Max-Age': '3600'
        }
        return ('', 204, headers)

    headers = {
        'Access-Control-Allow-Origin': '*'
    }

    path = request.path if request.path else '/'

    if path.endswith('/email'):
        try:
            if not request.is_json:
                return (json.dumps({"error": "Request must be JSON"}), 400, headers)
            
            data = request.get_json()
            ticket_id = data.get("ticket_id")
            if not ticket_id:
                return (json.dumps({"error": "Missing 'ticket_id' in request body"}), 400, headers)

            response = supabase.table("incidents").select("caller_email, email, short_description").eq("ticket_id", ticket_id).single().execute()
            
            incident_data = response.data
            if not incident_data:
                return (json.dumps({"error": f"Incident with ticket_id {ticket_id} not found."}), 404, headers)

            email_subject = f"Update on your request: {incident_data.get('short_description', 'IT Support')}"
            send_email(incident_data['caller_email'], email_subject, incident_data['email'])

            return (json.dumps({"status": "success", "message": f"Email sent for ticket {ticket_id}."}), 200, headers)

        except Exception as e:
            error_message = f"Failed to send email: {e}"
            print(error_message)
            return (json.dumps({"status": "error", "message": error_message}), 500, headers)

    else:
        try:
            if not request.is_json:
                return (json.dumps({"error": "Request must be JSON"}), 400, headers)
            
            data = request.get_json()
            ticket_id = data.get("number") 
            caller_email = data.get("caller_email")

            if not ticket_id or not caller_email:
                return (json.dumps({"error": "Missing 'number' (for ticket_id) or 'caller_email' in request body"}), 400, headers)

            ai_assistance = generate_agent_assistance(data)
            properties = ai_assistance.get("property_suggestion", {})

            db_payload = {
                "ticket_id": ticket_id,
                "caller_email": caller_email,
                "short_description": data.get("short_description"),
                "description": data.get("description"),
                "urgency": data.get("urgency"),
                "impact": data.get("impact"),
                "suggested_priority": properties.get("priority"),
                "suggested_category": properties.get("category"),
                "suggested_severity": properties.get("severity"),
                "suggested_support_level": properties.get("support_level"),
                "solution_suggestion": ai_assistance.get("solution_suggestion"),
                "resolution_suggestion": ai_assistance.get("resolution_suggestion"),
                "summary": ai_assistance.get("summary"),
                "email": ai_assistance.get("email_draft")
            }

            response = supabase.table("incidents").upsert(db_payload).execute()
            if hasattr(response, 'error') and response.error:
                raise Exception(response.error.message)

            return (json.dumps({
                "status": "success",
                "message": f"Incident {ticket_id} processed and saved to Supabase.",
                "data_saved": db_payload
            }), 200, headers)

        except Exception as e:
            error_message = f"Failed to process incident: {e}"
            print(error_message)
            return (json.dumps({"status": "error", "message": error_message}), 500, headers)
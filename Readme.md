# ServiceNow AIOps Incident Assistant

An **AI-powered assistance backend** for IT Service Desk workflows integrated with **ServiceNow**.  
It uses a **Google Cloud Function** to handle incident webhooks, perform **RAG (Retrieval-Augmented Generation)** with data from **Supabase**, and generate structured, actionable insights via **Google Gemini** or a **local Ollama model**.

---

## Features

- **ServiceNow Integration:** Automatically triggered on new incident creation.
- **Vector RAG Search:** Retrieves relevant SOPs using `pgvector` and `HuggingFaceEmbeddings`.
- **Hybrid LLM Support:** Easily switch between **Google Gemini** and **Ollama** via environment variables.
- **Structured AI Responses:** Returns JSON with clear, actionable fields.
- **Persistent Storage:** Saves incidents and AI suggestions to **Supabase**.
- **Automated Email Drafting:** Generates pre-written email replies for end users.

---

## Architecture Overview

1. **Incident Creation:** A user or agent creates a new incident in ServiceNow.
2. **Webhook Trigger:** A Business Rule fires a POST request to the Cloud Function.
3. **Cloud Function:** Receives the incident payload at the `/` endpoint.
4. **RAG Search:**
   - Embeds the incident description using a local `sentence-transformers` model.
   - Queries the `match_sop_chunks` function in Supabase for relevant SOPs.
5. **AI Generation:**
   - Constructs a detailed prompt using incident + SOP data.
   - Sends the prompt to the chosen LLM (Gemini or Ollama).
   - Receives a structured JSON response.
6. **Save Results:** Stores the AI suggestions in the `incidents` Supabase table.
7. **Email Sending (Optional):** The `/email` endpoint can later send the drafted email to the user.

---

## Technology Stack

| Component      | Technology                                                        |
| -------------- | ----------------------------------------------------------------- |
| **Backend**    | Python 3.10+, Google Cloud Functions                              |
| **ServiceNow** | Business Rules (`sn_ws.RESTMessageV2`)                            |
| **Database**   | Supabase (PostgreSQL + `pgvector`)                                |
| **LLMs**       | Google Gemini / Ollama                                            |
| **Embeddings** | `HuggingFaceEmbeddings`, `sentence-transformers`                  |
| **Email**      | Python `smtplib`                                                  |
| **Tooling**    | `supabase-py`, `python-dotenv`, `requests`, `functions-framework` |

---

## Setup and Deployment

### 1. Supabase Project Setup

#### Create and Configure Tables

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE sop_chunks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  content TEXT NOT NULL,
  embedding VECTOR(384)
);
```

#### Vector Search Function

```sql
CREATE OR REPLACE FUNCTION match_sop_chunks (
  query_embedding VECTOR(384),
  match_threshold FLOAT,
  match_count INT
)
RETURNS TABLE (
  id UUID,
  content TEXT,
  similarity FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  SELECT
    sop_chunks.id,
    sop_chunks.content,
    1 - (sop_chunks.embedding <=> query_embedding) AS similarity
  FROM sop_chunks
  WHERE 1 - (sop_chunks.embedding <=> query_embedding) > match_threshold
  ORDER BY similarity DESC
  LIMIT match_count;
END;
$$;
```

#### Incident Storage Table

```sql
CREATE TABLE incidents (
  id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
  ticket_id TEXT NOT NULL UNIQUE,
  caller_email TEXT,
  short_description TEXT,
  description TEXT,
  urgency TEXT,
  impact TEXT,
  suggested_priority TEXT,
  suggested_category TEXT,
  suggested_severity TEXT,
  suggested_support_level TEXT,
  solution_suggestion TEXT,
  resolution_suggestion TEXT,
  summary TEXT,
  email TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);
```

---

### 2. Backend (Google Cloud Function)

#### Clone and Install

```bash
git clone <your-repo-url>
cd <your-repo-name>
pip install -r requirements.txt
```

### 3. ServiceNow Setup

#### Create a Business Rule

- **Name:** `Trigger AI Incident Analysis Webhook`
- **Table:** `Incident [incident]`
- **Active:**
- **Advanced:**

#### When to Run

- **When:** `after`
- **Insert:**
- (Optional) Add filters such as `Assignment group is IT Service Desk`.

## Usage

1. Create a new **Incident** in ServiceNow.
2. The **Business Rule** triggers the webhook to your Cloud Function.
3. Within seconds, a new record appears in your **Supabase `incidents`** table containing:

   - AI-generated summary
   - Suggested priority, category, and resolution
   - Draft email response

## Sending the Email

**Endpoint:**

```
POST https://your-cloud-function-url-here.a.run.app/email
```

**Request Body:**

```json
{
  "ticket_id": "INC0010025"
}
```

The Cloud Function retrieves the incident’s `caller_email` and `email` draft from Supabase and sends it through your SMTP configuration.

import os
from dotenv import load_dotenv
from supabase.client import Client, create_client
from langchain_community.document_loaders import UnstructuredPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import SupabaseVectorStore

load_dotenv()

supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")
if not supabase_url or not supabase_key:
    raise ValueError("Supabase URL or Key not found in environment variables.")
supabase_client: Client = create_client(supabase_url, supabase_key)

model_name = "sentence-transformers/all-MiniLM-L6-v2"
embeddings = HuggingFaceEmbeddings(model_name=model_name)
print("Model initialized.")

doc_path = "sop.pdf"

print(f"Loading document: {doc_path}")
loader = UnstructuredPDFLoader(file_path=doc_path)
data = loader.load()

print("Document loaded. Now chunking...")
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=150,
    separators=["\n\n", "\n", ".", " ", ""]
)
chunks = text_splitter.split_documents(data)
print(f"Document split into {len(chunks)} chunks.")

print("Embedding chunks and storing them in Supabase...")

vector_store = SupabaseVectorStore.from_documents(
    documents=chunks,
    client=supabase_client,
    table_name="sop_chunks",
    query_name="match_sop_chunks"
)

print("\n Processing has been completed!")

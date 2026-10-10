import os
import glob
from dotenv import load_dotenv
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma
import chromadb

load_dotenv()

# We can accept either GEMINI_API_KEY or GOOGLE_API_KEY
api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
if not api_key:
    raise ValueError("API key not found. Please set GEMINI_API_KEY or GOOGLE_API_KEY.")

os.environ["GOOGLE_API_KEY"] = api_key

CHROMA_PERSIST_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "chroma_db")

def ingest_documents():
    print("Ingesting documents...")
    base_dir = os.path.join(os.path.dirname(__file__), "..", "..", "data")
    
    documents = []
    
    # Load general documents
    general_dir = os.path.join(base_dir, "general")
    if os.path.exists(general_dir):
        for filepath in glob.glob(os.path.join(general_dir, "*.txt")):
            loader = TextLoader(filepath)
            docs = loader.load()
            for doc in docs:
                doc.metadata["role"] = "employee"
                doc.metadata["source"] = os.path.basename(filepath)
            documents.extend(docs)

    # Load HR documents
    hr_dir = os.path.join(base_dir, "hr")
    if os.path.exists(hr_dir):
        for filepath in glob.glob(os.path.join(hr_dir, "*.txt")):
            loader = TextLoader(filepath)
            docs = loader.load()
            for doc in docs:
                doc.metadata["role"] = "hr"
                doc.metadata["source"] = os.path.basename(filepath)
            documents.extend(docs)

    if not documents:
        print("No documents found to ingest.")
        return

    text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    splits = text_splitter.split_documents(documents)

    embeddings = GoogleGenerativeAIEmbeddings(model="gemini-embedding-2")
    
    # Initialize Chroma client
    client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
    
    # Create or get collection
    vectorstore = Chroma(   
        client=client,
        collection_name="northwind_docs",
        embedding_function=embeddings,
    )
    
    print(f"Adding {len(splits)} chunks to Chroma...")
    vectorstore.add_documents(documents=splits)
    print("Ingestion complete.")

if __name__ == "__main__":
    ingest_documents()


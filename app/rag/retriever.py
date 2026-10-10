import os
from langchain_chroma import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings
import chromadb

CHROMA_PERSIST_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "chroma_db")

def get_retriever(role: str):
    """
    Returns a retriever that filters documents based on the user's role.
    HR users can access both 'hr' and 'employee' documents.
    Employee users can only access 'employee' documents.
    """
    embeddings = GoogleGenerativeAIEmbeddings(model="gemini-embedding-2")
    client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
    
    vectorstore = Chroma(
        client=client,
        collection_name="northwind_docs",
        embedding_function=embeddings,
    )
    
    # Configure metadata filtering based on role
    if role == "hr":
        filter_dict = {"role": {"$in": ["employee", "hr"]}}
    else:
        # Default to least privilege
        filter_dict = {"role": "employee"}
        
    return vectorstore.as_retriever(
        search_kwargs={"filter": filter_dict, "k": 4}
    )


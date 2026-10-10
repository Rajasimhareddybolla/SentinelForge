from fastapi import FastAPI, Depends, Header, HTTPException
from pydantic import BaseModel
from app.rag.chain import get_rag_chain
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Secure RAG Application", description="Northwind Retail Internal Assistant")

class QueryRequest(BaseModel):
    question: str

class QueryResponse(BaseModel):
    answer: str
    role_used: str

def get_role(x_role: str = Header(default="employee", alias="X-Role")):
    """
    Mock authentication dependency.
    Extracts the user role from the X-Role header.
    Valid roles: 'employee', 'hr'. Defaults to 'employee'.
    """
    role = x_role.lower()
    if role not in ["employee", "hr"]:
        raise HTTPException(status_code=400, detail="Invalid role. Must be 'employee' or 'hr'")
    return role

@app.post("/query", response_model=QueryResponse)
def query_rag(request: QueryRequest, role: str = Depends(get_role)):
    try:
        # Get the chain configured for the specific role
        chain = get_rag_chain(role)
        
        # Execute the query
        answer = chain.invoke(request.question)
        
        # Basic output validation could be added here (e.g., checking for leaked systemic prompts)
        
        return QueryResponse(answer=answer, role_used=role)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)


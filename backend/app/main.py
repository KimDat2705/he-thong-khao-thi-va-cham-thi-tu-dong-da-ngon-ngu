from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Multi-language Automated Examination and Grading System API",
    description="API for managing courses, exams, submissions, auto-grading, and AI evaluation feedback.",
    version="1.0.0",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "Welcome to the AI-Powered Grading System API"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "grading-api"}

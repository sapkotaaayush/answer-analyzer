from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import analyze, parse, reference

app = FastAPI(title="Answer Analyzer API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(parse.router)
app.include_router(analyze.router)
app.include_router(reference.router)
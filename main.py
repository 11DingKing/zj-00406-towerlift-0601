from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import engine, Base
from app.routers import master_data, transport, lifting, stats

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="塔架运输与吊装施工管理系统",
    description="125米塔架上山运输与吊装施工组织管理后端系统",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(master_data.router)
app.include_router(transport.router)
app.include_router(lifting.router)
app.include_router(stats.router)


@app.get("/")
def root():
    return {
        "message": "塔架运输与吊装施工管理系统",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/health")
def health_check():
    return {"status": "healthy"}

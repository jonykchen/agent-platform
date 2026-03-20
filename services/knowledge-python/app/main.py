"""Knowledge Service 主入口"""

from fastapi import FastAPI

from app.api.v1 import documents, search


def create_app() -> FastAPI:
    app = FastAPI(
        title="Knowledge Service",
        description="RAG 知识库服务",
        version="1.0.0",
    )

    app.include_router(documents.router, prefix="/api/v1/documents", tags=["documents"])
    app.include_router(search.router, prefix="/api/v1/search", tags=["search"])

    return app


app = create_app()

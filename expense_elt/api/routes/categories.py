from __future__ import annotations

from fastapi import APIRouter

from config.config_writer import load_categories

router = APIRouter()


@router.get("/categories")
def get_categories() -> list[str]:
    return load_categories()

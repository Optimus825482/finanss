from fastapi import FastAPI

from app.routers import (
    reports, watchlist, portfolio, balance, profile, chat, memory, admin,
    screener, screener_analyze, screener_screen, notifications, predictions,
)


def register_routers(app: FastAPI):
    app.include_router(reports.router)
    app.include_router(watchlist.router)
    app.include_router(portfolio.router)
    app.include_router(balance.router)
    app.include_router(profile.router)
    app.include_router(chat.router)
    app.include_router(memory.router)
    app.include_router(admin.router)
    app.include_router(screener.router)
    app.include_router(screener_analyze.router)
    app.include_router(notifications.router)
    app.include_router(screener_screen.router)
    app.include_router(predictions.router)

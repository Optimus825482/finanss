import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import ChatSessionOut, ChatMessageOut, ChatIn, ChatResponse
from app.services.memory_service import (
    get_or_create_profile, create_chat_session, add_chat_message,
    get_recent_messages, list_sessions, build_context_for_ticker, search_similar_memories,
)
from app.services.llm_bridge import generate, get_default_model

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def api_chat(body: ChatIn, db: Session = Depends(get_db)):
    """LLM destekli sohbet. Hafiza sistemini kullanarak baglam olusturur."""
    session_id = body.session_id
    if not session_id:
        session = create_chat_session(db, title=body.message[:60])
        session_id = session.id

    history = get_recent_messages(db, session_id, limit=10)
    profile = get_or_create_profile(db)

    ticker_match = re.search(r'\b([A-Z]{2,5}(?:\.[A-Z]{2})?)\b', body.message.upper())
    detected_ticker = ticker_match.group(1) if ticker_match else None

    context_parts = []
    if detected_ticker:
        context_parts.append(build_context_for_ticker(db, detected_ticker))

    similar = await search_similar_memories(db, body.message, ticker=detected_ticker, top_k=3)
    if similar:
        context_parts.append("## Ilgili Gecmis Analizler")
        for s in similar:
            context_parts.append(f"- [{s['ticker']}] {s['topic']}: {s['summary'][:200]}")

    context = "\n\n".join(context_parts) if context_parts else "Henuz kayitli hafiza yok."

    system_prompt = f"""Sen ORBIS FINAI arastirma asistanisin. Kullaniciya yatirim arastirmalarinda yardimci olursun.

Kullanici profili:
- Risk toleransi: {profile.risk_tolerance}
- Yatirim stili: {profile.investment_style}
- Tercih ettigi piyasalar: {', '.join(profile.preferred_markets or [])}

Hafiza baglami:
{context}

Yanitlarin Turkce, net ve veri odakli olmali. Yatirim tavsiyesi vermedigini her zaman belirt.
Kisa sorularda kisa yanit ver, analiz istenirse detaylandir."""

    messages_text = "\n".join(
        f"{'Kullanici' if m.role == 'user' else 'Asistan'}: {m.content[:300]}"
        for m in history
    )

    full_prompt = body.message
    if messages_text:
        full_prompt = f"Onceki konusma:\n{messages_text}\n\nYeni mesaj: {body.message}"

    model = get_default_model()
    try:
        response_text = await generate(
            prompt=full_prompt,
            system=system_prompt,
            model=model,
        )
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"LLM yanit uretemedi. Model: {model or 'yok'}. Hata: {e}",
        )

    add_chat_message(db, session_id, "user", body.message,
                     metadata_={"ticker": detected_ticker} if detected_ticker else None)
    add_chat_message(db, session_id, "assistant", response_text)

    sources = [f"Hafiza: {s['ticker']} {s['topic']}" for s in similar]

    return ChatResponse(
        session_id=session_id,
        response=response_text,
        sources=sources,
        ticker=detected_ticker,
    )


@router.get("/sessions", response_model=list[ChatSessionOut])
def api_list_chat_sessions(db: Session = Depends(get_db)):
    return list_sessions(db)


@router.get("/sessions/{session_id}/messages", response_model=list[ChatMessageOut])
def api_get_chat_messages(session_id: int, db: Session = Depends(get_db)):
    return get_recent_messages(db, session_id, limit=100)

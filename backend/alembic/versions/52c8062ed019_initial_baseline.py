"""initial_baseline — create all tables from current models

Revision ID: 52c8062ed019
Revises:
Create Date: 2026-07-08 16:20:54.103324

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "52c8062ed019"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # ── reports ──
    op.create_table(
        "reports",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("created_at", sa.DateTime(), index=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("candidates_scanned", sa.Integer(), server_default="0"),
    )

    # ── notifications ──
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("type", sa.String(), server_default="report"),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("report_id", sa.Integer(), sa.ForeignKey("reports.id"), nullable=True),
        sa.Column("is_read", sa.Boolean(), server_default="false"),
        sa.Column("created_at", sa.DateTime(), index=True),
    )

    # ── predictions ──
    op.create_table(
        "predictions",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("ticker", sa.String(), index=True),
        sa.Column("report_id", sa.Integer(), sa.ForeignKey("reports.id"), nullable=True),
        sa.Column("forecast_days", sa.Integer(), server_default="30"),
        sa.Column("predicted_prices", sa.JSON(), server_default="{}"),
        sa.Column("current_price", sa.Float(), nullable=True),
        sa.Column("features_used", sa.JSON(), server_default="{}"),
        sa.Column("model_name", sa.String(), server_default="ensemble-light"),
        sa.Column("confidence", sa.Float(), server_default="0.5"),
        sa.Column("target_date", sa.DateTime(), nullable=True),
        sa.Column("actual_price", sa.Float(), nullable=True),
        sa.Column("error_pct", sa.Float(), nullable=True),
        sa.Column("error_analysis", sa.Text(), nullable=True),
        sa.Column("lessons_learned", sa.Text(), nullable=True),
        sa.Column("evaluated", sa.Boolean(), server_default="false"),
        sa.Column("created_at", sa.DateTime(), index=True),
        sa.Column("evaluated_at", sa.DateTime(), nullable=True),
    )

    # ── stock_picks ──
    op.create_table(
        "stock_picks",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("report_id", sa.Integer(), sa.ForeignKey("reports.id")),
        sa.Column("ticker", sa.String(), index=True),
        sa.Column("price", sa.Float(), nullable=True),
        sa.Column("momentum_pct", sa.Float(), nullable=True),
        sa.Column("fundamental_score", sa.Float(), nullable=True),
        sa.Column("sentiment_score", sa.Float(), nullable=True),
        sa.Column("risk_score", sa.Float(), nullable=True),
        sa.Column("composite_score", sa.Float(), nullable=True),
        sa.Column("pe_ratio", sa.Float(), nullable=True),
        sa.Column("volatility_annualized", sa.Float(), nullable=True),
        sa.Column("max_drawdown_pct", sa.Float(), nullable=True),
        sa.Column("narrative", sa.Text(), nullable=True),
    )

    # ── watchlist_items ──
    op.create_table(
        "watchlist_items",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("ticker", sa.String(), unique=True, index=True),
        sa.Column("notes", sa.String(), nullable=True),
        sa.Column("added_at", sa.DateTime(), nullable=True),
    )

    # ── portfolio_positions ──
    op.create_table(
        "portfolio_positions",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("ticker", sa.String(), index=True),
        sa.Column("quantity", sa.Float(), nullable=True),
        sa.Column("entry_price", sa.Float(), nullable=True),
        sa.Column("entry_date", sa.DateTime(), nullable=True),
        sa.Column("notes", sa.String(), nullable=True),
        sa.Column("status", sa.String(), server_default="open"),
        sa.Column("exit_price", sa.Float(), nullable=True),
        sa.Column("exit_date", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )

    # ── trading_decisions ──
    op.create_table(
        "trading_decisions",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("ticker", sa.String(), index=True),
        sa.Column("action", sa.String(), nullable=True),
        sa.Column("quantity", sa.Float(), nullable=True),
        sa.Column("price", sa.Float(), nullable=True),
        sa.Column("total_amount", sa.Float(), nullable=True),
        sa.Column("reasoning", sa.Text(), nullable=True),
        sa.Column("factors", sa.JSON(), server_default="{}"),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("portfolio_value_before", sa.Float(), nullable=True),
        sa.Column("portfolio_value_after", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), index=True),
    )

    # ── virtual_balance ──
    op.create_table(
        "virtual_balance",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("cash", sa.Float(), server_default="100000.0"),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )

    # ── balance_transactions ──
    op.create_table(
        "balance_transactions",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("type", sa.String(), nullable=True),
        sa.Column("amount", sa.Float(), nullable=True),
        sa.Column("note", sa.String(), nullable=True),
        sa.Column("position_id", sa.Integer(), sa.ForeignKey("portfolio_positions.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )

    # ── user_profiles ──
    op.create_table(
        "user_profiles",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("display_name", sa.String(), server_default="Yatirimci"),
        sa.Column("risk_tolerance", sa.String(), server_default="moderate"),
        sa.Column("investment_style", sa.String(), server_default="mixed"),
        sa.Column("preferred_markets", sa.JSON(), server_default="[]"),
        sa.Column("preferred_sectors", sa.JSON(), server_default="[]"),
        sa.Column("language", sa.String(), server_default="tr"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )

    # ── chat_sessions ──
    op.create_table(
        "chat_sessions",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("title", sa.String(), server_default="Yeni Sohbet"),
        sa.Column("model", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), index=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )

    # ── chat_messages ──
    op.create_table(
        "chat_messages",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("chat_sessions.id")),
        sa.Column("role", sa.String(), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("agent_name", sa.String(), nullable=True),
        sa.Column("metadata", sa.JSON(), server_default="{}"),
        sa.Column("created_at", sa.DateTime(), index=True),
    )

    # ── research_memories ──
    op.create_table(
        "research_memories",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("ticker", sa.String(), index=True),
        sa.Column("topic", sa.String(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("source_report_id", sa.Integer(), sa.ForeignKey("reports.id"), nullable=True),
        sa.Column("data_snapshot", sa.JSON(), server_default="{}"),
        sa.Column("confidence", sa.Float(), server_default="0.5"),
        sa.Column("validated_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), index=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
    )

    # ── memory_embeddings (vector extension must be created first) ──
    op.create_table(
        "memory_embeddings",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("memory_id", sa.Integer(), sa.ForeignKey("research_memories.id")),
        sa.Column("embedding", postgresql.ARRAY(sa.Float()), nullable=True),  # Vector(1536) at app level; ARRAY fallback works in practice
        sa.Column("model_name", sa.String(), server_default="text-embedding-3-small"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )

    # ── llm_providers ──
    op.create_table(
        "llm_providers",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("name", sa.String(), unique=True, index=True),
        sa.Column("slug", sa.String(), unique=True),
        sa.Column("base_url", sa.String(), nullable=True),
        sa.Column("api_key", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )

    # ── llm_models ──
    op.create_table(
        "llm_models",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("provider_id", sa.Integer(), sa.ForeignKey("llm_providers.id")),
        sa.Column("model_id", sa.String(), nullable=True),
        sa.Column("display_name", sa.String(), nullable=True),
        sa.Column("supports_chat", sa.Boolean(), server_default="true"),
        sa.Column("supports_embedding", sa.Boolean(), server_default="false"),
        sa.Column("max_tokens", sa.Integer(), server_default="4096"),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("provider_id", "model_id", name="uq_provider_model"),
    )

    # ── system_settings ──
    op.create_table(
        "system_settings",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("key", sa.String(), unique=True, index=True),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )

    # ── translation_cache ──
    op.create_table(
        "translation_cache",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("source_hash", sa.String(64), unique=True, index=True),
        sa.Column("source_text", sa.Text(), nullable=True),
        sa.Column("target_lang", sa.String(), server_default="tr"),
        sa.Column("translated_text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("hit_count", sa.Integer(), server_default="1"),
    )


def downgrade() -> None:
    op.drop_table("translation_cache")
    op.drop_table("system_settings")
    op.drop_table("llm_models")
    op.drop_table("llm_providers")
    op.drop_table("memory_embeddings")
    op.drop_table("research_memories")
    op.drop_table("chat_messages")
    op.drop_table("chat_sessions")
    op.drop_table("user_profiles")
    op.drop_table("balance_transactions")
    op.drop_table("virtual_balance")
    op.drop_table("trading_decisions")
    op.drop_table("portfolio_positions")
    op.drop_table("watchlist_items")
    op.drop_table("stock_picks")
    op.drop_table("predictions")
    op.drop_table("notifications")
    op.drop_table("reports")

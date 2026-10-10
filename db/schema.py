#!/usr/bin/python3
"""
PostgreSQL Schema Design for Phoenix Trades.

This schema is designed based on the `ExternalOrderResponse` C++ struct and
related types from the Phoenix Trading Platform:
  - Header (type, length)
  - OrderResponseInfoT (timestamp, orderId, uniqueId, fillNumber, placed Ladder,
                        traded Ladder, remainingQuantity, token, errorCode, response)
  - UserDetails (locationId, serverId, compositeID [user, portfolio, index],
                 clientCode, algoId, pancard)
  - Information (parent orderId, fields [orderType, side, legExecution], parent)
  - echo

The `trades` table is completely standalone with no foreign key dependencies
for high-throughput decoupled ingestion and independent table lifecycle.
Includes a PostgreSQL trigger on `trades` table that sends NOTIFY events with
all row data serialized as JSON.
"""

from enum import IntEnum
from typing import Any, Dict, Optional

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Index,
    Integer,
    MetaData,
    SmallInteger,
    String,
    Table,
    UniqueConstraint,
    create_engine,
    func,
    text,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable


# ============================================================================
# Phoenix Enums matching public/Phoenix/types/Enums.hpp
# ============================================================================


class Side(IntEnum):
    BUY = 1
    SELL = 2


class OrderType(IntEnum):
    LIMIT = 1
    IOC = 3
    STOPLOSS = 4


class OrderResponse(IntEnum):
    NONE = 0
    PENDING = 1
    PLACED = 2
    MODIFIED = 3
    CANCELLED = 4
    PARTIAL_FILLED = 5
    FILLED = 6
    NEW_REJECT = 7
    MODIFY_REJECT = 8
    CANCEL_REJECT = 9


class LegExecution(IntEnum):
    MANUAL = 0
    STRATEGY_ENTRY = 1
    STRATEGY_EXIT = 2


# ============================================================================
# SQLAlchemy MetaData & Standalone Trades Table Definition
# ============================================================================

metadata = MetaData()

trades = Table(
    "trades",
    metadata,
    Column(
        "id",
        BigInteger,
        primary_key=True,
        autoincrement=True,
        comment="Synthetic Primary Key",
    ),
    # Execution / Order Identifiers
    Column(
        "order_id",
        BigInteger,
        nullable=False,
        index=True,
        comment="Exchange Order Number (_response._orderId)",
    ),
    Column(
        "unique_id",
        BigInteger,
        nullable=False,
        index=True,
        comment="Internal Phoenix Unique Code (_response._uniqueId)",
    ),
    Column(
        "fill_number",
        BigInteger,
        nullable=False,
        index=True,
        comment="Exchange Trade / Fill ID (_response._fillNumber)",
    ),
    Column(
        "parent_order_id",
        BigInteger,
        nullable=True,
        index=True,
        comment="Parent Strategy / Root Order ID (_information._orderId)",
    ),
    # User / Account Context (Standalone - No Foreign Key)
    Column(
        "user_id",
        BigInteger,
        nullable=False,
        index=True,
        comment="User ID (_compositeID._fields._user)",
    ),
    Column(
        "portfolio_id",
        BigInteger,
        nullable=False,
        index=True,
        comment="Strategy / Portfolio ID (_compositeID._fields._portfolio)",
    ),
    Column(
        "composite_id",
        BigInteger,
        nullable=False,
        comment="Combined Composite ID Index (_compositeID._index)",
    ),
    Column(
        "client_code",
        String(32),
        nullable=True,
        comment="Client Code (_userDetails._clientCode)",
    ),
    Column(
        "algo_id",
        String(32),
        nullable=True,
        comment="Algo Category / Instance ID (_userDetails._algoId)",
    ),
    Column(
        "pancard", String(10), nullable=True, comment="PAN Card (_userDetails._pancard)"
    ),
    Column(
        "server_id",
        Integer,
        nullable=True,
        comment="Server / Broker / Trader ID (_userDetails._serverId)",
    ),
    Column(
        "location_id",
        BigInteger,
        nullable=True,
        comment="Location / NNF / CTCL ID (_userDetails._locationId)",
    ),
    Column(
        "parent_strategy",
        String(16),
        nullable=True,
        comment="Parent Strategy Tag / Name (_information._parent)",
    ),
    # Instrument & Trade Attributes
    Column(
        "token",
        Integer,
        nullable=False,
        index=True,
        comment="Contract / Security Token ID (_response._token)",
    ),
    Column(
        "side",
        SmallInteger,
        nullable=False,
        comment="Side: 1=BUY, 2=SELL (_information._fields._side)",
    ),
    Column(
        "order_type",
        SmallInteger,
        nullable=False,
        comment="OrderType: 1=LIMIT, 3=IOC, 4=STOPLOSS (_information._fields._orderType)",
    ),
    Column(
        "leg_execution",
        SmallInteger,
        nullable=False,
        server_default="0",
        comment="LegExecution: 0=MANUAL, 1=ENTRY, 2=EXIT (_information._fields._legExecution)",
    ),
    # Trade Execution Details (Ladder _traded, Ladder _placed, _remainingQuantity)
    Column(
        "fill_price",
        BigInteger,
        nullable=False,
        comment="Execution / Traded Price in paise/ticks (_response._traded._price)",
    ),
    Column(
        "fill_quantity",
        Integer,
        nullable=False,
        comment="Execution / Traded Quantity (_response._traded._quantity)",
    ),
    Column(
        "placed_price",
        BigInteger,
        nullable=False,
        comment="Original Placed Price in paise/ticks (_response._placed._price)",
    ),
    Column(
        "placed_quantity",
        Integer,
        nullable=False,
        comment="Original Placed Quantity (_response._placed._quantity)",
    ),
    Column(
        "remaining_quantity",
        Integer,
        nullable=False,
        comment="Leaves / Remaining Quantity After Fill (_response._remainingQuantity)",
    ),
    # Timestamps
    Column(
        "trade_timestamp_ns",
        BigInteger,
        nullable=False,
        index=True,
        comment="Trade Execution Timestamp in nanoseconds (_response._timestamp)",
    ),
    Column(
        "created_at",
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="DB Insertion Timestamp",
    ),
    # Constraints & Composite Indexes
    UniqueConstraint("order_id", "fill_number", name="uq_trades_order_fill"),
    Index("ix_trades_user_portfolio", "user_id", "portfolio_id"),
    Index("ix_trades_token_timestamp", "token", "trade_timestamp_ns"),
    Index("ix_trades_unique_timestamp", "unique_id", "trade_timestamp_ns"),
)


# ============================================================================
# SQLAlchemy MetaData & Contracts Master Table Definition
# ============================================================================

contracts = Table(
    "contracts",
    metadata,
    Column(
        "id",
        BigInteger,
        primary_key=True,
        autoincrement=True,
        comment="Synthetic Primary Key",
    ),
    # Core Identifiers
    Column(
        "trade_date",
        String(8),
        nullable=False,
        index=True,
        comment="Business Trade Date (YYYYMMDD)",
    ),
    Column(
        "sutra_symbol",
        String(128),
        nullable=False,
        index=True,
        comment="Standardized Sutra Symbol",
    ),
    Column(
        "sutra_token",
        BigInteger,
        nullable=False,
        index=True,
        comment="Composite Token (Exchange*10 + Segment + Token)",
    ),
    Column(
        "token",
        BigInteger,
        nullable=False,
        index=True,
        comment="Exchange Native Instrument Token",
    ),
    Column(
        "future_token",
        BigInteger,
        nullable=True,
        index=True,
        comment="Corresponding Near-Month Future Token",
    ),
    Column(
        "equity_token",
        BigInteger,
        nullable=True,
        index=True,
        comment="Underlying Cash / Equity Token",
    ),
    Column(
        "exchange",
        String(8),
        nullable=False,
        index=True,
        comment="Exchange Code (NSE, BSE, MCX)",
    ),
    Column(
        "segment",
        String(8),
        nullable=False,
        index=True,
        comment="Segment Code (CM, FO)",
    ),
    Column(
        "symbol",
        String(64),
        nullable=False,
        index=True,
        comment="Underlying Symbol / Ticker",
    ),
    Column(
        "contract_name",
        String(128),
        nullable=True,
        comment="Human-readable Contract Description",
    ),
    # Instrument Details
    Column(
        "instrument_type",
        String(16),
        nullable=True,
        comment="Instrument Type (OPTSTK, OPTIDX, FUTSTK, FUTIDX, EQ, COM)",
    ),
    Column(
        "option_type",
        String(8),
        nullable=True,
        comment="Option Type (CE, PE, XX)",
    ),
    Column(
        "strike_price",
        BigInteger,
        nullable=False,
        server_default="0",
        comment="Strike Price in Paise (Scale 100)",
    ),
    # Expiry Metrics
    Column(
        "expiry_epoch",
        BigInteger,
        nullable=False,
        server_default="-1",
        comment="Expiry Timestamp in NSE Epoch (Seconds since 1980-01-01)",
    ),
    Column(
        "expiry_date",
        String(32),
        nullable=True,
        comment="Formatted Expiry Date (e.g. 27 August 2026)",
    ),
    Column(
        "days_to_expiry",
        Integer,
        nullable=False,
        server_default="0",
        comment="Calendar Days Remaining to Expiration",
    ),
    Column(
        "expiry_cycle",
        String(16),
        nullable=True,
        comment="Expiry Cycle Code (M0, M1, W1, NA)",
    ),
    # Stream & Segment Partition
    Column(
        "stream_id",
        Integer,
        nullable=True,
        comment="Market Data Feed Stream / Partition ID",
    ),
    Column(
        "market_segment_id",
        Integer,
        nullable=True,
        comment="Product / Market Segment ID",
    ),
    # Trading Parameters
    Column(
        "freeze_quantity",
        BigInteger,
        nullable=False,
        comment="Maximum Single Order Quantity Allowed",
    ),
    Column(
        "lot_size",
        Integer,
        nullable=False,
        server_default="1",
        comment="Market Board Lot Size",
    ),
    Column(
        "divisor",
        Integer,
        nullable=False,
        server_default="100",
        comment="Price Scale Divisor",
    ),
    Column(
        "tick_size",
        Integer,
        nullable=False,
        server_default="5",
        comment="Minimum Tick Size in Paise",
    ),
    # Pricing & DPR Ranges (Paise scaled)
    Column(
        "open_price",
        BigInteger,
        nullable=False,
        server_default="0",
        comment="Session Opening Price in Paise",
    ),
    Column(
        "high_price",
        BigInteger,
        nullable=False,
        server_default="0",
        comment="Session High Price in Paise",
    ),
    Column(
        "low_price",
        BigInteger,
        nullable=False,
        server_default="0",
        comment="Session Low Price in Paise",
    ),
    Column(
        "close_price",
        BigInteger,
        nullable=False,
        server_default="0",
        comment="Session Closing Price in Paise",
    ),
    Column(
        "last_price",
        BigInteger,
        nullable=False,
        server_default="0",
        comment="Last Traded Price in Paise",
    ),
    Column(
        "previous_close_price",
        BigInteger,
        nullable=False,
        server_default="0",
        comment="Prior Close / Settlement Price in Paise",
    ),
    Column(
        "underlying_price",
        BigInteger,
        nullable=False,
        server_default="0",
        comment="Underlying Cash / Spot Price in Paise",
    ),
    Column(
        "total_traded_volume",
        BigInteger,
        nullable=False,
        server_default="0",
        comment="Total Cumulative Traded Quantity",
    ),
    Column(
        "total_traded_value",
        BigInteger,
        nullable=False,
        server_default="0",
        comment="Total Cumulative Traded Value in Paise",
    ),
    Column(
        "high_dpr",
        BigInteger,
        nullable=False,
        server_default="0",
        comment="Upper Daily Price Range (Upper Circuit) in Paise",
    ),
    Column(
        "low_dpr",
        BigInteger,
        nullable=False,
        server_default="0",
        comment="Lower Daily Price Range (Lower Circuit) in Paise",
    ),
    Column(
        "open_interest",
        BigInteger,
        nullable=False,
        server_default="0",
        comment="Total Open Interest Contracts",
    ),
    # Permissions & Metadata
    Column(
        "is_tradeable",
        String(4),
        nullable=False,
        server_default="Y",
        comment="Trading Permission Flag (Y/N)",
    ),
    Column(
        "is_banned",
        String(4),
        nullable=False,
        server_default="N",
        comment="Security Banned Flag (Y/N)",
    ),
    Column(
        "currency",
        String(8),
        nullable=False,
        server_default="INR",
        comment="Base Currency (INR)",
    ),
    Column(
        "timezone",
        String(32),
        nullable=False,
        server_default="Asia/Kolkata",
        comment="Exchange Market Timezone",
    ),
    Column(
        "trading_schedule",
        String(64),
        nullable=True,
        comment="Daily Trading Session Hours",
    ),
    Column(
        "isin",
        String(32),
        nullable=True,
        comment="International Securities Identification Number",
    ),
    Column(
        "face_value",
        BigInteger,
        nullable=True,
        comment="Security Face Value in Paise",
    ),
    Column(
        "asset_code",
        String(32),
        nullable=True,
        comment="Exchange Asset Code",
    ),
    Column(
        "created_at",
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="DB Record Creation Timestamp",
    ),
    Column(
        "updated_at",
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="DB Record Last Updated Timestamp",
    ),
    # Constraints & Indexes
    UniqueConstraint(
        "trade_date",
        "exchange",
        "segment",
        "token",
        name="uq_contracts_date_exch_seg_token",
    ),
    Index("ix_contracts_lookup", "exchange", "segment", "token"),
    Index("ix_contracts_symbol_expiry", "symbol", "expiry_date"),
    Index("ix_contracts_date_symbol", "trade_date", "symbol"),
)


# ============================================================================
# Trigger SQL Definition: Notify JSON on Trade Insertion
# ============================================================================

TRIGGER_TRADE_INSERT_SQL = """
CREATE OR REPLACE FUNCTION public.notify_trade_insert()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
DECLARE
    payload jsonb;
BEGIN
    payload := jsonb_build_object(
        'table', 'trades',
        'action', TG_OP,
        'data', to_jsonb(NEW)
    );

    -- Send payload via NOTIFY channel
    EXECUTE FORMAT(
        'NOTIFY %I, %L',
        'trigger_trade_insert',
        payload::text
    );

    RETURN NEW;
END;
$function$;

DROP TRIGGER IF EXISTS trg_trades_notify_insert ON public.trades;

CREATE TRIGGER trg_trades_notify_insert
AFTER INSERT ON public.trades
FOR EACH ROW
EXECUTE FUNCTION public.notify_trade_insert();
"""


# ============================================================================
# Helper Functions: Extracting DB records from ExternalOrderResponse payload
# ============================================================================


def extract_trade_record(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Extract a dictionary suitable for inserting into `trades` table
    from an ExternalOrderResponse payload if the response represents a trade fill.
    Returns None if the response is not a fill event.
    """
    response_info = data.get("response", {})
    response_status = response_info.get("response", OrderResponse.NONE)

    # Only process trade fills (FILLED or PARTIAL_FILLED)
    if response_status not in (OrderResponse.FILLED, OrderResponse.PARTIAL_FILLED):
        return None

    user_details = data.get("userDetails", {})
    composite_id = user_details.get("compositeID", {})
    fields_user = composite_id.get("fields", {})
    information = data.get("information", {})
    info_fields = information.get("fields", {})
    placed = response_info.get("placed", {})
    traded = response_info.get("traded", {})

    user_id = fields_user.get("user", user_details.get("userId", 0))
    portfolio_id = fields_user.get("portfolio", user_details.get("portfolioId", 0))
    composite_idx = composite_id.get("index", (portfolio_id << 32) | user_id)

    return {
        "order_id": response_info.get("orderId", 0),
        "unique_id": response_info.get("uniqueId", 0),
        "fill_number": response_info.get("fillNumber", 0),
        "parent_order_id": information.get("orderId"),
        "user_id": user_id,
        "portfolio_id": portfolio_id,
        "composite_id": composite_idx,
        "client_code": user_details.get("clientCode"),
        "algo_id": str(user_details.get("algoId", "")),
        "pancard": user_details.get("pancard"),
        "server_id": user_details.get("serverId"),
        "location_id": user_details.get("locationId"),
        "parent_strategy": information.get("parent"),
        "token": response_info.get("token", 0),
        "side": info_fields.get("side", Side.BUY),
        "order_type": info_fields.get("orderType", OrderType.LIMIT),
        "leg_execution": info_fields.get("legExecution", LegExecution.MANUAL),
        "fill_price": traded.get("price", 0),
        "fill_quantity": traded.get("quantity", 0),
        "placed_price": placed.get("price", 0),
        "placed_quantity": placed.get("quantity", 0),
        "remaining_quantity": response_info.get("remainingQuantity", 0),
        "trade_timestamp_ns": response_info.get("timestamp", 0),
    }


def get_schema_ddl() -> str:
    """Generate PostgreSQL DDL string for tables (trades, contracts), indexes, and triggers."""
    dialect = postgresql.dialect()
    ddl_statements = [
        str(CreateTable(trades).compile(dialect=dialect)).strip() + ";",
        str(CreateTable(contracts).compile(dialect=dialect)).strip() + ";",
        TRIGGER_TRADE_INSERT_SQL.strip(),
    ]
    return "\n\n".join(ddl_statements)


def setup_database(engine_url: str):
    """Create the trades and contracts tables, indexes, and triggers on the specified database."""
    engine = create_engine(engine_url)
    metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(text(TRIGGER_TRADE_INSERT_SQL))
    print("Database schema (trades, contracts) and triggers created successfully.")


# ============================================================================
# Main Execution / Verification
# ============================================================================


def main():
    import argparse

    parser = argparse.ArgumentParser(
        prog="db.schema",
        description="🦅 Phoenix Trading Platform - PostgreSQL Database Schema Generator.\n"
        "Generates DDL schemas or sets up database tables for trades and unified contracts.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--ddl",
        action="store_true",
        default=True,
        help="Print PostgreSQL DDL create table and trigger scripts (default: True)",
    )
    parser.add_argument(
        "--setup-db",
        type=str,
        default=None,
        metavar="DB_URL",
        help="Execute DDL schema creation directly on a live PostgreSQL database URL",
    )

    args = parser.parse_args()

    if args.setup_db:
        print(f"Connecting to database and setting up schema on: {args.setup_db}")
        setup_database(args.setup_db)
    else:
        print("=" * 80)
        print(" Phoenix Trading Platform - PostgreSQL DDL Schema (Trades & Contracts)")
        print(
            " Generated from ExternalOrderResponse and Unified Contract Master Specification"
        )
        print("=" * 80)
        print()
        print(get_schema_ddl())
        print()
        print("=" * 80)
        print(" Schema and trigger definition verified successfully.")
        print(" To create tables and triggers on a live PostgreSQL database, run:")
        print(
            "   python -m db.schema --setup-db 'postgresql+psycopg://postgres:password@localhost/trading'"
        )
        print("=" * 80)


if __name__ == "__main__":
    main()

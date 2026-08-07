CREATE TABLE IF NOT EXISTS securities_master (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    market_segment TEXT,
    sector_33_code TEXT,
    sector_33_name TEXT,
    sector_17_code TEXT,
    sector_17_name TEXT,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS daily_price (
    code TEXT NOT NULL,
    date TEXT NOT NULL,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume INTEGER,
    source TEXT NOT NULL,
    PRIMARY KEY (code, date)
);

CREATE TABLE IF NOT EXISTS technical_score (
    code TEXT NOT NULL,
    date TEXT NOT NULL,
    rsi14 REAL,
    ma25_deviation REAL,
    ma75_deviation REAL,
    low52w_deviation REAL,
    PRIMARY KEY (code, date)
);

CREATE TABLE IF NOT EXISTS valuation_score (
    code TEXT NOT NULL,
    date TEXT NOT NULL,
    per REAL,
    pbr REAL,
    roe REAL,
    composite_score REAL,
    sector_deviation REAL,
    PRIMARY KEY (code, date)
);

CREATE TABLE IF NOT EXISTS fundamentals (
    code TEXT NOT NULL,
    fiscal_period TEXT NOT NULL,
    eps REAL,
    bps REAL,
    net_income REAL,
    equity REAL,
    shares_outstanding REAL,
    doc_id TEXT,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (code, fiscal_period)
);

CREATE TABLE IF NOT EXISTS report_output (
    date TEXT NOT NULL,
    sector TEXT NOT NULL,
    rank INTEGER,
    code TEXT NOT NULL,
    comment TEXT,
    PRIMARY KEY (date, code)
);

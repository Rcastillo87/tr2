-- Esquema public de TR2 (solo estructura). Generado con ops/schema_dump.sh — no editar a mano.
-- PostgreSQL 16.14 (Ubuntu 16.14-0ubuntu0.24.04.1) · TimescaleDB 2.27.2
-- Hypertables (recrear con create_hypertable después de crear la tabla):
--   ohlcv_data por time cada 7 days
-- Políticas de TimescaleDB:
--   policy_compression en ohlcv_data cada 12:00:00 {"hypertable_id": 1, "compress_after": "14 days"}
-- Migraciones SQL aplicadas después: database/sql-migrations (este volcado ya las incluye).

--
-- PostgreSQL database dump
--



SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: public; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA public;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: ohlcv_data; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ohlcv_data (
    "time" timestamp with time zone NOT NULL,
    symbol character varying(20) NOT NULL,
    "interval" character varying(5) NOT NULL,
    open numeric(20,8) NOT NULL,
    high numeric(20,8) NOT NULL,
    low numeric(20,8) NOT NULL,
    close numeric(20,8) NOT NULL,
    volume numeric(30,8) NOT NULL,
    broker character varying(32) DEFAULT 'bybit'::character varying NOT NULL
);


--
-- Name: backtests; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.backtests (
    id bigint NOT NULL,
    strategy_id bigint NOT NULL,
    symbols json NOT NULL,
    "interval" character varying(255) NOT NULL,
    months integer NOT NULL,
    config_params json NOT NULL,
    strategy_snapshot json NOT NULL,
    metrics json,
    approved boolean DEFAULT false NOT NULL,
    created_at timestamp(0) without time zone,
    updated_at timestamp(0) without time zone,
    hash character varying(32),
    origin character varying(16),
    origin_meta jsonb,
    CONSTRAINT backtests_origin_check CHECK (((origin IS NULL) OR ((origin)::text = ANY ((ARRAY['manual'::character varying, 'search'::character varying])::text[]))))
);


--
-- Name: backtests_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.backtests_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: backtests_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.backtests_id_seq OWNED BY public.backtests.id;


--
-- Name: broker_accounts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.broker_accounts (
    id bigint NOT NULL,
    user_id bigint NOT NULL,
    broker character varying(255) DEFAULT 'bybit'::character varying NOT NULL,
    account_type character varying(255) DEFAULT 'real'::character varying NOT NULL,
    label character varying(255) NOT NULL,
    api_key text,
    api_secret text,
    status character varying(255) DEFAULT 'active'::character varying NOT NULL,
    created_at timestamp(0) without time zone,
    updated_at timestamp(0) without time zone,
    single_position_per_symbol boolean DEFAULT true NOT NULL,
    max_monthly_loss_pct numeric(5,2) DEFAULT 5 NOT NULL,
    max_open_trades smallint DEFAULT 3 NOT NULL,
    month_start_balance numeric(20,8),
    month_start_at date,
    monthly_loss_enabled boolean DEFAULT true NOT NULL,
    open_trades_limit_enabled boolean DEFAULT true NOT NULL,
    loss_pause_days smallint,
    loss_paused_until timestamp without time zone,
    loss_period_start timestamp without time zone,
    loss_period_balance numeric(20,8),
    CONSTRAINT broker_accounts_account_type_check CHECK (((account_type)::text = ANY ((ARRAY['real'::character varying, 'demo'::character varying])::text[]))),
    CONSTRAINT broker_accounts_loss_pause_days_check CHECK (((loss_pause_days IS NULL) OR ((loss_pause_days >= 1) AND (loss_pause_days <= 30)))),
    CONSTRAINT broker_accounts_max_monthly_loss_chk CHECK (((max_monthly_loss_pct >= (1)::numeric) AND (max_monthly_loss_pct <= (30)::numeric))),
    CONSTRAINT broker_accounts_max_open_trades_chk CHECK (((max_open_trades >= 1) AND (max_open_trades <= 20))),
    CONSTRAINT broker_accounts_status_check CHECK (((status)::text = ANY ((ARRAY['active'::character varying, 'paused'::character varying])::text[])))
);


--
-- Name: broker_accounts_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.broker_accounts_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: broker_accounts_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.broker_accounts_id_seq OWNED BY public.broker_accounts.id;


--
-- Name: broker_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.broker_events (
    id bigint NOT NULL,
    broker_account_id bigint NOT NULL,
    trade_id bigint,
    event character varying(40) NOT NULL,
    data jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    processed_at timestamp with time zone
);


--
-- Name: broker_events_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.broker_events_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: broker_events_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.broker_events_id_seq OWNED BY public.broker_events.id;


--
-- Name: cache; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.cache (
    key character varying(255) NOT NULL,
    value text NOT NULL,
    expiration bigint NOT NULL
);


--
-- Name: cache_locks; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.cache_locks (
    key character varying(255) NOT NULL,
    owner character varying(255) NOT NULL,
    expiration bigint NOT NULL
);


--
-- Name: collector_configs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.collector_configs (
    id bigint NOT NULL,
    symbol character varying(20) NOT NULL,
    "interval" character varying(10) NOT NULL,
    active boolean DEFAULT true NOT NULL,
    notes text,
    created_at timestamp(0) without time zone,
    updated_at timestamp(0) without time zone,
    broker character varying(20) DEFAULT 'bybit'::character varying NOT NULL
);


--
-- Name: collector_configs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.collector_configs_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: collector_configs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.collector_configs_id_seq OWNED BY public.collector_configs.id;


--
-- Name: failed_jobs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.failed_jobs (
    id bigint NOT NULL,
    uuid character varying(255) NOT NULL,
    connection character varying(255) NOT NULL,
    queue character varying(255) NOT NULL,
    payload text NOT NULL,
    exception text NOT NULL,
    failed_at timestamp(0) without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);


--
-- Name: failed_jobs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.failed_jobs_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: failed_jobs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.failed_jobs_id_seq OWNED BY public.failed_jobs.id;


--
-- Name: funding_coverage; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.funding_coverage (
    symbol character varying(30) NOT NULL,
    covered_from timestamp with time zone NOT NULL,
    covered_to timestamp with time zone NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT funding_coverage_check CHECK ((covered_from <= covered_to))
);


--
-- Name: funding_rates; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.funding_rates (
    symbol character varying(30) NOT NULL,
    funding_time timestamp with time zone NOT NULL,
    rate double precision NOT NULL
);


--
-- Name: job_batches; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.job_batches (
    id character varying(255) NOT NULL,
    name character varying(255) NOT NULL,
    total_jobs integer NOT NULL,
    pending_jobs integer NOT NULL,
    failed_jobs integer NOT NULL,
    failed_job_ids text NOT NULL,
    options text,
    cancelled_at integer,
    created_at integer NOT NULL,
    finished_at integer
);


--
-- Name: jobs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.jobs (
    id bigint NOT NULL,
    queue character varying(255) NOT NULL,
    payload text NOT NULL,
    attempts smallint NOT NULL,
    reserved_at integer,
    available_at integer NOT NULL,
    created_at integer NOT NULL
);


--
-- Name: jobs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.jobs_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: jobs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.jobs_id_seq OWNED BY public.jobs.id;


--
-- Name: migrations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.migrations (
    id integer NOT NULL,
    migration character varying(255) NOT NULL,
    batch integer NOT NULL
);


--
-- Name: migrations_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.migrations_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: migrations_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.migrations_id_seq OWNED BY public.migrations.id;


--
-- Name: notifications; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.notifications (
    id uuid NOT NULL,
    type character varying(255) NOT NULL,
    notifiable_type character varying(255) NOT NULL,
    notifiable_id bigint NOT NULL,
    data text NOT NULL,
    read_at timestamp(0) without time zone,
    created_at timestamp(0) without time zone,
    updated_at timestamp(0) without time zone
);


--
-- Name: ohlcv_deletions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ohlcv_deletions (
    id bigint NOT NULL,
    broker character varying(32) NOT NULL,
    symbol character varying(20) NOT NULL,
    "interval" character varying(5) NOT NULL,
    source character varying(16) NOT NULL,
    reason text NOT NULL,
    deleted_count integer NOT NULL,
    first_time timestamp with time zone,
    last_time timestamp with time zone,
    bars jsonb,
    bars_saved boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ohlcv_deletions_source_chk CHECK (((source)::text = ANY ((ARRAY['reload'::character varying, 'invalidate'::character varying])::text[])))
);


--
-- Name: ohlcv_deletions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.ohlcv_deletions_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: ohlcv_deletions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.ohlcv_deletions_id_seq OWNED BY public.ohlcv_deletions.id;


--
-- Name: paper_eval_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.paper_eval_log (
    id bigint NOT NULL,
    paper_strategy_config_id bigint NOT NULL,
    bucket_time timestamp without time zone NOT NULL,
    code character varying(32) NOT NULL,
    detail text NOT NULL,
    regime character varying(16),
    signal smallint,
    filters jsonb,
    first_at timestamp without time zone NOT NULL,
    last_at timestamp without time zone NOT NULL,
    evaluations integer DEFAULT 1 NOT NULL
);


--
-- Name: paper_eval_log_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.paper_eval_log_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: paper_eval_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.paper_eval_log_id_seq OWNED BY public.paper_eval_log.id;


--
-- Name: paper_eval_state; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.paper_eval_state (
    paper_strategy_config_id bigint NOT NULL,
    evaluated_at timestamp without time zone NOT NULL,
    code character varying(32) NOT NULL,
    detail text NOT NULL,
    regime character varying(16),
    signal smallint,
    filters jsonb,
    candle_time timestamp without time zone,
    last_bar_time timestamp without time zone,
    bars integer
);


--
-- Name: paper_strategy_configs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.paper_strategy_configs (
    id bigint NOT NULL,
    display_name character varying(255) NOT NULL,
    strategy_class character varying(255) NOT NULL,
    symbol character varying(255) NOT NULL,
    "interval" character varying(10) NOT NULL,
    params jsonb NOT NULL,
    active boolean DEFAULT true NOT NULL,
    created_at timestamp(0) without time zone,
    updated_at timestamp(0) without time zone,
    audited_months integer,
    avg_win_rate numeric(5,2),
    avg_monthly_pnl numeric(7,4),
    avg_monthly_trades numeric(6,2),
    total_return_pct numeric(8,4),
    star_wr numeric(3,1),
    star_sharpe numeric(3,1),
    star_ret numeric(3,1),
    star_consistency numeric(3,1),
    star_pf numeric(3,1),
    star_rating numeric(3,1),
    backtest_range_from character varying(7),
    backtest_range_to character varying(7),
    sharpe_ratio numeric(6,2),
    consistency_pct numeric(5,1),
    profit_factor numeric(5,2),
    backtest_id bigint NOT NULL
);


--
-- Name: paper_strategy_configs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.paper_strategy_configs_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: paper_strategy_configs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.paper_strategy_configs_id_seq OWNED BY public.paper_strategy_configs.id;


--
-- Name: paper_trades; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.paper_trades (
    id bigint NOT NULL,
    strategy character varying(255) NOT NULL,
    symbol character varying(255) NOT NULL,
    "interval" character varying(255) NOT NULL,
    side character varying(255) NOT NULL,
    entry_price numeric(20,8) NOT NULL,
    exit_price numeric(20,8),
    sl numeric(20,8) NOT NULL,
    tp numeric(20,8) NOT NULL,
    be_level numeric(20,8) NOT NULL,
    be_activated boolean DEFAULT false NOT NULL,
    size numeric(20,8) NOT NULL,
    pnl numeric(20,8),
    pnl_pct numeric(10,4),
    exit_reason character varying(255),
    regime character varying(255),
    entry_time timestamp(0) without time zone NOT NULL,
    exit_time timestamp(0) without time zone,
    status character varying(255) DEFAULT 'open'::character varying NOT NULL,
    created_at timestamp(0) without time zone,
    updated_at timestamp(0) without time zone,
    max_profit_pct numeric(10,4) DEFAULT '0'::numeric NOT NULL,
    max_loss_pct numeric(10,4) DEFAULT '0'::numeric NOT NULL,
    tp2 numeric(15,8),
    tp3 numeric(20,8),
    tp4 numeric(20,8),
    trailing_applied boolean DEFAULT false NOT NULL,
    last_monitored_at timestamp(0) without time zone,
    commission numeric(20,8),
    config_snapshot jsonb,
    paper_strategy_config_id bigint,
    vol_widened boolean DEFAULT false NOT NULL,
    funding numeric(20,8),
    strategy_code_md5 character(32) GENERATED ALWAYS AS (md5((config_snapshot ->> 'strategy_code'::text))) STORED,
    CONSTRAINT paper_trades_side_check CHECK (((side)::text = ANY ((ARRAY['long'::character varying, 'short'::character varying])::text[]))),
    CONSTRAINT paper_trades_status_check CHECK (((status)::text = ANY ((ARRAY['open'::character varying, 'closed'::character varying])::text[])))
);


--
-- Name: paper_trades_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.paper_trades_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: paper_trades_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.paper_trades_id_seq OWNED BY public.paper_trades.id;


--
-- Name: param_search_runs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.param_search_runs (
    id bigint NOT NULL,
    strategy_id bigint NOT NULL,
    user_id bigint,
    status character varying(16) DEFAULT 'queued'::character varying NOT NULL,
    intervals jsonb NOT NULL,
    search_symbols jsonb NOT NULL,
    validation_symbols jsonb DEFAULT '[]'::jsonb NOT NULL,
    months smallint DEFAULT 24 NOT NULL,
    samples smallint DEFAULT 40 NOT NULL,
    seed integer DEFAULT 7 NOT NULL,
    strategy_code_md5 character(32),
    period_start date,
    split_date date,
    period_end date,
    phase character varying(32),
    progress_done integer DEFAULT 0 NOT NULL,
    progress_total integer DEFAULT 0 NOT NULL,
    progress_note text,
    heartbeat_at timestamp with time zone,
    pid integer,
    cancel_requested boolean DEFAULT false NOT NULL,
    results jsonb,
    error text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    started_at timestamp with time zone,
    finished_at timestamp with time zone,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    focus character varying(8) DEFAULT 'gain'::character varying NOT NULL,
    mode character varying(8) DEFAULT 'interval'::character varying NOT NULL,
    sltp character varying(8) DEFAULT 'fixed'::character varying NOT NULL,
    CONSTRAINT param_search_runs_focus_chk CHECK (((focus)::text = ANY ((ARRAY['gain'::character varying, 'wr'::character varying, 'cons'::character varying])::text[]))),
    CONSTRAINT param_search_runs_mode_chk CHECK (((mode)::text = ANY ((ARRAY['interval'::character varying, 'symbol'::character varying])::text[]))),
    CONSTRAINT param_search_runs_months_check CHECK (((months >= 6) AND (months <= 36))),
    CONSTRAINT param_search_runs_samples_check CHECK (((samples >= 1) AND (samples <= 200))),
    CONSTRAINT param_search_runs_sltp_chk CHECK (((sltp)::text = ANY ((ARRAY['fixed'::character varying, 'auto'::character varying, 'both'::character varying])::text[]))),
    CONSTRAINT param_search_runs_status_check CHECK (((status)::text = ANY ((ARRAY['queued'::character varying, 'running'::character varying, 'done'::character varying, 'failed'::character varying, 'cancelled'::character varying])::text[])))
);


--
-- Name: param_search_runs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.param_search_runs_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: param_search_runs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.param_search_runs_id_seq OWNED BY public.param_search_runs.id;


--
-- Name: password_reset_tokens; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.password_reset_tokens (
    email character varying(255) NOT NULL,
    token character varying(255) NOT NULL,
    created_at timestamp(0) without time zone
);


--
-- Name: python_engine_state; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.python_engine_state (
    key text NOT NULL,
    value text NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: real_strategy_subscriptions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.real_strategy_subscriptions (
    id bigint NOT NULL,
    user_id bigint NOT NULL,
    strategy character varying(255) NOT NULL,
    symbol character varying(255) NOT NULL,
    status character varying(255) DEFAULT 'active'::character varying NOT NULL,
    created_at timestamp(0) without time zone,
    updated_at timestamp(0) without time zone,
    broker_account_id bigint NOT NULL,
    paper_strategy_config_id bigint,
    "interval" character varying(255),
    risk_override_pct numeric(5,2),
    retire_on_close boolean DEFAULT false NOT NULL,
    CONSTRAINT real_strategy_subscriptions_risk_override_check CHECK (((risk_override_pct IS NULL) OR ((risk_override_pct > (0)::numeric) AND (risk_override_pct <= (100)::numeric)))),
    CONSTRAINT real_strategy_subscriptions_status_check CHECK (((status)::text = ANY ((ARRAY['active'::character varying, 'paused'::character varying])::text[])))
);


--
-- Name: real_strategy_subscriptions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.real_strategy_subscriptions_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: real_strategy_subscriptions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.real_strategy_subscriptions_id_seq OWNED BY public.real_strategy_subscriptions.id;


--
-- Name: real_trade_executions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.real_trade_executions (
    id bigint NOT NULL,
    real_trade_id bigint NOT NULL,
    leg character varying(5) NOT NULL,
    exec_id character varying(64) NOT NULL,
    order_id character varying(64) NOT NULL,
    symbol character varying(32) NOT NULL,
    side character varying(4) NOT NULL,
    exec_price numeric NOT NULL,
    exec_qty numeric NOT NULL,
    exec_value numeric,
    exec_fee numeric,
    fee_rate numeric,
    is_maker boolean,
    exec_type character varying(24),
    stop_order_type character varying(32),
    exec_time timestamp without time zone NOT NULL,
    created_at timestamp without time zone DEFAULT timezone('UTC'::text, now()) NOT NULL,
    CONSTRAINT real_trade_executions_leg_check CHECK (((leg)::text = ANY ((ARRAY['open'::character varying, 'close'::character varying])::text[])))
);


--
-- Name: real_trade_executions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.real_trade_executions_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: real_trade_executions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.real_trade_executions_id_seq OWNED BY public.real_trade_executions.id;


--
-- Name: real_trades; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.real_trades (
    id bigint NOT NULL,
    user_id bigint NOT NULL,
    subscription_id bigint,
    strategy character varying(255) NOT NULL,
    symbol character varying(255) NOT NULL,
    broker character varying(255) DEFAULT 'bybit'::character varying NOT NULL,
    "interval" character varying(255) NOT NULL,
    side character varying(255) NOT NULL,
    entry_price numeric(20,8) NOT NULL,
    exit_price numeric(20,8),
    sl numeric(20,8) NOT NULL,
    tp numeric(20,8) NOT NULL,
    be_level numeric(20,8) NOT NULL,
    be_activated boolean DEFAULT false NOT NULL,
    size numeric(20,8) NOT NULL,
    pnl numeric(20,8),
    pnl_pct numeric(10,4),
    exit_reason character varying(255),
    regime character varying(255),
    entry_time timestamp(0) without time zone NOT NULL,
    exit_time timestamp(0) without time zone,
    created_at timestamp(0) without time zone,
    updated_at timestamp(0) without time zone,
    broker_account_id bigint,
    paper_strategy_config_id bigint,
    order_id character varying(255),
    close_order_id character varying(255),
    balance_before numeric(20,8),
    balance_after numeric(20,8),
    commission numeric(20,8),
    net_pnl numeric(20,8),
    entry_price_signal numeric(20,8),
    slippage_pct numeric(10,6),
    leverage numeric(10,2) DEFAULT '1'::numeric NOT NULL,
    tp2 numeric(20,8),
    tp3 numeric(20,8),
    tp4 numeric(20,8),
    status character varying(255) DEFAULT 'pending_open'::character varying NOT NULL,
    error_message text,
    audit_log jsonb,
    trailing_applied boolean DEFAULT false NOT NULL,
    original_size numeric(20,8),
    tp2_hit boolean DEFAULT false NOT NULL,
    tp3_hit boolean DEFAULT false NOT NULL,
    tp4_hit boolean DEFAULT false NOT NULL,
    realized_pnl_partial numeric(20,8) DEFAULT '0'::numeric NOT NULL,
    original_sl numeric(20,8),
    config_snapshot jsonb,
    vol_widened boolean DEFAULT false NOT NULL,
    order_link_id character varying(40),
    strategy_code_md5 character(32) GENERATED ALWAYS AS (md5((config_snapshot ->> 'strategy_code'::text))) STORED,
    executions_status character varying(12),
    funding numeric(20,8),
    CONSTRAINT real_trades_side_check CHECK (((side)::text = ANY ((ARRAY['long'::character varying, 'short'::character varying])::text[]))),
    CONSTRAINT real_trades_status_check CHECK (((status)::text = ANY (ARRAY['pending_open'::text, 'open'::text, 'pending_close'::text, 'closed'::text, 'error'::text, 'orphaned'::text, 'failed'::text, 'ignored'::text])))
);


--
-- Name: real_trades_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.real_trades_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: real_trades_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.real_trades_id_seq OWNED BY public.real_trades.id;


--
-- Name: risk_controls; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.risk_controls (
    id bigint NOT NULL,
    strategy character varying(255),
    symbol character varying(255),
    reason character varying(255) NOT NULL,
    value numeric(10,4),
    threshold numeric(10,4),
    active boolean DEFAULT true NOT NULL,
    paused_at timestamp(0) without time zone NOT NULL,
    auto_resume_at timestamp(0) without time zone,
    resumed_at timestamp(0) without time zone,
    created_at timestamp(0) without time zone,
    updated_at timestamp(0) without time zone,
    CONSTRAINT risk_controls_reason_check CHECK (((reason)::text = ANY ((ARRAY['daily_drawdown'::character varying, 'total_drawdown'::character varying, 'volatility_extreme'::character varying, 'kill_switch_manual'::character varying])::text[])))
);


--
-- Name: risk_controls_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.risk_controls_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: risk_controls_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.risk_controls_id_seq OWNED BY public.risk_controls.id;


--
-- Name: sessions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sessions (
    id character varying(255) NOT NULL,
    user_id bigint,
    ip_address character varying(45),
    user_agent text,
    payload text NOT NULL,
    last_activity integer NOT NULL
);


--
-- Name: strategies; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.strategies (
    id bigint NOT NULL,
    name character varying(255) NOT NULL,
    description text,
    code text,
    active boolean DEFAULT true NOT NULL,
    created_at timestamp(0) without time zone,
    updated_at timestamp(0) without time zone,
    config json
);


--
-- Name: strategies_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.strategies_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: strategies_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.strategies_id_seq OWNED BY public.strategies.id;


--
-- Name: strategy_config_changes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.strategy_config_changes (
    id bigint NOT NULL,
    paper_strategy_config_id bigint,
    backtest_id bigint,
    symbol character varying(32) NOT NULL,
    action character varying(16) NOT NULL,
    old_params jsonb,
    new_params jsonb,
    changed_keys text[] DEFAULT '{}'::text[] NOT NULL,
    source character varying(32) NOT NULL,
    user_id bigint,
    created_at timestamp(0) without time zone DEFAULT timezone('UTC'::text, now()) NOT NULL,
    CONSTRAINT strategy_config_changes_action_check CHECK (((action)::text = ANY ((ARRAY['created'::character varying, 'updated'::character varying, 'deactivated'::character varying, 'deleted'::character varying])::text[])))
);


--
-- Name: strategy_config_changes_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.strategy_config_changes_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: strategy_config_changes_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.strategy_config_changes_id_seq OWNED BY public.strategy_config_changes.id;


--
-- Name: users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.users (
    id bigint NOT NULL,
    name character varying(255) NOT NULL,
    email character varying(255) NOT NULL,
    email_verified_at timestamp(0) without time zone,
    password character varying(255) NOT NULL,
    remember_token character varying(100),
    created_at timestamp(0) without time zone,
    updated_at timestamp(0) without time zone,
    role character varying(255) DEFAULT 'inversionista'::character varying NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    CONSTRAINT users_role_check CHECK (((role)::text = ANY ((ARRAY['admin'::character varying, 'consultor'::character varying, 'inversionista'::character varying])::text[])))
);


--
-- Name: users_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.users_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: users_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.users_id_seq OWNED BY public.users.id;


--
-- Name: backtests id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.backtests ALTER COLUMN id SET DEFAULT nextval('public.backtests_id_seq'::regclass);


--
-- Name: broker_accounts id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.broker_accounts ALTER COLUMN id SET DEFAULT nextval('public.broker_accounts_id_seq'::regclass);


--
-- Name: broker_events id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.broker_events ALTER COLUMN id SET DEFAULT nextval('public.broker_events_id_seq'::regclass);


--
-- Name: collector_configs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.collector_configs ALTER COLUMN id SET DEFAULT nextval('public.collector_configs_id_seq'::regclass);


--
-- Name: failed_jobs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.failed_jobs ALTER COLUMN id SET DEFAULT nextval('public.failed_jobs_id_seq'::regclass);


--
-- Name: jobs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.jobs ALTER COLUMN id SET DEFAULT nextval('public.jobs_id_seq'::regclass);


--
-- Name: migrations id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.migrations ALTER COLUMN id SET DEFAULT nextval('public.migrations_id_seq'::regclass);


--
-- Name: ohlcv_deletions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ohlcv_deletions ALTER COLUMN id SET DEFAULT nextval('public.ohlcv_deletions_id_seq'::regclass);


--
-- Name: paper_eval_log id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.paper_eval_log ALTER COLUMN id SET DEFAULT nextval('public.paper_eval_log_id_seq'::regclass);


--
-- Name: paper_strategy_configs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.paper_strategy_configs ALTER COLUMN id SET DEFAULT nextval('public.paper_strategy_configs_id_seq'::regclass);


--
-- Name: paper_trades id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.paper_trades ALTER COLUMN id SET DEFAULT nextval('public.paper_trades_id_seq'::regclass);


--
-- Name: param_search_runs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.param_search_runs ALTER COLUMN id SET DEFAULT nextval('public.param_search_runs_id_seq'::regclass);


--
-- Name: real_strategy_subscriptions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.real_strategy_subscriptions ALTER COLUMN id SET DEFAULT nextval('public.real_strategy_subscriptions_id_seq'::regclass);


--
-- Name: real_trade_executions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.real_trade_executions ALTER COLUMN id SET DEFAULT nextval('public.real_trade_executions_id_seq'::regclass);


--
-- Name: real_trades id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.real_trades ALTER COLUMN id SET DEFAULT nextval('public.real_trades_id_seq'::regclass);


--
-- Name: risk_controls id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.risk_controls ALTER COLUMN id SET DEFAULT nextval('public.risk_controls_id_seq'::regclass);


--
-- Name: strategies id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.strategies ALTER COLUMN id SET DEFAULT nextval('public.strategies_id_seq'::regclass);


--
-- Name: strategy_config_changes id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.strategy_config_changes ALTER COLUMN id SET DEFAULT nextval('public.strategy_config_changes_id_seq'::regclass);


--
-- Name: users id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users ALTER COLUMN id SET DEFAULT nextval('public.users_id_seq'::regclass);


--
-- Name: backtests backtests_hash_unique; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.backtests
    ADD CONSTRAINT backtests_hash_unique UNIQUE (hash);


--
-- Name: backtests backtests_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.backtests
    ADD CONSTRAINT backtests_pkey PRIMARY KEY (id);


--
-- Name: broker_accounts broker_accounts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.broker_accounts
    ADD CONSTRAINT broker_accounts_pkey PRIMARY KEY (id);


--
-- Name: broker_accounts broker_accounts_user_broker_type_unique; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.broker_accounts
    ADD CONSTRAINT broker_accounts_user_broker_type_unique UNIQUE (user_id, broker, account_type);


--
-- Name: broker_events broker_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.broker_events
    ADD CONSTRAINT broker_events_pkey PRIMARY KEY (id);


--
-- Name: cache_locks cache_locks_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cache_locks
    ADD CONSTRAINT cache_locks_pkey PRIMARY KEY (key);


--
-- Name: cache cache_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cache
    ADD CONSTRAINT cache_pkey PRIMARY KEY (key);


--
-- Name: collector_configs collector_configs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.collector_configs
    ADD CONSTRAINT collector_configs_pkey PRIMARY KEY (id);


--
-- Name: collector_configs collector_configs_symbol_interval_broker_unique; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.collector_configs
    ADD CONSTRAINT collector_configs_symbol_interval_broker_unique UNIQUE (symbol, "interval", broker);


--
-- Name: failed_jobs failed_jobs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.failed_jobs
    ADD CONSTRAINT failed_jobs_pkey PRIMARY KEY (id);


--
-- Name: failed_jobs failed_jobs_uuid_unique; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.failed_jobs
    ADD CONSTRAINT failed_jobs_uuid_unique UNIQUE (uuid);


--
-- Name: funding_coverage funding_coverage_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.funding_coverage
    ADD CONSTRAINT funding_coverage_pkey PRIMARY KEY (symbol);


--
-- Name: funding_rates funding_rates_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.funding_rates
    ADD CONSTRAINT funding_rates_pkey PRIMARY KEY (symbol, funding_time);


--
-- Name: job_batches job_batches_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.job_batches
    ADD CONSTRAINT job_batches_pkey PRIMARY KEY (id);


--
-- Name: jobs jobs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.jobs
    ADD CONSTRAINT jobs_pkey PRIMARY KEY (id);


--
-- Name: migrations migrations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.migrations
    ADD CONSTRAINT migrations_pkey PRIMARY KEY (id);


--
-- Name: notifications notifications_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notifications
    ADD CONSTRAINT notifications_pkey PRIMARY KEY (id);


--
-- Name: ohlcv_deletions ohlcv_deletions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ohlcv_deletions
    ADD CONSTRAINT ohlcv_deletions_pkey PRIMARY KEY (id);


--
-- Name: paper_eval_log paper_eval_log_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.paper_eval_log
    ADD CONSTRAINT paper_eval_log_key UNIQUE (paper_strategy_config_id, bucket_time, code);


--
-- Name: paper_eval_log paper_eval_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.paper_eval_log
    ADD CONSTRAINT paper_eval_log_pkey PRIMARY KEY (id);


--
-- Name: paper_eval_state paper_eval_state_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.paper_eval_state
    ADD CONSTRAINT paper_eval_state_pkey PRIMARY KEY (paper_strategy_config_id);


--
-- Name: paper_strategy_configs paper_strategy_configs_backtest_symbol_unique; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.paper_strategy_configs
    ADD CONSTRAINT paper_strategy_configs_backtest_symbol_unique UNIQUE (backtest_id, symbol);


--
-- Name: paper_strategy_configs paper_strategy_configs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.paper_strategy_configs
    ADD CONSTRAINT paper_strategy_configs_pkey PRIMARY KEY (id);


--
-- Name: paper_trades paper_trades_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.paper_trades
    ADD CONSTRAINT paper_trades_pkey PRIMARY KEY (id);


--
-- Name: param_search_runs param_search_runs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.param_search_runs
    ADD CONSTRAINT param_search_runs_pkey PRIMARY KEY (id);


--
-- Name: password_reset_tokens password_reset_tokens_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.password_reset_tokens
    ADD CONSTRAINT password_reset_tokens_pkey PRIMARY KEY (email);


--
-- Name: python_engine_state python_engine_state_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.python_engine_state
    ADD CONSTRAINT python_engine_state_pkey PRIMARY KEY (key);


--
-- Name: real_strategy_subscriptions real_strategy_subscriptions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.real_strategy_subscriptions
    ADD CONSTRAINT real_strategy_subscriptions_pkey PRIMARY KEY (id);


--
-- Name: real_strategy_subscriptions real_subs_unique_v2; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.real_strategy_subscriptions
    ADD CONSTRAINT real_subs_unique_v2 UNIQUE (broker_account_id, paper_strategy_config_id);


--
-- Name: real_trade_executions real_trade_executions_exec_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.real_trade_executions
    ADD CONSTRAINT real_trade_executions_exec_id_key UNIQUE (exec_id);


--
-- Name: real_trade_executions real_trade_executions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.real_trade_executions
    ADD CONSTRAINT real_trade_executions_pkey PRIMARY KEY (id);


--
-- Name: real_trades real_trades_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.real_trades
    ADD CONSTRAINT real_trades_pkey PRIMARY KEY (id);


--
-- Name: risk_controls risk_controls_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.risk_controls
    ADD CONSTRAINT risk_controls_pkey PRIMARY KEY (id);


--
-- Name: sessions sessions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sessions
    ADD CONSTRAINT sessions_pkey PRIMARY KEY (id);


--
-- Name: strategies strategies_name_unique; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.strategies
    ADD CONSTRAINT strategies_name_unique UNIQUE (name);


--
-- Name: strategies strategies_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.strategies
    ADD CONSTRAINT strategies_pkey PRIMARY KEY (id);


--
-- Name: strategy_config_changes strategy_config_changes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.strategy_config_changes
    ADD CONSTRAINT strategy_config_changes_pkey PRIMARY KEY (id);


--
-- Name: users users_email_unique; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_email_unique UNIQUE (email);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: broker_accounts_user_id_status_index; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX broker_accounts_user_id_status_index ON public.broker_accounts USING btree (user_id, status);


--
-- Name: broker_events_account_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX broker_events_account_idx ON public.broker_events USING btree (broker_account_id, created_at DESC);


--
-- Name: broker_events_created_at_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX broker_events_created_at_idx ON public.broker_events USING btree (created_at);


--
-- Name: broker_events_pending_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX broker_events_pending_idx ON public.broker_events USING btree (id) WHERE (processed_at IS NULL);


--
-- Name: cache_expiration_index; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX cache_expiration_index ON public.cache USING btree (expiration);


--
-- Name: cache_locks_expiration_index; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX cache_locks_expiration_index ON public.cache_locks USING btree (expiration);


--
-- Name: failed_jobs_connection_queue_failed_at_index; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX failed_jobs_connection_queue_failed_at_index ON public.failed_jobs USING btree (connection, queue, failed_at);


--
-- Name: idx_backtests_strategy_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_backtests_strategy_created ON public.backtests USING btree (strategy_id, created_at DESC);


--
-- Name: idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_ohlcv_broker_symbol_interval_time ON public.ohlcv_data USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ohlcv_symbol_interval_time ON public.ohlcv_data USING btree (symbol, "interval", "time" DESC);


--
-- Name: jobs_queue_index; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX jobs_queue_index ON public.jobs USING btree (queue);


--
-- Name: notifications_created_at_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX notifications_created_at_idx ON public.notifications USING btree (created_at);


--
-- Name: notifications_notifiable_type_notifiable_id_index; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX notifications_notifiable_type_notifiable_id_index ON public.notifications USING btree (notifiable_type, notifiable_id);


--
-- Name: notifications_unread_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX notifications_unread_idx ON public.notifications USING btree (notifiable_id, created_at DESC) WHERE (read_at IS NULL);


--
-- Name: ohlcv_data_time_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ohlcv_data_time_idx ON public.ohlcv_data USING btree ("time" DESC);


--
-- Name: ohlcv_deletions_series_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ohlcv_deletions_series_idx ON public.ohlcv_deletions USING btree (broker, symbol, "interval", created_at DESC);


--
-- Name: paper_eval_log_last_at_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX paper_eval_log_last_at_idx ON public.paper_eval_log USING btree (last_at);


--
-- Name: paper_eval_log_recent_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX paper_eval_log_recent_idx ON public.paper_eval_log USING btree (paper_strategy_config_id, last_at DESC);


--
-- Name: paper_trades_config_status_index; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX paper_trades_config_status_index ON public.paper_trades USING btree (paper_strategy_config_id, status);


--
-- Name: paper_trades_one_open_per_config; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX paper_trades_one_open_per_config ON public.paper_trades USING btree (paper_strategy_config_id) WHERE ((status)::text = 'open'::text);


--
-- Name: paper_trades_status_index; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX paper_trades_status_index ON public.paper_trades USING btree (status);


--
-- Name: paper_trades_strategy_symbol_status_index; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX paper_trades_strategy_symbol_status_index ON public.paper_trades USING btree (strategy, symbol, status);


--
-- Name: param_search_runs_one_active_per_strategy; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX param_search_runs_one_active_per_strategy ON public.param_search_runs USING btree (strategy_id) WHERE ((status)::text = ANY ((ARRAY['queued'::character varying, 'running'::character varying])::text[]));


--
-- Name: param_search_runs_one_running; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX param_search_runs_one_running ON public.param_search_runs USING btree ((true)) WHERE ((status)::text = 'running'::text);


--
-- Name: param_search_runs_strategy_created_index; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX param_search_runs_strategy_created_index ON public.param_search_runs USING btree (strategy_id, created_at DESC);


--
-- Name: real_strategy_subscriptions_user_id_status_index; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX real_strategy_subscriptions_user_id_status_index ON public.real_strategy_subscriptions USING btree (user_id, status);


--
-- Name: real_trade_executions_trade_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX real_trade_executions_trade_idx ON public.real_trade_executions USING btree (real_trade_id);


--
-- Name: real_trades_broker_account_id_status_index; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX real_trades_broker_account_id_status_index ON public.real_trades USING btree (broker_account_id, status);


--
-- Name: real_trades_closed_month_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX real_trades_closed_month_idx ON public.real_trades USING btree (broker_account_id, exit_time) WHERE ((status)::text = 'closed'::text);


--
-- Name: real_trades_paper_strategy_config_id_index; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX real_trades_paper_strategy_config_id_index ON public.real_trades USING btree (paper_strategy_config_id);


--
-- Name: real_trades_pending_open_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX real_trades_pending_open_idx ON public.real_trades USING btree (broker_account_id) WHERE ((status)::text = 'pending_open'::text);


--
-- Name: risk_controls_strategy_symbol_active_index; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX risk_controls_strategy_symbol_active_index ON public.risk_controls USING btree (strategy, symbol, active);


--
-- Name: sessions_last_activity_index; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX sessions_last_activity_index ON public.sessions USING btree (last_activity);


--
-- Name: sessions_user_id_index; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX sessions_user_id_index ON public.sessions USING btree (user_id);


--
-- Name: strategy_config_changes_config_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX strategy_config_changes_config_created ON public.strategy_config_changes USING btree (paper_strategy_config_id, created_at DESC);


--
-- Name: backtests backtests_strategy_id_foreign; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.backtests
    ADD CONSTRAINT backtests_strategy_id_foreign FOREIGN KEY (strategy_id) REFERENCES public.strategies(id) ON DELETE CASCADE;


--
-- Name: broker_accounts broker_accounts_user_id_foreign; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.broker_accounts
    ADD CONSTRAINT broker_accounts_user_id_foreign FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: paper_strategy_configs paper_strategy_configs_backtest_id_foreign; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.paper_strategy_configs
    ADD CONSTRAINT paper_strategy_configs_backtest_id_foreign FOREIGN KEY (backtest_id) REFERENCES public.backtests(id) ON DELETE RESTRICT;


--
-- Name: paper_trades paper_trades_paper_strategy_config_id_foreign; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.paper_trades
    ADD CONSTRAINT paper_trades_paper_strategy_config_id_foreign FOREIGN KEY (paper_strategy_config_id) REFERENCES public.paper_strategy_configs(id) ON DELETE SET NULL;


--
-- Name: param_search_runs param_search_runs_strategy_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.param_search_runs
    ADD CONSTRAINT param_search_runs_strategy_id_fkey FOREIGN KEY (strategy_id) REFERENCES public.strategies(id) ON DELETE CASCADE;


--
-- Name: param_search_runs param_search_runs_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.param_search_runs
    ADD CONSTRAINT param_search_runs_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: real_strategy_subscriptions real_strategy_subscriptions_broker_account_id_foreign; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.real_strategy_subscriptions
    ADD CONSTRAINT real_strategy_subscriptions_broker_account_id_foreign FOREIGN KEY (broker_account_id) REFERENCES public.broker_accounts(id) ON DELETE CASCADE;


--
-- Name: real_strategy_subscriptions real_strategy_subscriptions_paper_strategy_config_id_foreign; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.real_strategy_subscriptions
    ADD CONSTRAINT real_strategy_subscriptions_paper_strategy_config_id_foreign FOREIGN KEY (paper_strategy_config_id) REFERENCES public.paper_strategy_configs(id) ON DELETE SET NULL;


--
-- Name: real_strategy_subscriptions real_strategy_subscriptions_user_id_foreign; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.real_strategy_subscriptions
    ADD CONSTRAINT real_strategy_subscriptions_user_id_foreign FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: real_trade_executions real_trade_executions_real_trade_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.real_trade_executions
    ADD CONSTRAINT real_trade_executions_real_trade_id_fkey FOREIGN KEY (real_trade_id) REFERENCES public.real_trades(id) ON DELETE CASCADE;


--
-- Name: real_trades real_trades_broker_account_id_foreign; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.real_trades
    ADD CONSTRAINT real_trades_broker_account_id_foreign FOREIGN KEY (broker_account_id) REFERENCES public.broker_accounts(id) ON DELETE SET NULL;


--
-- Name: real_trades real_trades_paper_strategy_config_id_foreign; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.real_trades
    ADD CONSTRAINT real_trades_paper_strategy_config_id_foreign FOREIGN KEY (paper_strategy_config_id) REFERENCES public.paper_strategy_configs(id) ON DELETE SET NULL;


--
-- Name: real_trades real_trades_subscription_id_foreign; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.real_trades
    ADD CONSTRAINT real_trades_subscription_id_foreign FOREIGN KEY (subscription_id) REFERENCES public.real_strategy_subscriptions(id) ON DELETE SET NULL;


--
-- Name: real_trades real_trades_user_id_foreign; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.real_trades
    ADD CONSTRAINT real_trades_user_id_foreign FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: strategy_config_changes strategy_config_changes_backtest_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.strategy_config_changes
    ADD CONSTRAINT strategy_config_changes_backtest_id_fkey FOREIGN KEY (backtest_id) REFERENCES public.backtests(id) ON DELETE SET NULL;


--
-- Name: strategy_config_changes strategy_config_changes_paper_strategy_config_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.strategy_config_changes
    ADD CONSTRAINT strategy_config_changes_paper_strategy_config_id_fkey FOREIGN KEY (paper_strategy_config_id) REFERENCES public.paper_strategy_configs(id) ON DELETE SET NULL;


--
-- Name: strategy_config_changes strategy_config_changes_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.strategy_config_changes
    ADD CONSTRAINT strategy_config_changes_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- PostgreSQL database dump complete
--



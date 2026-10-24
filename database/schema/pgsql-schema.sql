--
-- PostgreSQL database dump
--

\restrict qkJ5nAfwDKWwpSmNTsTz7UXB9dMOtKlY7dgbCuQoedbxBZ7GpG6jfgogzxxVLzo

-- Dumped from database version 16.14 (Ubuntu 16.14-0ubuntu0.24.04.1)
-- Dumped by pg_dump version 16.14 (Ubuntu 16.14-0ubuntu0.24.04.1)

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
-- Name: timescaledb; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS timescaledb WITH SCHEMA public;


--
-- Name: EXTENSION timescaledb; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION timescaledb IS 'Enables scalable inserts and complex queries for time-series data (Community Edition)';


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
-- Name: _hyper_1_100_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_100_chunk (
    CONSTRAINT constraint_100 CHECK ((("time" >= '2026-03-05 00:00:00+00'::timestamp with time zone) AND ("time" < '2026-03-12 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_101_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_101_chunk (
    CONSTRAINT constraint_101 CHECK ((("time" >= '2026-03-12 00:00:00+00'::timestamp with time zone) AND ("time" < '2026-03-19 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_102_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_102_chunk (
    CONSTRAINT constraint_102 CHECK ((("time" >= '2026-03-19 00:00:00+00'::timestamp with time zone) AND ("time" < '2026-03-26 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_103_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_103_chunk (
    CONSTRAINT constraint_103 CHECK ((("time" >= '2026-03-26 00:00:00+00'::timestamp with time zone) AND ("time" < '2026-04-02 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_104_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_104_chunk (
    CONSTRAINT constraint_104 CHECK ((("time" >= '2026-04-02 00:00:00+00'::timestamp with time zone) AND ("time" < '2026-04-09 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_105_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_105_chunk (
    CONSTRAINT constraint_105 CHECK ((("time" >= '2026-04-09 00:00:00+00'::timestamp with time zone) AND ("time" < '2026-04-16 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_106_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_106_chunk (
    CONSTRAINT constraint_106 CHECK ((("time" >= '2026-06-11 00:00:00+00'::timestamp with time zone) AND ("time" < '2026-06-18 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_107_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_107_chunk (
    CONSTRAINT constraint_107 CHECK ((("time" >= '2026-06-18 00:00:00+00'::timestamp with time zone) AND ("time" < '2026-06-25 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_108_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_108_chunk (
    CONSTRAINT constraint_108 CHECK ((("time" >= '2026-06-25 00:00:00+00'::timestamp with time zone) AND ("time" < '2026-07-02 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_109_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_109_chunk (
    CONSTRAINT constraint_109 CHECK ((("time" >= '2026-07-02 00:00:00+00'::timestamp with time zone) AND ("time" < '2026-07-09 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_10_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_10_chunk (
    CONSTRAINT constraint_10 CHECK ((("time" >= '2024-06-13 00:00:00+00'::timestamp with time zone) AND ("time" < '2024-06-20 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_110_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_110_chunk (
    CONSTRAINT constraint_110 CHECK ((("time" >= '2026-07-09 00:00:00+00'::timestamp with time zone) AND ("time" < '2026-07-16 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_111_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_111_chunk (
    CONSTRAINT constraint_111 CHECK ((("time" >= '2026-07-16 00:00:00+00'::timestamp with time zone) AND ("time" < '2026-07-23 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_112_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_112_chunk (
    CONSTRAINT constraint_112 CHECK ((("time" >= '2026-07-23 00:00:00+00'::timestamp with time zone) AND ("time" < '2026-07-30 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_113_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_113_chunk (
    CONSTRAINT constraint_113 CHECK ((("time" >= '2026-07-30 00:00:00+00'::timestamp with time zone) AND ("time" < '2026-08-06 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_114_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_114_chunk (
    CONSTRAINT constraint_114 CHECK ((("time" >= '2026-08-06 00:00:00+00'::timestamp with time zone) AND ("time" < '2026-08-13 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_115_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_115_chunk (
    CONSTRAINT constraint_115 CHECK ((("time" >= '2026-08-13 00:00:00+00'::timestamp with time zone) AND ("time" < '2026-08-20 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_116_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_116_chunk (
    CONSTRAINT constraint_116 CHECK ((("time" >= '2026-08-20 00:00:00+00'::timestamp with time zone) AND ("time" < '2026-08-27 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_117_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_117_chunk (
    CONSTRAINT constraint_117 CHECK ((("time" >= '2026-08-27 00:00:00+00'::timestamp with time zone) AND ("time" < '2026-09-03 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_118_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_118_chunk (
    CONSTRAINT constraint_118 CHECK ((("time" >= '2026-09-03 00:00:00+00'::timestamp with time zone) AND ("time" < '2026-09-10 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_119_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_119_chunk (
    CONSTRAINT constraint_119 CHECK ((("time" >= '2026-09-10 00:00:00+00'::timestamp with time zone) AND ("time" < '2026-09-17 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_11_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_11_chunk (
    CONSTRAINT constraint_11 CHECK ((("time" >= '2024-06-20 00:00:00+00'::timestamp with time zone) AND ("time" < '2024-06-27 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_120_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_120_chunk (
    CONSTRAINT constraint_120 CHECK ((("time" >= '2026-09-17 00:00:00+00'::timestamp with time zone) AND ("time" < '2026-09-24 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_121_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_121_chunk (
    CONSTRAINT constraint_121 CHECK ((("time" >= '2026-09-24 00:00:00+00'::timestamp with time zone) AND ("time" < '2026-10-01 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_122_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_122_chunk (
    CONSTRAINT constraint_122 CHECK ((("time" >= '2026-10-01 00:00:00+00'::timestamp with time zone) AND ("time" < '2026-10-08 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_123_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_123_chunk (
    CONSTRAINT constraint_123 CHECK ((("time" >= '2026-10-08 00:00:00+00'::timestamp with time zone) AND ("time" < '2026-10-15 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_124_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_124_chunk (
    CONSTRAINT constraint_124 CHECK ((("time" >= '2026-10-15 00:00:00+00'::timestamp with time zone) AND ("time" < '2026-10-22 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_125_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_125_chunk (
    CONSTRAINT constraint_125 CHECK ((("time" >= '2024-05-30 00:00:00+00'::timestamp with time zone) AND ("time" < '2024-06-06 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_126_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_126_chunk (
    CONSTRAINT constraint_126 CHECK ((("time" >= '2026-10-22 00:00:00+00'::timestamp with time zone) AND ("time" < '2026-10-29 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_12_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_12_chunk (
    CONSTRAINT constraint_12 CHECK ((("time" >= '2024-06-27 00:00:00+00'::timestamp with time zone) AND ("time" < '2024-07-04 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_13_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_13_chunk (
    CONSTRAINT constraint_13 CHECK ((("time" >= '2024-07-04 00:00:00+00'::timestamp with time zone) AND ("time" < '2024-07-11 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_14_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_14_chunk (
    CONSTRAINT constraint_14 CHECK ((("time" >= '2024-07-11 00:00:00+00'::timestamp with time zone) AND ("time" < '2024-07-18 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_15_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_15_chunk (
    CONSTRAINT constraint_15 CHECK ((("time" >= '2024-07-18 00:00:00+00'::timestamp with time zone) AND ("time" < '2024-07-25 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_16_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_16_chunk (
    CONSTRAINT constraint_16 CHECK ((("time" >= '2024-07-25 00:00:00+00'::timestamp with time zone) AND ("time" < '2024-08-01 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_17_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_17_chunk (
    CONSTRAINT constraint_17 CHECK ((("time" >= '2024-08-01 00:00:00+00'::timestamp with time zone) AND ("time" < '2024-08-08 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_18_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_18_chunk (
    CONSTRAINT constraint_18 CHECK ((("time" >= '2024-08-08 00:00:00+00'::timestamp with time zone) AND ("time" < '2024-08-15 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_19_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_19_chunk (
    CONSTRAINT constraint_19 CHECK ((("time" >= '2024-08-15 00:00:00+00'::timestamp with time zone) AND ("time" < '2024-08-22 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_1_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_1_chunk (
    CONSTRAINT constraint_1 CHECK ((("time" >= '2026-04-16 00:00:00+00'::timestamp with time zone) AND ("time" < '2026-04-23 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_20_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_20_chunk (
    CONSTRAINT constraint_20 CHECK ((("time" >= '2024-08-22 00:00:00+00'::timestamp with time zone) AND ("time" < '2024-08-29 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_21_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_21_chunk (
    CONSTRAINT constraint_21 CHECK ((("time" >= '2024-08-29 00:00:00+00'::timestamp with time zone) AND ("time" < '2024-09-05 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_22_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_22_chunk (
    CONSTRAINT constraint_22 CHECK ((("time" >= '2024-09-05 00:00:00+00'::timestamp with time zone) AND ("time" < '2024-09-12 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_23_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_23_chunk (
    CONSTRAINT constraint_23 CHECK ((("time" >= '2024-09-12 00:00:00+00'::timestamp with time zone) AND ("time" < '2024-09-19 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_24_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_24_chunk (
    CONSTRAINT constraint_24 CHECK ((("time" >= '2024-09-19 00:00:00+00'::timestamp with time zone) AND ("time" < '2024-09-26 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_25_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_25_chunk (
    CONSTRAINT constraint_25 CHECK ((("time" >= '2024-09-26 00:00:00+00'::timestamp with time zone) AND ("time" < '2024-10-03 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_26_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_26_chunk (
    CONSTRAINT constraint_26 CHECK ((("time" >= '2024-10-03 00:00:00+00'::timestamp with time zone) AND ("time" < '2024-10-10 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_27_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_27_chunk (
    CONSTRAINT constraint_27 CHECK ((("time" >= '2024-10-10 00:00:00+00'::timestamp with time zone) AND ("time" < '2024-10-17 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_28_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_28_chunk (
    CONSTRAINT constraint_28 CHECK ((("time" >= '2024-10-17 00:00:00+00'::timestamp with time zone) AND ("time" < '2024-10-24 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_29_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_29_chunk (
    CONSTRAINT constraint_29 CHECK ((("time" >= '2024-10-24 00:00:00+00'::timestamp with time zone) AND ("time" < '2024-10-31 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_2_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_2_chunk (
    CONSTRAINT constraint_2 CHECK ((("time" >= '2026-04-23 00:00:00+00'::timestamp with time zone) AND ("time" < '2026-04-30 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_30_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_30_chunk (
    CONSTRAINT constraint_30 CHECK ((("time" >= '2024-10-31 00:00:00+00'::timestamp with time zone) AND ("time" < '2024-11-07 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_31_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_31_chunk (
    CONSTRAINT constraint_31 CHECK ((("time" >= '2024-11-07 00:00:00+00'::timestamp with time zone) AND ("time" < '2024-11-14 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_32_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_32_chunk (
    CONSTRAINT constraint_32 CHECK ((("time" >= '2024-11-14 00:00:00+00'::timestamp with time zone) AND ("time" < '2024-11-21 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_33_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_33_chunk (
    CONSTRAINT constraint_33 CHECK ((("time" >= '2024-11-21 00:00:00+00'::timestamp with time zone) AND ("time" < '2024-11-28 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_34_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_34_chunk (
    CONSTRAINT constraint_34 CHECK ((("time" >= '2024-11-28 00:00:00+00'::timestamp with time zone) AND ("time" < '2024-12-05 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_35_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_35_chunk (
    CONSTRAINT constraint_35 CHECK ((("time" >= '2024-12-05 00:00:00+00'::timestamp with time zone) AND ("time" < '2024-12-12 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_36_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_36_chunk (
    CONSTRAINT constraint_36 CHECK ((("time" >= '2024-12-12 00:00:00+00'::timestamp with time zone) AND ("time" < '2024-12-19 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_37_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_37_chunk (
    CONSTRAINT constraint_37 CHECK ((("time" >= '2024-12-19 00:00:00+00'::timestamp with time zone) AND ("time" < '2024-12-26 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_38_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_38_chunk (
    CONSTRAINT constraint_38 CHECK ((("time" >= '2024-12-26 00:00:00+00'::timestamp with time zone) AND ("time" < '2025-01-02 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_39_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_39_chunk (
    CONSTRAINT constraint_39 CHECK ((("time" >= '2025-01-02 00:00:00+00'::timestamp with time zone) AND ("time" < '2025-01-09 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_3_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_3_chunk (
    CONSTRAINT constraint_3 CHECK ((("time" >= '2026-04-30 00:00:00+00'::timestamp with time zone) AND ("time" < '2026-05-07 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_40_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_40_chunk (
    CONSTRAINT constraint_40 CHECK ((("time" >= '2025-01-09 00:00:00+00'::timestamp with time zone) AND ("time" < '2025-01-16 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_41_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_41_chunk (
    CONSTRAINT constraint_41 CHECK ((("time" >= '2025-01-16 00:00:00+00'::timestamp with time zone) AND ("time" < '2025-01-23 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_42_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_42_chunk (
    CONSTRAINT constraint_42 CHECK ((("time" >= '2025-01-23 00:00:00+00'::timestamp with time zone) AND ("time" < '2025-01-30 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_43_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_43_chunk (
    CONSTRAINT constraint_43 CHECK ((("time" >= '2025-01-30 00:00:00+00'::timestamp with time zone) AND ("time" < '2025-02-06 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_44_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_44_chunk (
    CONSTRAINT constraint_44 CHECK ((("time" >= '2025-02-06 00:00:00+00'::timestamp with time zone) AND ("time" < '2025-02-13 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_45_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_45_chunk (
    CONSTRAINT constraint_45 CHECK ((("time" >= '2025-02-13 00:00:00+00'::timestamp with time zone) AND ("time" < '2025-02-20 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_46_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_46_chunk (
    CONSTRAINT constraint_46 CHECK ((("time" >= '2025-02-20 00:00:00+00'::timestamp with time zone) AND ("time" < '2025-02-27 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_47_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_47_chunk (
    CONSTRAINT constraint_47 CHECK ((("time" >= '2025-02-27 00:00:00+00'::timestamp with time zone) AND ("time" < '2025-03-06 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_48_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_48_chunk (
    CONSTRAINT constraint_48 CHECK ((("time" >= '2025-03-06 00:00:00+00'::timestamp with time zone) AND ("time" < '2025-03-13 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_49_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_49_chunk (
    CONSTRAINT constraint_49 CHECK ((("time" >= '2025-03-13 00:00:00+00'::timestamp with time zone) AND ("time" < '2025-03-20 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_4_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_4_chunk (
    CONSTRAINT constraint_4 CHECK ((("time" >= '2026-05-07 00:00:00+00'::timestamp with time zone) AND ("time" < '2026-05-14 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_50_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_50_chunk (
    CONSTRAINT constraint_50 CHECK ((("time" >= '2025-03-20 00:00:00+00'::timestamp with time zone) AND ("time" < '2025-03-27 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_51_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_51_chunk (
    CONSTRAINT constraint_51 CHECK ((("time" >= '2025-03-27 00:00:00+00'::timestamp with time zone) AND ("time" < '2025-04-03 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_52_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_52_chunk (
    CONSTRAINT constraint_52 CHECK ((("time" >= '2025-04-03 00:00:00+00'::timestamp with time zone) AND ("time" < '2025-04-10 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_53_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_53_chunk (
    CONSTRAINT constraint_53 CHECK ((("time" >= '2025-04-10 00:00:00+00'::timestamp with time zone) AND ("time" < '2025-04-17 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_54_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_54_chunk (
    CONSTRAINT constraint_54 CHECK ((("time" >= '2025-04-17 00:00:00+00'::timestamp with time zone) AND ("time" < '2025-04-24 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_55_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_55_chunk (
    CONSTRAINT constraint_55 CHECK ((("time" >= '2025-04-24 00:00:00+00'::timestamp with time zone) AND ("time" < '2025-05-01 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_56_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_56_chunk (
    CONSTRAINT constraint_56 CHECK ((("time" >= '2025-05-01 00:00:00+00'::timestamp with time zone) AND ("time" < '2025-05-08 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_57_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_57_chunk (
    CONSTRAINT constraint_57 CHECK ((("time" >= '2025-05-08 00:00:00+00'::timestamp with time zone) AND ("time" < '2025-05-15 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_58_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_58_chunk (
    CONSTRAINT constraint_58 CHECK ((("time" >= '2025-05-15 00:00:00+00'::timestamp with time zone) AND ("time" < '2025-05-22 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_59_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_59_chunk (
    CONSTRAINT constraint_59 CHECK ((("time" >= '2025-05-22 00:00:00+00'::timestamp with time zone) AND ("time" < '2025-05-29 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_5_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_5_chunk (
    CONSTRAINT constraint_5 CHECK ((("time" >= '2026-05-14 00:00:00+00'::timestamp with time zone) AND ("time" < '2026-05-21 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_60_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_60_chunk (
    CONSTRAINT constraint_60 CHECK ((("time" >= '2025-05-29 00:00:00+00'::timestamp with time zone) AND ("time" < '2025-06-05 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_61_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_61_chunk (
    CONSTRAINT constraint_61 CHECK ((("time" >= '2025-06-05 00:00:00+00'::timestamp with time zone) AND ("time" < '2025-06-12 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_62_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_62_chunk (
    CONSTRAINT constraint_62 CHECK ((("time" >= '2025-06-12 00:00:00+00'::timestamp with time zone) AND ("time" < '2025-06-19 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_63_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_63_chunk (
    CONSTRAINT constraint_63 CHECK ((("time" >= '2025-06-19 00:00:00+00'::timestamp with time zone) AND ("time" < '2025-06-26 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_64_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_64_chunk (
    CONSTRAINT constraint_64 CHECK ((("time" >= '2025-06-26 00:00:00+00'::timestamp with time zone) AND ("time" < '2025-07-03 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_65_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_65_chunk (
    CONSTRAINT constraint_65 CHECK ((("time" >= '2025-07-03 00:00:00+00'::timestamp with time zone) AND ("time" < '2025-07-10 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_66_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_66_chunk (
    CONSTRAINT constraint_66 CHECK ((("time" >= '2025-07-10 00:00:00+00'::timestamp with time zone) AND ("time" < '2025-07-17 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_67_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_67_chunk (
    CONSTRAINT constraint_67 CHECK ((("time" >= '2025-07-17 00:00:00+00'::timestamp with time zone) AND ("time" < '2025-07-24 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_68_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_68_chunk (
    CONSTRAINT constraint_68 CHECK ((("time" >= '2025-07-24 00:00:00+00'::timestamp with time zone) AND ("time" < '2025-07-31 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_69_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_69_chunk (
    CONSTRAINT constraint_69 CHECK ((("time" >= '2025-07-31 00:00:00+00'::timestamp with time zone) AND ("time" < '2025-08-07 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_6_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_6_chunk (
    CONSTRAINT constraint_6 CHECK ((("time" >= '2026-05-21 00:00:00+00'::timestamp with time zone) AND ("time" < '2026-05-28 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_70_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_70_chunk (
    CONSTRAINT constraint_70 CHECK ((("time" >= '2025-08-07 00:00:00+00'::timestamp with time zone) AND ("time" < '2025-08-14 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_71_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_71_chunk (
    CONSTRAINT constraint_71 CHECK ((("time" >= '2025-08-14 00:00:00+00'::timestamp with time zone) AND ("time" < '2025-08-21 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_72_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_72_chunk (
    CONSTRAINT constraint_72 CHECK ((("time" >= '2025-08-21 00:00:00+00'::timestamp with time zone) AND ("time" < '2025-08-28 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_73_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_73_chunk (
    CONSTRAINT constraint_73 CHECK ((("time" >= '2025-08-28 00:00:00+00'::timestamp with time zone) AND ("time" < '2025-09-04 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_74_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_74_chunk (
    CONSTRAINT constraint_74 CHECK ((("time" >= '2025-09-04 00:00:00+00'::timestamp with time zone) AND ("time" < '2025-09-11 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_75_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_75_chunk (
    CONSTRAINT constraint_75 CHECK ((("time" >= '2025-09-11 00:00:00+00'::timestamp with time zone) AND ("time" < '2025-09-18 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_76_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_76_chunk (
    CONSTRAINT constraint_76 CHECK ((("time" >= '2025-09-18 00:00:00+00'::timestamp with time zone) AND ("time" < '2025-09-25 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_77_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_77_chunk (
    CONSTRAINT constraint_77 CHECK ((("time" >= '2025-09-25 00:00:00+00'::timestamp with time zone) AND ("time" < '2025-10-02 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_78_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_78_chunk (
    CONSTRAINT constraint_78 CHECK ((("time" >= '2025-10-02 00:00:00+00'::timestamp with time zone) AND ("time" < '2025-10-09 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_79_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_79_chunk (
    CONSTRAINT constraint_79 CHECK ((("time" >= '2025-10-09 00:00:00+00'::timestamp with time zone) AND ("time" < '2025-10-16 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_7_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_7_chunk (
    CONSTRAINT constraint_7 CHECK ((("time" >= '2026-05-28 00:00:00+00'::timestamp with time zone) AND ("time" < '2026-06-04 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_80_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_80_chunk (
    CONSTRAINT constraint_80 CHECK ((("time" >= '2025-10-16 00:00:00+00'::timestamp with time zone) AND ("time" < '2025-10-23 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_81_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_81_chunk (
    CONSTRAINT constraint_81 CHECK ((("time" >= '2025-10-23 00:00:00+00'::timestamp with time zone) AND ("time" < '2025-10-30 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_82_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_82_chunk (
    CONSTRAINT constraint_82 CHECK ((("time" >= '2025-10-30 00:00:00+00'::timestamp with time zone) AND ("time" < '2025-11-06 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_83_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_83_chunk (
    CONSTRAINT constraint_83 CHECK ((("time" >= '2025-11-06 00:00:00+00'::timestamp with time zone) AND ("time" < '2025-11-13 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_84_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_84_chunk (
    CONSTRAINT constraint_84 CHECK ((("time" >= '2025-11-13 00:00:00+00'::timestamp with time zone) AND ("time" < '2025-11-20 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_85_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_85_chunk (
    CONSTRAINT constraint_85 CHECK ((("time" >= '2025-11-20 00:00:00+00'::timestamp with time zone) AND ("time" < '2025-11-27 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_86_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_86_chunk (
    CONSTRAINT constraint_86 CHECK ((("time" >= '2025-11-27 00:00:00+00'::timestamp with time zone) AND ("time" < '2025-12-04 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_87_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_87_chunk (
    CONSTRAINT constraint_87 CHECK ((("time" >= '2025-12-04 00:00:00+00'::timestamp with time zone) AND ("time" < '2025-12-11 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_88_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_88_chunk (
    CONSTRAINT constraint_88 CHECK ((("time" >= '2025-12-11 00:00:00+00'::timestamp with time zone) AND ("time" < '2025-12-18 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_89_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_89_chunk (
    CONSTRAINT constraint_89 CHECK ((("time" >= '2025-12-18 00:00:00+00'::timestamp with time zone) AND ("time" < '2025-12-25 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_8_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_8_chunk (
    CONSTRAINT constraint_8 CHECK ((("time" >= '2026-06-04 00:00:00+00'::timestamp with time zone) AND ("time" < '2026-06-11 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_90_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_90_chunk (
    CONSTRAINT constraint_90 CHECK ((("time" >= '2025-12-25 00:00:00+00'::timestamp with time zone) AND ("time" < '2026-01-01 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_91_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_91_chunk (
    CONSTRAINT constraint_91 CHECK ((("time" >= '2026-01-01 00:00:00+00'::timestamp with time zone) AND ("time" < '2026-01-08 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_92_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_92_chunk (
    CONSTRAINT constraint_92 CHECK ((("time" >= '2026-01-08 00:00:00+00'::timestamp with time zone) AND ("time" < '2026-01-15 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_93_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_93_chunk (
    CONSTRAINT constraint_93 CHECK ((("time" >= '2026-01-15 00:00:00+00'::timestamp with time zone) AND ("time" < '2026-01-22 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_94_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_94_chunk (
    CONSTRAINT constraint_94 CHECK ((("time" >= '2026-01-22 00:00:00+00'::timestamp with time zone) AND ("time" < '2026-01-29 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_95_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_95_chunk (
    CONSTRAINT constraint_95 CHECK ((("time" >= '2026-01-29 00:00:00+00'::timestamp with time zone) AND ("time" < '2026-02-05 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_96_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_96_chunk (
    CONSTRAINT constraint_96 CHECK ((("time" >= '2026-02-05 00:00:00+00'::timestamp with time zone) AND ("time" < '2026-02-12 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_97_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_97_chunk (
    CONSTRAINT constraint_97 CHECK ((("time" >= '2026-02-12 00:00:00+00'::timestamp with time zone) AND ("time" < '2026-02-19 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_98_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_98_chunk (
    CONSTRAINT constraint_98 CHECK ((("time" >= '2026-02-19 00:00:00+00'::timestamp with time zone) AND ("time" < '2026-02-26 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_99_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_99_chunk (
    CONSTRAINT constraint_99 CHECK ((("time" >= '2026-02-26 00:00:00+00'::timestamp with time zone) AND ("time" < '2026-03-05 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


--
-- Name: _hyper_1_9_chunk; Type: TABLE; Schema: _timescaledb_internal; Owner: -
--

CREATE TABLE _timescaledb_internal._hyper_1_9_chunk (
    CONSTRAINT constraint_9 CHECK ((("time" >= '2024-06-06 00:00:00+00'::timestamp with time zone) AND ("time" < '2024-06-13 00:00:00+00'::timestamp with time zone)))
)
INHERITS (public.ohlcv_data);


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
    hash character varying(32)
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
    credentials_extra text,
    CONSTRAINT broker_accounts_account_type_check CHECK (((account_type)::text = ANY ((ARRAY['real'::character varying, 'demo'::character varying])::text[]))),
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
    broker character varying(20) DEFAULT 'bybit'::character varying NOT NULL,
    epic character varying(40)
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
    backtest_id bigint
);


--
-- Name: COLUMN paper_strategy_configs.audited_months; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.paper_strategy_configs.audited_months IS 'Meses auditados en el ultimo backtest';


--
-- Name: COLUMN paper_strategy_configs.avg_win_rate; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.paper_strategy_configs.avg_win_rate IS 'Win rate promedio mensual del ultimo backtest (%)';


--
-- Name: COLUMN paper_strategy_configs.avg_monthly_pnl; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.paper_strategy_configs.avg_monthly_pnl IS 'P&L promedio mensual del ultimo backtest (%)';


--
-- Name: COLUMN paper_strategy_configs.avg_monthly_trades; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.paper_strategy_configs.avg_monthly_trades IS 'Promedio de operaciones por mes del ultimo backtest';


--
-- Name: COLUMN paper_strategy_configs.total_return_pct; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.paper_strategy_configs.total_return_pct IS 'Retorno total acumulado del ultimo backtest (%)';


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
    CONSTRAINT real_strategy_subscriptions_status_check CHECK (((status)::text = ANY ((ARRAY['active'::character varying, 'paused'::character varying])::text[])))
);


--
-- Name: COLUMN real_strategy_subscriptions.risk_override_pct; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.real_strategy_subscriptions.risk_override_pct IS 'Sobrescribe risk_per_trade_pct de la config para esta suscripcion especifica';


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
-- Name: _hyper_1_100_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_100_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_101_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_101_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_102_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_102_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_103_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_103_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_104_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_104_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_105_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_105_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_106_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_106_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_107_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_107_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_108_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_108_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_109_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_109_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_10_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_10_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_110_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_110_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_111_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_111_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_112_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_112_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_113_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_113_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_114_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_114_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_115_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_115_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_116_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_116_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_117_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_117_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_118_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_118_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_119_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_119_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_11_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_11_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_120_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_120_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_121_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_121_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_122_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_122_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_123_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_123_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_124_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_124_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_125_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_125_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_126_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_126_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_12_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_12_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_13_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_13_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_14_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_14_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_15_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_15_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_16_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_16_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_17_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_17_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_18_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_18_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_19_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_19_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_1_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_1_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_20_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_20_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_21_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_21_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_22_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_22_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_23_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_23_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_24_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_24_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_25_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_25_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_26_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_26_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_27_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_27_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_28_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_28_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_29_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_29_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_2_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_2_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_30_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_30_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_31_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_31_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_32_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_32_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_33_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_33_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_34_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_34_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_35_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_35_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_36_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_36_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_37_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_37_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_38_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_38_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_39_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_39_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_3_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_3_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_40_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_40_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_41_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_41_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_42_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_42_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_43_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_43_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_44_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_44_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_45_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_45_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_46_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_46_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_47_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_47_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_48_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_48_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_49_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_49_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_4_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_4_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_50_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_50_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_51_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_51_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_52_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_52_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_53_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_53_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_54_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_54_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_55_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_55_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_56_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_56_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_57_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_57_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_58_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_58_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_59_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_59_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_5_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_5_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_60_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_60_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_61_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_61_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_62_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_62_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_63_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_63_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_64_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_64_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_65_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_65_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_66_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_66_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_67_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_67_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_68_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_68_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_69_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_69_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_6_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_6_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_70_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_70_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_71_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_71_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_72_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_72_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_73_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_73_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_74_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_74_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_75_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_75_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_76_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_76_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_77_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_77_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_78_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_78_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_79_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_79_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_7_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_7_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_80_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_80_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_81_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_81_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_82_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_82_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_83_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_83_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_84_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_84_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_85_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_85_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_86_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_86_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_87_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_87_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_88_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_88_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_89_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_89_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_8_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_8_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_90_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_90_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_91_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_91_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_92_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_92_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_93_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_93_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_94_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_94_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_95_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_95_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_96_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_96_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_97_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_97_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_98_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_98_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_99_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_99_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: _hyper_1_9_chunk broker; Type: DEFAULT; Schema: _timescaledb_internal; Owner: -
--

ALTER TABLE ONLY _timescaledb_internal._hyper_1_9_chunk ALTER COLUMN broker SET DEFAULT 'bybit'::character varying;


--
-- Name: backtests id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.backtests ALTER COLUMN id SET DEFAULT nextval('public.backtests_id_seq'::regclass);


--
-- Name: broker_accounts id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.broker_accounts ALTER COLUMN id SET DEFAULT nextval('public.broker_accounts_id_seq'::regclass);


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
-- Name: paper_strategy_configs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.paper_strategy_configs ALTER COLUMN id SET DEFAULT nextval('public.paper_strategy_configs_id_seq'::regclass);


--
-- Name: paper_trades id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.paper_trades ALTER COLUMN id SET DEFAULT nextval('public.paper_trades_id_seq'::regclass);


--
-- Name: real_strategy_subscriptions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.real_strategy_subscriptions ALTER COLUMN id SET DEFAULT nextval('public.real_strategy_subscriptions_id_seq'::regclass);


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
-- Name: _hyper_1_100_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_100_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_100_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_100_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_100_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_100_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_100_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_100_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_100_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_101_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_101_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_101_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_101_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_101_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_101_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_101_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_101_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_101_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_102_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_102_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_102_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_102_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_102_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_102_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_102_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_102_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_102_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_103_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_103_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_103_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_103_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_103_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_103_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_103_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_103_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_103_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_104_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_104_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_104_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_104_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_104_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_104_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_104_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_104_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_104_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_105_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_105_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_105_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_105_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_105_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_105_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_105_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_105_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_105_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_106_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_106_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_106_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_106_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_106_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_106_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_106_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_106_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_106_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_107_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_107_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_107_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_107_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_107_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_107_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_107_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_107_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_107_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_108_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_108_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_108_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_108_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_108_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_108_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_108_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_108_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_108_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_109_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_109_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_109_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_109_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_109_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_109_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_109_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_109_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_109_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_10_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_10_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_10_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_10_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_10_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_10_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_10_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_10_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_10_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_110_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_110_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_110_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_110_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_110_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_110_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_110_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_110_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_110_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_111_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_111_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_111_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_111_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_111_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_111_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_111_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_111_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_111_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_112_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_112_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_112_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_112_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_112_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_112_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_112_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_112_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_112_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_113_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_113_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_113_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_113_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_113_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_113_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_113_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_113_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_113_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_114_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_114_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_114_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_114_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_114_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_114_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_114_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_114_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_114_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_115_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_115_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_115_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_115_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_115_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_115_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_115_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_115_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_115_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_116_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_116_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_116_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_116_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_116_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_116_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_116_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_116_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_116_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_117_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_117_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_117_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_117_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_117_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_117_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_117_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_117_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_117_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_118_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_118_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_118_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_118_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_118_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_118_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_118_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_118_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_118_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_119_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_119_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_119_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_119_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_119_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_119_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_119_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_119_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_119_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_11_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_11_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_11_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_11_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_11_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_11_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_11_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_11_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_11_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_120_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_120_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_120_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_120_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_120_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_120_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_120_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_120_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_120_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_121_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_121_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_121_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_121_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_121_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_121_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_121_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_121_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_121_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_122_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_122_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_122_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_122_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_122_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_122_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_122_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_122_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_122_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_123_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_123_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_123_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_123_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_123_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_123_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_123_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_123_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_123_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_124_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_124_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_124_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_124_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_124_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_124_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_124_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_124_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_124_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_125_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_125_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_125_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_125_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_125_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_125_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_125_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_125_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_125_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_126_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_126_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_126_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_126_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_126_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_126_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_126_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_126_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_126_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_12_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_12_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_12_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_12_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_12_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_12_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_12_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_12_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_12_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_13_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_13_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_13_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_13_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_13_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_13_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_13_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_13_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_13_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_14_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_14_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_14_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_14_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_14_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_14_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_14_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_14_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_14_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_15_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_15_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_15_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_15_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_15_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_15_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_15_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_15_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_15_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_16_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_16_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_16_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_16_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_16_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_16_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_16_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_16_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_16_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_17_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_17_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_17_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_17_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_17_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_17_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_17_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_17_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_17_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_18_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_18_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_18_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_18_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_18_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_18_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_18_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_18_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_18_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_19_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_19_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_19_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_19_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_19_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_19_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_19_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_19_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_19_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_1_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_1_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_1_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_1_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_1_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_1_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_1_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_1_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_1_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_20_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_20_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_20_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_20_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_20_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_20_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_20_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_20_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_20_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_21_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_21_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_21_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_21_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_21_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_21_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_21_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_21_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_21_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_22_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_22_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_22_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_22_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_22_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_22_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_22_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_22_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_22_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_23_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_23_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_23_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_23_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_23_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_23_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_23_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_23_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_23_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_24_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_24_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_24_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_24_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_24_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_24_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_24_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_24_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_24_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_25_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_25_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_25_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_25_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_25_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_25_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_25_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_25_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_25_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_26_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_26_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_26_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_26_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_26_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_26_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_26_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_26_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_26_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_27_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_27_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_27_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_27_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_27_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_27_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_27_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_27_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_27_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_28_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_28_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_28_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_28_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_28_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_28_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_28_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_28_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_28_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_29_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_29_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_29_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_29_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_29_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_29_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_29_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_29_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_29_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_2_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_2_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_2_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_2_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_2_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_2_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_2_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_2_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_2_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_30_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_30_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_30_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_30_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_30_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_30_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_30_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_30_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_30_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_31_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_31_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_31_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_31_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_31_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_31_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_31_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_31_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_31_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_32_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_32_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_32_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_32_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_32_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_32_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_32_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_32_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_32_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_33_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_33_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_33_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_33_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_33_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_33_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_33_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_33_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_33_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_34_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_34_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_34_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_34_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_34_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_34_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_34_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_34_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_34_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_35_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_35_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_35_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_35_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_35_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_35_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_35_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_35_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_35_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_36_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_36_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_36_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_36_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_36_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_36_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_36_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_36_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_36_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_37_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_37_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_37_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_37_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_37_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_37_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_37_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_37_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_37_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_38_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_38_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_38_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_38_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_38_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_38_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_38_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_38_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_38_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_39_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_39_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_39_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_39_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_39_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_39_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_39_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_39_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_39_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_3_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_3_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_3_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_3_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_3_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_3_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_3_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_3_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_3_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_40_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_40_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_40_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_40_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_40_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_40_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_40_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_40_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_40_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_41_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_41_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_41_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_41_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_41_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_41_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_41_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_41_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_41_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_42_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_42_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_42_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_42_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_42_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_42_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_42_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_42_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_42_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_43_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_43_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_43_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_43_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_43_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_43_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_43_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_43_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_43_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_44_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_44_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_44_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_44_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_44_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_44_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_44_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_44_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_44_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_45_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_45_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_45_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_45_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_45_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_45_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_45_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_45_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_45_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_46_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_46_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_46_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_46_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_46_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_46_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_46_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_46_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_46_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_47_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_47_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_47_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_47_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_47_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_47_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_47_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_47_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_47_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_48_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_48_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_48_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_48_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_48_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_48_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_48_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_48_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_48_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_49_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_49_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_49_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_49_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_49_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_49_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_49_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_49_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_49_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_4_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_4_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_4_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_4_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_4_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_4_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_4_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_4_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_4_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_50_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_50_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_50_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_50_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_50_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_50_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_50_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_50_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_50_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_51_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_51_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_51_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_51_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_51_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_51_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_51_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_51_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_51_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_52_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_52_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_52_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_52_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_52_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_52_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_52_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_52_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_52_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_53_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_53_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_53_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_53_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_53_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_53_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_53_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_53_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_53_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_54_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_54_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_54_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_54_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_54_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_54_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_54_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_54_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_54_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_55_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_55_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_55_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_55_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_55_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_55_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_55_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_55_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_55_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_56_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_56_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_56_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_56_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_56_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_56_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_56_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_56_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_56_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_57_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_57_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_57_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_57_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_57_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_57_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_57_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_57_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_57_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_58_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_58_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_58_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_58_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_58_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_58_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_58_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_58_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_58_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_59_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_59_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_59_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_59_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_59_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_59_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_59_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_59_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_59_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_5_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_5_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_5_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_5_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_5_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_5_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_5_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_5_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_5_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_60_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_60_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_60_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_60_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_60_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_60_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_60_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_60_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_60_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_61_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_61_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_61_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_61_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_61_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_61_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_61_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_61_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_61_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_62_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_62_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_62_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_62_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_62_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_62_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_62_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_62_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_62_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_63_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_63_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_63_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_63_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_63_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_63_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_63_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_63_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_63_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_64_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_64_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_64_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_64_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_64_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_64_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_64_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_64_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_64_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_65_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_65_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_65_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_65_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_65_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_65_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_65_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_65_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_65_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_66_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_66_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_66_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_66_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_66_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_66_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_66_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_66_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_66_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_67_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_67_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_67_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_67_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_67_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_67_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_67_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_67_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_67_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_68_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_68_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_68_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_68_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_68_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_68_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_68_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_68_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_68_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_69_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_69_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_69_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_69_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_69_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_69_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_69_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_69_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_69_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_6_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_6_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_6_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_6_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_6_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_6_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_6_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_6_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_6_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_70_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_70_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_70_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_70_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_70_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_70_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_70_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_70_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_70_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_71_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_71_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_71_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_71_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_71_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_71_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_71_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_71_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_71_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_72_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_72_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_72_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_72_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_72_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_72_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_72_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_72_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_72_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_73_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_73_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_73_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_73_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_73_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_73_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_73_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_73_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_73_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_74_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_74_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_74_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_74_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_74_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_74_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_74_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_74_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_74_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_75_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_75_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_75_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_75_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_75_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_75_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_75_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_75_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_75_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_76_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_76_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_76_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_76_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_76_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_76_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_76_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_76_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_76_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_77_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_77_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_77_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_77_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_77_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_77_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_77_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_77_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_77_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_78_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_78_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_78_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_78_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_78_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_78_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_78_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_78_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_78_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_79_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_79_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_79_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_79_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_79_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_79_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_79_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_79_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_79_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_7_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_7_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_7_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_7_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_7_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_7_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_7_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_7_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_7_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_80_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_80_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_80_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_80_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_80_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_80_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_80_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_80_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_80_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_81_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_81_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_81_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_81_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_81_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_81_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_81_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_81_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_81_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_82_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_82_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_82_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_82_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_82_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_82_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_82_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_82_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_82_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_83_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_83_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_83_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_83_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_83_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_83_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_83_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_83_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_83_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_84_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_84_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_84_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_84_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_84_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_84_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_84_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_84_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_84_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_85_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_85_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_85_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_85_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_85_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_85_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_85_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_85_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_85_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_86_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_86_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_86_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_86_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_86_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_86_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_86_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_86_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_86_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_87_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_87_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_87_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_87_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_87_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_87_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_87_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_87_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_87_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_88_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_88_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_88_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_88_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_88_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_88_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_88_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_88_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_88_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_89_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_89_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_89_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_89_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_89_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_89_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_89_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_89_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_89_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_8_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_8_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_8_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_8_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_8_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_8_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_8_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_8_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_8_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_90_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_90_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_90_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_90_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_90_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_90_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_90_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_90_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_90_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_91_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_91_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_91_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_91_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_91_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_91_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_91_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_91_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_91_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_92_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_92_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_92_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_92_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_92_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_92_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_92_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_92_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_92_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_93_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_93_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_93_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_93_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_93_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_93_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_93_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_93_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_93_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_94_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_94_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_94_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_94_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_94_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_94_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_94_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_94_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_94_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_95_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_95_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_95_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_95_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_95_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_95_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_95_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_95_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_95_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_96_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_96_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_96_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_96_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_96_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_96_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_96_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_96_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_96_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_97_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_97_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_97_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_97_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_97_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_97_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_97_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_97_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_97_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_98_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_98_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_98_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_98_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_98_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_98_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_98_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_98_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_98_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_99_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_99_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_99_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_99_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_99_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_99_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_99_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_99_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_99_chunk USING btree ("time" DESC);


--
-- Name: _hyper_1_9_chunk_idx_ohlcv_broker_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE UNIQUE INDEX _hyper_1_9_chunk_idx_ohlcv_broker_symbol_interval_time ON _timescaledb_internal._hyper_1_9_chunk USING btree (broker, symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_9_chunk_idx_ohlcv_symbol_interval_time; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_9_chunk_idx_ohlcv_symbol_interval_time ON _timescaledb_internal._hyper_1_9_chunk USING btree (symbol, "interval", "time" DESC);


--
-- Name: _hyper_1_9_chunk_ohlcv_data_time_idx; Type: INDEX; Schema: _timescaledb_internal; Owner: -
--

CREATE INDEX _hyper_1_9_chunk_ohlcv_data_time_idx ON _timescaledb_internal._hyper_1_9_chunk USING btree ("time" DESC);


--
-- Name: broker_accounts_user_id_status_index; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX broker_accounts_user_id_status_index ON public.broker_accounts USING btree (user_id, status);


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
-- Name: ohlcv_data_time_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ohlcv_data_time_idx ON public.ohlcv_data USING btree ("time" DESC);


--
-- Name: paper_strategy_configs_unique; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX paper_strategy_configs_unique ON public.paper_strategy_configs USING btree (strategy_class, symbol, "interval", ((params ->> 'mode'::text)));


--
-- Name: paper_trades_status_index; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX paper_trades_status_index ON public.paper_trades USING btree (status);


--
-- Name: paper_trades_strategy_symbol_status_index; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX paper_trades_strategy_symbol_status_index ON public.paper_trades USING btree (strategy, symbol, status);


--
-- Name: real_strategy_subscriptions_user_id_status_index; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX real_strategy_subscriptions_user_id_status_index ON public.real_strategy_subscriptions USING btree (user_id, status);


--
-- Name: real_trades_broker_account_id_status_index; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX real_trades_broker_account_id_status_index ON public.real_trades USING btree (broker_account_id, status);


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
    ADD CONSTRAINT paper_strategy_configs_backtest_id_foreign FOREIGN KEY (backtest_id) REFERENCES public.backtests(id) ON DELETE SET NULL;


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
-- PostgreSQL database dump complete
--

\unrestrict qkJ5nAfwDKWwpSmNTsTz7UXB9dMOtKlY7dgbCuQoedbxBZ7GpG6jfgogzxxVLzo

--
-- PostgreSQL database dump
--

\restrict Fyoe0EkbjjSN4tCJbXvsgUku86QEvHaVQ44TXgclOjMrQNGKvR5Net0YJXMkN0Y

-- Dumped from database version 16.14 (Ubuntu 16.14-0ubuntu0.24.04.1)
-- Dumped by pg_dump version 16.14 (Ubuntu 16.14-0ubuntu0.24.04.1)

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
-- Data for Name: migrations; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.migrations (id, migration, batch) FROM stdin;
1	0001_01_01_000000_create_users_table	1
2	0001_01_01_000001_create_cache_table	1
3	0001_01_01_000002_create_jobs_table	1
4	2026_06_10_031106_create_ohlcv_data_table	2
5	2026_06_13_212650_create_paper_trades_table	3
6	2026_06_13_234626_create_risk_controls_table	4
7	2026_06_14_220220_add_role_and_status_to_users_table	5
8	2026_06_14_220221_create_real_strategy_subscriptions_table	5
9	2026_06_14_220222_create_real_trades_table	5
10	2026_06_15_032606_create_broker_accounts_table	6
11	2026_06_15_032607_update_real_strategy_subscriptions_table	6
12	2026_06_15_032608_add_broker_account_id_to_real_trades_table	6
13	2026_06_18_041904_add_max_profit_loss_to_paper_trades_table	7
14	2026_06_18_201634_create_paper_strategy_configs_table	8
15	2026_06_19_011512_create_collector_configs_table	9
16	2026_06_19_144230_add_tp2_to_paper_trades_table	10
17	2026_06_23_000000_extend_trading_tables	11
18	2026_06_23_100000_broker_accounts_unique	12
19	2026_06_25_221018_add_stats_to_paper_strategy_configs	13
20	2026_06_26_045957_add_avg_monthly_trades_to_paper_strategy_configs	14
21	2026_06_26_054108_add_total_return_pct_to_paper_strategy_configs	15
22	2026_06_26_190005_change_audit_log_to_jsonb_in_real_trades	16
23	2026_06_27_195227_add_risk_override_to_real_strategy_subscriptions	17
24	2026_06_27_231408_update_real_trades_status_check	18
25	2026_06_28_221854_add_star_rating_to_paper_strategy_configs	19
26	2026_06_29_024100_add_metrics_to_paper_strategy_configs	20
27	2026_07_01_151756_fix_paper_strategy_configs_unique_constraint	21
28	2026_07_01_152513_add_tp3_tp4_trailing_to_trades	22
29	2026_07_01_165440_add_partial_tp_closes_to_real_trades	23
30	2026_07_04_200729_add_single_position_per_symbol_to_broker_accounts	24
31	2026_07_07_220119_add_credentials_extra_to_broker_accounts_table	25
32	2026_07_07_235900_add_broker_and_epic_to_collector_configs_table	26
33	2026_07_09_163559_add_commission_to_paper_trades_table	27
34	2026_10_21_100000_create_strategies_table	28
35	2026_10_21_100001_create_backtests_table	28
36	2026_10_21_100002_add_backtest_id_to_paper_strategy_configs	28
37	2026_10_21_100005_update_strategies_table	29
38	2026_10_22_100006_add_hash_to_backtests	30
\.


--
-- Name: migrations_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.migrations_id_seq', 38, true);


--
-- PostgreSQL database dump complete
--

\unrestrict Fyoe0EkbjjSN4tCJbXvsgUku86QEvHaVQ44TXgclOjMrQNGKvR5Net0YJXMkN0Y


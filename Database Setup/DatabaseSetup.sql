--
-- PostgreSQL database dump
--

-- Dumped from database version 17.2
-- Dumped by pg_dump version 17.2

-- Started on 2025-08-12 09:23:24

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- TOC entry 386 (class 1255 OID 174702)
-- Name: set_updated_at(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.set_updated_at() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  NEW.updated_at = CURRENT_TIMESTAMP;
  RETURN NEW;
END;
$$;


ALTER FUNCTION public.set_updated_at() OWNER TO postgres;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- TOC entry 217 (class 1259 OID 174703)
-- Name: goal_action_plans; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.goal_action_plans (
    action_plan_id integer NOT NULL,
    goal_id integer,
    action_item character varying(255),
    due_date date,
    status character varying(50) DEFAULT 'Pending'::character varying,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at date
);


ALTER TABLE public.goal_action_plans OWNER TO postgres;

--
-- TOC entry 218 (class 1259 OID 174708)
-- Name: action_plans_action_plan_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.action_plans_action_plan_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.action_plans_action_plan_id_seq OWNER TO postgres;

--
-- TOC entry 6036 (class 0 OID 0)
-- Dependencies: 218
-- Name: action_plans_action_plan_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.action_plans_action_plan_id_seq OWNED BY public.goal_action_plans.action_plan_id;


--
-- TOC entry 219 (class 1259 OID 174709)
-- Name: actions; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.actions (
    id integer NOT NULL,
    action_name character varying NOT NULL,
    description character varying
);


ALTER TABLE public.actions OWNER TO postgres;

--
-- TOC entry 220 (class 1259 OID 174714)
-- Name: actions_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.actions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.actions_id_seq OWNER TO postgres;

--
-- TOC entry 6037 (class 0 OID 0)
-- Dependencies: 220
-- Name: actions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.actions_id_seq OWNED BY public.actions.id;


--
-- TOC entry 221 (class 1259 OID 174715)
-- Name: admin_access_requests; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.admin_access_requests (
    id integer NOT NULL,
    admin_id integer,
    super_admin_id integer,
    route_id integer NOT NULL,
    action_id integer NOT NULL,
    requested_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    status character varying(32) DEFAULT 'pending'::character varying NOT NULL,
    CONSTRAINT admin_access_requests_check CHECK ((((admin_id IS NOT NULL) AND (super_admin_id IS NULL)) OR ((admin_id IS NULL) AND (super_admin_id IS NOT NULL))))
);


ALTER TABLE public.admin_access_requests OWNER TO postgres;

--
-- TOC entry 222 (class 1259 OID 174721)
-- Name: admin_access_requests_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.admin_access_requests_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.admin_access_requests_id_seq OWNER TO postgres;

--
-- TOC entry 6038 (class 0 OID 0)
-- Dependencies: 222
-- Name: admin_access_requests_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.admin_access_requests_id_seq OWNED BY public.admin_access_requests.id;


--
-- TOC entry 223 (class 1259 OID 174722)
-- Name: admin_route_actions; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.admin_route_actions (
    id integer NOT NULL,
    admin_id integer,
    route_id integer,
    action_id integer
);


ALTER TABLE public.admin_route_actions OWNER TO postgres;

--
-- TOC entry 224 (class 1259 OID 174725)
-- Name: admin_route_actions_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.admin_route_actions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.admin_route_actions_id_seq OWNER TO postgres;

--
-- TOC entry 6039 (class 0 OID 0)
-- Dependencies: 224
-- Name: admin_route_actions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.admin_route_actions_id_seq OWNED BY public.admin_route_actions.id;


--
-- TOC entry 225 (class 1259 OID 174733)
-- Name: admins_admin_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.admins_admin_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.admins_admin_id_seq OWNER TO postgres;

--
-- TOC entry 226 (class 1259 OID 174734)
-- Name: admins; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.admins (
    admin_id integer DEFAULT nextval('public.admins_admin_id_seq'::regclass) NOT NULL,
    email character varying(255),
    password text,
    first_name character varying(100),
    last_name character varying(100),
    profile_image bytea,
    created_at timestamp without time zone,
    last_login timestamp without time zone,
    status character varying(20),
    last_modified timestamp without time zone,
    permissions jsonb DEFAULT '[]'::jsonb,
    is_verified boolean DEFAULT false,
    is_2fa_enabled boolean DEFAULT false,
    two_factor_secret character varying(255),
    role_id integer,
    phone_number integer,
    bio text,
    gender character varying(1),
    date_of_birth date,
    jti text
);


ALTER TABLE public.admins OWNER TO postgres;

--
-- TOC entry 227 (class 1259 OID 174743)
-- Name: alert_reads; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.alert_reads (
    alert_read_id integer NOT NULL,
    employee_id integer,
    read_at timestamp without time zone,
    team_id integer,
    alert_id integer
);


ALTER TABLE public.alert_reads OWNER TO postgres;

--
-- TOC entry 228 (class 1259 OID 174746)
-- Name: alert_reads_alert_read_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

ALTER TABLE public.alert_reads ALTER COLUMN alert_read_id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.alert_reads_alert_read_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- TOC entry 229 (class 1259 OID 174747)
-- Name: alerts; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.alerts (
    alert_id integer NOT NULL,
    title character varying(255) NOT NULL,
    message text NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    employee_id integer,
    team_id integer,
    admin_id integer,
    alert_type character varying(50),
    severity_level character varying(20),
    assigned_by_admin integer,
    assigned_by_super_admin integer
);


ALTER TABLE public.alerts OWNER TO postgres;

--
-- TOC entry 230 (class 1259 OID 174753)
-- Name: alerts_alert_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.alerts_alert_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.alerts_alert_id_seq OWNER TO postgres;

--
-- TOC entry 6040 (class 0 OID 0)
-- Dependencies: 230
-- Name: alerts_alert_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.alerts_alert_id_seq OWNED BY public.alerts.alert_id;


--
-- TOC entry 231 (class 1259 OID 174754)
-- Name: announcement_reads; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.announcement_reads (
    read_id integer NOT NULL,
    announcement_id integer,
    employee_id integer,
    read_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    team_id integer
);


ALTER TABLE public.announcement_reads OWNER TO postgres;

--
-- TOC entry 232 (class 1259 OID 174758)
-- Name: announcement_reads_read_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.announcement_reads_read_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.announcement_reads_read_id_seq OWNER TO postgres;

--
-- TOC entry 6041 (class 0 OID 0)
-- Dependencies: 232
-- Name: announcement_reads_read_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.announcement_reads_read_id_seq OWNED BY public.announcement_reads.read_id;


--
-- TOC entry 233 (class 1259 OID 174759)
-- Name: announcements; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.announcements (
    announcement_id integer NOT NULL,
    title character varying(255) NOT NULL,
    message text NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    employee_id integer,
    team_id integer,
    assigned_by_admin integer,
    assigned_by_super_admin integer
);


ALTER TABLE public.announcements OWNER TO postgres;

--
-- TOC entry 234 (class 1259 OID 174765)
-- Name: announcements_announcement_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.announcements_announcement_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.announcements_announcement_id_seq OWNER TO postgres;

--
-- TOC entry 6042 (class 0 OID 0)
-- Dependencies: 234
-- Name: announcements_announcement_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.announcements_announcement_id_seq OWNED BY public.announcements.announcement_id;


--
-- TOC entry 235 (class 1259 OID 174775)
-- Name: assessment_answers; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.assessment_answers (
    answer_id integer NOT NULL,
    assessment_id integer NOT NULL,
    question_id integer NOT NULL,
    employee_id integer NOT NULL,
    selected_option_id integer,
    correct_option_id integer
);


ALTER TABLE public.assessment_answers OWNER TO postgres;

--
-- TOC entry 236 (class 1259 OID 174778)
-- Name: assessment_answers_answer_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.assessment_answers_answer_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.assessment_answers_answer_id_seq OWNER TO postgres;

--
-- TOC entry 6043 (class 0 OID 0)
-- Dependencies: 236
-- Name: assessment_answers_answer_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.assessment_answers_answer_id_seq OWNED BY public.assessment_answers.answer_id;


--
-- TOC entry 237 (class 1259 OID 174779)
-- Name: assessment_options; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.assessment_options (
    option_id integer NOT NULL,
    question_id integer,
    option_text text NOT NULL,
    is_checked boolean DEFAULT false
);


ALTER TABLE public.assessment_options OWNER TO postgres;

--
-- TOC entry 238 (class 1259 OID 174785)
-- Name: assessment_options_option_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.assessment_options_option_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.assessment_options_option_id_seq OWNER TO postgres;

--
-- TOC entry 6044 (class 0 OID 0)
-- Dependencies: 238
-- Name: assessment_options_option_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.assessment_options_option_id_seq OWNED BY public.assessment_options.option_id;


--
-- TOC entry 239 (class 1259 OID 174786)
-- Name: assessment_questions; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.assessment_questions (
    question_id integer NOT NULL,
    question_text text NOT NULL,
    assessment_id integer
);


ALTER TABLE public.assessment_questions OWNER TO postgres;

--
-- TOC entry 240 (class 1259 OID 174791)
-- Name: assessment_questions_question_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.assessment_questions_question_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.assessment_questions_question_id_seq OWNER TO postgres;

--
-- TOC entry 6045 (class 0 OID 0)
-- Dependencies: 240
-- Name: assessment_questions_question_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.assessment_questions_question_id_seq OWNED BY public.assessment_questions.question_id;


--
-- TOC entry 241 (class 1259 OID 174792)
-- Name: attendance_logs; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.attendance_logs (
    log_id integer NOT NULL,
    employee_id integer NOT NULL,
    date date NOT NULL,
    clock_in_time time with time zone,
    clock_out_time time with time zone,
    status character varying(20) DEFAULT 'Absent'::character varying,
    hours_worked double precision DEFAULT 0,
    shift_id integer,
    overtime_hours double precision DEFAULT 0,
    is_overtime character varying(3) DEFAULT 'No'::character varying,
    remarks text,
    leave_type character varying(50),
    attendance_verified boolean DEFAULT false,
    is_overtime_approved boolean DEFAULT false,
    role_id integer
);


ALTER TABLE public.attendance_logs OWNER TO postgres;

--
-- TOC entry 242 (class 1259 OID 174803)
-- Name: attendance_logs_log_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.attendance_logs_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.attendance_logs_log_id_seq OWNER TO postgres;

--
-- TOC entry 6046 (class 0 OID 0)
-- Dependencies: 242
-- Name: attendance_logs_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.attendance_logs_log_id_seq OWNED BY public.attendance_logs.log_id;


--
-- TOC entry 243 (class 1259 OID 174804)
-- Name: audit_trail_admin; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.audit_trail_admin (
    audit_id integer NOT NULL,
    action character varying(255) NOT NULL,
    details text,
    "timestamp" timestamp without time zone DEFAULT now(),
    category text,
    compliance_status character varying(10),
    role_id integer
);


ALTER TABLE public.audit_trail_admin OWNER TO postgres;

--
-- TOC entry 244 (class 1259 OID 174810)
-- Name: audit_trail_audit_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.audit_trail_audit_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.audit_trail_audit_id_seq OWNER TO postgres;

--
-- TOC entry 6047 (class 0 OID 0)
-- Dependencies: 244
-- Name: audit_trail_audit_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.audit_trail_audit_id_seq OWNED BY public.audit_trail_admin.audit_id;


--
-- TOC entry 383 (class 1259 OID 176603)
-- Name: audit_trail_employee; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.audit_trail_employee (
    audit_id integer NOT NULL,
    employee_id integer NOT NULL,
    action character varying(255) NOT NULL,
    details text,
    "timestamp" timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    category character varying(100),
    compliance_status character varying(50) DEFAULT 'Active'::character varying
);


ALTER TABLE public.audit_trail_employee OWNER TO postgres;

--
-- TOC entry 382 (class 1259 OID 176602)
-- Name: audit_trail_employee_audit_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.audit_trail_employee_audit_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.audit_trail_employee_audit_id_seq OWNER TO postgres;

--
-- TOC entry 6048 (class 0 OID 0)
-- Dependencies: 382
-- Name: audit_trail_employee_audit_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.audit_trail_employee_audit_id_seq OWNED BY public.audit_trail_employee.audit_id;


--
-- TOC entry 245 (class 1259 OID 174816)
-- Name: badge_assignments; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.badge_assignments (
    assignment_id integer NOT NULL,
    badge_id integer NOT NULL,
    employee_id integer,
    team_id integer,
    assigned_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.badge_assignments OWNER TO postgres;

--
-- TOC entry 246 (class 1259 OID 174820)
-- Name: badge_assignments_assignment_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.badge_assignments_assignment_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.badge_assignments_assignment_id_seq OWNER TO postgres;

--
-- TOC entry 6049 (class 0 OID 0)
-- Dependencies: 246
-- Name: badge_assignments_assignment_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.badge_assignments_assignment_id_seq OWNED BY public.badge_assignments.assignment_id;


--
-- TOC entry 247 (class 1259 OID 174821)
-- Name: badges; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.badges (
    badge_id integer NOT NULL,
    name character varying(100) NOT NULL,
    description text,
    icon_url text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.badges OWNER TO postgres;

--
-- TOC entry 248 (class 1259 OID 174827)
-- Name: badges_badge_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.badges_badge_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.badges_badge_id_seq OWNER TO postgres;

--
-- TOC entry 6050 (class 0 OID 0)
-- Dependencies: 248
-- Name: badges_badge_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.badges_badge_id_seq OWNED BY public.badges.badge_id;


--
-- TOC entry 249 (class 1259 OID 174828)
-- Name: bank_details; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.bank_details (
    bank_id integer NOT NULL,
    employee_id integer,
    bank_account_number character varying,
    bank_name character varying,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    account_name text
);


ALTER TABLE public.bank_details OWNER TO postgres;

--
-- TOC entry 250 (class 1259 OID 174834)
-- Name: bank_details_bank_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.bank_details_bank_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.bank_details_bank_id_seq OWNER TO postgres;

--
-- TOC entry 6051 (class 0 OID 0)
-- Dependencies: 250
-- Name: bank_details_bank_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.bank_details_bank_id_seq OWNED BY public.bank_details.bank_id;


--
-- TOC entry 251 (class 1259 OID 174835)
-- Name: blacklisted_tokens; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.blacklisted_tokens (
    jti text NOT NULL,
    employee_id integer NOT NULL,
    blacklisted_at timestamp without time zone DEFAULT now()
);


ALTER TABLE public.blacklisted_tokens OWNER TO postgres;

--
-- TOC entry 252 (class 1259 OID 174841)
-- Name: bonuses_incentives; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.bonuses_incentives (
    id integer NOT NULL,
    employee_id integer,
    type character varying(50),
    amount numeric(10,2),
    description text,
    awarded_date date DEFAULT CURRENT_DATE,
    status character varying(20) DEFAULT 'Granted'::character varying
);


ALTER TABLE public.bonuses_incentives OWNER TO postgres;

--
-- TOC entry 253 (class 1259 OID 174848)
-- Name: bonuses_incentives_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.bonuses_incentives_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.bonuses_incentives_id_seq OWNER TO postgres;

--
-- TOC entry 6052 (class 0 OID 0)
-- Dependencies: 253
-- Name: bonuses_incentives_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.bonuses_incentives_id_seq OWNED BY public.bonuses_incentives.id;


--
-- TOC entry 254 (class 1259 OID 174868)
-- Name: contact_replies; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.contact_replies (
    id integer NOT NULL,
    contact_request_id integer,
    admin_id integer,
    reply_message text NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    admin_type character varying(20)
);


ALTER TABLE public.contact_replies OWNER TO postgres;

--
-- TOC entry 255 (class 1259 OID 174874)
-- Name: contact_replies_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.contact_replies_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.contact_replies_id_seq OWNER TO postgres;

--
-- TOC entry 6053 (class 0 OID 0)
-- Dependencies: 255
-- Name: contact_replies_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.contact_replies_id_seq OWNED BY public.contact_replies.id;


--
-- TOC entry 256 (class 1259 OID 174875)
-- Name: contact_requests; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.contact_requests (
    id integer NOT NULL,
    first_name character varying(100) NOT NULL,
    last_name character varying(100) NOT NULL,
    email character varying(255) NOT NULL,
    message text NOT NULL,
    status character varying(20) DEFAULT 'pending'::character varying,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.contact_requests OWNER TO postgres;

--
-- TOC entry 257 (class 1259 OID 174882)
-- Name: contact_requests_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.contact_requests_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.contact_requests_id_seq OWNER TO postgres;

--
-- TOC entry 6054 (class 0 OID 0)
-- Dependencies: 257
-- Name: contact_requests_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.contact_requests_id_seq OWNED BY public.contact_requests.id;


--
-- TOC entry 258 (class 1259 OID 174896)
-- Name: devices; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.devices (
    device_id integer NOT NULL,
    employee_id integer,
    admin_id integer,
    device_name text,
    device_os text,
    browser_name text,
    browser_version text,
    ip_address text,
    jti text,
    issued_at timestamp without time zone
);


ALTER TABLE public.devices OWNER TO postgres;

--
-- TOC entry 259 (class 1259 OID 174901)
-- Name: devices_device_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.devices_device_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.devices_device_id_seq OWNER TO postgres;

--
-- TOC entry 6055 (class 0 OID 0)
-- Dependencies: 259
-- Name: devices_device_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.devices_device_id_seq OWNED BY public.devices.device_id;


--
-- TOC entry 260 (class 1259 OID 174910)
-- Name: document_categories; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.document_categories (
    category_id integer NOT NULL,
    name text NOT NULL
);


ALTER TABLE public.document_categories OWNER TO postgres;

--
-- TOC entry 261 (class 1259 OID 174915)
-- Name: document_categories_category_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.document_categories_category_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.document_categories_category_id_seq OWNER TO postgres;

--
-- TOC entry 6056 (class 0 OID 0)
-- Dependencies: 261
-- Name: document_categories_category_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.document_categories_category_id_seq OWNED BY public.document_categories.category_id;


--
-- TOC entry 262 (class 1259 OID 174916)
-- Name: document_history; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.document_history (
    history_id integer NOT NULL,
    document_id integer,
    version integer,
    filename text,
    file_path text,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_by character varying(255)
);


ALTER TABLE public.document_history OWNER TO postgres;

--
-- TOC entry 263 (class 1259 OID 174922)
-- Name: document_history_history_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.document_history_history_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.document_history_history_id_seq OWNER TO postgres;

--
-- TOC entry 6057 (class 0 OID 0)
-- Dependencies: 263
-- Name: document_history_history_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.document_history_history_id_seq OWNED BY public.document_history.history_id;


--
-- TOC entry 264 (class 1259 OID 174923)
-- Name: documents; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.documents (
    document_id integer NOT NULL,
    title text NOT NULL,
    description text,
    filename text NOT NULL,
    file_path text NOT NULL,
    category_id integer,
    upload_date timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    download_count integer DEFAULT 0,
    version integer DEFAULT 1,
    visibility_by_role_id integer,
    uploaded_by_role_id integer,
    file_size bigint,
    mime_type character varying(100),
    status character varying(20) DEFAULT 'active'::character varying
);


ALTER TABLE public.documents OWNER TO postgres;

--
-- TOC entry 265 (class 1259 OID 174931)
-- Name: documents_document_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.documents_document_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.documents_document_id_seq OWNER TO postgres;

--
-- TOC entry 6058 (class 0 OID 0)
-- Dependencies: 265
-- Name: documents_document_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.documents_document_id_seq OWNED BY public.documents.document_id;


--
-- TOC entry 266 (class 1259 OID 174932)
-- Name: employee_breaks; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.employee_breaks (
    break_id integer NOT NULL,
    employee_id integer NOT NULL,
    break_type character varying(50) NOT NULL,
    break_start timestamp without time zone NOT NULL,
    break_end timestamp without time zone,
    break_duration interval GENERATED ALWAYS AS ((break_end - break_start)) STORED,
    status character varying(50) DEFAULT 'ongoing'::character varying,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    log_id integer,
    CONSTRAINT employee_breaks_break_type_check CHECK (((break_type)::text = ANY (ARRAY[('lunch'::character varying)::text, ('short'::character varying)::text, ('personal'::character varying)::text, ('other'::character varying)::text]))),
    CONSTRAINT employee_breaks_status_check CHECK (((status)::text = ANY (ARRAY[('ongoing'::character varying)::text, ('completed'::character varying)::text])))
);


ALTER TABLE public.employee_breaks OWNER TO postgres;

--
-- TOC entry 267 (class 1259 OID 174940)
-- Name: employee_breaks_break_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.employee_breaks_break_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.employee_breaks_break_id_seq OWNER TO postgres;

--
-- TOC entry 6059 (class 0 OID 0)
-- Dependencies: 267
-- Name: employee_breaks_break_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.employee_breaks_break_id_seq OWNED BY public.employee_breaks.break_id;


--
-- TOC entry 268 (class 1259 OID 174941)
-- Name: employee_recognition; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.employee_recognition (
    recognition_id integer NOT NULL,
    employee_id integer NOT NULL,
    recognition_type character varying(255) NOT NULL,
    reason text NOT NULL,
    date_awarded date DEFAULT CURRENT_DATE NOT NULL,
    awarded_by_admin integer,
    awarded_by_super_admin integer
);


ALTER TABLE public.employee_recognition OWNER TO postgres;

--
-- TOC entry 269 (class 1259 OID 174947)
-- Name: employee_recognition_recognition_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.employee_recognition_recognition_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.employee_recognition_recognition_id_seq OWNER TO postgres;

--
-- TOC entry 6060 (class 0 OID 0)
-- Dependencies: 269
-- Name: employee_recognition_recognition_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.employee_recognition_recognition_id_seq OWNED BY public.employee_recognition.recognition_id;


--
-- TOC entry 270 (class 1259 OID 174948)
-- Name: employee_shifts; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.employee_shifts (
    id integer NOT NULL,
    employee_id integer,
    is_rotating boolean DEFAULT false,
    location text,
    shift_date date,
    shift_id integer,
    assigned_by text
);


ALTER TABLE public.employee_shifts OWNER TO postgres;

--
-- TOC entry 271 (class 1259 OID 174954)
-- Name: employee_shifts_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.employee_shifts_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.employee_shifts_id_seq OWNER TO postgres;

--
-- TOC entry 6061 (class 0 OID 0)
-- Dependencies: 271
-- Name: employee_shifts_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.employee_shifts_id_seq OWNED BY public.employee_shifts.id;


--
-- TOC entry 272 (class 1259 OID 174962)
-- Name: employees; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.employees (
    employee_id integer NOT NULL,
    first_name character varying(100),
    last_name character varying(100),
    email character varying(150),
    phone_number character varying(15),
    department character varying(100),
    salary numeric(10,2),
    status character varying(50) DEFAULT 'active'::character varying,
    date_hired date,
    date_terminated date,
    profile bytea,
    created date DEFAULT CURRENT_DATE,
    account_status text,
    address1 text,
    city text,
    address2 text,
    password text NOT NULL,
    skills text,
    certification text,
    education text,
    language text,
    hobbies text,
    goal_id integer,
    team_id integer,
    announcement_id integer,
    is_2fa_enabled boolean DEFAULT false,
    two_factor_secret character varying(255),
    role_id integer,
    current_jti text,
    gender character varying(1),
    date_of_birth date
);


ALTER TABLE public.employees OWNER TO postgres;

--
-- TOC entry 273 (class 1259 OID 174970)
-- Name: employees_employee_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.employees_employee_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.employees_employee_id_seq OWNER TO postgres;

--
-- TOC entry 6062 (class 0 OID 0)
-- Dependencies: 273
-- Name: employees_employee_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.employees_employee_id_seq OWNED BY public.employees.employee_id;


--
-- TOC entry 274 (class 1259 OID 174971)
-- Name: goal_evaluations; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.goal_evaluations (
    evaluation_id integer NOT NULL,
    goal_id integer,
    final_score text,
    lessons_learned text,
    action_plan text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    course text,
    updated_at timestamp without time zone
);


ALTER TABLE public.goal_evaluations OWNER TO postgres;

--
-- TOC entry 275 (class 1259 OID 174977)
-- Name: evaluations_evaluation_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.evaluations_evaluation_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.evaluations_evaluation_id_seq OWNER TO postgres;

--
-- TOC entry 6063 (class 0 OID 0)
-- Dependencies: 275
-- Name: evaluations_evaluation_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.evaluations_evaluation_id_seq OWNED BY public.goal_evaluations.evaluation_id;


--
-- TOC entry 276 (class 1259 OID 174998)
-- Name: event_participants; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.event_participants (
    participant_id integer NOT NULL,
    event_id integer,
    employee_id integer,
    status character varying(50) DEFAULT 'invited'::character varying,
    team_id integer,
    admin_id integer,
    CONSTRAINT event_participants_status_check CHECK (((status)::text = ANY (ARRAY[('invited'::character varying)::text, ('confirmed'::character varying)::text, ('attended'::character varying)::text, ('declined'::character varying)::text])))
);


ALTER TABLE public.event_participants OWNER TO postgres;

--
-- TOC entry 277 (class 1259 OID 175003)
-- Name: event_participants_participant_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.event_participants_participant_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.event_participants_participant_id_seq OWNER TO postgres;

--
-- TOC entry 6064 (class 0 OID 0)
-- Dependencies: 277
-- Name: event_participants_participant_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.event_participants_participant_id_seq OWNED BY public.event_participants.participant_id;


--
-- TOC entry 278 (class 1259 OID 175004)
-- Name: events; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.events (
    event_id integer NOT NULL,
    title character varying(255) NOT NULL,
    description text,
    event_date timestamp without time zone NOT NULL,
    location character varying(255),
    budget numeric(10,2),
    recurrence character varying(50),
    status character varying(50) DEFAULT 'upcoming'::character varying,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    assigned_by_admins integer,
    assigned_by_super_admins integer,
    CONSTRAINT events_recurrence_check CHECK (((recurrence)::text = ANY (ARRAY[('none'::character varying)::text, ('daily'::character varying)::text, ('weekly'::character varying)::text, ('monthly'::character varying)::text, ('yearly'::character varying)::text]))),
    CONSTRAINT events_status_check CHECK (((status)::text = ANY (ARRAY[('upcoming'::character varying)::text, ('ongoing'::character varying)::text, ('completed'::character varying)::text, ('cancelled'::character varying)::text])))
);


ALTER TABLE public.events OWNER TO postgres;

--
-- TOC entry 279 (class 1259 OID 175014)
-- Name: events_event_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.events_event_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.events_event_id_seq OWNER TO postgres;

--
-- TOC entry 6065 (class 0 OID 0)
-- Dependencies: 279
-- Name: events_event_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.events_event_id_seq OWNED BY public.events.event_id;


--
-- TOC entry 280 (class 1259 OID 175015)
-- Name: expense_claims; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.expense_claims (
    claim_id integer NOT NULL,
    employee_id integer,
    claim_date timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    amount numeric(10,2),
    description text,
    receipt_image bytea,
    status character varying(20) DEFAULT 'pending'::character varying,
    submitted_at date,
    receipt_path text,
    title text,
    category text,
    CONSTRAINT expense_claims_status_check CHECK ((lower((status)::text) = ANY (ARRAY['pending'::text, 'approved'::text, 'rejected'::text])))
);


ALTER TABLE public.expense_claims OWNER TO postgres;

--
-- TOC entry 281 (class 1259 OID 175023)
-- Name: expense_claims_claim_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.expense_claims_claim_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.expense_claims_claim_id_seq OWNER TO postgres;

--
-- TOC entry 6066 (class 0 OID 0)
-- Dependencies: 281
-- Name: expense_claims_claim_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.expense_claims_claim_id_seq OWNED BY public.expense_claims.claim_id;


--
-- TOC entry 282 (class 1259 OID 175029)
-- Name: feedbac_id_sequence; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.feedbac_id_sequence
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.feedbac_id_sequence OWNER TO postgres;

--
-- TOC entry 283 (class 1259 OID 175030)
-- Name: feedback_requests; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.feedback_requests (
    request_id integer NOT NULL,
    title character varying(255) NOT NULL,
    message text NOT NULL,
    deadline date NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    employee_id integer,
    team_id integer,
    assigned_by_super_admins integer,
    assigned_by_admins integer
);


ALTER TABLE public.feedback_requests OWNER TO postgres;

--
-- TOC entry 284 (class 1259 OID 175036)
-- Name: feedback_requests_request_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.feedback_requests_request_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.feedback_requests_request_id_seq OWNER TO postgres;

--
-- TOC entry 6067 (class 0 OID 0)
-- Dependencies: 284
-- Name: feedback_requests_request_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.feedback_requests_request_id_seq OWNED BY public.feedback_requests.request_id;


--
-- TOC entry 285 (class 1259 OID 175037)
-- Name: feedback_responses; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.feedback_responses (
    response_id integer NOT NULL,
    request_id integer,
    employee_id integer,
    response text NOT NULL,
    submitted_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.feedback_responses OWNER TO postgres;

--
-- TOC entry 286 (class 1259 OID 175043)
-- Name: feedback_responses_response_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.feedback_responses_response_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.feedback_responses_response_id_seq OWNER TO postgres;

--
-- TOC entry 6068 (class 0 OID 0)
-- Dependencies: 286
-- Name: feedback_responses_response_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.feedback_responses_response_id_seq OWNED BY public.feedback_responses.response_id;


--
-- TOC entry 287 (class 1259 OID 175044)
-- Name: goal_progress_progress_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.goal_progress_progress_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.goal_progress_progress_id_seq OWNER TO postgres;

--
-- TOC entry 288 (class 1259 OID 175045)
-- Name: goal_progress; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.goal_progress (
    progress_id integer DEFAULT nextval('public.goal_progress_progress_id_seq'::regclass) NOT NULL,
    goal_id integer,
    employee_id integer,
    team_id integer,
    progress_percentage_id integer,
    note_id integer,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    feedback_id integer
);


ALTER TABLE public.goal_progress OWNER TO postgres;

--
-- TOC entry 289 (class 1259 OID 175051)
-- Name: goal_progress_feedback; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.goal_progress_feedback (
    feedback_id integer DEFAULT nextval('public.feedbac_id_sequence'::regclass) NOT NULL,
    feedback_description text,
    feedback_created_at timestamp without time zone,
    feedback_updated_at timestamp without time zone,
    goal_id integer,
    employee_id integer,
    team_id integer
);


ALTER TABLE public.goal_progress_feedback OWNER TO postgres;

--
-- TOC entry 290 (class 1259 OID 175057)
-- Name: goal_progress_notes; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.goal_progress_notes (
    note_id integer NOT NULL,
    note_description text NOT NULL,
    notes_created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    notes_updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    goal_id integer,
    employee_id integer,
    team_id integer
);


ALTER TABLE public.goal_progress_notes OWNER TO postgres;

--
-- TOC entry 291 (class 1259 OID 175064)
-- Name: goal_progress_notes_note_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.goal_progress_notes_note_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.goal_progress_notes_note_id_seq OWNER TO postgres;

--
-- TOC entry 6069 (class 0 OID 0)
-- Dependencies: 291
-- Name: goal_progress_notes_note_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.goal_progress_notes_note_id_seq OWNED BY public.goal_progress_notes.note_id;


--
-- TOC entry 292 (class 1259 OID 175065)
-- Name: goal_progress_percentage; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.goal_progress_percentage (
    progress_percentage_id integer NOT NULL,
    progress_percentage integer NOT NULL,
    percentage_created_at timestamp with time zone DEFAULT CURRENT_DATE,
    percentage_updated_at timestamp with time zone,
    employee_id integer,
    team_id integer,
    goal_id integer
);


ALTER TABLE public.goal_progress_percentage OWNER TO postgres;

--
-- TOC entry 293 (class 1259 OID 175069)
-- Name: goals; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.goals (
    goal_id integer NOT NULL,
    goal_name character varying(255) NOT NULL,
    description text,
    specific_goal text,
    measurable_goal text,
    achievable_goal text,
    relevant_goal text,
    time_bound_goal date,
    employee_id integer,
    team_id integer,
    status character varying(50) DEFAULT 'Not Started'::character varying,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.goals OWNER TO postgres;

--
-- TOC entry 294 (class 1259 OID 175077)
-- Name: goals_goal_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.goals_goal_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.goals_goal_id_seq OWNER TO postgres;

--
-- TOC entry 6070 (class 0 OID 0)
-- Dependencies: 294
-- Name: goals_goal_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.goals_goal_id_seq OWNED BY public.goals.goal_id;


--
-- TOC entry 295 (class 1259 OID 175078)
-- Name: health_wellness_resources; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.health_wellness_resources (
    resource_id integer NOT NULL,
    title text NOT NULL,
    description text,
    category text NOT NULL,
    url text,
    file_path text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT health_wellness_resources_category_check CHECK ((category = ANY (ARRAY['Mental Health'::text, 'Safety Training'::text])))
);


ALTER TABLE public.health_wellness_resources OWNER TO postgres;

--
-- TOC entry 296 (class 1259 OID 175085)
-- Name: health_wellness_resources_resource_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.health_wellness_resources_resource_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.health_wellness_resources_resource_id_seq OWNER TO postgres;

--
-- TOC entry 6071 (class 0 OID 0)
-- Dependencies: 296
-- Name: health_wellness_resources_resource_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.health_wellness_resources_resource_id_seq OWNED BY public.health_wellness_resources.resource_id;


--
-- TOC entry 297 (class 1259 OID 175086)
-- Name: holiday_assignments; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.holiday_assignments (
    id integer NOT NULL,
    holiday_id integer,
    team_id integer,
    employee_id integer
);


ALTER TABLE public.holiday_assignments OWNER TO postgres;

--
-- TOC entry 298 (class 1259 OID 175089)
-- Name: holiday_assignments_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.holiday_assignments_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.holiday_assignments_id_seq OWNER TO postgres;

--
-- TOC entry 6072 (class 0 OID 0)
-- Dependencies: 298
-- Name: holiday_assignments_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.holiday_assignments_id_seq OWNED BY public.holiday_assignments.id;


--
-- TOC entry 299 (class 1259 OID 175090)
-- Name: holiday_assignments_id_seq1; Type: SEQUENCE; Schema: public; Owner: postgres
--

ALTER TABLE public.holiday_assignments ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.holiday_assignments_id_seq1
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- TOC entry 300 (class 1259 OID 175091)
-- Name: holidays; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.holidays (
    id integer NOT NULL,
    holiday_name character varying(255) NOT NULL,
    holiday_date date NOT NULL,
    is_paid boolean DEFAULT true,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    assigned_by_admins integer,
    assigned_by_super_admins integer
);


ALTER TABLE public.holidays OWNER TO postgres;

--
-- TOC entry 301 (class 1259 OID 175096)
-- Name: holidays_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.holidays_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.holidays_id_seq OWNER TO postgres;

--
-- TOC entry 6073 (class 0 OID 0)
-- Dependencies: 301
-- Name: holidays_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.holidays_id_seq OWNED BY public.holidays.id;


--
-- TOC entry 302 (class 1259 OID 175097)
-- Name: incident_logs; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.incident_logs (
    incident_id integer NOT NULL,
    admin_id integer,
    incident_type text DEFAULT 'system'::text NOT NULL,
    description text NOT NULL,
    severity_level text,
    status text DEFAULT 'Open'::text,
    reported_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    resolved_at timestamp without time zone,
    super_admin_id integer,
    role character varying(32),
    severity character varying(32),
    "timestamp" timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT incident_logs_severity_level_check CHECK ((severity_level = ANY (ARRAY['Low'::text, 'Medium'::text, 'High'::text, 'Critical'::text]))),
    CONSTRAINT incident_logs_status_check CHECK ((status = ANY (ARRAY['Open'::text, 'In Progress'::text, 'Resolved'::text])))
);


ALTER TABLE public.incident_logs OWNER TO postgres;

--
-- TOC entry 385 (class 1259 OID 176619)
-- Name: incident_logs_employee; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.incident_logs_employee (
    incident_id integer NOT NULL,
    employee_id integer NOT NULL,
    incident_type character varying(100) DEFAULT 'system'::character varying,
    description text NOT NULL,
    severity_level character varying(50) NOT NULL,
    status character varying(50) DEFAULT 'Open'::character varying,
    reported_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    resolved_at timestamp without time zone,
    "timestamp" timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.incident_logs_employee OWNER TO postgres;

--
-- TOC entry 384 (class 1259 OID 176618)
-- Name: incident_logs_employee_incident_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.incident_logs_employee_incident_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.incident_logs_employee_incident_id_seq OWNER TO postgres;

--
-- TOC entry 6074 (class 0 OID 0)
-- Dependencies: 384
-- Name: incident_logs_employee_incident_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.incident_logs_employee_incident_id_seq OWNED BY public.incident_logs_employee.incident_id;


--
-- TOC entry 303 (class 1259 OID 175108)
-- Name: incident_logs_incident_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.incident_logs_incident_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.incident_logs_incident_id_seq OWNER TO postgres;

--
-- TOC entry 6075 (class 0 OID 0)
-- Dependencies: 303
-- Name: incident_logs_incident_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.incident_logs_incident_id_seq OWNED BY public.incident_logs.incident_id;


--
-- TOC entry 304 (class 1259 OID 175117)
-- Name: learning_resources; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.learning_resources (
    resource_id integer NOT NULL,
    title character varying(255) NOT NULL,
    description text,
    resource_type character varying(50),
    content text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.learning_resources OWNER TO postgres;

--
-- TOC entry 305 (class 1259 OID 175127)
-- Name: learning_resources_resource_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.learning_resources_resource_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.learning_resources_resource_id_seq OWNER TO postgres;

--
-- TOC entry 6076 (class 0 OID 0)
-- Dependencies: 305
-- Name: learning_resources_resource_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.learning_resources_resource_id_seq OWNED BY public.learning_resources.resource_id;


--
-- TOC entry 306 (class 1259 OID 175128)
-- Name: leave_balances; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.leave_balances (
    balance_id integer NOT NULL,
    employee_id integer,
    sick_leave integer DEFAULT 0,
    vacation_leave integer DEFAULT 0,
    personal_leave integer DEFAULT 0,
    unpaid_leave integer DEFAULT 0
);


ALTER TABLE public.leave_balances OWNER TO postgres;

--
-- TOC entry 307 (class 1259 OID 175135)
-- Name: leave_balances_balance_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.leave_balances_balance_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.leave_balances_balance_id_seq OWNER TO postgres;

--
-- TOC entry 6077 (class 0 OID 0)
-- Dependencies: 307
-- Name: leave_balances_balance_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.leave_balances_balance_id_seq OWNED BY public.leave_balances.balance_id;


--
-- TOC entry 308 (class 1259 OID 175136)
-- Name: leave_requests; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.leave_requests (
    request_id integer NOT NULL,
    employee_id integer,
    leave_type text,
    start_date date,
    end_date date,
    total_days integer NOT NULL,
    status character varying(20) DEFAULT 'Pending'::character varying,
    remarks text,
    verification_status boolean,
    created_at date,
    CONSTRAINT leave_requests_status_check CHECK (((status)::text = ANY (ARRAY[('active'::character varying)::text, ('inactive'::character varying)::text])))
);


ALTER TABLE public.leave_requests OWNER TO postgres;

--
-- TOC entry 309 (class 1259 OID 175143)
-- Name: leave_requests_request_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.leave_requests_request_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.leave_requests_request_id_seq OWNER TO postgres;

--
-- TOC entry 6078 (class 0 OID 0)
-- Dependencies: 309
-- Name: leave_requests_request_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.leave_requests_request_id_seq OWNED BY public.leave_requests.request_id;


--
-- TOC entry 310 (class 1259 OID 175144)
-- Name: meetings; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.meetings (
    meeting_id integer NOT NULL,
    title character varying(255) NOT NULL,
    description text,
    meeting_date timestamp without time zone NOT NULL,
    duration interval NOT NULL,
    location character varying(255),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    employee_id integer,
    team_id integer,
    status text,
    assigned_by_admins integer,
    assigned_by_super_admins integer
);


ALTER TABLE public.meetings OWNER TO postgres;

--
-- TOC entry 311 (class 1259 OID 175150)
-- Name: meetings_meeting_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.meetings_meeting_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.meetings_meeting_id_seq OWNER TO postgres;

--
-- TOC entry 6079 (class 0 OID 0)
-- Dependencies: 311
-- Name: meetings_meeting_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.meetings_meeting_id_seq OWNED BY public.meetings.meeting_id;


--
-- TOC entry 312 (class 1259 OID 175151)
-- Name: messages; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.messages (
    message_id integer NOT NULL,
    sender_id integer NOT NULL,
    sender_role character varying(50) NOT NULL,
    receiver_id integer NOT NULL,
    receiver_role character varying(50) NOT NULL,
    subject text,
    body text NOT NULL,
    is_read boolean DEFAULT false,
    "timestamp" timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.messages OWNER TO postgres;

--
-- TOC entry 313 (class 1259 OID 175158)
-- Name: messages_message_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.messages_message_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.messages_message_id_seq OWNER TO postgres;

--
-- TOC entry 6080 (class 0 OID 0)
-- Dependencies: 313
-- Name: messages_message_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.messages_message_id_seq OWNED BY public.messages.message_id;


--
-- TOC entry 314 (class 1259 OID 175175)
-- Name: payroll; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.payroll (
    payroll_id integer NOT NULL,
    employee_id integer,
    month date NOT NULL,
    base_salary numeric(10,2) NOT NULL,
    hours_worked numeric(5,2),
    overtime_hours numeric(5,2),
    overtime_pay numeric(10,2),
    bonuses numeric(10,2) DEFAULT 0,
    tax_rate numeric(5,2),
    tax numeric(10,2),
    net_salary numeric(10,2),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    deductions numeric(10,2) DEFAULT 0,
    payment_status character varying(20) DEFAULT 'Pending'::character varying,
    payment_date timestamp without time zone
);


ALTER TABLE public.payroll OWNER TO postgres;

--
-- TOC entry 315 (class 1259 OID 175182)
-- Name: payroll_payroll_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.payroll_payroll_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.payroll_payroll_id_seq OWNER TO postgres;

--
-- TOC entry 6081 (class 0 OID 0)
-- Dependencies: 315
-- Name: payroll_payroll_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.payroll_payroll_id_seq OWNED BY public.payroll.payroll_id;


--
-- TOC entry 316 (class 1259 OID 175188)
-- Name: performance_reviews; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.performance_reviews (
    review_id integer NOT NULL,
    employee_id integer,
    review_date date DEFAULT CURRENT_DATE NOT NULL,
    feedback text,
    rating character varying(50),
    reviewer text,
    CONSTRAINT performance_reviews_rating_check CHECK (((rating)::text = ANY (ARRAY[('Excellent'::character varying)::text, ('Good'::character varying)::text, ('Average'::character varying)::text, ('Needs Improvement'::character varying)::text])))
);


ALTER TABLE public.performance_reviews OWNER TO postgres;

--
-- TOC entry 317 (class 1259 OID 175195)
-- Name: performance_reviews_review_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.performance_reviews_review_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.performance_reviews_review_id_seq OWNER TO postgres;

--
-- TOC entry 6082 (class 0 OID 0)
-- Dependencies: 317
-- Name: performance_reviews_review_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.performance_reviews_review_id_seq OWNED BY public.performance_reviews.review_id;


--
-- TOC entry 318 (class 1259 OID 175206)
-- Name: progress_progress_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.progress_progress_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.progress_progress_id_seq OWNER TO postgres;

--
-- TOC entry 6083 (class 0 OID 0)
-- Dependencies: 318
-- Name: progress_progress_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.progress_progress_id_seq OWNED BY public.goal_progress.progress_id;


--
-- TOC entry 319 (class 1259 OID 175207)
-- Name: progress_progress_id_seq1; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.progress_progress_id_seq1
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.progress_progress_id_seq1 OWNER TO postgres;

--
-- TOC entry 6084 (class 0 OID 0)
-- Dependencies: 319
-- Name: progress_progress_id_seq1; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.progress_progress_id_seq1 OWNED BY public.goal_progress_percentage.progress_percentage_id;


--
-- TOC entry 320 (class 1259 OID 175208)
-- Name: projects; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.projects (
    project_id integer NOT NULL,
    project_name text,
    description text,
    start_date date,
    end_date date,
    status text,
    progress integer DEFAULT 0
);


ALTER TABLE public.projects OWNER TO postgres;

--
-- TOC entry 321 (class 1259 OID 175214)
-- Name: projects_project_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.projects_project_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.projects_project_id_seq OWNER TO postgres;

--
-- TOC entry 6085 (class 0 OID 0)
-- Dependencies: 321
-- Name: projects_project_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.projects_project_id_seq OWNED BY public.projects.project_id;


--
-- TOC entry 322 (class 1259 OID 175231)
-- Name: roles; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.roles (
    role_id integer NOT NULL,
    role_name character varying(50) NOT NULL
);


ALTER TABLE public.roles OWNER TO postgres;

--
-- TOC entry 323 (class 1259 OID 175234)
-- Name: roles_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.roles_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.roles_id_seq OWNER TO postgres;

--
-- TOC entry 6086 (class 0 OID 0)
-- Dependencies: 323
-- Name: roles_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.roles_id_seq OWNED BY public.roles.role_id;


--
-- TOC entry 324 (class 1259 OID 175235)
-- Name: route_actions; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.route_actions (
    id integer NOT NULL,
    route_id integer,
    action_id integer
);


ALTER TABLE public.route_actions OWNER TO postgres;

--
-- TOC entry 325 (class 1259 OID 175238)
-- Name: route_actions_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.route_actions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.route_actions_id_seq OWNER TO postgres;

--
-- TOC entry 6087 (class 0 OID 0)
-- Dependencies: 325
-- Name: route_actions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.route_actions_id_seq OWNED BY public.route_actions.id;


--
-- TOC entry 326 (class 1259 OID 175239)
-- Name: routes; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.routes (
    id integer NOT NULL,
    route_name character varying NOT NULL,
    description character varying
);


ALTER TABLE public.routes OWNER TO postgres;

--
-- TOC entry 327 (class 1259 OID 175244)
-- Name: routes_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.routes_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.routes_id_seq OWNER TO postgres;

--
-- TOC entry 6088 (class 0 OID 0)
-- Dependencies: 327
-- Name: routes_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.routes_id_seq OWNED BY public.routes.id;


--
-- TOC entry 328 (class 1259 OID 175245)
-- Name: savings_plan_requests; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.savings_plan_requests (
    request_id integer NOT NULL,
    plan_id integer,
    employee_id integer,
    message text NOT NULL,
    status character varying(50) DEFAULT 'Pending'::character varying,
    submitted_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    reviewed_by character varying(100),
    reviewed_at timestamp without time zone,
    response text
);


ALTER TABLE public.savings_plan_requests OWNER TO postgres;

--
-- TOC entry 329 (class 1259 OID 175252)
-- Name: savings_plan_requests_request_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.savings_plan_requests_request_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.savings_plan_requests_request_id_seq OWNER TO postgres;

--
-- TOC entry 6089 (class 0 OID 0)
-- Dependencies: 329
-- Name: savings_plan_requests_request_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.savings_plan_requests_request_id_seq OWNED BY public.savings_plan_requests.request_id;


--
-- TOC entry 330 (class 1259 OID 175253)
-- Name: savings_plans; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.savings_plans (
    plan_id integer NOT NULL,
    employee_id integer,
    plan_type character varying(100),
    provider character varying(255),
    contribution_percent numeric(5,2),
    employer_match_percent numeric(5,2),
    status character varying(50),
    start_date date,
    notes text,
    document_path text,
    contribution_amount numeric(12,2),
    contribution_unit character varying(20),
    employer_match_amount numeric(12,2),
    employer_match_unit character varying(20)
);


ALTER TABLE public.savings_plans OWNER TO postgres;

--
-- TOC entry 331 (class 1259 OID 175258)
-- Name: savings_plans_plan_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.savings_plans_plan_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.savings_plans_plan_id_seq OWNER TO postgres;

--
-- TOC entry 6090 (class 0 OID 0)
-- Dependencies: 331
-- Name: savings_plans_plan_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.savings_plans_plan_id_seq OWNED BY public.savings_plans.plan_id;


--
-- TOC entry 332 (class 1259 OID 175259)
-- Name: shift_request_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.shift_request_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.shift_request_id_seq OWNER TO postgres;

--
-- TOC entry 333 (class 1259 OID 175260)
-- Name: shift_request; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.shift_request (
    shift_request_id integer DEFAULT nextval('public.shift_request_id_seq'::regclass),
    sender_id integer,
    sender_role character varying(50),
    subject text,
    body text,
    is_read boolean,
    "timestamp" timestamp without time zone,
    is_approved boolean,
    approver_role integer
);


ALTER TABLE public.shift_request OWNER TO postgres;

--
-- TOC entry 334 (class 1259 OID 175266)
-- Name: shifts; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.shifts (
    shift_name character varying(100),
    start_time time without time zone NOT NULL,
    end_time time without time zone NOT NULL,
    shift_id integer NOT NULL
);


ALTER TABLE public.shifts OWNER TO postgres;

--
-- TOC entry 335 (class 1259 OID 175269)
-- Name: shifts_new_shift_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.shifts_new_shift_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.shifts_new_shift_id_seq OWNER TO postgres;

--
-- TOC entry 6091 (class 0 OID 0)
-- Dependencies: 335
-- Name: shifts_new_shift_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.shifts_new_shift_id_seq OWNED BY public.shifts.shift_id;


--
-- TOC entry 336 (class 1259 OID 175270)
-- Name: skill_assessments; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.skill_assessments (
    assessment_id integer NOT NULL,
    employee_id integer,
    assessment_date timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    score numeric(5,2),
    feedback text,
    module_id integer,
    is_completed boolean DEFAULT false,
    CONSTRAINT skill_assessments_score_check CHECK (((score >= (0)::numeric) AND (score <= (100)::numeric)))
);


ALTER TABLE public.skill_assessments OWNER TO postgres;

--
-- TOC entry 337 (class 1259 OID 175278)
-- Name: skill_assessments_assessment_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.skill_assessments_assessment_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.skill_assessments_assessment_id_seq OWNER TO postgres;

--
-- TOC entry 6092 (class 0 OID 0)
-- Dependencies: 337
-- Name: skill_assessments_assessment_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.skill_assessments_assessment_id_seq OWNED BY public.skill_assessments.assessment_id;


--
-- TOC entry 338 (class 1259 OID 175279)
-- Name: skill_development; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.skill_development (
    skill_id integer NOT NULL,
    employee_id integer,
    training_name character varying(255) NOT NULL,
    provider character varying(255),
    completion_date timestamp without time zone,
    status character varying(50) DEFAULT 'Not Started'::character varying
);


ALTER TABLE public.skill_development OWNER TO postgres;

--
-- TOC entry 339 (class 1259 OID 175285)
-- Name: skill_development_skill_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.skill_development_skill_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.skill_development_skill_id_seq OWNER TO postgres;

--
-- TOC entry 6093 (class 0 OID 0)
-- Dependencies: 339
-- Name: skill_development_skill_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.skill_development_skill_id_seq OWNED BY public.skill_development.skill_id;


--
-- TOC entry 340 (class 1259 OID 175286)
-- Name: super_admins; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.super_admins (
    super_admin_id integer NOT NULL,
    email character varying(255) NOT NULL,
    password_hash text NOT NULL,
    first_name character varying(100),
    last_name character varying(100),
    profile_image bytea,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    last_login timestamp without time zone,
    status character varying(20) DEFAULT 'Active'::character varying,
    last_modified timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    role_id integer,
    jti text,
    phone_number integer,
    bio text,
    gender character varying(1),
    date_of_birth timestamp without time zone
);


ALTER TABLE public.super_admins OWNER TO postgres;

--
-- TOC entry 341 (class 1259 OID 175294)
-- Name: super_admins_super_admin_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.super_admins_super_admin_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.super_admins_super_admin_id_seq OWNER TO postgres;

--
-- TOC entry 6094 (class 0 OID 0)
-- Dependencies: 341
-- Name: super_admins_super_admin_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.super_admins_super_admin_id_seq OWNED BY public.super_admins.super_admin_id;


--
-- TOC entry 342 (class 1259 OID 175295)
-- Name: survey_answer_options; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.survey_answer_options (
    option_id integer NOT NULL,
    question_id integer NOT NULL,
    option_text text NOT NULL
);


ALTER TABLE public.survey_answer_options OWNER TO postgres;

--
-- TOC entry 343 (class 1259 OID 175300)
-- Name: survey_answer_options_option_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.survey_answer_options_option_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.survey_answer_options_option_id_seq OWNER TO postgres;

--
-- TOC entry 6095 (class 0 OID 0)
-- Dependencies: 343
-- Name: survey_answer_options_option_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.survey_answer_options_option_id_seq OWNED BY public.survey_answer_options.option_id;


--
-- TOC entry 344 (class 1259 OID 175301)
-- Name: survey_assignments; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.survey_assignments (
    assignment_id integer NOT NULL,
    survey_id integer,
    employee_id integer,
    team_id integer,
    assigned_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    has_submitted boolean,
    attempt_number integer,
    CONSTRAINT survey_assignments_check CHECK ((((employee_id IS NOT NULL) AND (team_id IS NULL)) OR ((employee_id IS NULL) AND (team_id IS NOT NULL))))
);


ALTER TABLE public.survey_assignments OWNER TO postgres;

--
-- TOC entry 345 (class 1259 OID 175306)
-- Name: survey_assignments_assignment_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.survey_assignments_assignment_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.survey_assignments_assignment_id_seq OWNER TO postgres;

--
-- TOC entry 6096 (class 0 OID 0)
-- Dependencies: 345
-- Name: survey_assignments_assignment_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.survey_assignments_assignment_id_seq OWNED BY public.survey_assignments.assignment_id;


--
-- TOC entry 346 (class 1259 OID 175307)
-- Name: survey_question_options; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.survey_question_options (
    option_id integer NOT NULL,
    question_id integer,
    option_text text NOT NULL,
    is_correct boolean DEFAULT false
);


ALTER TABLE public.survey_question_options OWNER TO postgres;

--
-- TOC entry 347 (class 1259 OID 175313)
-- Name: survey_question_options_option_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.survey_question_options_option_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.survey_question_options_option_id_seq OWNER TO postgres;

--
-- TOC entry 6097 (class 0 OID 0)
-- Dependencies: 347
-- Name: survey_question_options_option_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.survey_question_options_option_id_seq OWNED BY public.survey_question_options.option_id;


--
-- TOC entry 348 (class 1259 OID 175314)
-- Name: survey_questions; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.survey_questions (
    question_id integer NOT NULL,
    survey_id integer,
    question_text text NOT NULL,
    question_type character varying(50),
    CONSTRAINT survey_questions_question_type_check CHECK (((question_type)::text = ANY (ARRAY[('text'::character varying)::text, ('multiple_choice'::character varying)::text, ('rating'::character varying)::text])))
);


ALTER TABLE public.survey_questions OWNER TO postgres;

--
-- TOC entry 349 (class 1259 OID 175320)
-- Name: survey_questions_question_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.survey_questions_question_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.survey_questions_question_id_seq OWNER TO postgres;

--
-- TOC entry 6098 (class 0 OID 0)
-- Dependencies: 349
-- Name: survey_questions_question_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.survey_questions_question_id_seq OWNED BY public.survey_questions.question_id;


--
-- TOC entry 350 (class 1259 OID 175321)
-- Name: survey_responses; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.survey_responses (
    response_id integer NOT NULL,
    survey_id integer,
    question_id integer,
    submitted_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    employee_id integer,
    option_id integer,
    response_text text,
    attempt_number integer
);


ALTER TABLE public.survey_responses OWNER TO postgres;

--
-- TOC entry 351 (class 1259 OID 175327)
-- Name: survey_responses_response_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.survey_responses_response_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.survey_responses_response_id_seq OWNER TO postgres;

--
-- TOC entry 6099 (class 0 OID 0)
-- Dependencies: 351
-- Name: survey_responses_response_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.survey_responses_response_id_seq OWNED BY public.survey_responses.response_id;


--
-- TOC entry 352 (class 1259 OID 175328)
-- Name: surveys; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.surveys (
    survey_id integer NOT NULL,
    title character varying(255) NOT NULL,
    description text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    is_active boolean DEFAULT true,
    super_admin_id integer,
    admin_id integer,
    created_by text
);


ALTER TABLE public.surveys OWNER TO postgres;

--
-- TOC entry 353 (class 1259 OID 175335)
-- Name: surveys_survey_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.surveys_survey_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.surveys_survey_id_seq OWNER TO postgres;

--
-- TOC entry 6100 (class 0 OID 0)
-- Dependencies: 353
-- Name: surveys_survey_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.surveys_survey_id_seq OWNED BY public.surveys.survey_id;


--
-- TOC entry 354 (class 1259 OID 175336)
-- Name: task_parts; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.task_parts (
    part_id integer NOT NULL,
    task_id integer,
    part_name character varying(255) NOT NULL,
    part_percentage integer,
    completed boolean DEFAULT false,
    executed_at timestamp without time zone,
    CONSTRAINT task_parts_part_percentage_check CHECK (((part_percentage >= 0) AND (part_percentage <= 100)))
);


ALTER TABLE public.task_parts OWNER TO postgres;

--
-- TOC entry 355 (class 1259 OID 175341)
-- Name: task_parts_part_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.task_parts_part_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.task_parts_part_id_seq OWNER TO postgres;

--
-- TOC entry 6101 (class 0 OID 0)
-- Dependencies: 355
-- Name: task_parts_part_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.task_parts_part_id_seq OWNED BY public.task_parts.part_id;


--
-- TOC entry 356 (class 1259 OID 175342)
-- Name: tasks; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.tasks (
    task_id integer NOT NULL,
    task_name character varying(255) NOT NULL,
    description text,
    employee_id integer,
    assigned_date timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    due_date timestamp without time zone,
    status character varying(50) DEFAULT 'Pending'::character varying,
    team_id integer,
    progress integer DEFAULT 0,
    project_id integer,
    CONSTRAINT tasks_progress_check CHECK (((progress >= 0) AND (progress <= 100)))
);


ALTER TABLE public.tasks OWNER TO postgres;

--
-- TOC entry 357 (class 1259 OID 175351)
-- Name: tasks_task_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.tasks_task_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.tasks_task_id_seq OWNER TO postgres;

--
-- TOC entry 6102 (class 0 OID 0)
-- Dependencies: 357
-- Name: tasks_task_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.tasks_task_id_seq OWNED BY public.tasks.task_id;


--
-- TOC entry 358 (class 1259 OID 175352)
-- Name: tax_documents; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.tax_documents (
    document_id integer NOT NULL,
    employee_id integer,
    tax_year integer NOT NULL,
    document_type character varying(255) NOT NULL,
    file_path character varying(255) NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.tax_documents OWNER TO postgres;

--
-- TOC entry 359 (class 1259 OID 175358)
-- Name: tax_documents_document_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.tax_documents_document_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.tax_documents_document_id_seq OWNER TO postgres;

--
-- TOC entry 6103 (class 0 OID 0)
-- Dependencies: 359
-- Name: tax_documents_document_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.tax_documents_document_id_seq OWNED BY public.tax_documents.document_id;


--
-- TOC entry 360 (class 1259 OID 175359)
-- Name: tax_records; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.tax_records (
    record_id integer NOT NULL,
    employee_id integer,
    gross_income numeric(10,2) NOT NULL,
    tax_deducted numeric(10,2) NOT NULL,
    net_income numeric(10,2) NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    document_id integer
);


ALTER TABLE public.tax_records OWNER TO postgres;

--
-- TOC entry 361 (class 1259 OID 175363)
-- Name: tax_records_record_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.tax_records_record_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.tax_records_record_id_seq OWNER TO postgres;

--
-- TOC entry 6104 (class 0 OID 0)
-- Dependencies: 361
-- Name: tax_records_record_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.tax_records_record_id_seq OWNED BY public.tax_records.record_id;


--
-- TOC entry 362 (class 1259 OID 175364)
-- Name: team_members; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.team_members (
    id integer NOT NULL,
    team_id integer NOT NULL,
    employee_id integer NOT NULL,
    role character varying(100) DEFAULT 'Member'::character varying,
    assigned_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    admin_id integer
);


ALTER TABLE public.team_members OWNER TO postgres;

--
-- TOC entry 363 (class 1259 OID 175369)
-- Name: team_members_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.team_members_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.team_members_id_seq OWNER TO postgres;

--
-- TOC entry 6105 (class 0 OID 0)
-- Dependencies: 363
-- Name: team_members_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.team_members_id_seq OWNED BY public.team_members.id;


--
-- TOC entry 364 (class 1259 OID 175370)
-- Name: teams; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.teams (
    team_id integer NOT NULL,
    team_name character varying(100) NOT NULL,
    created_at date,
    team_lead_employee_id integer,
    team_lead_admin_id integer
);


ALTER TABLE public.teams OWNER TO postgres;

--
-- TOC entry 365 (class 1259 OID 175373)
-- Name: teams_team_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.teams_team_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.teams_team_id_seq OWNER TO postgres;

--
-- TOC entry 6106 (class 0 OID 0)
-- Dependencies: 365
-- Name: teams_team_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.teams_team_id_seq OWNED BY public.teams.team_id;


--
-- TOC entry 366 (class 1259 OID 175374)
-- Name: ticket_responses; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.ticket_responses (
    response_id integer NOT NULL,
    ticket_id integer,
    employee_id integer,
    response text,
    responded_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    responded_by text,
    admin_response text,
    responded_by_admin text
);


ALTER TABLE public.ticket_responses OWNER TO postgres;

--
-- TOC entry 367 (class 1259 OID 175380)
-- Name: ticket_responses_response_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.ticket_responses_response_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.ticket_responses_response_id_seq OWNER TO postgres;

--
-- TOC entry 6107 (class 0 OID 0)
-- Dependencies: 367
-- Name: ticket_responses_response_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.ticket_responses_response_id_seq OWNED BY public.ticket_responses.response_id;


--
-- TOC entry 368 (class 1259 OID 175381)
-- Name: tickets; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.tickets (
    ticket_id integer NOT NULL,
    employee_id integer NOT NULL,
    category character varying(255) NOT NULL,
    subject character varying(255) NOT NULL,
    description text NOT NULL,
    priority character varying(50) DEFAULT 'medium'::character varying,
    status character varying(50) DEFAULT 'open'::character varying,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    file_path text,
    CONSTRAINT tickets_priority_check CHECK (((priority)::text = ANY (ARRAY[('Low'::character varying)::text, ('Medium'::character varying)::text, ('High'::character varying)::text, ('Critical'::character varying)::text]))),
    CONSTRAINT tickets_status_check CHECK (((status)::text = ANY (ARRAY[('Open'::character varying)::text, ('Pending'::character varying)::text, ('Resolved'::character varying)::text, ('Closed'::character varying)::text])))
);


ALTER TABLE public.tickets OWNER TO postgres;

--
-- TOC entry 369 (class 1259 OID 175392)
-- Name: tickets_ticket_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.tickets_ticket_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.tickets_ticket_id_seq OWNER TO postgres;

--
-- TOC entry 6108 (class 0 OID 0)
-- Dependencies: 369
-- Name: tickets_ticket_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.tickets_ticket_id_seq OWNED BY public.tickets.ticket_id;


--
-- TOC entry 370 (class 1259 OID 175393)
-- Name: timesheets; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.timesheets (
    timesheet_id integer NOT NULL,
    employee_id integer NOT NULL,
    log_date date NOT NULL,
    total_work_hours interval,
    total_break_time interval DEFAULT '00:00:00'::interval,
    overtime interval DEFAULT '00:00:00'::interval,
    status character varying(50) DEFAULT 'pending'::character varying,
    submitted_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    approved_by text,
    log_id integer,
    break_id integer[],
    CONSTRAINT timesheets_status_check CHECK (((status)::text = ANY (ARRAY[('pending'::character varying)::text, ('approved'::character varying)::text, ('rejected'::character varying)::text])))
);


ALTER TABLE public.timesheets OWNER TO postgres;

--
-- TOC entry 371 (class 1259 OID 175403)
-- Name: timesheets_timesheet_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.timesheets_timesheet_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.timesheets_timesheet_id_seq OWNER TO postgres;

--
-- TOC entry 6109 (class 0 OID 0)
-- Dependencies: 371
-- Name: timesheets_timesheet_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.timesheets_timesheet_id_seq OWNED BY public.timesheets.timesheet_id;


--
-- TOC entry 372 (class 1259 OID 175404)
-- Name: training_certificates; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.training_certificates (
    certificate_id integer NOT NULL,
    employee_id integer,
    module_id integer,
    issued_date timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    certificate_status character varying(50) DEFAULT 'Pending'::character varying,
    CONSTRAINT certificate_status_check CHECK (((certificate_status)::text = ANY (ARRAY[('Pending'::character varying)::text, ('Issued'::character varying)::text, ('Revoked'::character varying)::text])))
);


ALTER TABLE public.training_certificates OWNER TO postgres;

--
-- TOC entry 373 (class 1259 OID 175410)
-- Name: training_certificates_certificate_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.training_certificates_certificate_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.training_certificates_certificate_id_seq OWNER TO postgres;

--
-- TOC entry 6110 (class 0 OID 0)
-- Dependencies: 373
-- Name: training_certificates_certificate_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.training_certificates_certificate_id_seq OWNED BY public.training_certificates.certificate_id;


--
-- TOC entry 374 (class 1259 OID 175411)
-- Name: training_modules; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.training_modules (
    module_id integer NOT NULL,
    module_name character varying(255) NOT NULL,
    description text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    deadline date,
    updated_at timestamp without time zone
);


ALTER TABLE public.training_modules OWNER TO postgres;

--
-- TOC entry 375 (class 1259 OID 175417)
-- Name: training_modules_module_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.training_modules_module_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.training_modules_module_id_seq OWNER TO postgres;

--
-- TOC entry 6111 (class 0 OID 0)
-- Dependencies: 375
-- Name: training_modules_module_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.training_modules_module_id_seq OWNED BY public.training_modules.module_id;


--
-- TOC entry 376 (class 1259 OID 175425)
-- Name: travel_requests; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.travel_requests (
    request_id integer NOT NULL,
    employee_id integer NOT NULL,
    destination character varying(255) NOT NULL,
    start_date date NOT NULL,
    end_date date NOT NULL,
    purpose text NOT NULL,
    estimated_expense numeric(10,2) NOT NULL,
    status character varying(20) DEFAULT 'Pending'::character varying NOT NULL,
    submission_date timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    approved_by text,
    remarks text
);


ALTER TABLE public.travel_requests OWNER TO postgres;

--
-- TOC entry 377 (class 1259 OID 175432)
-- Name: travel_requests_request_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.travel_requests_request_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.travel_requests_request_id_seq OWNER TO postgres;

--
-- TOC entry 6112 (class 0 OID 0)
-- Dependencies: 377
-- Name: travel_requests_request_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.travel_requests_request_id_seq OWNED BY public.travel_requests.request_id;


--
-- TOC entry 378 (class 1259 OID 175433)
-- Name: two_factor_verifications; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.two_factor_verifications (
    verification_id integer NOT NULL,
    admin_id integer,
    employee_id integer,
    verification_code character varying(10),
    is_verified boolean,
    verification_timestamp timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    purpose character varying(20)
);


ALTER TABLE public.two_factor_verifications OWNER TO postgres;

--
-- TOC entry 379 (class 1259 OID 175437)
-- Name: two_factor_verifications_verification_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.two_factor_verifications_verification_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.two_factor_verifications_verification_id_seq OWNER TO postgres;

--
-- TOC entry 6113 (class 0 OID 0)
-- Dependencies: 379
-- Name: two_factor_verifications_verification_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.two_factor_verifications_verification_id_seq OWNED BY public.two_factor_verifications.verification_id;


--
-- TOC entry 380 (class 1259 OID 175438)
-- Name: workflows; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.workflows (
    workflow_id integer NOT NULL,
    name character varying(100) NOT NULL,
    description text,
    steps jsonb,
    status character varying(50) DEFAULT 'active'::character varying
);


ALTER TABLE public.workflows OWNER TO postgres;

--
-- TOC entry 381 (class 1259 OID 175444)
-- Name: workflows_workflow_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.workflows_workflow_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.workflows_workflow_id_seq OWNER TO postgres;

--
-- TOC entry 6114 (class 0 OID 0)
-- Dependencies: 381
-- Name: workflows_workflow_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.workflows_workflow_id_seq OWNED BY public.workflows.workflow_id;


--
-- TOC entry 5162 (class 2604 OID 175445)
-- Name: actions id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.actions ALTER COLUMN id SET DEFAULT nextval('public.actions_id_seq'::regclass);


--
-- TOC entry 5163 (class 2604 OID 175446)
-- Name: admin_access_requests id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.admin_access_requests ALTER COLUMN id SET DEFAULT nextval('public.admin_access_requests_id_seq'::regclass);


--
-- TOC entry 5166 (class 2604 OID 175447)
-- Name: admin_route_actions id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.admin_route_actions ALTER COLUMN id SET DEFAULT nextval('public.admin_route_actions_id_seq'::regclass);


--
-- TOC entry 5171 (class 2604 OID 175449)
-- Name: alerts alert_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.alerts ALTER COLUMN alert_id SET DEFAULT nextval('public.alerts_alert_id_seq'::regclass);


--
-- TOC entry 5173 (class 2604 OID 175450)
-- Name: announcement_reads read_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.announcement_reads ALTER COLUMN read_id SET DEFAULT nextval('public.announcement_reads_read_id_seq'::regclass);


--
-- TOC entry 5175 (class 2604 OID 175451)
-- Name: announcements announcement_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.announcements ALTER COLUMN announcement_id SET DEFAULT nextval('public.announcements_announcement_id_seq'::regclass);


--
-- TOC entry 5177 (class 2604 OID 175453)
-- Name: assessment_answers answer_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.assessment_answers ALTER COLUMN answer_id SET DEFAULT nextval('public.assessment_answers_answer_id_seq'::regclass);


--
-- TOC entry 5178 (class 2604 OID 175454)
-- Name: assessment_options option_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.assessment_options ALTER COLUMN option_id SET DEFAULT nextval('public.assessment_options_option_id_seq'::regclass);


--
-- TOC entry 5180 (class 2604 OID 175455)
-- Name: assessment_questions question_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.assessment_questions ALTER COLUMN question_id SET DEFAULT nextval('public.assessment_questions_question_id_seq'::regclass);


--
-- TOC entry 5181 (class 2604 OID 175456)
-- Name: attendance_logs log_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.attendance_logs ALTER COLUMN log_id SET DEFAULT nextval('public.attendance_logs_log_id_seq'::regclass);


--
-- TOC entry 5188 (class 2604 OID 175457)
-- Name: audit_trail_admin audit_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.audit_trail_admin ALTER COLUMN audit_id SET DEFAULT nextval('public.audit_trail_audit_id_seq'::regclass);


--
-- TOC entry 5355 (class 2604 OID 176606)
-- Name: audit_trail_employee audit_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.audit_trail_employee ALTER COLUMN audit_id SET DEFAULT nextval('public.audit_trail_employee_audit_id_seq'::regclass);


--
-- TOC entry 5190 (class 2604 OID 175458)
-- Name: badge_assignments assignment_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.badge_assignments ALTER COLUMN assignment_id SET DEFAULT nextval('public.badge_assignments_assignment_id_seq'::regclass);


--
-- TOC entry 5192 (class 2604 OID 175459)
-- Name: badges badge_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.badges ALTER COLUMN badge_id SET DEFAULT nextval('public.badges_badge_id_seq'::regclass);


--
-- TOC entry 5194 (class 2604 OID 175460)
-- Name: bank_details bank_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.bank_details ALTER COLUMN bank_id SET DEFAULT nextval('public.bank_details_bank_id_seq'::regclass);


--
-- TOC entry 5197 (class 2604 OID 175461)
-- Name: bonuses_incentives id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.bonuses_incentives ALTER COLUMN id SET DEFAULT nextval('public.bonuses_incentives_id_seq'::regclass);


--
-- TOC entry 5200 (class 2604 OID 175464)
-- Name: contact_replies id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.contact_replies ALTER COLUMN id SET DEFAULT nextval('public.contact_replies_id_seq'::regclass);


--
-- TOC entry 5202 (class 2604 OID 175465)
-- Name: contact_requests id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.contact_requests ALTER COLUMN id SET DEFAULT nextval('public.contact_requests_id_seq'::regclass);


--
-- TOC entry 5205 (class 2604 OID 175468)
-- Name: devices device_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.devices ALTER COLUMN device_id SET DEFAULT nextval('public.devices_device_id_seq'::regclass);


--
-- TOC entry 5206 (class 2604 OID 175470)
-- Name: document_categories category_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.document_categories ALTER COLUMN category_id SET DEFAULT nextval('public.document_categories_category_id_seq'::regclass);


--
-- TOC entry 5207 (class 2604 OID 175471)
-- Name: document_history history_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.document_history ALTER COLUMN history_id SET DEFAULT nextval('public.document_history_history_id_seq'::regclass);


--
-- TOC entry 5209 (class 2604 OID 175472)
-- Name: documents document_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.documents ALTER COLUMN document_id SET DEFAULT nextval('public.documents_document_id_seq'::regclass);


--
-- TOC entry 5214 (class 2604 OID 175473)
-- Name: employee_breaks break_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.employee_breaks ALTER COLUMN break_id SET DEFAULT nextval('public.employee_breaks_break_id_seq'::regclass);


--
-- TOC entry 5218 (class 2604 OID 175474)
-- Name: employee_recognition recognition_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.employee_recognition ALTER COLUMN recognition_id SET DEFAULT nextval('public.employee_recognition_recognition_id_seq'::regclass);


--
-- TOC entry 5220 (class 2604 OID 175475)
-- Name: employee_shifts id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.employee_shifts ALTER COLUMN id SET DEFAULT nextval('public.employee_shifts_id_seq'::regclass);


--
-- TOC entry 5222 (class 2604 OID 175477)
-- Name: employees employee_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.employees ALTER COLUMN employee_id SET DEFAULT nextval('public.employees_employee_id_seq'::regclass);


--
-- TOC entry 5228 (class 2604 OID 175481)
-- Name: event_participants participant_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.event_participants ALTER COLUMN participant_id SET DEFAULT nextval('public.event_participants_participant_id_seq'::regclass);


--
-- TOC entry 5230 (class 2604 OID 175482)
-- Name: events event_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.events ALTER COLUMN event_id SET DEFAULT nextval('public.events_event_id_seq'::regclass);


--
-- TOC entry 5234 (class 2604 OID 175483)
-- Name: expense_claims claim_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.expense_claims ALTER COLUMN claim_id SET DEFAULT nextval('public.expense_claims_claim_id_seq'::regclass);


--
-- TOC entry 5237 (class 2604 OID 175484)
-- Name: feedback_requests request_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.feedback_requests ALTER COLUMN request_id SET DEFAULT nextval('public.feedback_requests_request_id_seq'::regclass);


--
-- TOC entry 5239 (class 2604 OID 175485)
-- Name: feedback_responses response_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.feedback_responses ALTER COLUMN response_id SET DEFAULT nextval('public.feedback_responses_response_id_seq'::regclass);


--
-- TOC entry 5159 (class 2604 OID 175486)
-- Name: goal_action_plans action_plan_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.goal_action_plans ALTER COLUMN action_plan_id SET DEFAULT nextval('public.action_plans_action_plan_id_seq'::regclass);


--
-- TOC entry 5226 (class 2604 OID 175487)
-- Name: goal_evaluations evaluation_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.goal_evaluations ALTER COLUMN evaluation_id SET DEFAULT nextval('public.evaluations_evaluation_id_seq'::regclass);


--
-- TOC entry 5245 (class 2604 OID 175488)
-- Name: goal_progress_notes note_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.goal_progress_notes ALTER COLUMN note_id SET DEFAULT nextval('public.goal_progress_notes_note_id_seq'::regclass);


--
-- TOC entry 5248 (class 2604 OID 175489)
-- Name: goal_progress_percentage progress_percentage_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.goal_progress_percentage ALTER COLUMN progress_percentage_id SET DEFAULT nextval('public.progress_progress_id_seq1'::regclass);


--
-- TOC entry 5250 (class 2604 OID 175490)
-- Name: goals goal_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.goals ALTER COLUMN goal_id SET DEFAULT nextval('public.goals_goal_id_seq'::regclass);


--
-- TOC entry 5254 (class 2604 OID 175491)
-- Name: health_wellness_resources resource_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.health_wellness_resources ALTER COLUMN resource_id SET DEFAULT nextval('public.health_wellness_resources_resource_id_seq'::regclass);


--
-- TOC entry 5256 (class 2604 OID 175492)
-- Name: holidays id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.holidays ALTER COLUMN id SET DEFAULT nextval('public.holidays_id_seq'::regclass);


--
-- TOC entry 5259 (class 2604 OID 175493)
-- Name: incident_logs incident_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.incident_logs ALTER COLUMN incident_id SET DEFAULT nextval('public.incident_logs_incident_id_seq'::regclass);


--
-- TOC entry 5358 (class 2604 OID 176622)
-- Name: incident_logs_employee incident_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.incident_logs_employee ALTER COLUMN incident_id SET DEFAULT nextval('public.incident_logs_employee_incident_id_seq'::regclass);


--
-- TOC entry 5264 (class 2604 OID 175495)
-- Name: learning_resources resource_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.learning_resources ALTER COLUMN resource_id SET DEFAULT nextval('public.learning_resources_resource_id_seq'::regclass);


--
-- TOC entry 5267 (class 2604 OID 175496)
-- Name: leave_balances balance_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.leave_balances ALTER COLUMN balance_id SET DEFAULT nextval('public.leave_balances_balance_id_seq'::regclass);


--
-- TOC entry 5272 (class 2604 OID 175497)
-- Name: leave_requests request_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.leave_requests ALTER COLUMN request_id SET DEFAULT nextval('public.leave_requests_request_id_seq'::regclass);


--
-- TOC entry 5274 (class 2604 OID 175498)
-- Name: meetings meeting_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.meetings ALTER COLUMN meeting_id SET DEFAULT nextval('public.meetings_meeting_id_seq'::regclass);


--
-- TOC entry 5276 (class 2604 OID 175499)
-- Name: messages message_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.messages ALTER COLUMN message_id SET DEFAULT nextval('public.messages_message_id_seq'::regclass);


--
-- TOC entry 5279 (class 2604 OID 175502)
-- Name: payroll payroll_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.payroll ALTER COLUMN payroll_id SET DEFAULT nextval('public.payroll_payroll_id_seq'::regclass);


--
-- TOC entry 5284 (class 2604 OID 175504)
-- Name: performance_reviews review_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.performance_reviews ALTER COLUMN review_id SET DEFAULT nextval('public.performance_reviews_review_id_seq'::regclass);


--
-- TOC entry 5286 (class 2604 OID 175506)
-- Name: projects project_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.projects ALTER COLUMN project_id SET DEFAULT nextval('public.projects_project_id_seq'::regclass);


--
-- TOC entry 5288 (class 2604 OID 175510)
-- Name: roles role_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.roles ALTER COLUMN role_id SET DEFAULT nextval('public.roles_id_seq'::regclass);


--
-- TOC entry 5289 (class 2604 OID 175511)
-- Name: route_actions id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.route_actions ALTER COLUMN id SET DEFAULT nextval('public.route_actions_id_seq'::regclass);


--
-- TOC entry 5290 (class 2604 OID 175512)
-- Name: routes id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.routes ALTER COLUMN id SET DEFAULT nextval('public.routes_id_seq'::regclass);


--
-- TOC entry 5291 (class 2604 OID 175513)
-- Name: savings_plan_requests request_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.savings_plan_requests ALTER COLUMN request_id SET DEFAULT nextval('public.savings_plan_requests_request_id_seq'::regclass);


--
-- TOC entry 5294 (class 2604 OID 175514)
-- Name: savings_plans plan_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.savings_plans ALTER COLUMN plan_id SET DEFAULT nextval('public.savings_plans_plan_id_seq'::regclass);


--
-- TOC entry 5296 (class 2604 OID 175515)
-- Name: shifts shift_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.shifts ALTER COLUMN shift_id SET DEFAULT nextval('public.shifts_new_shift_id_seq'::regclass);


--
-- TOC entry 5297 (class 2604 OID 175516)
-- Name: skill_assessments assessment_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.skill_assessments ALTER COLUMN assessment_id SET DEFAULT nextval('public.skill_assessments_assessment_id_seq'::regclass);


--
-- TOC entry 5300 (class 2604 OID 175517)
-- Name: skill_development skill_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.skill_development ALTER COLUMN skill_id SET DEFAULT nextval('public.skill_development_skill_id_seq'::regclass);


--
-- TOC entry 5302 (class 2604 OID 175518)
-- Name: super_admins super_admin_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.super_admins ALTER COLUMN super_admin_id SET DEFAULT nextval('public.super_admins_super_admin_id_seq'::regclass);


--
-- TOC entry 5306 (class 2604 OID 175519)
-- Name: survey_answer_options option_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.survey_answer_options ALTER COLUMN option_id SET DEFAULT nextval('public.survey_answer_options_option_id_seq'::regclass);


--
-- TOC entry 5307 (class 2604 OID 175520)
-- Name: survey_assignments assignment_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.survey_assignments ALTER COLUMN assignment_id SET DEFAULT nextval('public.survey_assignments_assignment_id_seq'::regclass);


--
-- TOC entry 5309 (class 2604 OID 175521)
-- Name: survey_question_options option_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.survey_question_options ALTER COLUMN option_id SET DEFAULT nextval('public.survey_question_options_option_id_seq'::regclass);


--
-- TOC entry 5311 (class 2604 OID 175522)
-- Name: survey_questions question_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.survey_questions ALTER COLUMN question_id SET DEFAULT nextval('public.survey_questions_question_id_seq'::regclass);


--
-- TOC entry 5312 (class 2604 OID 175523)
-- Name: survey_responses response_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.survey_responses ALTER COLUMN response_id SET DEFAULT nextval('public.survey_responses_response_id_seq'::regclass);


--
-- TOC entry 5314 (class 2604 OID 175524)
-- Name: surveys survey_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.surveys ALTER COLUMN survey_id SET DEFAULT nextval('public.surveys_survey_id_seq'::regclass);


--
-- TOC entry 5317 (class 2604 OID 175525)
-- Name: task_parts part_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.task_parts ALTER COLUMN part_id SET DEFAULT nextval('public.task_parts_part_id_seq'::regclass);


--
-- TOC entry 5319 (class 2604 OID 175526)
-- Name: tasks task_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.tasks ALTER COLUMN task_id SET DEFAULT nextval('public.tasks_task_id_seq'::regclass);


--
-- TOC entry 5323 (class 2604 OID 175527)
-- Name: tax_documents document_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.tax_documents ALTER COLUMN document_id SET DEFAULT nextval('public.tax_documents_document_id_seq'::regclass);


--
-- TOC entry 5325 (class 2604 OID 175528)
-- Name: tax_records record_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.tax_records ALTER COLUMN record_id SET DEFAULT nextval('public.tax_records_record_id_seq'::regclass);


--
-- TOC entry 5327 (class 2604 OID 175529)
-- Name: team_members id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.team_members ALTER COLUMN id SET DEFAULT nextval('public.team_members_id_seq'::regclass);


--
-- TOC entry 5330 (class 2604 OID 175530)
-- Name: teams team_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.teams ALTER COLUMN team_id SET DEFAULT nextval('public.teams_team_id_seq'::regclass);


--
-- TOC entry 5331 (class 2604 OID 175531)
-- Name: ticket_responses response_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.ticket_responses ALTER COLUMN response_id SET DEFAULT nextval('public.ticket_responses_response_id_seq'::regclass);


--
-- TOC entry 5333 (class 2604 OID 175532)
-- Name: tickets ticket_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.tickets ALTER COLUMN ticket_id SET DEFAULT nextval('public.tickets_ticket_id_seq'::regclass);


--
-- TOC entry 5338 (class 2604 OID 175533)
-- Name: timesheets timesheet_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.timesheets ALTER COLUMN timesheet_id SET DEFAULT nextval('public.timesheets_timesheet_id_seq'::regclass);


--
-- TOC entry 5343 (class 2604 OID 175534)
-- Name: training_certificates certificate_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.training_certificates ALTER COLUMN certificate_id SET DEFAULT nextval('public.training_certificates_certificate_id_seq'::regclass);


--
-- TOC entry 5346 (class 2604 OID 175535)
-- Name: training_modules module_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.training_modules ALTER COLUMN module_id SET DEFAULT nextval('public.training_modules_module_id_seq'::regclass);


--
-- TOC entry 5348 (class 2604 OID 175537)
-- Name: travel_requests request_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.travel_requests ALTER COLUMN request_id SET DEFAULT nextval('public.travel_requests_request_id_seq'::regclass);


--
-- TOC entry 5351 (class 2604 OID 175538)
-- Name: two_factor_verifications verification_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.two_factor_verifications ALTER COLUMN verification_id SET DEFAULT nextval('public.two_factor_verifications_verification_id_seq'::regclass);


--
-- TOC entry 5353 (class 2604 OID 175539)
-- Name: workflows workflow_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.workflows ALTER COLUMN workflow_id SET DEFAULT nextval('public.workflows_workflow_id_seq'::regclass);


--
-- TOC entry 6115 (class 0 OID 0)
-- Dependencies: 218
-- Name: action_plans_action_plan_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.action_plans_action_plan_id_seq', 59, true);


--
-- TOC entry 6116 (class 0 OID 0)
-- Dependencies: 220
-- Name: actions_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.actions_id_seq', 1047, true);


--
-- TOC entry 6117 (class 0 OID 0)
-- Dependencies: 222
-- Name: admin_access_requests_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.admin_access_requests_id_seq', 19, true);


--
-- TOC entry 6118 (class 0 OID 0)
-- Dependencies: 224
-- Name: admin_route_actions_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.admin_route_actions_id_seq', 137, true);


--
-- TOC entry 6119 (class 0 OID 0)
-- Dependencies: 225
-- Name: admins_admin_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.admins_admin_id_seq', 21, true);


--
-- TOC entry 6120 (class 0 OID 0)
-- Dependencies: 228
-- Name: alert_reads_alert_read_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.alert_reads_alert_read_id_seq', 5, true);


--
-- TOC entry 6121 (class 0 OID 0)
-- Dependencies: 230
-- Name: alerts_alert_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.alerts_alert_id_seq', 279, true);


--
-- TOC entry 6122 (class 0 OID 0)
-- Dependencies: 232
-- Name: announcement_reads_read_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.announcement_reads_read_id_seq', 9, true);


--
-- TOC entry 6123 (class 0 OID 0)
-- Dependencies: 234
-- Name: announcements_announcement_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.announcements_announcement_id_seq', 262, true);


--
-- TOC entry 6124 (class 0 OID 0)
-- Dependencies: 236
-- Name: assessment_answers_answer_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.assessment_answers_answer_id_seq', 27, true);


--
-- TOC entry 6125 (class 0 OID 0)
-- Dependencies: 238
-- Name: assessment_options_option_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.assessment_options_option_id_seq', 272, true);


--
-- TOC entry 6126 (class 0 OID 0)
-- Dependencies: 240
-- Name: assessment_questions_question_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.assessment_questions_question_id_seq', 134, true);


--
-- TOC entry 6127 (class 0 OID 0)
-- Dependencies: 242
-- Name: attendance_logs_log_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.attendance_logs_log_id_seq', 149, true);


--
-- TOC entry 6128 (class 0 OID 0)
-- Dependencies: 244
-- Name: audit_trail_audit_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.audit_trail_audit_id_seq', 12764, true);


--
-- TOC entry 6129 (class 0 OID 0)
-- Dependencies: 382
-- Name: audit_trail_employee_audit_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.audit_trail_employee_audit_id_seq', 1522, true);


--
-- TOC entry 6130 (class 0 OID 0)
-- Dependencies: 246
-- Name: badge_assignments_assignment_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.badge_assignments_assignment_id_seq', 20, true);


--
-- TOC entry 6131 (class 0 OID 0)
-- Dependencies: 248
-- Name: badges_badge_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.badges_badge_id_seq', 15, true);


--
-- TOC entry 6132 (class 0 OID 0)
-- Dependencies: 250
-- Name: bank_details_bank_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.bank_details_bank_id_seq', 4, true);


--
-- TOC entry 6133 (class 0 OID 0)
-- Dependencies: 253
-- Name: bonuses_incentives_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.bonuses_incentives_id_seq', 15, true);


--
-- TOC entry 6134 (class 0 OID 0)
-- Dependencies: 255
-- Name: contact_replies_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.contact_replies_id_seq', 19, true);


--
-- TOC entry 6135 (class 0 OID 0)
-- Dependencies: 257
-- Name: contact_requests_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.contact_requests_id_seq', 6, true);


--
-- TOC entry 6136 (class 0 OID 0)
-- Dependencies: 259
-- Name: devices_device_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.devices_device_id_seq', 324, true);


--
-- TOC entry 6137 (class 0 OID 0)
-- Dependencies: 261
-- Name: document_categories_category_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.document_categories_category_id_seq', 28, true);


--
-- TOC entry 6138 (class 0 OID 0)
-- Dependencies: 263
-- Name: document_history_history_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.document_history_history_id_seq', 63, true);


--
-- TOC entry 6139 (class 0 OID 0)
-- Dependencies: 265
-- Name: documents_document_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.documents_document_id_seq', 67, true);


--
-- TOC entry 6140 (class 0 OID 0)
-- Dependencies: 267
-- Name: employee_breaks_break_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.employee_breaks_break_id_seq', 4, true);


--
-- TOC entry 6141 (class 0 OID 0)
-- Dependencies: 269
-- Name: employee_recognition_recognition_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.employee_recognition_recognition_id_seq', 13, true);


--
-- TOC entry 6142 (class 0 OID 0)
-- Dependencies: 271
-- Name: employee_shifts_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.employee_shifts_id_seq', 60, true);


--
-- TOC entry 6143 (class 0 OID 0)
-- Dependencies: 273
-- Name: employees_employee_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.employees_employee_id_seq', 106, true);


--
-- TOC entry 6144 (class 0 OID 0)
-- Dependencies: 275
-- Name: evaluations_evaluation_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.evaluations_evaluation_id_seq', 110, true);


--
-- TOC entry 6145 (class 0 OID 0)
-- Dependencies: 277
-- Name: event_participants_participant_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.event_participants_participant_id_seq', 95, true);


--
-- TOC entry 6146 (class 0 OID 0)
-- Dependencies: 279
-- Name: events_event_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.events_event_id_seq', 36, true);


--
-- TOC entry 6147 (class 0 OID 0)
-- Dependencies: 281
-- Name: expense_claims_claim_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.expense_claims_claim_id_seq', 30, true);


--
-- TOC entry 6148 (class 0 OID 0)
-- Dependencies: 282
-- Name: feedbac_id_sequence; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.feedbac_id_sequence', 35, true);


--
-- TOC entry 6149 (class 0 OID 0)
-- Dependencies: 284
-- Name: feedback_requests_request_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.feedback_requests_request_id_seq', 134, true);


--
-- TOC entry 6150 (class 0 OID 0)
-- Dependencies: 286
-- Name: feedback_responses_response_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.feedback_responses_response_id_seq', 18, true);


--
-- TOC entry 6151 (class 0 OID 0)
-- Dependencies: 291
-- Name: goal_progress_notes_note_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.goal_progress_notes_note_id_seq', 62, true);


--
-- TOC entry 6152 (class 0 OID 0)
-- Dependencies: 287
-- Name: goal_progress_progress_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.goal_progress_progress_id_seq', 194, true);


--
-- TOC entry 6153 (class 0 OID 0)
-- Dependencies: 294
-- Name: goals_goal_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.goals_goal_id_seq', 69, true);


--
-- TOC entry 6154 (class 0 OID 0)
-- Dependencies: 296
-- Name: health_wellness_resources_resource_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.health_wellness_resources_resource_id_seq', 12, true);


--
-- TOC entry 6155 (class 0 OID 0)
-- Dependencies: 298
-- Name: holiday_assignments_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.holiday_assignments_id_seq', 114, true);


--
-- TOC entry 6156 (class 0 OID 0)
-- Dependencies: 299
-- Name: holiday_assignments_id_seq1; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.holiday_assignments_id_seq1', 21, true);


--
-- TOC entry 6157 (class 0 OID 0)
-- Dependencies: 301
-- Name: holidays_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.holidays_id_seq', 30, true);


--
-- TOC entry 6158 (class 0 OID 0)
-- Dependencies: 384
-- Name: incident_logs_employee_incident_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.incident_logs_employee_incident_id_seq', 47, true);


--
-- TOC entry 6159 (class 0 OID 0)
-- Dependencies: 303
-- Name: incident_logs_incident_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.incident_logs_incident_id_seq', 86, true);


--
-- TOC entry 6160 (class 0 OID 0)
-- Dependencies: 305
-- Name: learning_resources_resource_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.learning_resources_resource_id_seq', 12, true);


--
-- TOC entry 6161 (class 0 OID 0)
-- Dependencies: 307
-- Name: leave_balances_balance_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.leave_balances_balance_id_seq', 6, true);


--
-- TOC entry 6162 (class 0 OID 0)
-- Dependencies: 309
-- Name: leave_requests_request_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.leave_requests_request_id_seq', 29, true);


--
-- TOC entry 6163 (class 0 OID 0)
-- Dependencies: 311
-- Name: meetings_meeting_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.meetings_meeting_id_seq', 143, true);


--
-- TOC entry 6164 (class 0 OID 0)
-- Dependencies: 313
-- Name: messages_message_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.messages_message_id_seq', 120, true);


--
-- TOC entry 6165 (class 0 OID 0)
-- Dependencies: 315
-- Name: payroll_payroll_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.payroll_payroll_id_seq', 31, true);


--
-- TOC entry 6166 (class 0 OID 0)
-- Dependencies: 317
-- Name: performance_reviews_review_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.performance_reviews_review_id_seq', 16, true);


--
-- TOC entry 6167 (class 0 OID 0)
-- Dependencies: 318
-- Name: progress_progress_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.progress_progress_id_seq', 38, true);


--
-- TOC entry 6168 (class 0 OID 0)
-- Dependencies: 319
-- Name: progress_progress_id_seq1; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.progress_progress_id_seq1', 73, true);


--
-- TOC entry 6169 (class 0 OID 0)
-- Dependencies: 321
-- Name: projects_project_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.projects_project_id_seq', 18, true);


--
-- TOC entry 6170 (class 0 OID 0)
-- Dependencies: 323
-- Name: roles_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.roles_id_seq', 4, true);


--
-- TOC entry 6171 (class 0 OID 0)
-- Dependencies: 325
-- Name: route_actions_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.route_actions_id_seq', 1098, true);


--
-- TOC entry 6172 (class 0 OID 0)
-- Dependencies: 327
-- Name: routes_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.routes_id_seq', 22, true);


--
-- TOC entry 6173 (class 0 OID 0)
-- Dependencies: 329
-- Name: savings_plan_requests_request_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.savings_plan_requests_request_id_seq', 25, true);


--
-- TOC entry 6174 (class 0 OID 0)
-- Dependencies: 331
-- Name: savings_plans_plan_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.savings_plans_plan_id_seq', 18, true);


--
-- TOC entry 6175 (class 0 OID 0)
-- Dependencies: 332
-- Name: shift_request_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.shift_request_id_seq', 7, true);


--
-- TOC entry 6176 (class 0 OID 0)
-- Dependencies: 335
-- Name: shifts_new_shift_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.shifts_new_shift_id_seq', 22, true);


--
-- TOC entry 6177 (class 0 OID 0)
-- Dependencies: 337
-- Name: skill_assessments_assessment_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.skill_assessments_assessment_id_seq', 68, true);


--
-- TOC entry 6178 (class 0 OID 0)
-- Dependencies: 339
-- Name: skill_development_skill_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.skill_development_skill_id_seq', 1, false);


--
-- TOC entry 6179 (class 0 OID 0)
-- Dependencies: 341
-- Name: super_admins_super_admin_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.super_admins_super_admin_id_seq', 2, true);


--
-- TOC entry 6180 (class 0 OID 0)
-- Dependencies: 343
-- Name: survey_answer_options_option_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.survey_answer_options_option_id_seq', 12, true);


--
-- TOC entry 6181 (class 0 OID 0)
-- Dependencies: 345
-- Name: survey_assignments_assignment_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.survey_assignments_assignment_id_seq', 65, true);


--
-- TOC entry 6182 (class 0 OID 0)
-- Dependencies: 347
-- Name: survey_question_options_option_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.survey_question_options_option_id_seq', 97, true);


--
-- TOC entry 6183 (class 0 OID 0)
-- Dependencies: 349
-- Name: survey_questions_question_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.survey_questions_question_id_seq', 112, true);


--
-- TOC entry 6184 (class 0 OID 0)
-- Dependencies: 351
-- Name: survey_responses_response_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.survey_responses_response_id_seq', 48, true);


--
-- TOC entry 6185 (class 0 OID 0)
-- Dependencies: 353
-- Name: surveys_survey_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.surveys_survey_id_seq', 63, true);


--
-- TOC entry 6186 (class 0 OID 0)
-- Dependencies: 355
-- Name: task_parts_part_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.task_parts_part_id_seq', 142, true);


--
-- TOC entry 6187 (class 0 OID 0)
-- Dependencies: 357
-- Name: tasks_task_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.tasks_task_id_seq', 93, true);


--
-- TOC entry 6188 (class 0 OID 0)
-- Dependencies: 359
-- Name: tax_documents_document_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.tax_documents_document_id_seq', 50, true);


--
-- TOC entry 6189 (class 0 OID 0)
-- Dependencies: 361
-- Name: tax_records_record_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.tax_records_record_id_seq', 36, true);


--
-- TOC entry 6190 (class 0 OID 0)
-- Dependencies: 363
-- Name: team_members_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.team_members_id_seq', 81, true);


--
-- TOC entry 6191 (class 0 OID 0)
-- Dependencies: 365
-- Name: teams_team_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.teams_team_id_seq', 51, true);


--
-- TOC entry 6192 (class 0 OID 0)
-- Dependencies: 367
-- Name: ticket_responses_response_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.ticket_responses_response_id_seq', 22, true);


--
-- TOC entry 6193 (class 0 OID 0)
-- Dependencies: 369
-- Name: tickets_ticket_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.tickets_ticket_id_seq', 24, true);


--
-- TOC entry 6194 (class 0 OID 0)
-- Dependencies: 371
-- Name: timesheets_timesheet_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.timesheets_timesheet_id_seq', 21, true);


--
-- TOC entry 6195 (class 0 OID 0)
-- Dependencies: 373
-- Name: training_certificates_certificate_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.training_certificates_certificate_id_seq', 28, true);


--
-- TOC entry 6196 (class 0 OID 0)
-- Dependencies: 375
-- Name: training_modules_module_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.training_modules_module_id_seq', 31, true);


--
-- TOC entry 6197 (class 0 OID 0)
-- Dependencies: 377
-- Name: travel_requests_request_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.travel_requests_request_id_seq', 13, true);


--
-- TOC entry 6198 (class 0 OID 0)
-- Dependencies: 379
-- Name: two_factor_verifications_verification_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.two_factor_verifications_verification_id_seq', 134, true);


--
-- TOC entry 6199 (class 0 OID 0)
-- Dependencies: 381
-- Name: workflows_workflow_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.workflows_workflow_id_seq', 2, true);


--
-- TOC entry 5385 (class 2606 OID 175550)
-- Name: goal_action_plans action_plans_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.goal_action_plans
    ADD CONSTRAINT action_plans_pkey PRIMARY KEY (action_plan_id);


--
-- TOC entry 5389 (class 2606 OID 175552)
-- Name: actions actions_action_name_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.actions
    ADD CONSTRAINT actions_action_name_key UNIQUE (action_name);


--
-- TOC entry 5391 (class 2606 OID 175554)
-- Name: actions actions_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.actions
    ADD CONSTRAINT actions_pkey PRIMARY KEY (id);


--
-- TOC entry 5393 (class 2606 OID 175556)
-- Name: admin_access_requests admin_access_requests_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.admin_access_requests
    ADD CONSTRAINT admin_access_requests_pkey PRIMARY KEY (id);


--
-- TOC entry 5395 (class 2606 OID 175558)
-- Name: admin_route_actions admin_route_actions_admin_id_route_id_action_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.admin_route_actions
    ADD CONSTRAINT admin_route_actions_admin_id_route_id_action_id_key UNIQUE (admin_id, route_id, action_id);


--
-- TOC entry 5397 (class 2606 OID 175560)
-- Name: admin_route_actions admin_route_actions_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.admin_route_actions
    ADD CONSTRAINT admin_route_actions_pkey PRIMARY KEY (id);


--
-- TOC entry 5399 (class 2606 OID 175566)
-- Name: admins admins_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.admins
    ADD CONSTRAINT admins_pkey PRIMARY KEY (admin_id);


--
-- TOC entry 5401 (class 2606 OID 175568)
-- Name: alerts alerts_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.alerts
    ADD CONSTRAINT alerts_pkey PRIMARY KEY (alert_id);


--
-- TOC entry 5403 (class 2606 OID 175570)
-- Name: announcement_reads announcement_reads_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.announcement_reads
    ADD CONSTRAINT announcement_reads_pkey PRIMARY KEY (read_id);


--
-- TOC entry 5405 (class 2606 OID 175572)
-- Name: announcements announcements_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.announcements
    ADD CONSTRAINT announcements_pkey PRIMARY KEY (announcement_id);


--
-- TOC entry 5407 (class 2606 OID 175576)
-- Name: assessment_answers assessment_answers_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.assessment_answers
    ADD CONSTRAINT assessment_answers_pkey PRIMARY KEY (answer_id);


--
-- TOC entry 5409 (class 2606 OID 175578)
-- Name: assessment_options assessment_options_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.assessment_options
    ADD CONSTRAINT assessment_options_pkey PRIMARY KEY (option_id);


--
-- TOC entry 5411 (class 2606 OID 175580)
-- Name: assessment_questions assessment_questions_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.assessment_questions
    ADD CONSTRAINT assessment_questions_pkey PRIMARY KEY (question_id);


--
-- TOC entry 5413 (class 2606 OID 175582)
-- Name: attendance_logs attendance_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.attendance_logs
    ADD CONSTRAINT attendance_logs_pkey PRIMARY KEY (log_id);


--
-- TOC entry 5580 (class 2606 OID 176612)
-- Name: audit_trail_employee audit_trail_employee_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.audit_trail_employee
    ADD CONSTRAINT audit_trail_employee_pkey PRIMARY KEY (audit_id);


--
-- TOC entry 5415 (class 2606 OID 175584)
-- Name: audit_trail_admin audit_trail_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.audit_trail_admin
    ADD CONSTRAINT audit_trail_pkey PRIMARY KEY (audit_id);


--
-- TOC entry 5417 (class 2606 OID 175586)
-- Name: badge_assignments badge_assignments_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.badge_assignments
    ADD CONSTRAINT badge_assignments_pkey PRIMARY KEY (assignment_id);


--
-- TOC entry 5419 (class 2606 OID 175588)
-- Name: badges badges_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.badges
    ADD CONSTRAINT badges_pkey PRIMARY KEY (badge_id);


--
-- TOC entry 5421 (class 2606 OID 175590)
-- Name: bank_details bank_details_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.bank_details
    ADD CONSTRAINT bank_details_pkey PRIMARY KEY (bank_id);


--
-- TOC entry 5423 (class 2606 OID 175592)
-- Name: blacklisted_tokens blacklisted_tokens_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.blacklisted_tokens
    ADD CONSTRAINT blacklisted_tokens_pkey PRIMARY KEY (jti);


--
-- TOC entry 5425 (class 2606 OID 175594)
-- Name: bonuses_incentives bonuses_incentives_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.bonuses_incentives
    ADD CONSTRAINT bonuses_incentives_pkey PRIMARY KEY (id);


--
-- TOC entry 5427 (class 2606 OID 175600)
-- Name: contact_replies contact_replies_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.contact_replies
    ADD CONSTRAINT contact_replies_pkey PRIMARY KEY (id);


--
-- TOC entry 5429 (class 2606 OID 175602)
-- Name: contact_requests contact_requests_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.contact_requests
    ADD CONSTRAINT contact_requests_pkey PRIMARY KEY (id);


--
-- TOC entry 5431 (class 2606 OID 175608)
-- Name: devices devices_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.devices
    ADD CONSTRAINT devices_pkey PRIMARY KEY (device_id);


--
-- TOC entry 5433 (class 2606 OID 175612)
-- Name: document_categories document_categories_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.document_categories
    ADD CONSTRAINT document_categories_pkey PRIMARY KEY (category_id);


--
-- TOC entry 5436 (class 2606 OID 175614)
-- Name: document_history document_history_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.document_history
    ADD CONSTRAINT document_history_pkey PRIMARY KEY (history_id);


--
-- TOC entry 5438 (class 2606 OID 175616)
-- Name: documents documents_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.documents
    ADD CONSTRAINT documents_pkey PRIMARY KEY (document_id);


--
-- TOC entry 5440 (class 2606 OID 175618)
-- Name: employee_breaks employee_breaks_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.employee_breaks
    ADD CONSTRAINT employee_breaks_pkey PRIMARY KEY (break_id);


--
-- TOC entry 5442 (class 2606 OID 175620)
-- Name: employee_recognition employee_recognition_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.employee_recognition
    ADD CONSTRAINT employee_recognition_pkey PRIMARY KEY (recognition_id);


--
-- TOC entry 5444 (class 2606 OID 175622)
-- Name: employee_shifts employee_shifts_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.employee_shifts
    ADD CONSTRAINT employee_shifts_pkey PRIMARY KEY (id);


--
-- TOC entry 5446 (class 2606 OID 175626)
-- Name: employees employees_email_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.employees
    ADD CONSTRAINT employees_email_key UNIQUE (email);


--
-- TOC entry 5448 (class 2606 OID 175628)
-- Name: employees employees_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.employees
    ADD CONSTRAINT employees_pkey PRIMARY KEY (employee_id);


--
-- TOC entry 5452 (class 2606 OID 175630)
-- Name: goal_evaluations evaluations_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.goal_evaluations
    ADD CONSTRAINT evaluations_pkey PRIMARY KEY (evaluation_id);


--
-- TOC entry 5456 (class 2606 OID 175638)
-- Name: event_participants event_participants_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.event_participants
    ADD CONSTRAINT event_participants_pkey PRIMARY KEY (participant_id);


--
-- TOC entry 5464 (class 2606 OID 175640)
-- Name: events events_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.events
    ADD CONSTRAINT events_pkey PRIMARY KEY (event_id);


--
-- TOC entry 5466 (class 2606 OID 175642)
-- Name: expense_claims expense_claims_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.expense_claims
    ADD CONSTRAINT expense_claims_pkey PRIMARY KEY (claim_id);


--
-- TOC entry 5468 (class 2606 OID 175644)
-- Name: feedback_requests feedback_requests_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.feedback_requests
    ADD CONSTRAINT feedback_requests_pkey PRIMARY KEY (request_id);


--
-- TOC entry 5470 (class 2606 OID 175646)
-- Name: feedback_responses feedback_responses_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.feedback_responses
    ADD CONSTRAINT feedback_responses_pkey PRIMARY KEY (response_id);


--
-- TOC entry 5476 (class 2606 OID 175648)
-- Name: goal_progress_notes goal_progress_notes_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.goal_progress_notes
    ADD CONSTRAINT goal_progress_notes_pkey PRIMARY KEY (note_id);


--
-- TOC entry 5480 (class 2606 OID 175650)
-- Name: goals goals_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.goals
    ADD CONSTRAINT goals_pkey PRIMARY KEY (goal_id);


--
-- TOC entry 5482 (class 2606 OID 175652)
-- Name: health_wellness_resources health_wellness_resources_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.health_wellness_resources
    ADD CONSTRAINT health_wellness_resources_pkey PRIMARY KEY (resource_id);


--
-- TOC entry 5484 (class 2606 OID 175654)
-- Name: holiday_assignments holiday_assignments_holiday_id_employee_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.holiday_assignments
    ADD CONSTRAINT holiday_assignments_holiday_id_employee_id_key UNIQUE (holiday_id, employee_id);


--
-- TOC entry 5486 (class 2606 OID 175656)
-- Name: holiday_assignments holiday_assignments_holiday_id_team_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.holiday_assignments
    ADD CONSTRAINT holiday_assignments_holiday_id_team_id_key UNIQUE (holiday_id, team_id);


--
-- TOC entry 5488 (class 2606 OID 175658)
-- Name: holiday_assignments holiday_assignments_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.holiday_assignments
    ADD CONSTRAINT holiday_assignments_pkey PRIMARY KEY (id);


--
-- TOC entry 5490 (class 2606 OID 175660)
-- Name: holidays holidays_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.holidays
    ADD CONSTRAINT holidays_pkey PRIMARY KEY (id);


--
-- TOC entry 5582 (class 2606 OID 176630)
-- Name: incident_logs_employee incident_logs_employee_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.incident_logs_employee
    ADD CONSTRAINT incident_logs_employee_pkey PRIMARY KEY (incident_id);


--
-- TOC entry 5492 (class 2606 OID 175662)
-- Name: incident_logs incident_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.incident_logs
    ADD CONSTRAINT incident_logs_pkey PRIMARY KEY (incident_id);


--
-- TOC entry 5494 (class 2606 OID 175668)
-- Name: learning_resources learning_resources_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.learning_resources
    ADD CONSTRAINT learning_resources_pkey PRIMARY KEY (resource_id);


--
-- TOC entry 5496 (class 2606 OID 175670)
-- Name: leave_balances leave_balances_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.leave_balances
    ADD CONSTRAINT leave_balances_pkey PRIMARY KEY (balance_id);


--
-- TOC entry 5498 (class 2606 OID 175672)
-- Name: leave_requests leave_requests_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.leave_requests
    ADD CONSTRAINT leave_requests_pkey PRIMARY KEY (request_id);


--
-- TOC entry 5500 (class 2606 OID 175674)
-- Name: meetings meetings_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.meetings
    ADD CONSTRAINT meetings_pkey PRIMARY KEY (meeting_id);


--
-- TOC entry 5502 (class 2606 OID 175676)
-- Name: messages messages_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.messages
    ADD CONSTRAINT messages_pkey PRIMARY KEY (message_id);


--
-- TOC entry 5504 (class 2606 OID 175682)
-- Name: payroll payroll_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.payroll
    ADD CONSTRAINT payroll_pkey PRIMARY KEY (payroll_id);


--
-- TOC entry 5506 (class 2606 OID 175688)
-- Name: performance_reviews performance_reviews_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.performance_reviews
    ADD CONSTRAINT performance_reviews_pkey PRIMARY KEY (review_id);


--
-- TOC entry 5474 (class 2606 OID 175690)
-- Name: goal_progress_feedback primary_feedback_id; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.goal_progress_feedback
    ADD CONSTRAINT primary_feedback_id PRIMARY KEY (feedback_id);


--
-- TOC entry 5472 (class 2606 OID 175694)
-- Name: goal_progress progress_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.goal_progress
    ADD CONSTRAINT progress_pkey PRIMARY KEY (progress_id);


--
-- TOC entry 5478 (class 2606 OID 175696)
-- Name: goal_progress_percentage progress_pkey1; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.goal_progress_percentage
    ADD CONSTRAINT progress_pkey1 PRIMARY KEY (progress_percentage_id);


--
-- TOC entry 5508 (class 2606 OID 175698)
-- Name: projects projects_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.projects
    ADD CONSTRAINT projects_pkey PRIMARY KEY (project_id);


--
-- TOC entry 5510 (class 2606 OID 175706)
-- Name: roles roles_name_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.roles
    ADD CONSTRAINT roles_name_key UNIQUE (role_name);


--
-- TOC entry 5512 (class 2606 OID 175708)
-- Name: roles roles_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.roles
    ADD CONSTRAINT roles_pkey PRIMARY KEY (role_id);


--
-- TOC entry 5514 (class 2606 OID 175710)
-- Name: route_actions route_actions_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.route_actions
    ADD CONSTRAINT route_actions_pkey PRIMARY KEY (id);


--
-- TOC entry 5516 (class 2606 OID 175712)
-- Name: route_actions route_actions_route_id_action_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.route_actions
    ADD CONSTRAINT route_actions_route_id_action_id_key UNIQUE (route_id, action_id);


--
-- TOC entry 5518 (class 2606 OID 175714)
-- Name: routes routes_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.routes
    ADD CONSTRAINT routes_pkey PRIMARY KEY (id);


--
-- TOC entry 5520 (class 2606 OID 175716)
-- Name: routes routes_route_name_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.routes
    ADD CONSTRAINT routes_route_name_key UNIQUE (route_name);


--
-- TOC entry 5522 (class 2606 OID 175718)
-- Name: savings_plan_requests savings_plan_requests_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.savings_plan_requests
    ADD CONSTRAINT savings_plan_requests_pkey PRIMARY KEY (request_id);


--
-- TOC entry 5524 (class 2606 OID 175720)
-- Name: savings_plans savings_plans_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.savings_plans
    ADD CONSTRAINT savings_plans_pkey PRIMARY KEY (plan_id);


--
-- TOC entry 5526 (class 2606 OID 175722)
-- Name: shifts shifts_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.shifts
    ADD CONSTRAINT shifts_pkey PRIMARY KEY (shift_id);


--
-- TOC entry 5528 (class 2606 OID 175724)
-- Name: skill_assessments skill_assessments_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.skill_assessments
    ADD CONSTRAINT skill_assessments_pkey PRIMARY KEY (assessment_id);


--
-- TOC entry 5530 (class 2606 OID 175726)
-- Name: skill_development skill_development_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.skill_development
    ADD CONSTRAINT skill_development_pkey PRIMARY KEY (skill_id);


--
-- TOC entry 5532 (class 2606 OID 175728)
-- Name: super_admins super_admins_email_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.super_admins
    ADD CONSTRAINT super_admins_email_key UNIQUE (email);


--
-- TOC entry 5534 (class 2606 OID 175730)
-- Name: super_admins super_admins_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.super_admins
    ADD CONSTRAINT super_admins_pkey PRIMARY KEY (super_admin_id);


--
-- TOC entry 5536 (class 2606 OID 175732)
-- Name: survey_answer_options survey_answer_options_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.survey_answer_options
    ADD CONSTRAINT survey_answer_options_pkey PRIMARY KEY (option_id);


--
-- TOC entry 5538 (class 2606 OID 175734)
-- Name: survey_assignments survey_assignments_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.survey_assignments
    ADD CONSTRAINT survey_assignments_pkey PRIMARY KEY (assignment_id);


--
-- TOC entry 5542 (class 2606 OID 175736)
-- Name: survey_question_options survey_question_options_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.survey_question_options
    ADD CONSTRAINT survey_question_options_pkey PRIMARY KEY (option_id);


--
-- TOC entry 5544 (class 2606 OID 175738)
-- Name: survey_questions survey_questions_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.survey_questions
    ADD CONSTRAINT survey_questions_pkey PRIMARY KEY (question_id);


--
-- TOC entry 5546 (class 2606 OID 175740)
-- Name: survey_responses survey_responses_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.survey_responses
    ADD CONSTRAINT survey_responses_pkey PRIMARY KEY (response_id);


--
-- TOC entry 5548 (class 2606 OID 175742)
-- Name: surveys surveys_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.surveys
    ADD CONSTRAINT surveys_pkey PRIMARY KEY (survey_id);


--
-- TOC entry 5550 (class 2606 OID 175744)
-- Name: task_parts task_parts_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.task_parts
    ADD CONSTRAINT task_parts_pkey PRIMARY KEY (part_id);


--
-- TOC entry 5552 (class 2606 OID 175746)
-- Name: tasks tasks_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.tasks
    ADD CONSTRAINT tasks_pkey PRIMARY KEY (task_id);


--
-- TOC entry 5554 (class 2606 OID 175748)
-- Name: tax_documents tax_documents_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.tax_documents
    ADD CONSTRAINT tax_documents_pkey PRIMARY KEY (document_id);


--
-- TOC entry 5556 (class 2606 OID 175750)
-- Name: tax_records tax_records_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.tax_records
    ADD CONSTRAINT tax_records_pkey PRIMARY KEY (record_id);


--
-- TOC entry 5558 (class 2606 OID 175752)
-- Name: team_members team_members_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.team_members
    ADD CONSTRAINT team_members_pkey PRIMARY KEY (id);


--
-- TOC entry 5560 (class 2606 OID 175754)
-- Name: teams teams_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.teams
    ADD CONSTRAINT teams_pkey PRIMARY KEY (team_id);


--
-- TOC entry 5562 (class 2606 OID 175756)
-- Name: teams teams_team_name_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.teams
    ADD CONSTRAINT teams_team_name_key UNIQUE (team_name);


--
-- TOC entry 5564 (class 2606 OID 175758)
-- Name: ticket_responses ticket_responses_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.ticket_responses
    ADD CONSTRAINT ticket_responses_pkey PRIMARY KEY (response_id);


--
-- TOC entry 5566 (class 2606 OID 175760)
-- Name: tickets tickets_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.tickets
    ADD CONSTRAINT tickets_pkey PRIMARY KEY (ticket_id);


--
-- TOC entry 5568 (class 2606 OID 175762)
-- Name: timesheets timesheets_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.timesheets
    ADD CONSTRAINT timesheets_pkey PRIMARY KEY (timesheet_id);


--
-- TOC entry 5570 (class 2606 OID 175764)
-- Name: training_certificates training_certificates_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.training_certificates
    ADD CONSTRAINT training_certificates_pkey PRIMARY KEY (certificate_id);


--
-- TOC entry 5572 (class 2606 OID 175766)
-- Name: training_modules training_modules_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.training_modules
    ADD CONSTRAINT training_modules_pkey PRIMARY KEY (module_id);


--
-- TOC entry 5574 (class 2606 OID 175770)
-- Name: travel_requests travel_requests_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.travel_requests
    ADD CONSTRAINT travel_requests_pkey PRIMARY KEY (request_id);


--
-- TOC entry 5576 (class 2606 OID 175772)
-- Name: two_factor_verifications two_factor_verifications_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.two_factor_verifications
    ADD CONSTRAINT two_factor_verifications_pkey PRIMARY KEY (verification_id);


--
-- TOC entry 5387 (class 2606 OID 175774)
-- Name: goal_action_plans unique_action_plans_goal_id; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.goal_action_plans
    ADD CONSTRAINT unique_action_plans_goal_id UNIQUE (goal_id);


--
-- TOC entry 5458 (class 2606 OID 175776)
-- Name: event_participants unique_event_admin; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.event_participants
    ADD CONSTRAINT unique_event_admin UNIQUE (event_id, admin_id);


--
-- TOC entry 5460 (class 2606 OID 175778)
-- Name: event_participants unique_event_employee; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.event_participants
    ADD CONSTRAINT unique_event_employee UNIQUE (event_id, employee_id);


--
-- TOC entry 5462 (class 2606 OID 175780)
-- Name: event_participants unique_event_team; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.event_participants
    ADD CONSTRAINT unique_event_team UNIQUE (event_id, team_id);


--
-- TOC entry 5454 (class 2606 OID 175782)
-- Name: goal_evaluations unique_goal_id; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.goal_evaluations
    ADD CONSTRAINT unique_goal_id UNIQUE (goal_id);


--
-- TOC entry 5450 (class 2606 OID 175784)
-- Name: employees unique_phone_number; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.employees
    ADD CONSTRAINT unique_phone_number UNIQUE (phone_number);


--
-- TOC entry 5540 (class 2606 OID 175786)
-- Name: survey_assignments unique_survey_assignment; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.survey_assignments
    ADD CONSTRAINT unique_survey_assignment UNIQUE (survey_id, employee_id, team_id);


--
-- TOC entry 5578 (class 2606 OID 175788)
-- Name: workflows workflows_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.workflows
    ADD CONSTRAINT workflows_pkey PRIMARY KEY (workflow_id);


--
-- TOC entry 5434 (class 1259 OID 175789)
-- Name: unique_category_name; Type: INDEX; Schema: public; Owner: postgres
--

CREATE UNIQUE INDEX unique_category_name ON public.document_categories USING btree (lower(name));


--
-- TOC entry 5716 (class 2620 OID 175790)
-- Name: goal_progress update_goal_progress_updated_at; Type: TRIGGER; Schema: public; Owner: postgres
--

CREATE TRIGGER update_goal_progress_updated_at BEFORE UPDATE ON public.goal_progress FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- TOC entry 5583 (class 2606 OID 175791)
-- Name: goal_action_plans action_plans_goal_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.goal_action_plans
    ADD CONSTRAINT action_plans_goal_id_fkey FOREIGN KEY (goal_id) REFERENCES public.goals(goal_id);


--
-- TOC entry 5584 (class 2606 OID 175796)
-- Name: admin_access_requests admin_access_requests_action_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.admin_access_requests
    ADD CONSTRAINT admin_access_requests_action_id_fkey FOREIGN KEY (action_id) REFERENCES public.actions(id) ON DELETE CASCADE;


--
-- TOC entry 5585 (class 2606 OID 175801)
-- Name: admin_access_requests admin_access_requests_admin_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.admin_access_requests
    ADD CONSTRAINT admin_access_requests_admin_id_fkey FOREIGN KEY (admin_id) REFERENCES public.admins(admin_id) ON DELETE CASCADE;


--
-- TOC entry 5586 (class 2606 OID 175806)
-- Name: admin_access_requests admin_access_requests_route_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.admin_access_requests
    ADD CONSTRAINT admin_access_requests_route_id_fkey FOREIGN KEY (route_id) REFERENCES public.routes(id) ON DELETE CASCADE;


--
-- TOC entry 5587 (class 2606 OID 175811)
-- Name: admin_access_requests admin_access_requests_super_admin_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.admin_access_requests
    ADD CONSTRAINT admin_access_requests_super_admin_id_fkey FOREIGN KEY (super_admin_id) REFERENCES public.super_admins(super_admin_id) ON DELETE CASCADE;


--
-- TOC entry 5588 (class 2606 OID 175816)
-- Name: admin_route_actions admin_route_actions_action_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.admin_route_actions
    ADD CONSTRAINT admin_route_actions_action_id_fkey FOREIGN KEY (action_id) REFERENCES public.actions(id) ON DELETE CASCADE;


--
-- TOC entry 5589 (class 2606 OID 175821)
-- Name: admin_route_actions admin_route_actions_admin_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.admin_route_actions
    ADD CONSTRAINT admin_route_actions_admin_id_fkey FOREIGN KEY (admin_id) REFERENCES public.admins(admin_id) ON DELETE CASCADE;


--
-- TOC entry 5590 (class 2606 OID 175826)
-- Name: admin_route_actions admin_route_actions_route_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.admin_route_actions
    ADD CONSTRAINT admin_route_actions_route_id_fkey FOREIGN KEY (route_id) REFERENCES public.routes(id) ON DELETE CASCADE;


--
-- TOC entry 5591 (class 2606 OID 175831)
-- Name: admins admins_role_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.admins
    ADD CONSTRAINT admins_role_id_fkey FOREIGN KEY (role_id) REFERENCES public.roles(role_id) ON DELETE CASCADE;


--
-- TOC entry 5597 (class 2606 OID 175836)
-- Name: announcement_reads announcement_reads_announcement_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.announcement_reads
    ADD CONSTRAINT announcement_reads_announcement_id_fkey FOREIGN KEY (announcement_id) REFERENCES public.announcements(announcement_id) ON DELETE CASCADE;


--
-- TOC entry 5598 (class 2606 OID 175841)
-- Name: announcement_reads announcement_reads_employee_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.announcement_reads
    ADD CONSTRAINT announcement_reads_employee_id_fkey FOREIGN KEY (employee_id) REFERENCES public.employees(employee_id) ON DELETE CASCADE;


--
-- TOC entry 5604 (class 2606 OID 175856)
-- Name: assessment_answers assessment_answers_assessment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.assessment_answers
    ADD CONSTRAINT assessment_answers_assessment_id_fkey FOREIGN KEY (assessment_id) REFERENCES public.skill_assessments(assessment_id);


--
-- TOC entry 5605 (class 2606 OID 175861)
-- Name: assessment_answers assessment_answers_correct_option_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.assessment_answers
    ADD CONSTRAINT assessment_answers_correct_option_id_fkey FOREIGN KEY (correct_option_id) REFERENCES public.assessment_options(option_id);


--
-- TOC entry 5606 (class 2606 OID 175866)
-- Name: assessment_answers assessment_answers_employee_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.assessment_answers
    ADD CONSTRAINT assessment_answers_employee_id_fkey FOREIGN KEY (employee_id) REFERENCES public.employees(employee_id);


--
-- TOC entry 5607 (class 2606 OID 175871)
-- Name: assessment_answers assessment_answers_question_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.assessment_answers
    ADD CONSTRAINT assessment_answers_question_id_fkey FOREIGN KEY (question_id) REFERENCES public.assessment_questions(question_id);


--
-- TOC entry 5608 (class 2606 OID 175876)
-- Name: assessment_answers assessment_answers_selected_option_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.assessment_answers
    ADD CONSTRAINT assessment_answers_selected_option_id_fkey FOREIGN KEY (selected_option_id) REFERENCES public.assessment_options(option_id);


--
-- TOC entry 5609 (class 2606 OID 175881)
-- Name: assessment_options assessment_options_question_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.assessment_options
    ADD CONSTRAINT assessment_options_question_id_fkey FOREIGN KEY (question_id) REFERENCES public.assessment_questions(question_id) ON DELETE CASCADE;


--
-- TOC entry 5612 (class 2606 OID 175886)
-- Name: audit_trail_admin audit_trail_admin_role_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.audit_trail_admin
    ADD CONSTRAINT audit_trail_admin_role_id_fkey FOREIGN KEY (role_id) REFERENCES public.roles(role_id) ON DELETE CASCADE;


--
-- TOC entry 5714 (class 2606 OID 176613)
-- Name: audit_trail_employee audit_trail_employee_employee_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.audit_trail_employee
    ADD CONSTRAINT audit_trail_employee_employee_id_fkey FOREIGN KEY (employee_id) REFERENCES public.employees(employee_id) ON DELETE CASCADE;


--
-- TOC entry 5613 (class 2606 OID 175891)
-- Name: badge_assignments badge_assignments_badge_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.badge_assignments
    ADD CONSTRAINT badge_assignments_badge_id_fkey FOREIGN KEY (badge_id) REFERENCES public.badges(badge_id);


--
-- TOC entry 5614 (class 2606 OID 175896)
-- Name: badge_assignments badge_assignments_employee_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.badge_assignments
    ADD CONSTRAINT badge_assignments_employee_id_fkey FOREIGN KEY (employee_id) REFERENCES public.employees(employee_id);


--
-- TOC entry 5615 (class 2606 OID 175901)
-- Name: badge_assignments badge_assignments_team_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.badge_assignments
    ADD CONSTRAINT badge_assignments_team_id_fkey FOREIGN KEY (team_id) REFERENCES public.teams(team_id);


--
-- TOC entry 5616 (class 2606 OID 175906)
-- Name: bank_details bank_details_employee_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.bank_details
    ADD CONSTRAINT bank_details_employee_id_fkey FOREIGN KEY (employee_id) REFERENCES public.employees(employee_id);


--
-- TOC entry 5617 (class 2606 OID 175911)
-- Name: bonuses_incentives bonuses_incentives_employee_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.bonuses_incentives
    ADD CONSTRAINT bonuses_incentives_employee_id_fkey FOREIGN KEY (employee_id) REFERENCES public.employees(employee_id);


--
-- TOC entry 5618 (class 2606 OID 175931)
-- Name: contact_replies contact_replies_contact_request_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.contact_replies
    ADD CONSTRAINT contact_replies_contact_request_id_fkey FOREIGN KEY (contact_request_id) REFERENCES public.contact_requests(id) ON DELETE CASCADE;


--
-- TOC entry 5619 (class 2606 OID 175941)
-- Name: document_history document_history_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.document_history
    ADD CONSTRAINT document_history_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.documents(document_id);


--
-- TOC entry 5622 (class 2606 OID 175946)
-- Name: employee_breaks employee_breaks_employee_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.employee_breaks
    ADD CONSTRAINT employee_breaks_employee_id_fkey FOREIGN KEY (employee_id) REFERENCES public.employees(employee_id) ON DELETE CASCADE;


--
-- TOC entry 5624 (class 2606 OID 175951)
-- Name: employee_recognition employee_recognition_employee_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.employee_recognition
    ADD CONSTRAINT employee_recognition_employee_id_fkey FOREIGN KEY (employee_id) REFERENCES public.employees(employee_id) ON DELETE CASCADE;


--
-- TOC entry 5627 (class 2606 OID 175956)
-- Name: employee_shifts employee_shifts_employee_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.employee_shifts
    ADD CONSTRAINT employee_shifts_employee_id_fkey FOREIGN KEY (employee_id) REFERENCES public.employees(employee_id) ON DELETE CASCADE;


--
-- TOC entry 5633 (class 2606 OID 175971)
-- Name: goal_evaluations evaluations_goal_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.goal_evaluations
    ADD CONSTRAINT evaluations_goal_id_fkey FOREIGN KEY (goal_id) REFERENCES public.goals(goal_id);


--
-- TOC entry 5634 (class 2606 OID 176001)
-- Name: event_participants event_participants_employee_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.event_participants
    ADD CONSTRAINT event_participants_employee_id_fkey FOREIGN KEY (employee_id) REFERENCES public.employees(employee_id) ON DELETE SET NULL;


--
-- TOC entry 5635 (class 2606 OID 176006)
-- Name: event_participants event_participants_event_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.event_participants
    ADD CONSTRAINT event_participants_event_id_fkey FOREIGN KEY (event_id) REFERENCES public.events(event_id) ON DELETE CASCADE;


--
-- TOC entry 5639 (class 2606 OID 176011)
-- Name: expense_claims expense_claims_employee_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.expense_claims
    ADD CONSTRAINT expense_claims_employee_id_fkey FOREIGN KEY (employee_id) REFERENCES public.employees(employee_id);


--
-- TOC entry 5644 (class 2606 OID 176016)
-- Name: feedback_responses feedback_responses_employee_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.feedback_responses
    ADD CONSTRAINT feedback_responses_employee_id_fkey FOREIGN KEY (employee_id) REFERENCES public.employees(employee_id) ON DELETE SET NULL;


--
-- TOC entry 5645 (class 2606 OID 176021)
-- Name: feedback_responses feedback_responses_request_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.feedback_responses
    ADD CONSTRAINT feedback_responses_request_id_fkey FOREIGN KEY (request_id) REFERENCES public.feedback_requests(request_id) ON DELETE CASCADE;


--
-- TOC entry 5640 (class 2606 OID 176026)
-- Name: feedback_requests fk_admin; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.feedback_requests
    ADD CONSTRAINT fk_admin FOREIGN KEY (assigned_by_admins) REFERENCES public.admins(admin_id);


--
-- TOC entry 5691 (class 2606 OID 176031)
-- Name: surveys fk_admin_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.surveys
    ADD CONSTRAINT fk_admin_id FOREIGN KEY (admin_id) REFERENCES public.admins(admin_id);


--
-- TOC entry 5600 (class 2606 OID 176041)
-- Name: announcements fk_admin_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.announcements
    ADD CONSTRAINT fk_admin_id FOREIGN KEY (assigned_by_admin) REFERENCES public.admins(admin_id);


--
-- TOC entry 5666 (class 2606 OID 176046)
-- Name: meetings fk_admin_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.meetings
    ADD CONSTRAINT fk_admin_id FOREIGN KEY (assigned_by_admins) REFERENCES public.admins(admin_id);


--
-- TOC entry 5660 (class 2606 OID 176051)
-- Name: holidays fk_admin_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.holidays
    ADD CONSTRAINT fk_admin_id FOREIGN KEY (assigned_by_admins) REFERENCES public.admins(admin_id);


--
-- TOC entry 5637 (class 2606 OID 176056)
-- Name: events fk_admin_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.events
    ADD CONSTRAINT fk_admin_id FOREIGN KEY (assigned_by_admins) REFERENCES public.admins(admin_id);


--
-- TOC entry 5703 (class 2606 OID 176061)
-- Name: teams fk_admin_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.teams
    ADD CONSTRAINT fk_admin_id FOREIGN KEY (team_lead_admin_id) REFERENCES public.admins(admin_id);


--
-- TOC entry 5700 (class 2606 OID 176066)
-- Name: team_members fk_admin_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.team_members
    ADD CONSTRAINT fk_admin_id FOREIGN KEY (admin_id) REFERENCES public.admins(admin_id);


--
-- TOC entry 5593 (class 2606 OID 176071)
-- Name: alerts fk_admin_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.alerts
    ADD CONSTRAINT fk_admin_id FOREIGN KEY (assigned_by_admin) REFERENCES public.admins(admin_id);


--
-- TOC entry 5592 (class 2606 OID 176076)
-- Name: alert_reads fk_alert_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.alert_reads
    ADD CONSTRAINT fk_alert_id FOREIGN KEY (alert_id) REFERENCES public.alerts(alert_id);


--
-- TOC entry 5629 (class 2606 OID 176081)
-- Name: employees fk_announcement_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.employees
    ADD CONSTRAINT fk_announcement_id FOREIGN KEY (announcement_id) REFERENCES public.announcements(announcement_id);


--
-- TOC entry 5610 (class 2606 OID 176086)
-- Name: assessment_questions fk_assessment_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.assessment_questions
    ADD CONSTRAINT fk_assessment_id FOREIGN KEY (assessment_id) REFERENCES public.skill_assessments(assessment_id) ON DELETE CASCADE;


--
-- TOC entry 5625 (class 2606 OID 176091)
-- Name: employee_recognition fk_awarded_by_admin; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.employee_recognition
    ADD CONSTRAINT fk_awarded_by_admin FOREIGN KEY (awarded_by_admin) REFERENCES public.admins(admin_id);


--
-- TOC entry 5626 (class 2606 OID 176096)
-- Name: employee_recognition fk_awarded_by_super_admin; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.employee_recognition
    ADD CONSTRAINT fk_awarded_by_super_admin FOREIGN KEY (awarded_by_super_admin) REFERENCES public.super_admins(super_admin_id);


--
-- TOC entry 5698 (class 2606 OID 176101)
-- Name: tax_records fk_document_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.tax_records
    ADD CONSTRAINT fk_document_id FOREIGN KEY (document_id) REFERENCES public.tax_documents(document_id);


--
-- TOC entry 5711 (class 2606 OID 176106)
-- Name: travel_requests fk_employee; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.travel_requests
    ADD CONSTRAINT fk_employee FOREIGN KEY (employee_id) REFERENCES public.employees(employee_id) ON DELETE CASCADE;


--
-- TOC entry 5646 (class 2606 OID 176111)
-- Name: goal_progress fk_employee_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.goal_progress
    ADD CONSTRAINT fk_employee_id FOREIGN KEY (employee_id) REFERENCES public.employees(employee_id);


--
-- TOC entry 5651 (class 2606 OID 176116)
-- Name: goal_progress_notes fk_employee_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.goal_progress_notes
    ADD CONSTRAINT fk_employee_id FOREIGN KEY (employee_id) REFERENCES public.employees(employee_id);


--
-- TOC entry 5654 (class 2606 OID 176121)
-- Name: goal_progress_percentage fk_employee_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.goal_progress_percentage
    ADD CONSTRAINT fk_employee_id FOREIGN KEY (employee_id) REFERENCES public.employees(employee_id);


--
-- TOC entry 5601 (class 2606 OID 176126)
-- Name: announcements fk_employee_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.announcements
    ADD CONSTRAINT fk_employee_id FOREIGN KEY (employee_id) REFERENCES public.employees(employee_id);


--
-- TOC entry 5667 (class 2606 OID 176131)
-- Name: meetings fk_employee_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.meetings
    ADD CONSTRAINT fk_employee_id FOREIGN KEY (employee_id) REFERENCES public.employees(employee_id);


--
-- TOC entry 5594 (class 2606 OID 176136)
-- Name: alerts fk_employee_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.alerts
    ADD CONSTRAINT fk_employee_id FOREIGN KEY (employee_id) REFERENCES public.employees(employee_id);


--
-- TOC entry 5641 (class 2606 OID 176141)
-- Name: feedback_requests fk_employee_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.feedback_requests
    ADD CONSTRAINT fk_employee_id FOREIGN KEY (employee_id) REFERENCES public.employees(employee_id);


--
-- TOC entry 5687 (class 2606 OID 176151)
-- Name: survey_responses fk_employee_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.survey_responses
    ADD CONSTRAINT fk_employee_id FOREIGN KEY (employee_id) REFERENCES public.employees(employee_id);


--
-- TOC entry 5704 (class 2606 OID 176156)
-- Name: teams fk_employee_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.teams
    ADD CONSTRAINT fk_employee_id FOREIGN KEY (team_lead_employee_id) REFERENCES public.employees(employee_id);


--
-- TOC entry 5647 (class 2606 OID 176161)
-- Name: goal_progress fk_feedback_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.goal_progress
    ADD CONSTRAINT fk_feedback_id FOREIGN KEY (feedback_id) REFERENCES public.goal_progress_feedback(feedback_id);


--
-- TOC entry 5655 (class 2606 OID 176166)
-- Name: goal_progress_percentage fk_goal_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.goal_progress_percentage
    ADD CONSTRAINT fk_goal_id FOREIGN KEY (goal_id) REFERENCES public.goals(goal_id);


--
-- TOC entry 5648 (class 2606 OID 176171)
-- Name: goal_progress fk_goal_progress_notes; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.goal_progress
    ADD CONSTRAINT fk_goal_progress_notes FOREIGN KEY (note_id) REFERENCES public.goal_progress_notes(note_id) ON DELETE SET NULL;


--
-- TOC entry 5630 (class 2606 OID 176176)
-- Name: employees fk_goals; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.employees
    ADD CONSTRAINT fk_goals FOREIGN KEY (goal_id) REFERENCES public.goals(goal_id) ON DELETE SET NULL;


--
-- TOC entry 5623 (class 2606 OID 176181)
-- Name: employee_breaks fk_log_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.employee_breaks
    ADD CONSTRAINT fk_log_id FOREIGN KEY (log_id) REFERENCES public.attendance_logs(log_id);


--
-- TOC entry 5707 (class 2606 OID 176186)
-- Name: timesheets fk_log_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.timesheets
    ADD CONSTRAINT fk_log_id FOREIGN KEY (log_id) REFERENCES public.attendance_logs(log_id) ON DELETE CASCADE;


--
-- TOC entry 5677 (class 2606 OID 176191)
-- Name: skill_assessments fk_module_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.skill_assessments
    ADD CONSTRAINT fk_module_id FOREIGN KEY (module_id) REFERENCES public.training_modules(module_id);


--
-- TOC entry 5652 (class 2606 OID 176196)
-- Name: goal_progress_notes fk_notes; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.goal_progress_notes
    ADD CONSTRAINT fk_notes FOREIGN KEY (goal_id) REFERENCES public.goals(goal_id) ON DELETE CASCADE;


--
-- TOC entry 5688 (class 2606 OID 176201)
-- Name: survey_responses fk_option_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.survey_responses
    ADD CONSTRAINT fk_option_id FOREIGN KEY (option_id) REFERENCES public.survey_question_options(option_id);


--
-- TOC entry 5631 (class 2606 OID 176206)
-- Name: employees fk_role_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.employees
    ADD CONSTRAINT fk_role_id FOREIGN KEY (role_id) REFERENCES public.roles(role_id);


--
-- TOC entry 5620 (class 2606 OID 176216)
-- Name: documents fk_role_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.documents
    ADD CONSTRAINT fk_role_id FOREIGN KEY (visibility_by_role_id) REFERENCES public.roles(role_id);


--
-- TOC entry 5611 (class 2606 OID 176221)
-- Name: attendance_logs fk_role_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.attendance_logs
    ADD CONSTRAINT fk_role_id FOREIGN KEY (role_id) REFERENCES public.roles(role_id);


--
-- TOC entry 5628 (class 2606 OID 176226)
-- Name: employee_shifts fk_shift_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.employee_shifts
    ADD CONSTRAINT fk_shift_id FOREIGN KEY (shift_id) REFERENCES public.shifts(shift_id);


--
-- TOC entry 5642 (class 2606 OID 176231)
-- Name: feedback_requests fk_super_admin; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.feedback_requests
    ADD CONSTRAINT fk_super_admin FOREIGN KEY (assigned_by_super_admins) REFERENCES public.super_admins(super_admin_id);


--
-- TOC entry 5692 (class 2606 OID 176236)
-- Name: surveys fk_super_admin_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.surveys
    ADD CONSTRAINT fk_super_admin_id FOREIGN KEY (super_admin_id) REFERENCES public.super_admins(super_admin_id);


--
-- TOC entry 5662 (class 2606 OID 176241)
-- Name: incident_logs fk_super_admin_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.incident_logs
    ADD CONSTRAINT fk_super_admin_id FOREIGN KEY (super_admin_id) REFERENCES public.super_admins(super_admin_id);


--
-- TOC entry 5602 (class 2606 OID 176246)
-- Name: announcements fk_super_admin_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.announcements
    ADD CONSTRAINT fk_super_admin_id FOREIGN KEY (assigned_by_super_admin) REFERENCES public.super_admins(super_admin_id);


--
-- TOC entry 5668 (class 2606 OID 176251)
-- Name: meetings fk_super_admin_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.meetings
    ADD CONSTRAINT fk_super_admin_id FOREIGN KEY (assigned_by_super_admins) REFERENCES public.super_admins(super_admin_id);


--
-- TOC entry 5661 (class 2606 OID 176256)
-- Name: holidays fk_super_admin_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.holidays
    ADD CONSTRAINT fk_super_admin_id FOREIGN KEY (assigned_by_super_admins) REFERENCES public.super_admins(super_admin_id);


--
-- TOC entry 5638 (class 2606 OID 176261)
-- Name: events fk_super_admin_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.events
    ADD CONSTRAINT fk_super_admin_id FOREIGN KEY (assigned_by_super_admins) REFERENCES public.super_admins(super_admin_id);


--
-- TOC entry 5595 (class 2606 OID 176266)
-- Name: alerts fk_super_admin_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.alerts
    ADD CONSTRAINT fk_super_admin_id FOREIGN KEY (assigned_by_super_admin) REFERENCES public.super_admins(super_admin_id);


--
-- TOC entry 5649 (class 2606 OID 176271)
-- Name: goal_progress fk_team_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.goal_progress
    ADD CONSTRAINT fk_team_id FOREIGN KEY (team_id) REFERENCES public.teams(team_id);


--
-- TOC entry 5653 (class 2606 OID 176276)
-- Name: goal_progress_notes fk_team_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.goal_progress_notes
    ADD CONSTRAINT fk_team_id FOREIGN KEY (team_id) REFERENCES public.teams(team_id);


--
-- TOC entry 5656 (class 2606 OID 176281)
-- Name: goal_progress_percentage fk_team_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.goal_progress_percentage
    ADD CONSTRAINT fk_team_id FOREIGN KEY (team_id) REFERENCES public.teams(team_id);


--
-- TOC entry 5632 (class 2606 OID 176286)
-- Name: employees fk_team_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.employees
    ADD CONSTRAINT fk_team_id FOREIGN KEY (team_id) REFERENCES public.teams(team_id);


--
-- TOC entry 5603 (class 2606 OID 176291)
-- Name: announcements fk_team_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.announcements
    ADD CONSTRAINT fk_team_id FOREIGN KEY (team_id) REFERENCES public.teams(team_id);


--
-- TOC entry 5599 (class 2606 OID 176296)
-- Name: announcement_reads fk_team_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.announcement_reads
    ADD CONSTRAINT fk_team_id FOREIGN KEY (team_id) REFERENCES public.teams(team_id);


--
-- TOC entry 5669 (class 2606 OID 176301)
-- Name: meetings fk_team_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.meetings
    ADD CONSTRAINT fk_team_id FOREIGN KEY (team_id) REFERENCES public.teams(team_id);


--
-- TOC entry 5596 (class 2606 OID 176306)
-- Name: alerts fk_team_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.alerts
    ADD CONSTRAINT fk_team_id FOREIGN KEY (team_id) REFERENCES public.teams(team_id);


--
-- TOC entry 5643 (class 2606 OID 176311)
-- Name: feedback_requests fk_team_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.feedback_requests
    ADD CONSTRAINT fk_team_id FOREIGN KEY (team_id) REFERENCES public.teams(team_id);


--
-- TOC entry 5636 (class 2606 OID 176316)
-- Name: event_participants fk_team_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.event_participants
    ADD CONSTRAINT fk_team_id FOREIGN KEY (team_id) REFERENCES public.teams(team_id);


--
-- TOC entry 5621 (class 2606 OID 176321)
-- Name: documents fk_uploaded_by_role_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.documents
    ADD CONSTRAINT fk_uploaded_by_role_id FOREIGN KEY (visibility_by_role_id) REFERENCES public.roles(role_id);


--
-- TOC entry 5657 (class 2606 OID 176326)
-- Name: goals goals_employee_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.goals
    ADD CONSTRAINT goals_employee_id_fkey FOREIGN KEY (employee_id) REFERENCES public.employees(employee_id);


--
-- TOC entry 5658 (class 2606 OID 176331)
-- Name: goals goals_team_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.goals
    ADD CONSTRAINT goals_team_id_fkey FOREIGN KEY (team_id) REFERENCES public.teams(team_id);


--
-- TOC entry 5659 (class 2606 OID 176336)
-- Name: holiday_assignments holiday_assignments_holiday_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.holiday_assignments
    ADD CONSTRAINT holiday_assignments_holiday_id_fkey FOREIGN KEY (holiday_id) REFERENCES public.holidays(id) ON DELETE CASCADE;


--
-- TOC entry 5663 (class 2606 OID 176341)
-- Name: incident_logs incident_logs_admin_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.incident_logs
    ADD CONSTRAINT incident_logs_admin_id_fkey FOREIGN KEY (admin_id) REFERENCES public.admins(admin_id);


--
-- TOC entry 5715 (class 2606 OID 176631)
-- Name: incident_logs_employee incident_logs_employee_employee_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.incident_logs_employee
    ADD CONSTRAINT incident_logs_employee_employee_id_fkey FOREIGN KEY (employee_id) REFERENCES public.employees(employee_id) ON DELETE CASCADE;


--
-- TOC entry 5664 (class 2606 OID 176356)
-- Name: leave_balances leave_balances_employee_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.leave_balances
    ADD CONSTRAINT leave_balances_employee_id_fkey FOREIGN KEY (employee_id) REFERENCES public.employees(employee_id) ON DELETE CASCADE;


--
-- TOC entry 5665 (class 2606 OID 176361)
-- Name: leave_requests leave_requests_employee_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.leave_requests
    ADD CONSTRAINT leave_requests_employee_id_fkey FOREIGN KEY (employee_id) REFERENCES public.employees(employee_id) ON DELETE CASCADE;


--
-- TOC entry 5670 (class 2606 OID 176391)
-- Name: payroll payroll_employee_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.payroll
    ADD CONSTRAINT payroll_employee_id_fkey FOREIGN KEY (employee_id) REFERENCES public.employees(employee_id);


--
-- TOC entry 5671 (class 2606 OID 176396)
-- Name: performance_reviews performance_reviews_employee_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.performance_reviews
    ADD CONSTRAINT performance_reviews_employee_id_fkey FOREIGN KEY (employee_id) REFERENCES public.employees(employee_id) ON DELETE CASCADE;


--
-- TOC entry 5650 (class 2606 OID 176401)
-- Name: goal_progress progress_goal_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.goal_progress
    ADD CONSTRAINT progress_goal_id_fkey FOREIGN KEY (goal_id) REFERENCES public.goals(goal_id);


--
-- TOC entry 5672 (class 2606 OID 176421)
-- Name: route_actions route_actions_action_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.route_actions
    ADD CONSTRAINT route_actions_action_id_fkey FOREIGN KEY (action_id) REFERENCES public.actions(id) ON DELETE CASCADE;


--
-- TOC entry 5673 (class 2606 OID 176426)
-- Name: route_actions route_actions_route_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.route_actions
    ADD CONSTRAINT route_actions_route_id_fkey FOREIGN KEY (route_id) REFERENCES public.routes(id) ON DELETE CASCADE;


--
-- TOC entry 5674 (class 2606 OID 176431)
-- Name: savings_plan_requests savings_plan_requests_employee_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.savings_plan_requests
    ADD CONSTRAINT savings_plan_requests_employee_id_fkey FOREIGN KEY (employee_id) REFERENCES public.employees(employee_id) ON DELETE CASCADE;


--
-- TOC entry 5675 (class 2606 OID 176436)
-- Name: savings_plan_requests savings_plan_requests_plan_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.savings_plan_requests
    ADD CONSTRAINT savings_plan_requests_plan_id_fkey FOREIGN KEY (plan_id) REFERENCES public.savings_plans(plan_id) ON DELETE CASCADE;


--
-- TOC entry 5676 (class 2606 OID 176441)
-- Name: savings_plans savings_plans_employee_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.savings_plans
    ADD CONSTRAINT savings_plans_employee_id_fkey FOREIGN KEY (employee_id) REFERENCES public.employees(employee_id);


--
-- TOC entry 5678 (class 2606 OID 176446)
-- Name: skill_assessments skill_assessments_employee_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.skill_assessments
    ADD CONSTRAINT skill_assessments_employee_id_fkey FOREIGN KEY (employee_id) REFERENCES public.employees(employee_id) ON DELETE CASCADE;


--
-- TOC entry 5679 (class 2606 OID 176451)
-- Name: skill_development skill_development_employee_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.skill_development
    ADD CONSTRAINT skill_development_employee_id_fkey FOREIGN KEY (employee_id) REFERENCES public.employees(employee_id) ON DELETE CASCADE;


--
-- TOC entry 5680 (class 2606 OID 176456)
-- Name: super_admins super_admins_role_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.super_admins
    ADD CONSTRAINT super_admins_role_id_fkey FOREIGN KEY (role_id) REFERENCES public.roles(role_id) ON DELETE CASCADE;


--
-- TOC entry 5681 (class 2606 OID 176461)
-- Name: survey_answer_options survey_answer_options_question_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.survey_answer_options
    ADD CONSTRAINT survey_answer_options_question_id_fkey FOREIGN KEY (question_id) REFERENCES public.survey_questions(question_id) ON DELETE CASCADE;


--
-- TOC entry 5682 (class 2606 OID 176466)
-- Name: survey_assignments survey_assignments_employee_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.survey_assignments
    ADD CONSTRAINT survey_assignments_employee_id_fkey FOREIGN KEY (employee_id) REFERENCES public.employees(employee_id) ON DELETE SET NULL;


--
-- TOC entry 5683 (class 2606 OID 176471)
-- Name: survey_assignments survey_assignments_survey_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.survey_assignments
    ADD CONSTRAINT survey_assignments_survey_id_fkey FOREIGN KEY (survey_id) REFERENCES public.surveys(survey_id) ON DELETE CASCADE;


--
-- TOC entry 5684 (class 2606 OID 176476)
-- Name: survey_assignments survey_assignments_team_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.survey_assignments
    ADD CONSTRAINT survey_assignments_team_id_fkey FOREIGN KEY (team_id) REFERENCES public.teams(team_id) ON DELETE SET NULL;


--
-- TOC entry 5685 (class 2606 OID 176481)
-- Name: survey_question_options survey_question_options_question_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.survey_question_options
    ADD CONSTRAINT survey_question_options_question_id_fkey FOREIGN KEY (question_id) REFERENCES public.survey_questions(question_id) ON DELETE CASCADE;


--
-- TOC entry 5686 (class 2606 OID 176486)
-- Name: survey_questions survey_questions_survey_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.survey_questions
    ADD CONSTRAINT survey_questions_survey_id_fkey FOREIGN KEY (survey_id) REFERENCES public.surveys(survey_id) ON DELETE CASCADE;


--
-- TOC entry 5689 (class 2606 OID 176491)
-- Name: survey_responses survey_responses_question_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.survey_responses
    ADD CONSTRAINT survey_responses_question_id_fkey FOREIGN KEY (question_id) REFERENCES public.survey_questions(question_id) ON DELETE CASCADE;


--
-- TOC entry 5690 (class 2606 OID 176496)
-- Name: survey_responses survey_responses_survey_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.survey_responses
    ADD CONSTRAINT survey_responses_survey_id_fkey FOREIGN KEY (survey_id) REFERENCES public.surveys(survey_id) ON DELETE CASCADE;


--
-- TOC entry 5693 (class 2606 OID 176501)
-- Name: task_parts task_parts_task_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.task_parts
    ADD CONSTRAINT task_parts_task_id_fkey FOREIGN KEY (task_id) REFERENCES public.tasks(task_id) ON DELETE CASCADE;


--
-- TOC entry 5694 (class 2606 OID 176506)
-- Name: tasks tasks_assigned_to_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.tasks
    ADD CONSTRAINT tasks_assigned_to_fkey FOREIGN KEY (employee_id) REFERENCES public.employees(employee_id) ON DELETE SET NULL;


--
-- TOC entry 5695 (class 2606 OID 176511)
-- Name: tasks tasks_project_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.tasks
    ADD CONSTRAINT tasks_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.projects(project_id);


--
-- TOC entry 5696 (class 2606 OID 176516)
-- Name: tasks tasks_team_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.tasks
    ADD CONSTRAINT tasks_team_id_fkey FOREIGN KEY (team_id) REFERENCES public.teams(team_id) ON DELETE SET NULL;


--
-- TOC entry 5697 (class 2606 OID 176521)
-- Name: tax_documents tax_documents_employee_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.tax_documents
    ADD CONSTRAINT tax_documents_employee_id_fkey FOREIGN KEY (employee_id) REFERENCES public.employees(employee_id) ON DELETE CASCADE;


--
-- TOC entry 5699 (class 2606 OID 176526)
-- Name: tax_records tax_records_employee_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.tax_records
    ADD CONSTRAINT tax_records_employee_id_fkey FOREIGN KEY (employee_id) REFERENCES public.employees(employee_id);


--
-- TOC entry 5701 (class 2606 OID 176531)
-- Name: team_members team_members_employee_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.team_members
    ADD CONSTRAINT team_members_employee_id_fkey FOREIGN KEY (employee_id) REFERENCES public.employees(employee_id) ON DELETE CASCADE;


--
-- TOC entry 5702 (class 2606 OID 176536)
-- Name: team_members team_members_team_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.team_members
    ADD CONSTRAINT team_members_team_id_fkey FOREIGN KEY (team_id) REFERENCES public.teams(team_id) ON DELETE CASCADE;


--
-- TOC entry 5705 (class 2606 OID 176541)
-- Name: ticket_responses ticket_responses_employee_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.ticket_responses
    ADD CONSTRAINT ticket_responses_employee_id_fkey FOREIGN KEY (employee_id) REFERENCES public.employees(employee_id);


--
-- TOC entry 5706 (class 2606 OID 176546)
-- Name: ticket_responses ticket_responses_ticket_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.ticket_responses
    ADD CONSTRAINT ticket_responses_ticket_id_fkey FOREIGN KEY (ticket_id) REFERENCES public.tickets(ticket_id) ON DELETE CASCADE;


--
-- TOC entry 5708 (class 2606 OID 176551)
-- Name: timesheets timesheets_employee_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.timesheets
    ADD CONSTRAINT timesheets_employee_id_fkey FOREIGN KEY (employee_id) REFERENCES public.employees(employee_id) ON DELETE CASCADE;


--
-- TOC entry 5709 (class 2606 OID 176556)
-- Name: training_certificates training_certificates_employee_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.training_certificates
    ADD CONSTRAINT training_certificates_employee_id_fkey FOREIGN KEY (employee_id) REFERENCES public.employees(employee_id) ON DELETE CASCADE;


--
-- TOC entry 5710 (class 2606 OID 176561)
-- Name: training_certificates training_certificates_module_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.training_certificates
    ADD CONSTRAINT training_certificates_module_id_fkey FOREIGN KEY (module_id) REFERENCES public.training_modules(module_id) ON DELETE CASCADE;


--
-- TOC entry 5712 (class 2606 OID 176586)
-- Name: two_factor_verifications two_factor_verifications_admin_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.two_factor_verifications
    ADD CONSTRAINT two_factor_verifications_admin_id_fkey FOREIGN KEY (admin_id) REFERENCES public.admins(admin_id);


--
-- TOC entry 5713 (class 2606 OID 176591)
-- Name: two_factor_verifications two_factor_verifications_employee_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.two_factor_verifications
    ADD CONSTRAINT two_factor_verifications_employee_id_fkey FOREIGN KEY (employee_id) REFERENCES public.employees(employee_id);


-- Completed on 2025-08-12 09:23:25

--
-- PostgreSQL database dump complete
--


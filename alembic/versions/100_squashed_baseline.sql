--
-- PostgreSQL database dump
--


-- Dumped from database version 18.4
-- Dumped by pg_dump version 18.4


--
-- Name: public; Type: SCHEMA; Schema: -; Owner: -
--

-- *not* creating schema, since initdb creates it


--
-- Name: SCHEMA public; Type: COMMENT; Schema: -; Owner: -
--



--
-- Name: pg_trgm; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pg_trgm WITH SCHEMA public;


--
-- Name: EXTENSION pg_trgm; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION pg_trgm IS 'text similarity measurement and index searching based on trigrams';


--
-- Name: accesscontroltypeenum; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.accesscontroltypeenum AS ENUM (
    'PAGE',
    'MANAGE_ORDER_STATUS',
    'FEATURE'
);


--
-- Name: inventorytypeenum; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.inventorytypeenum AS ENUM (
    'STORAGE',
    'DAMAGED',
    'WASTE',
    'SCRAP'
);


--
-- Name: machineeventtypeenum; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.machineeventtypeenum AS ENUM (
    'IDLE',
    'RUNNING',
    'OFF',
    'MAINTENANCE'
);


--
-- Name: maintenancetypeenum; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.maintenancetypeenum AS ENUM (
    'PREVENTIVE',
    'REPAIR',
    'EMERGENCY',
    'INSPECTION'
);


--
-- Name: projectpriorityenum; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.projectpriorityenum AS ENUM (
    'LOW',
    'MEDIUM',
    'HIGH',
    'URGENT'
);


--
-- Name: projectstatusenum; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.projectstatusenum AS ENUM (
    'PLANNING',
    'IN_PROGRESS',
    'COMPLETED',
    'ON_HOLD',
    'CANCELLED'
);


--
-- Name: roleenum; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.roleenum AS ENUM (
    'OWNER',
    'FINANCE',
    'GROUND_TEAM',
    'GROUND_TEAM_MANAGER'
);


--
-- Name: taskpriorityenum; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.taskpriorityenum AS ENUM (
    'LOW',
    'MEDIUM',
    'HIGH',
    'URGENT'
);


--
-- Name: unstabletypeenum; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.unstabletypeenum AS ENUM (
    'QUALITY_ISSUE',
    'COMPATIBILITY_ISSUE',
    'DAMAGED',
    'OTHER'
);


--
-- Name: workorderpriorityenum; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.workorderpriorityenum AS ENUM (
    'LOW',
    'MEDIUM',
    'HIGH',
    'URGENT'
);




--
-- Name: access_control; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.access_control (
    id integer NOT NULL,
    workspace_id integer,
    type public.accesscontroltypeenum NOT NULL,
    target character varying NOT NULL,
    role public.roleenum NOT NULL
);


--
-- Name: access_control_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.access_control_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: access_control_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.access_control_id_seq OWNED BY public.access_control.id;


--
-- Name: account_invoices; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.account_invoices (
    id integer NOT NULL,
    workspace_id integer NOT NULL,
    account_id integer NOT NULL,
    order_id integer,
    invoice_type character varying(20) NOT NULL,
    invoice_status character varying(20) NOT NULL,
    invoice_amount numeric(15,2) NOT NULL,
    paid_amount numeric(15,2) NOT NULL,
    invoice_number character varying(100),
    vendor_invoice_number character varying(100),
    invoice_date date NOT NULL,
    due_date date,
    payment_status character varying(20) NOT NULL,
    allow_payments boolean NOT NULL,
    payment_locked_reason text,
    description text,
    notes text,
    void_note text,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    created_by integer,
    updated_at timestamp without time zone,
    updated_by integer,
    order_type character varying(30),
    receiving_started boolean DEFAULT false NOT NULL,
    last_synced_at timestamp without time zone
);


--
-- Name: account_invoices_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.account_invoices_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: account_invoices_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.account_invoices_id_seq OWNED BY public.account_invoices.id;


--
-- Name: account_tag_assignments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.account_tag_assignments (
    id integer NOT NULL,
    workspace_id integer NOT NULL,
    account_id integer NOT NULL,
    tag_id integer NOT NULL,
    assigned_at timestamp without time zone NOT NULL,
    assigned_by integer
);


--
-- Name: account_tag_assignments_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.account_tag_assignments_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: account_tag_assignments_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.account_tag_assignments_id_seq OWNED BY public.account_tag_assignments.id;


--
-- Name: account_tags; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.account_tags (
    id integer NOT NULL,
    workspace_id integer NOT NULL,
    name character varying(100) NOT NULL,
    tag_code character varying(50) NOT NULL,
    color character varying(7),
    icon character varying(50),
    description text,
    is_system_tag boolean NOT NULL,
    is_active boolean NOT NULL,
    usage_count integer NOT NULL,
    created_at timestamp without time zone NOT NULL,
    created_by integer
);


--
-- Name: account_tags_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.account_tags_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: account_tags_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.account_tags_id_seq OWNED BY public.account_tags.id;


--
-- Name: accounts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.accounts (
    id integer NOT NULL,
    workspace_id integer NOT NULL,
    name character varying(255) NOT NULL,
    account_code character varying(50),
    primary_contact_person character varying(255),
    primary_email character varying(255),
    primary_phone character varying(50),
    secondary_contact_person character varying(255),
    secondary_email character varying(255),
    secondary_phone character varying(50),
    address text,
    city character varying(100),
    country character varying(100),
    postal_code character varying(20),
    payment_preferences text,
    bank_details text,
    allow_invoices boolean NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    created_by integer,
    updated_at timestamp without time zone,
    updated_by integer,
    is_active boolean NOT NULL,
    is_deleted boolean NOT NULL,
    deleted_at timestamp without time zone,
    deleted_by integer
);


--
-- Name: accounts_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.accounts_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: accounts_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.accounts_id_seq OWNED BY public.accounts.id;


--
-- Name: app_settings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.app_settings (
    id integer NOT NULL,
    workspace_id integer NOT NULL,
    name character varying NOT NULL,
    enabled boolean NOT NULL
);


--
-- Name: app_settings_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.app_settings_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: app_settings_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.app_settings_id_seq OWNED BY public.app_settings.id;


--
-- Name: attachments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.attachments (
    id integer NOT NULL,
    workspace_id integer NOT NULL,
    file_url character varying NOT NULL,
    file_name character varying NOT NULL,
    mime_type character varying NOT NULL,
    file_size bigint NOT NULL,
    uploaded_by integer NOT NULL,
    uploaded_at timestamp without time zone DEFAULT now() NOT NULL,
    note text,
    is_deleted boolean NOT NULL,
    deleted_at timestamp without time zone,
    deleted_by integer
);


--
-- Name: attachments_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.attachments_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: attachments_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.attachments_id_seq OWNED BY public.attachments.id;


--
-- Name: delivery_methods; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.delivery_methods (
    id integer NOT NULL,
    workspace_id integer NOT NULL,
    name character varying NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    created_by integer,
    updated_at timestamp without time zone,
    updated_by integer,
    is_active boolean DEFAULT true NOT NULL,
    is_deleted boolean DEFAULT false NOT NULL,
    deleted_at timestamp without time zone,
    deleted_by integer
);


--
-- Name: delivery_methods_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.delivery_methods_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: delivery_methods_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.delivery_methods_id_seq OWNED BY public.delivery_methods.id;


--
-- Name: departments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.departments (
    id integer NOT NULL,
    workspace_id integer NOT NULL,
    name character varying NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    created_by integer,
    updated_at timestamp without time zone,
    updated_by integer,
    is_active boolean NOT NULL,
    is_deleted boolean NOT NULL,
    deleted_at timestamp without time zone,
    deleted_by integer
);


--
-- Name: departments_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.departments_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: departments_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.departments_id_seq OWNED BY public.departments.id;


--
-- Name: discussions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.discussions (
    id integer NOT NULL,
    workspace_id integer NOT NULL,
    entity_type character varying(30) NOT NULL,
    entity_id integer NOT NULL,
    user_id integer,
    message text NOT NULL,
    parent_id integer,
    created_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: discussions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.discussions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: discussions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.discussions_id_seq OWNED BY public.discussions.id;


--
-- Name: expense_order_approvers; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.expense_order_approvers (
    id integer NOT NULL,
    workspace_id integer NOT NULL,
    expense_order_id integer NOT NULL,
    user_id integer NOT NULL,
    assigned_by integer,
    assigned_at timestamp without time zone NOT NULL,
    approved boolean DEFAULT false NOT NULL,
    approved_at timestamp without time zone
);


--
-- Name: expense_order_approvers_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.expense_order_approvers_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: expense_order_approvers_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.expense_order_approvers_id_seq OWNED BY public.expense_order_approvers.id;


--
-- Name: expense_order_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.expense_order_events (
    id integer NOT NULL,
    workspace_id integer NOT NULL,
    expense_order_id integer NOT NULL,
    event_type character varying(50) NOT NULL,
    description text NOT NULL,
    metadata json,
    performed_by integer,
    created_at timestamp without time zone NOT NULL
);


--
-- Name: expense_order_events_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.expense_order_events_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: expense_order_events_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.expense_order_events_id_seq OWNED BY public.expense_order_events.id;


--
-- Name: expense_order_items; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.expense_order_items (
    id integer NOT NULL,
    workspace_id integer NOT NULL,
    expense_order_id integer NOT NULL,
    line_number integer NOT NULL,
    description text,
    quantity numeric(15,2) NOT NULL,
    unit character varying(50),
    unit_price numeric(15,2),
    line_subtotal numeric(15,2),
    approved boolean NOT NULL,
    notes text
);


--
-- Name: expense_order_items_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.expense_order_items_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: expense_order_items_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.expense_order_items_id_seq OWNED BY public.expense_order_items.id;


--
-- Name: expense_orders; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.expense_orders (
    id integer NOT NULL,
    workspace_id integer NOT NULL,
    expense_number character varying(100) NOT NULL,
    order_template_id integer,
    account_id integer,
    expense_category character varying(100) NOT NULL,
    expense_date date NOT NULL,
    due_date date,
    subtotal numeric(15,2) NOT NULL,
    total_amount numeric(15,2) NOT NULL,
    invoice_id integer,
    description text,
    created_by integer NOT NULL,
    created_at timestamp without time zone NOT NULL,
    updated_by integer,
    updated_at timestamp without time zone,
    approved_by integer,
    approved_at timestamp without time zone,
    required_approvals integer,
    completed_by integer,
    completed_at timestamp without time zone,
    items_updated_at timestamp without time zone,
    cost_center_id integer,
    voided boolean DEFAULT false NOT NULL,
    void_note text,
    voided_at timestamp without time zone,
    voided_by integer
);


--
-- Name: expense_orders_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.expense_orders_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: expense_orders_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.expense_orders_id_seq OWNED BY public.expense_orders.id;


--
-- Name: factories; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.factories (
    id integer NOT NULL,
    workspace_id integer NOT NULL,
    name character varying NOT NULL,
    abbreviation character varying NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    created_by integer,
    updated_at timestamp without time zone,
    updated_by integer,
    is_active boolean NOT NULL,
    is_deleted boolean NOT NULL,
    deleted_at timestamp without time zone,
    deleted_by integer
);


--
-- Name: factories_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.factories_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: factories_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.factories_id_seq OWNED BY public.factories.id;


--
-- Name: factory_sections; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.factory_sections (
    id integer NOT NULL,
    workspace_id integer NOT NULL,
    name character varying NOT NULL,
    factory_id integer NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    created_by integer,
    updated_at timestamp without time zone,
    updated_by integer,
    is_active boolean NOT NULL,
    is_deleted boolean NOT NULL,
    deleted_at timestamp without time zone,
    deleted_by integer
);


--
-- Name: factory_sections_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.factory_sections_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: factory_sections_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.factory_sections_id_seq OWNED BY public.factory_sections.id;


--
-- Name: financial_audit_logs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.financial_audit_logs (
    id integer NOT NULL,
    workspace_id integer NOT NULL,
    entity_type character varying(50) NOT NULL,
    entity_id integer NOT NULL,
    action_type character varying(50) NOT NULL,
    related_entity_type character varying(50),
    related_entity_id integer,
    changes json,
    description text,
    ip_address character varying(45),
    user_agent character varying(255),
    performed_by integer NOT NULL,
    performed_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: financial_audit_logs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.financial_audit_logs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: financial_audit_logs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.financial_audit_logs_id_seq OWNED BY public.financial_audit_logs.id;


--
-- Name: inventory; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.inventory (
    id integer NOT NULL,
    workspace_id integer NOT NULL,
    item_id integer NOT NULL,
    inventory_type public.inventorytypeenum NOT NULL,
    factory_id integer NOT NULL,
    qty integer NOT NULL,
    avg_price numeric(15,2),
    note text,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    created_by integer,
    updated_at timestamp without time zone,
    updated_by integer,
    is_active boolean NOT NULL,
    is_deleted boolean NOT NULL,
    deleted_at timestamp without time zone,
    deleted_by integer
);


--
-- Name: inventory_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.inventory_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: inventory_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.inventory_id_seq OWNED BY public.inventory.id;


--
-- Name: inventory_ledger; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.inventory_ledger (
    id integer NOT NULL,
    workspace_id integer NOT NULL,
    inventory_type public.inventorytypeenum NOT NULL,
    factory_id integer NOT NULL,
    item_id integer NOT NULL,
    transaction_type character varying(50) NOT NULL,
    quantity integer NOT NULL,
    unit_cost numeric(15,2),
    total_cost numeric(15,2),
    qty_before integer NOT NULL,
    qty_after integer NOT NULL,
    avg_price_before numeric(15,2),
    avg_price_after numeric(15,2),
    source_type character varying(50),
    source_id integer,
    transfer_source_type character varying(50),
    transfer_source_id integer,
    transfer_destination_type character varying(50),
    transfer_destination_id integer,
    notes text,
    performed_by integer,
    performed_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: inventory_ledger_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.inventory_ledger_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: inventory_ledger_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.inventory_ledger_id_seq OWNED BY public.inventory_ledger.id;


--
-- Name: invoice_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.invoice_events (
    id integer NOT NULL,
    workspace_id integer NOT NULL,
    invoice_id integer NOT NULL,
    event_type character varying(50) NOT NULL,
    description text NOT NULL,
    metadata_json json,
    performed_by integer,
    created_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: invoice_events_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.invoice_events_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: invoice_events_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.invoice_events_id_seq OWNED BY public.invoice_events.id;


--
-- Name: invoice_items; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.invoice_items (
    id integer NOT NULL,
    workspace_id integer NOT NULL,
    invoice_id integer NOT NULL,
    line_number integer DEFAULT 1 NOT NULL,
    description text NOT NULL,
    item_id integer,
    source_order_item_id integer,
    source_order_item_type character varying(30),
    quantity numeric(15,2) NOT NULL,
    unit character varying(50),
    unit_price numeric(15,2) NOT NULL,
    line_subtotal numeric(15,2) NOT NULL,
    last_synced_at timestamp without time zone,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    created_by integer
);


--
-- Name: invoice_items_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.invoice_items_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: invoice_items_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.invoice_items_id_seq OWNED BY public.invoice_items.id;


--
-- Name: invoice_payments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.invoice_payments (
    id integer NOT NULL,
    workspace_id integer NOT NULL,
    invoice_id integer NOT NULL,
    payment_amount numeric(15,2) NOT NULL,
    payment_date date NOT NULL,
    payment_method character varying(50),
    payment_reference character varying(100),
    bank_name character varying(255),
    transaction_id character varying(100),
    notes text,
    is_voided boolean NOT NULL,
    voided_at timestamp without time zone,
    voided_by integer,
    void_note text,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    created_by integer
);


--
-- Name: invoice_payments_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.invoice_payments_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: invoice_payments_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.invoice_payments_id_seq OWNED BY public.invoice_payments.id;


--
-- Name: invoice_status_tracker; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.invoice_status_tracker (
    id integer NOT NULL,
    workspace_id integer NOT NULL,
    invoice_id integer NOT NULL,
    from_status character varying(20) NOT NULL,
    to_status character varying(20) NOT NULL,
    changed_by integer,
    changed_at timestamp without time zone NOT NULL
);


--
-- Name: invoice_status_tracker_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.invoice_status_tracker_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: invoice_status_tracker_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.invoice_status_tracker_id_seq OWNED BY public.invoice_status_tracker.id;


--
-- Name: item_tag_assignments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.item_tag_assignments (
    id integer NOT NULL,
    workspace_id integer NOT NULL,
    item_id integer NOT NULL,
    tag_id integer NOT NULL,
    assigned_at timestamp without time zone NOT NULL,
    assigned_by integer
);


--
-- Name: item_tag_assignments_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.item_tag_assignments_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: item_tag_assignments_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.item_tag_assignments_id_seq OWNED BY public.item_tag_assignments.id;


--
-- Name: item_tags; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.item_tags (
    id integer NOT NULL,
    workspace_id integer NOT NULL,
    name character varying NOT NULL,
    tag_code character varying NOT NULL,
    color character varying(7),
    icon character varying(50),
    description text,
    is_system_tag boolean NOT NULL,
    is_active boolean NOT NULL,
    usage_count integer NOT NULL,
    created_at timestamp without time zone NOT NULL,
    created_by integer
);


--
-- Name: item_tags_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.item_tags_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: item_tags_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.item_tags_id_seq OWNED BY public.item_tags.id;


--
-- Name: items; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.items (
    id integer NOT NULL,
    workspace_id integer NOT NULL,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone,
    name character varying NOT NULL,
    description character varying,
    unit character varying NOT NULL,
    sku character varying,
    created_by integer,
    updated_by integer,
    is_active boolean NOT NULL,
    name_normalized character varying NOT NULL,
    item_type character varying(20) DEFAULT 'physical'::character varying NOT NULL
);


--
-- Name: items_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.items_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: items_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.items_id_seq OWNED BY public.items.id;


--
-- Name: machine_activity_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.machine_activity_events (
    id integer NOT NULL,
    workspace_id integer NOT NULL,
    machine_id integer NOT NULL,
    event_type character varying(50) NOT NULL,
    description text NOT NULL,
    metadata json,
    performed_by integer,
    created_at timestamp without time zone NOT NULL
);


--
-- Name: machine_activity_events_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.machine_activity_events_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: machine_activity_events_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.machine_activity_events_id_seq OWNED BY public.machine_activity_events.id;


--
-- Name: machine_item_ledger; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.machine_item_ledger (
    id integer NOT NULL,
    workspace_id integer NOT NULL,
    machine_id integer NOT NULL,
    item_id integer NOT NULL,
    transaction_type character varying(50) NOT NULL,
    quantity integer NOT NULL,
    unit_cost numeric(15,2) NOT NULL,
    total_cost numeric(15,2) NOT NULL,
    qty_before integer NOT NULL,
    qty_after integer NOT NULL,
    value_before numeric(15,2),
    value_after numeric(15,2),
    avg_price_before numeric(15,2),
    avg_price_after numeric(15,2),
    source_type character varying(50) NOT NULL,
    source_id integer,
    order_id integer,
    invoice_id integer,
    transfer_source_type character varying(50),
    transfer_source_id integer,
    transfer_destination_type character varying(50),
    transfer_destination_id integer,
    notes text,
    performed_by integer NOT NULL,
    performed_at timestamp without time zone NOT NULL,
    order_type character varying(30)
);


--
-- Name: machine_item_ledger_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.machine_item_ledger_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: machine_item_ledger_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.machine_item_ledger_id_seq OWNED BY public.machine_item_ledger.id;


--
-- Name: machine_items; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.machine_items (
    id integer NOT NULL,
    workspace_id integer NOT NULL,
    machine_id integer NOT NULL,
    item_id integer NOT NULL,
    qty integer NOT NULL,
    req_qty integer,
    defective_qty integer
);


--
-- Name: machine_items_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.machine_items_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: machine_items_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.machine_items_id_seq OWNED BY public.machine_items.id;


--
-- Name: machine_maintenance_logs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.machine_maintenance_logs (
    id integer NOT NULL,
    workspace_id integer NOT NULL,
    machine_id integer NOT NULL,
    maintenance_type public.maintenancetypeenum NOT NULL,
    maintenance_date date NOT NULL,
    summary text NOT NULL,
    cost numeric(15,2),
    performed_by character varying(255),
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    created_by integer,
    updated_at timestamp without time zone,
    updated_by integer,
    is_active boolean NOT NULL,
    is_deleted boolean NOT NULL,
    deleted_at timestamp without time zone,
    deleted_by integer
);


--
-- Name: machine_maintenance_logs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.machine_maintenance_logs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: machine_maintenance_logs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.machine_maintenance_logs_id_seq OWNED BY public.machine_maintenance_logs.id;


--
-- Name: machine_section_assignments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.machine_section_assignments (
    id integer NOT NULL,
    workspace_id integer NOT NULL,
    machine_id integer NOT NULL,
    factory_section_id integer NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    created_by integer,
    updated_at timestamp without time zone,
    updated_by integer
);


--
-- Name: machine_section_assignments_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.machine_section_assignments_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: machine_section_assignments_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.machine_section_assignments_id_seq OWNED BY public.machine_section_assignments.id;


--
-- Name: machines; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.machines (
    id integer NOT NULL,
    workspace_id integer NOT NULL,
    name character varying NOT NULL,
    is_running boolean NOT NULL,
    model_number character varying(200),
    manufacturer character varying(200),
    note text,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    created_by integer,
    updated_at timestamp without time zone,
    updated_by integer,
    is_active boolean NOT NULL,
    is_deleted boolean NOT NULL,
    deleted_at timestamp without time zone,
    deleted_by integer,
    factory_id integer NOT NULL
);


--
-- Name: machines_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.machines_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: machines_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.machines_id_seq OWNED BY public.machines.id;


--
-- Name: miscellaneous_project_costs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.miscellaneous_project_costs (
    id integer NOT NULL,
    workspace_id integer NOT NULL,
    created_at timestamp without time zone NOT NULL,
    project_id integer,
    project_component_id integer,
    name character varying NOT NULL,
    description text,
    amount numeric(15,2) NOT NULL
);


--
-- Name: miscellaneous_project_costs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.miscellaneous_project_costs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: miscellaneous_project_costs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.miscellaneous_project_costs_id_seq OWNED BY public.miscellaneous_project_costs.id;


--
-- Name: notifications; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.notifications (
    id integer NOT NULL,
    workspace_id integer NOT NULL,
    recipient_user_id integer NOT NULL,
    actor_user_id integer,
    notification_type character varying(30) NOT NULL,
    entity_type character varying(30) NOT NULL,
    entity_id integer NOT NULL,
    source_type character varying(30) NOT NULL,
    source_id integer NOT NULL,
    preview text,
    is_read boolean DEFAULT false NOT NULL,
    read_at timestamp without time zone,
    created_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: notifications_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.notifications_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: notifications_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.notifications_id_seq OWNED BY public.notifications.id;


--
-- Name: order_template_items; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.order_template_items (
    id integer NOT NULL,
    workspace_id integer NOT NULL,
    order_template_id integer NOT NULL,
    line_number integer NOT NULL,
    description text,
    quantity numeric(15,2) NOT NULL,
    unit character varying(50),
    unit_price numeric(15,2),
    line_subtotal numeric(15,2),
    notes text
);


--
-- Name: order_template_items_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.order_template_items_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: order_template_items_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.order_template_items_id_seq OWNED BY public.order_template_items.id;


--
-- Name: order_templates; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.order_templates (
    id integer NOT NULL,
    workspace_id integer NOT NULL,
    template_name character varying(255) NOT NULL,
    description text,
    account_id integer,
    expense_category character varying(100),
    is_recurring boolean NOT NULL,
    recurrence_type character varying(50),
    recurrence_interval integer,
    recurrence_day integer,
    start_date date,
    end_date date,
    next_generation_date date,
    last_generated_date date,
    is_active boolean NOT NULL,
    generate_days_before integer NOT NULL,
    auto_approve boolean NOT NULL,
    requires_approval boolean NOT NULL,
    default_approver_id integer,
    notes text,
    created_by integer,
    created_at timestamp without time zone NOT NULL,
    updated_by integer,
    updated_at timestamp without time zone,
    cost_center_id integer
);


--
-- Name: order_templates_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.order_templates_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: order_templates_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.order_templates_id_seq OWNED BY public.order_templates.id;


--
-- Name: order_workflows; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.order_workflows (
    id integer NOT NULL,
    workspace_id integer NOT NULL,
    name character varying NOT NULL,
    type character varying NOT NULL,
    description character varying,
    status_sequence text NOT NULL,
    allowed_reverts_json json
);


--
-- Name: order_workflows_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.order_workflows_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: order_workflows_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.order_workflows_id_seq OWNED BY public.order_workflows.id;


--
-- Name: payment_transaction_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.payment_transaction_events (
    id integer NOT NULL,
    workspace_id integer NOT NULL,
    payment_transaction_id integer NOT NULL,
    event_type character varying(50) NOT NULL,
    description text NOT NULL,
    metadata_json json,
    performed_by integer,
    created_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: payment_transaction_events_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.payment_transaction_events_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: payment_transaction_events_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.payment_transaction_events_id_seq OWNED BY public.payment_transaction_events.id;


--
-- Name: payment_transactions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.payment_transactions (
    id integer NOT NULL,
    workspace_id integer NOT NULL,
    tran_id character varying(30) NOT NULL,
    status character varying(20) DEFAULT 'INITIATED'::character varying NOT NULL,
    amount numeric(15,2) NOT NULL,
    currency character varying(3) NOT NULL,
    cus_name character varying(255),
    cus_email character varying(255),
    cus_phone character varying(50),
    value_a character varying(255),
    value_b character varying(255),
    value_c character varying(255),
    value_d character varying(255),
    session_key character varying(64),
    gateway_page_url text,
    val_id character varying(512),
    risk_level integer,
    risk_title character varying(50),
    bank_tran_id character varying(100),
    card_type character varying(50),
    verify_sign character varying(255),
    last_ipn_payload json,
    risk_resolved_by integer,
    risk_resolved_at timestamp without time zone,
    risk_resolution_note text,
    initiated_by integer,
    initiated_at timestamp without time zone DEFAULT now() NOT NULL,
    validated_at timestamp without time zone,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: payment_transactions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.payment_transactions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: payment_transactions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.payment_transactions_id_seq OWNED BY public.payment_transactions.id;


--
-- Name: po_receive_event_items; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.po_receive_event_items (
    id integer NOT NULL,
    receive_event_id integer NOT NULL,
    po_item_id integer NOT NULL,
    quantity_delta numeric(15,4) NOT NULL
);


--
-- Name: po_receive_event_items_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.po_receive_event_items_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: po_receive_event_items_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.po_receive_event_items_id_seq OWNED BY public.po_receive_event_items.id;


--
-- Name: po_receive_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.po_receive_events (
    id integer NOT NULL,
    workspace_id integer NOT NULL,
    purchase_order_id integer NOT NULL,
    event_type character varying(20) NOT NULL,
    rcc character varying(100),
    received_by character varying(200),
    correction_note text,
    performed_by integer,
    created_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: po_receive_events_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.po_receive_events_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: po_receive_events_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.po_receive_events_id_seq OWNED BY public.po_receive_events.id;


--
-- Name: product_ledger; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.product_ledger (
    id integer NOT NULL,
    workspace_id integer NOT NULL,
    factory_id integer NOT NULL,
    item_id integer NOT NULL,
    transaction_type character varying(50) NOT NULL,
    quantity integer NOT NULL,
    unit_cost numeric(15,2),
    total_cost numeric(15,2),
    qty_before integer NOT NULL,
    qty_after integer NOT NULL,
    avg_cost_before numeric(15,2),
    avg_cost_after numeric(15,2),
    source_type character varying(50),
    source_id integer,
    transfer_source_type character varying(50),
    transfer_source_id integer,
    transfer_destination_type character varying(50),
    transfer_destination_id integer,
    notes text,
    performed_by integer,
    performed_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: product_ledger_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.product_ledger_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: product_ledger_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.product_ledger_id_seq OWNED BY public.product_ledger.id;


--
-- Name: production_batch_items; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.production_batch_items (
    id integer NOT NULL,
    workspace_id integer NOT NULL,
    batch_id integer NOT NULL,
    item_id integer NOT NULL,
    item_role character varying(20) NOT NULL,
    expected_quantity integer,
    actual_quantity integer,
    source_location_type character varying(50),
    source_location_id integer,
    destination_location_type character varying(50),
    destination_location_id integer,
    variance_quantity integer,
    variance_percentage numeric(5,2),
    notes text
);


--
-- Name: production_batch_items_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.production_batch_items_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: production_batch_items_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.production_batch_items_id_seq OWNED BY public.production_batch_items.id;


--
-- Name: production_batch_stage_logs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.production_batch_stage_logs (
    id integer NOT NULL,
    workspace_id integer NOT NULL,
    batch_id integer NOT NULL,
    formula_stage_id integer,
    stage_name character varying(200) NOT NULL,
    stage_order integer DEFAULT 0 NOT NULL,
    production_line_id integer,
    status character varying(20) DEFAULT 'pending'::character varying NOT NULL,
    started_at timestamp without time zone,
    completed_at timestamp without time zone,
    logged_by integer,
    input_quantity integer,
    output_quantity integer,
    waste_quantity integer,
    notes text,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: production_batch_stage_logs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.production_batch_stage_logs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: production_batch_stage_logs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.production_batch_stage_logs_id_seq OWNED BY public.production_batch_stage_logs.id;


--
-- Name: production_batches; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.production_batches (
    id integer NOT NULL,
    workspace_id integer NOT NULL,
    batch_number character varying(50) NOT NULL,
    production_line_id integer NOT NULL,
    formula_id integer,
    batch_date date NOT NULL,
    shift character varying(20),
    status character varying(20) NOT NULL,
    expected_output_quantity integer,
    expected_duration_minutes integer,
    actual_output_quantity integer,
    actual_duration_minutes integer,
    actual_start_time timestamp without time zone,
    actual_end_time timestamp without time zone,
    output_variance_quantity integer,
    output_variance_percentage numeric(5,2),
    efficiency_percentage numeric(5,2),
    notes text,
    created_by integer,
    updated_by integer,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL,
    started_by integer,
    started_at timestamp without time zone,
    completed_by integer,
    completed_at timestamp without time zone
);


--
-- Name: production_batches_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.production_batches_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: production_batches_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.production_batches_id_seq OWNED BY public.production_batches.id;


--
-- Name: production_formula_items; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.production_formula_items (
    id integer NOT NULL,
    workspace_id integer NOT NULL,
    formula_id integer NOT NULL,
    item_id integer NOT NULL,
    item_role character varying(20) NOT NULL,
    quantity integer NOT NULL,
    unit character varying(20),
    is_optional boolean NOT NULL,
    tolerance_percentage numeric(5,2)
);


--
-- Name: production_formula_items_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.production_formula_items_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: production_formula_items_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.production_formula_items_id_seq OWNED BY public.production_formula_items.id;


--
-- Name: production_formula_stages; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.production_formula_stages (
    id integer NOT NULL,
    workspace_id integer NOT NULL,
    formula_id integer NOT NULL,
    stage_order integer NOT NULL,
    name character varying(200) NOT NULL,
    production_line_id integer,
    machine_id integer,
    expected_duration_minutes integer,
    expected_output_quantity integer,
    expected_output_item_id integer,
    notes text
);


--
-- Name: production_formula_stages_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.production_formula_stages_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: production_formula_stages_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.production_formula_stages_id_seq OWNED BY public.production_formula_stages.id;


--
-- Name: production_formulas; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.production_formulas (
    id integer NOT NULL,
    workspace_id integer NOT NULL,
    formula_code character varying(50) NOT NULL,
    name character varying(200) NOT NULL,
    description text,
    version integer NOT NULL,
    estimated_duration_minutes integer,
    is_active boolean NOT NULL,
    is_default boolean NOT NULL,
    created_by integer,
    updated_by integer,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL
);


--
-- Name: production_formulas_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.production_formulas_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: production_formulas_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.production_formulas_id_seq OWNED BY public.production_formulas.id;


--
-- Name: production_lines; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.production_lines (
    id integer NOT NULL,
    workspace_id integer NOT NULL,
    factory_id integer NOT NULL,
    machine_id integer,
    name character varying(200) NOT NULL,
    description text,
    is_active boolean NOT NULL,
    created_by integer,
    updated_by integer
);


--
-- Name: production_lines_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.production_lines_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: production_lines_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.production_lines_id_seq OWNED BY public.production_lines.id;


--
-- Name: products; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.products (
    id integer NOT NULL,
    workspace_id integer NOT NULL,
    item_id integer NOT NULL,
    factory_id integer NOT NULL,
    qty integer NOT NULL,
    avg_cost numeric(15,2),
    selling_price numeric(15,2),
    min_order_qty integer,
    is_available_for_sale boolean NOT NULL,
    note text,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    created_by integer,
    updated_at timestamp without time zone,
    updated_by integer,
    is_active boolean NOT NULL,
    is_deleted boolean NOT NULL,
    deleted_at timestamp without time zone,
    deleted_by integer
);


--
-- Name: products_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.products_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: products_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.products_id_seq OWNED BY public.products.id;


--
-- Name: profiles; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.profiles (
    id integer NOT NULL,
    name character varying NOT NULL,
    email character varying NOT NULL,
    user_id character varying NOT NULL,
    hashed_password character varying NOT NULL
);


--
-- Name: profiles_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.profiles_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: profiles_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.profiles_id_seq OWNED BY public.profiles.id;


--
-- Name: project_attachments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.project_attachments (
    id integer NOT NULL,
    workspace_id integer NOT NULL,
    project_id integer NOT NULL,
    attachment_id integer NOT NULL,
    attached_at timestamp without time zone DEFAULT now() NOT NULL,
    attached_by integer NOT NULL
);


--
-- Name: project_attachments_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.project_attachments_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: project_attachments_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.project_attachments_id_seq OWNED BY public.project_attachments.id;


--
-- Name: project_component_activity_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.project_component_activity_events (
    id integer NOT NULL,
    workspace_id integer NOT NULL,
    project_component_id integer NOT NULL,
    event_type character varying(50) NOT NULL,
    description text NOT NULL,
    metadata json,
    performed_by integer,
    created_at timestamp without time zone NOT NULL
);


--
-- Name: project_component_activity_events_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.project_component_activity_events_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: project_component_activity_events_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.project_component_activity_events_id_seq OWNED BY public.project_component_activity_events.id;


--
-- Name: project_component_attachments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.project_component_attachments (
    id integer NOT NULL,
    workspace_id integer NOT NULL,
    project_component_id integer NOT NULL,
    attachment_id integer NOT NULL,
    attached_at timestamp without time zone DEFAULT now() NOT NULL,
    attached_by integer NOT NULL
);


--
-- Name: project_component_attachments_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.project_component_attachments_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: project_component_attachments_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.project_component_attachments_id_seq OWNED BY public.project_component_attachments.id;


--
-- Name: project_component_item_ledger; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.project_component_item_ledger (
    id integer NOT NULL,
    workspace_id integer NOT NULL,
    project_component_id integer NOT NULL,
    item_id integer NOT NULL,
    transaction_type character varying(50) NOT NULL,
    quantity integer NOT NULL,
    unit_cost numeric(15,2) NOT NULL,
    total_cost numeric(15,2) NOT NULL,
    qty_before integer NOT NULL,
    qty_after integer NOT NULL,
    value_before numeric(15,2),
    value_after numeric(15,2),
    avg_price_before numeric(15,2),
    avg_price_after numeric(15,2),
    source_type character varying(50) NOT NULL,
    source_id integer,
    order_id integer,
    invoice_id integer,
    transfer_source_type character varying(50),
    transfer_source_id integer,
    transfer_destination_type character varying(50),
    transfer_destination_id integer,
    notes text,
    performed_by integer NOT NULL,
    performed_at timestamp without time zone NOT NULL,
    order_type character varying(30)
);


--
-- Name: project_component_item_ledger_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.project_component_item_ledger_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: project_component_item_ledger_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.project_component_item_ledger_id_seq OWNED BY public.project_component_item_ledger.id;


--
-- Name: project_component_items; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.project_component_items (
    id integer NOT NULL,
    workspace_id integer NOT NULL,
    project_component_id integer NOT NULL,
    item_id integer NOT NULL,
    qty integer NOT NULL
);


--
-- Name: project_component_items_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.project_component_items_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: project_component_items_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.project_component_items_id_seq OWNED BY public.project_component_items.id;


--
-- Name: project_component_tasks; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.project_component_tasks (
    id integer NOT NULL,
    workspace_id integer NOT NULL,
    created_at timestamp without time zone NOT NULL,
    project_component_id integer NOT NULL,
    name character varying NOT NULL,
    description text NOT NULL,
    is_completed boolean NOT NULL,
    is_note boolean NOT NULL,
    task_priority public.taskpriorityenum
);


--
-- Name: project_component_tasks_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.project_component_tasks_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: project_component_tasks_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.project_component_tasks_id_seq OWNED BY public.project_component_tasks.id;


--
-- Name: project_components; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.project_components (
    id integer NOT NULL,
    workspace_id integer NOT NULL,
    created_at timestamp without time zone NOT NULL,
    project_id integer NOT NULL,
    name character varying NOT NULL,
    description text,
    budget numeric(15,2),
    deadline timestamp without time zone,
    start_date timestamp without time zone,
    end_date timestamp without time zone,
    status public.projectstatusenum NOT NULL
);


--
-- Name: project_components_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.project_components_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: project_components_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.project_components_id_seq OWNED BY public.project_components.id;


--
-- Name: project_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.project_events (
    id integer NOT NULL,
    workspace_id integer NOT NULL,
    project_id integer NOT NULL,
    event_type character varying(50) NOT NULL,
    description text NOT NULL,
    metadata json,
    performed_by integer,
    created_at timestamp without time zone NOT NULL
);


--
-- Name: project_events_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.project_events_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: project_events_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.project_events_id_seq OWNED BY public.project_events.id;


--
-- Name: project_members; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.project_members (
    id integer NOT NULL,
    workspace_id integer NOT NULL,
    project_id integer NOT NULL,
    user_id integer NOT NULL,
    assigned_by integer,
    assigned_at timestamp without time zone NOT NULL
);


--
-- Name: project_members_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.project_members_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: project_members_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.project_members_id_seq OWNED BY public.project_members.id;


--
-- Name: projects; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.projects (
    id integer NOT NULL,
    workspace_id integer NOT NULL,
    created_at timestamp without time zone NOT NULL,
    factory_id integer NOT NULL,
    name character varying NOT NULL,
    description text NOT NULL,
    budget numeric(15,2),
    deadline timestamp without time zone,
    start_date timestamp without time zone,
    end_date timestamp without time zone,
    priority public.projectpriorityenum NOT NULL,
    status public.projectstatusenum NOT NULL,
    visibility character varying(20) DEFAULT 'workspace'::character varying NOT NULL,
    created_by integer,
    updated_at timestamp without time zone,
    updated_by integer,
    is_active boolean NOT NULL,
    is_deleted boolean NOT NULL,
    deleted_at timestamp without time zone,
    deleted_by integer
);


--
-- Name: projects_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.projects_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: projects_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.projects_id_seq OWNED BY public.projects.id;


--
-- Name: purchase_order_approvers; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.purchase_order_approvers (
    id integer NOT NULL,
    workspace_id integer NOT NULL,
    purchase_order_id integer NOT NULL,
    user_id integer NOT NULL,
    assigned_by integer,
    assigned_at timestamp without time zone NOT NULL,
    approved boolean NOT NULL,
    approved_at timestamp without time zone
);


--
-- Name: purchase_order_approvers_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.purchase_order_approvers_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: purchase_order_approvers_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.purchase_order_approvers_id_seq OWNED BY public.purchase_order_approvers.id;


--
-- Name: purchase_order_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.purchase_order_events (
    id integer NOT NULL,
    workspace_id integer NOT NULL,
    purchase_order_id integer NOT NULL,
    event_type character varying(50) NOT NULL,
    description text NOT NULL,
    metadata json,
    performed_by integer,
    created_at timestamp without time zone NOT NULL
);


--
-- Name: purchase_order_events_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.purchase_order_events_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: purchase_order_events_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.purchase_order_events_id_seq OWNED BY public.purchase_order_events.id;


--
-- Name: purchase_order_items; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.purchase_order_items (
    id integer NOT NULL,
    workspace_id integer NOT NULL,
    purchase_order_id integer NOT NULL,
    line_number integer NOT NULL,
    item_id integer NOT NULL,
    quantity_ordered numeric(15,2) NOT NULL,
    quantity_received numeric(15,2) NOT NULL,
    unit_price numeric(15,2),
    line_subtotal numeric(15,2),
    notes text
);


--
-- Name: purchase_order_items_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.purchase_order_items_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: purchase_order_items_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.purchase_order_items_id_seq OWNED BY public.purchase_order_items.id;


--
-- Name: purchase_orders; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.purchase_orders (
    id integer NOT NULL,
    workspace_id integer NOT NULL,
    po_number character varying(100) NOT NULL,
    account_id integer,
    destination_type character varying(50) NOT NULL,
    destination_id integer NOT NULL,
    order_date date,
    expected_delivery_date date,
    actual_delivery_date date,
    subtotal numeric(15,2) NOT NULL,
    total_amount numeric(15,2) NOT NULL,
    current_status_id integer NOT NULL,
    order_workflow_id integer,
    required_approvals integer,
    invoice_id integer,
    description text,
    supplier_confirmed boolean NOT NULL,
    details_confirmed boolean NOT NULL,
    items_confirmed boolean NOT NULL,
    invoice_confirmed boolean NOT NULL,
    created_by integer NOT NULL,
    created_at timestamp without time zone NOT NULL,
    updated_by integer,
    updated_at timestamp without time zone,
    items_updated_at timestamp without time zone,
    voided boolean DEFAULT false NOT NULL,
    void_note text,
    voided_at timestamp without time zone,
    voided_by integer,
    invoice_ever_linked boolean DEFAULT false NOT NULL,
    paid boolean DEFAULT false NOT NULL
);


--
-- Name: purchase_orders_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.purchase_orders_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: purchase_orders_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.purchase_orders_id_seq OWNED BY public.purchase_orders.id;


--
-- Name: refresh_tokens; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.refresh_tokens (
    id integer NOT NULL,
    user_id integer NOT NULL,
    workspace_id integer,
    token_hash character varying(64) NOT NULL,
    family_id character varying(36) NOT NULL,
    issued_at timestamp without time zone NOT NULL,
    expires_at timestamp without time zone NOT NULL,
    revoked_at timestamp without time zone,
    replaced_by_id integer,
    user_agent character varying(512),
    ip_address character varying(64),
    last_used_at timestamp without time zone
);


--
-- Name: refresh_tokens_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.refresh_tokens_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: refresh_tokens_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.refresh_tokens_id_seq OWNED BY public.refresh_tokens.id;


--
-- Name: sales_deliveries; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sales_deliveries (
    id integer NOT NULL,
    workspace_id integer NOT NULL,
    sales_order_id integer NOT NULL,
    delivery_number character varying(100) NOT NULL,
    scheduled_date date,
    actual_delivery_date date,
    delivery_status character varying(50) NOT NULL,
    tracking_number character varying(255),
    notes text,
    created_by integer NOT NULL,
    created_at timestamp without time zone NOT NULL,
    updated_by integer,
    updated_at timestamp without time zone,
    delivery_method_id integer
);


--
-- Name: sales_deliveries_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.sales_deliveries_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: sales_deliveries_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.sales_deliveries_id_seq OWNED BY public.sales_deliveries.id;


--
-- Name: sales_delivery_items; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sales_delivery_items (
    id integer NOT NULL,
    workspace_id integer NOT NULL,
    delivery_id integer NOT NULL,
    sales_order_item_id integer NOT NULL,
    item_id integer,
    quantity_delivered integer NOT NULL,
    notes text
);


--
-- Name: sales_delivery_items_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.sales_delivery_items_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: sales_delivery_items_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.sales_delivery_items_id_seq OWNED BY public.sales_delivery_items.id;


--
-- Name: sales_order_items; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sales_order_items (
    id integer NOT NULL,
    workspace_id integer NOT NULL,
    sales_order_id integer NOT NULL,
    item_id integer,
    quantity_ordered integer NOT NULL,
    quantity_delivered integer NOT NULL,
    unit_price numeric(15,2) NOT NULL,
    line_total numeric(15,2) NOT NULL,
    notes text,
    description text,
    requires_delivery boolean DEFAULT true NOT NULL,
    CONSTRAINT ck_sales_order_items_item_or_description CHECK (((item_id IS NOT NULL) OR (description IS NOT NULL)))
);


--
-- Name: sales_order_items_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.sales_order_items_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: sales_order_items_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.sales_order_items_id_seq OWNED BY public.sales_order_items.id;


--
-- Name: sales_orders; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sales_orders (
    id integer NOT NULL,
    workspace_id integer NOT NULL,
    sales_order_number character varying(100) NOT NULL,
    account_id integer NOT NULL,
    factory_id integer NOT NULL,
    order_date date NOT NULL,
    quotation_sent_date date,
    expected_delivery_date date,
    total_amount numeric(15,2) NOT NULL,
    current_status_id integer NOT NULL,
    is_fully_delivered boolean NOT NULL,
    invoice_id integer,
    is_invoiced boolean NOT NULL,
    created_by integer NOT NULL,
    created_at timestamp without time zone NOT NULL,
    updated_by integer,
    updated_at timestamp without time zone,
    description text,
    items_updated_at timestamp without time zone
);


--
-- Name: sales_orders_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.sales_orders_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: sales_orders_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.sales_orders_id_seq OWNED BY public.sales_orders.id;


--
-- Name: statuses; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.statuses (
    id integer NOT NULL,
    workspace_id integer NOT NULL,
    name character varying NOT NULL,
    comment character varying NOT NULL
);


--
-- Name: statuses_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.statuses_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: statuses_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.statuses_id_seq OWNED BY public.statuses.id;


--
-- Name: subscription_plans; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.subscription_plans (
    id integer NOT NULL,
    name character varying(100) NOT NULL,
    display_name character varying(255) NOT NULL,
    description text,
    price_monthly numeric(10,2),
    price_yearly numeric(10,2),
    currency character varying(3) NOT NULL,
    max_members integer NOT NULL,
    max_storage_mb integer NOT NULL,
    max_orders_per_month integer NOT NULL,
    max_factories integer NOT NULL,
    max_machines integer NOT NULL,
    max_projects integer NOT NULL,
    features json NOT NULL,
    is_default boolean NOT NULL,
    is_custom boolean NOT NULL,
    is_active boolean NOT NULL,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL
);


--
-- Name: subscription_plans_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.subscription_plans_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: subscription_plans_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.subscription_plans_id_seq OWNED BY public.subscription_plans.id;


--
-- Name: transfer_order_approvers; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.transfer_order_approvers (
    id integer NOT NULL,
    workspace_id integer NOT NULL,
    transfer_order_id integer NOT NULL,
    user_id integer NOT NULL,
    assigned_by integer,
    assigned_at timestamp without time zone NOT NULL,
    approved boolean DEFAULT false NOT NULL,
    approved_at timestamp without time zone
);


--
-- Name: transfer_order_approvers_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.transfer_order_approvers_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: transfer_order_approvers_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.transfer_order_approvers_id_seq OWNED BY public.transfer_order_approvers.id;


--
-- Name: transfer_order_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.transfer_order_events (
    id integer NOT NULL,
    workspace_id integer NOT NULL,
    transfer_order_id integer NOT NULL,
    event_type character varying(50) NOT NULL,
    description text NOT NULL,
    metadata json,
    performed_by integer,
    created_at timestamp without time zone NOT NULL
);


--
-- Name: transfer_order_events_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.transfer_order_events_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: transfer_order_events_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.transfer_order_events_id_seq OWNED BY public.transfer_order_events.id;


--
-- Name: transfer_order_items; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.transfer_order_items (
    id integer NOT NULL,
    workspace_id integer NOT NULL,
    transfer_order_id integer NOT NULL,
    line_number integer NOT NULL,
    item_id integer NOT NULL,
    quantity numeric(15,2) NOT NULL,
    approved boolean NOT NULL,
    approved_by integer,
    approved_at timestamp without time zone,
    transferred_by character varying(200),
    transferred_at timestamp without time zone,
    notes text
);


--
-- Name: transfer_order_items_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.transfer_order_items_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: transfer_order_items_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.transfer_order_items_id_seq OWNED BY public.transfer_order_items.id;


--
-- Name: transfer_orders; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.transfer_orders (
    id integer NOT NULL,
    workspace_id integer NOT NULL,
    transfer_number character varying(100) NOT NULL,
    source_location_type character varying(50) NOT NULL,
    source_location_id integer NOT NULL,
    destination_location_type character varying(50) NOT NULL,
    destination_location_id integer NOT NULL,
    current_status_id integer NOT NULL,
    description text,
    created_by integer NOT NULL,
    created_at timestamp without time zone NOT NULL,
    updated_by integer,
    updated_at timestamp without time zone,
    completed_by integer,
    completed_at timestamp without time zone,
    required_approvals integer
);


--
-- Name: transfer_orders_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.transfer_orders_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: transfer_orders_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.transfer_orders_id_seq OWNED BY public.transfer_orders.id;


--
-- Name: waitlist_signups; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.waitlist_signups (
    id integer NOT NULL,
    email character varying(320) NOT NULL,
    wants_product_updates boolean DEFAULT false NOT NULL,
    source character varying(64),
    ip_hash character varying(64),
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: waitlist_signups_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.waitlist_signups_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: waitlist_signups_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.waitlist_signups_id_seq OWNED BY public.waitlist_signups.id;


--
-- Name: work_order_approvers; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.work_order_approvers (
    id integer NOT NULL,
    workspace_id integer NOT NULL,
    work_order_id integer NOT NULL,
    user_id integer NOT NULL,
    assigned_by integer,
    assigned_at timestamp without time zone NOT NULL,
    approved boolean DEFAULT false NOT NULL,
    approved_at timestamp without time zone,
    approver_slot character varying(32)
);


--
-- Name: work_order_approvers_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.work_order_approvers_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: work_order_approvers_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.work_order_approvers_id_seq OWNED BY public.work_order_approvers.id;


--
-- Name: work_order_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.work_order_events (
    id integer NOT NULL,
    workspace_id integer NOT NULL,
    work_order_id integer NOT NULL,
    event_type character varying(50) NOT NULL,
    description text NOT NULL,
    metadata json,
    performed_by integer,
    created_at timestamp without time zone NOT NULL
);


--
-- Name: work_order_events_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.work_order_events_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: work_order_events_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.work_order_events_id_seq OWNED BY public.work_order_events.id;


--
-- Name: work_order_items; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.work_order_items (
    id integer NOT NULL,
    workspace_id integer NOT NULL,
    work_order_id integer NOT NULL,
    item_id integer NOT NULL,
    quantity numeric(15,2) NOT NULL,
    notes text,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    created_by integer,
    uses_inventory boolean DEFAULT false NOT NULL,
    source_location_type character varying(20),
    source_location_id integer,
    consumed_at timestamp without time zone,
    consumed_by integer,
    unit_cost numeric(15,2),
    total_cost numeric(15,2),
    updated_at timestamp without time zone,
    updated_by integer,
    action_type character varying(20) DEFAULT 'CONSUME'::character varying NOT NULL,
    replaced_item_id integer,
    is_deleted boolean DEFAULT false NOT NULL,
    deleted_at timestamp without time zone,
    deleted_by integer
);


--
-- Name: work_order_items_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.work_order_items_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: work_order_items_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.work_order_items_id_seq OWNED BY public.work_order_items.id;


--
-- Name: work_order_template_approvers; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.work_order_template_approvers (
    id integer NOT NULL,
    workspace_id integer NOT NULL,
    work_order_template_id integer NOT NULL,
    user_id integer NOT NULL,
    approver_slot character varying(32)
);


--
-- Name: work_order_template_approvers_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.work_order_template_approvers_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: work_order_template_approvers_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.work_order_template_approvers_id_seq OWNED BY public.work_order_template_approvers.id;


--
-- Name: work_order_template_items; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.work_order_template_items (
    id integer NOT NULL,
    workspace_id integer NOT NULL,
    work_order_template_id integer NOT NULL,
    item_id integer NOT NULL,
    quantity numeric(15,2) DEFAULT '1'::numeric NOT NULL,
    action_type character varying(20) DEFAULT 'CONSUME'::character varying NOT NULL,
    replaced_item_id integer,
    notes text
);


--
-- Name: work_order_template_items_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.work_order_template_items_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: work_order_template_items_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.work_order_template_items_id_seq OWNED BY public.work_order_template_items.id;


--
-- Name: work_order_templates; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.work_order_templates (
    id integer NOT NULL,
    workspace_id integer NOT NULL,
    template_name character varying(255) NOT NULL,
    description text,
    work_order_type_id integer NOT NULL,
    priority character varying(20) DEFAULT 'MEDIUM'::character varying NOT NULL,
    assigned_to character varying(255),
    uses_inventory boolean DEFAULT false NOT NULL,
    account_id integer,
    cost numeric(15,2),
    requires_approval boolean DEFAULT false NOT NULL,
    notes text,
    is_active boolean DEFAULT true NOT NULL,
    created_by integer,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_by integer,
    updated_at timestamp without time zone,
    is_recurring boolean DEFAULT false NOT NULL,
    recurrence_type character varying(50),
    recurrence_day integer,
    next_generation_date date,
    auto_generate boolean DEFAULT false NOT NULL,
    default_factory_section_id integer,
    default_machine_id integer,
    recurrence_start_date date,
    recurrence_end_date date
);


--
-- Name: work_order_templates_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.work_order_templates_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: work_order_templates_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.work_order_templates_id_seq OWNED BY public.work_order_templates.id;


--
-- Name: work_order_types; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.work_order_types (
    id integer NOT NULL,
    workspace_id integer NOT NULL,
    name character varying NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    created_by integer,
    updated_at timestamp without time zone,
    updated_by integer,
    is_active boolean DEFAULT true NOT NULL,
    is_deleted boolean DEFAULT false NOT NULL,
    deleted_at timestamp without time zone,
    deleted_by integer
);


--
-- Name: work_order_types_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.work_order_types_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: work_order_types_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.work_order_types_id_seq OWNED BY public.work_order_types.id;


--
-- Name: work_orders; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.work_orders (
    id integer NOT NULL,
    workspace_id integer NOT NULL,
    work_order_number character varying(50) NOT NULL,
    title character varying(255) NOT NULL,
    description text,
    priority public.workorderpriorityenum NOT NULL,
    status character varying(20) NOT NULL,
    factory_id integer NOT NULL,
    machine_id integer,
    project_component_id integer,
    planned_date date,
    end_date date,
    cost numeric(15,2),
    assigned_to character varying(255),
    completion_notes text,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    created_by integer,
    updated_at timestamp without time zone,
    updated_by integer,
    is_active boolean NOT NULL,
    is_deleted boolean NOT NULL,
    deleted_at timestamp without time zone,
    deleted_by integer,
    required_approvals integer,
    approved_by integer,
    approved_at timestamp without time zone,
    started_by integer,
    started_at timestamp without time zone,
    completed_by integer,
    completed_at timestamp without time zone,
    void_note text,
    voided_at timestamp without time zone,
    voided_by integer,
    account_id integer,
    invoice_id integer,
    work_order_type_id integer NOT NULL,
    uses_inventory boolean DEFAULT true NOT NULL,
    work_order_template_id integer
);


--
-- Name: work_orders_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.work_orders_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: work_orders_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.work_orders_id_seq OWNED BY public.work_orders.id;


--
-- Name: workspace_audit_logs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.workspace_audit_logs (
    id integer NOT NULL,
    workspace_id integer,
    user_id integer,
    action character varying(100) NOT NULL,
    resource_type character varying(50),
    resource_id integer,
    ip_address character varying(45),
    user_agent text,
    metadata json,
    created_at timestamp without time zone NOT NULL
);


--
-- Name: workspace_audit_logs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.workspace_audit_logs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: workspace_audit_logs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.workspace_audit_logs_id_seq OWNED BY public.workspace_audit_logs.id;


--
-- Name: workspace_invitations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.workspace_invitations (
    id integer NOT NULL,
    workspace_id integer NOT NULL,
    email character varying(255) NOT NULL,
    role character varying(50) NOT NULL,
    "position" character varying(255),
    invited_by_user_id integer,
    token character varying(255) NOT NULL,
    status character varying(50) NOT NULL,
    invited_at timestamp without time zone NOT NULL,
    expires_at timestamp without time zone NOT NULL,
    accepted_at timestamp without time zone,
    accepted_by_user_id integer
);


--
-- Name: workspace_invitations_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.workspace_invitations_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: workspace_invitations_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.workspace_invitations_id_seq OWNED BY public.workspace_invitations.id;


--
-- Name: workspace_members; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.workspace_members (
    id integer NOT NULL,
    workspace_id integer NOT NULL,
    user_id integer NOT NULL,
    role character varying(50) NOT NULL,
    "position" character varying(255),
    invited_by_user_id integer,
    invited_at timestamp without time zone NOT NULL,
    joined_at timestamp without time zone,
    status character varying(50) NOT NULL,
    left_at timestamp without time zone,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL
);


--
-- Name: workspace_members_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.workspace_members_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: workspace_members_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.workspace_members_id_seq OWNED BY public.workspace_members.id;


--
-- Name: workspaces; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.workspaces (
    id integer NOT NULL,
    name character varying(255) NOT NULL,
    slug character varying(100) NOT NULL,
    owner_user_id integer,
    created_by_user_id integer,
    subscription_plan_id integer NOT NULL,
    subscription_status character varying(50) NOT NULL,
    trial_ends_at timestamp without time zone,
    subscription_started_at timestamp without time zone,
    subscription_ends_at timestamp without time zone,
    billing_cycle character varying(20),
    billing_email character varying(255),
    stripe_customer_id character varying(255),
    stripe_subscription_id character varying(255),
    current_members_count integer NOT NULL,
    current_storage_mb integer NOT NULL,
    current_orders_this_month integer NOT NULL,
    current_factories_count integer NOT NULL,
    current_machines_count integer NOT NULL,
    current_projects_count integer NOT NULL,
    last_usage_reset_at timestamp without time zone NOT NULL,
    settings json NOT NULL,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL
);


--
-- Name: workspaces_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.workspaces_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: workspaces_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.workspaces_id_seq OWNED BY public.workspaces.id;


--
-- Name: access_control id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.access_control ALTER COLUMN id SET DEFAULT nextval('public.access_control_id_seq'::regclass);


--
-- Name: account_invoices id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.account_invoices ALTER COLUMN id SET DEFAULT nextval('public.account_invoices_id_seq'::regclass);


--
-- Name: account_tag_assignments id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.account_tag_assignments ALTER COLUMN id SET DEFAULT nextval('public.account_tag_assignments_id_seq'::regclass);


--
-- Name: account_tags id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.account_tags ALTER COLUMN id SET DEFAULT nextval('public.account_tags_id_seq'::regclass);


--
-- Name: accounts id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.accounts ALTER COLUMN id SET DEFAULT nextval('public.accounts_id_seq'::regclass);


--
-- Name: app_settings id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.app_settings ALTER COLUMN id SET DEFAULT nextval('public.app_settings_id_seq'::regclass);


--
-- Name: attachments id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.attachments ALTER COLUMN id SET DEFAULT nextval('public.attachments_id_seq'::regclass);


--
-- Name: delivery_methods id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.delivery_methods ALTER COLUMN id SET DEFAULT nextval('public.delivery_methods_id_seq'::regclass);


--
-- Name: departments id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.departments ALTER COLUMN id SET DEFAULT nextval('public.departments_id_seq'::regclass);


--
-- Name: discussions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.discussions ALTER COLUMN id SET DEFAULT nextval('public.discussions_id_seq'::regclass);


--
-- Name: expense_order_approvers id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.expense_order_approvers ALTER COLUMN id SET DEFAULT nextval('public.expense_order_approvers_id_seq'::regclass);


--
-- Name: expense_order_events id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.expense_order_events ALTER COLUMN id SET DEFAULT nextval('public.expense_order_events_id_seq'::regclass);


--
-- Name: expense_order_items id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.expense_order_items ALTER COLUMN id SET DEFAULT nextval('public.expense_order_items_id_seq'::regclass);


--
-- Name: expense_orders id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.expense_orders ALTER COLUMN id SET DEFAULT nextval('public.expense_orders_id_seq'::regclass);


--
-- Name: factories id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.factories ALTER COLUMN id SET DEFAULT nextval('public.factories_id_seq'::regclass);


--
-- Name: factory_sections id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.factory_sections ALTER COLUMN id SET DEFAULT nextval('public.factory_sections_id_seq'::regclass);


--
-- Name: financial_audit_logs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.financial_audit_logs ALTER COLUMN id SET DEFAULT nextval('public.financial_audit_logs_id_seq'::regclass);


--
-- Name: inventory id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.inventory ALTER COLUMN id SET DEFAULT nextval('public.inventory_id_seq'::regclass);


--
-- Name: inventory_ledger id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.inventory_ledger ALTER COLUMN id SET DEFAULT nextval('public.inventory_ledger_id_seq'::regclass);


--
-- Name: invoice_events id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invoice_events ALTER COLUMN id SET DEFAULT nextval('public.invoice_events_id_seq'::regclass);


--
-- Name: invoice_items id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invoice_items ALTER COLUMN id SET DEFAULT nextval('public.invoice_items_id_seq'::regclass);


--
-- Name: invoice_payments id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invoice_payments ALTER COLUMN id SET DEFAULT nextval('public.invoice_payments_id_seq'::regclass);


--
-- Name: invoice_status_tracker id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invoice_status_tracker ALTER COLUMN id SET DEFAULT nextval('public.invoice_status_tracker_id_seq'::regclass);


--
-- Name: item_tag_assignments id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.item_tag_assignments ALTER COLUMN id SET DEFAULT nextval('public.item_tag_assignments_id_seq'::regclass);


--
-- Name: item_tags id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.item_tags ALTER COLUMN id SET DEFAULT nextval('public.item_tags_id_seq'::regclass);


--
-- Name: items id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.items ALTER COLUMN id SET DEFAULT nextval('public.items_id_seq'::regclass);


--
-- Name: machine_activity_events id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.machine_activity_events ALTER COLUMN id SET DEFAULT nextval('public.machine_activity_events_id_seq'::regclass);


--
-- Name: machine_item_ledger id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.machine_item_ledger ALTER COLUMN id SET DEFAULT nextval('public.machine_item_ledger_id_seq'::regclass);


--
-- Name: machine_items id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.machine_items ALTER COLUMN id SET DEFAULT nextval('public.machine_items_id_seq'::regclass);


--
-- Name: machine_maintenance_logs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.machine_maintenance_logs ALTER COLUMN id SET DEFAULT nextval('public.machine_maintenance_logs_id_seq'::regclass);


--
-- Name: machine_section_assignments id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.machine_section_assignments ALTER COLUMN id SET DEFAULT nextval('public.machine_section_assignments_id_seq'::regclass);


--
-- Name: machines id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.machines ALTER COLUMN id SET DEFAULT nextval('public.machines_id_seq'::regclass);


--
-- Name: miscellaneous_project_costs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.miscellaneous_project_costs ALTER COLUMN id SET DEFAULT nextval('public.miscellaneous_project_costs_id_seq'::regclass);


--
-- Name: notifications id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notifications ALTER COLUMN id SET DEFAULT nextval('public.notifications_id_seq'::regclass);


--
-- Name: order_template_items id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.order_template_items ALTER COLUMN id SET DEFAULT nextval('public.order_template_items_id_seq'::regclass);


--
-- Name: order_templates id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.order_templates ALTER COLUMN id SET DEFAULT nextval('public.order_templates_id_seq'::regclass);


--
-- Name: order_workflows id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.order_workflows ALTER COLUMN id SET DEFAULT nextval('public.order_workflows_id_seq'::regclass);


--
-- Name: payment_transaction_events id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payment_transaction_events ALTER COLUMN id SET DEFAULT nextval('public.payment_transaction_events_id_seq'::regclass);


--
-- Name: payment_transactions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payment_transactions ALTER COLUMN id SET DEFAULT nextval('public.payment_transactions_id_seq'::regclass);


--
-- Name: po_receive_event_items id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.po_receive_event_items ALTER COLUMN id SET DEFAULT nextval('public.po_receive_event_items_id_seq'::regclass);


--
-- Name: po_receive_events id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.po_receive_events ALTER COLUMN id SET DEFAULT nextval('public.po_receive_events_id_seq'::regclass);


--
-- Name: product_ledger id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.product_ledger ALTER COLUMN id SET DEFAULT nextval('public.product_ledger_id_seq'::regclass);


--
-- Name: production_batch_items id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.production_batch_items ALTER COLUMN id SET DEFAULT nextval('public.production_batch_items_id_seq'::regclass);


--
-- Name: production_batch_stage_logs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.production_batch_stage_logs ALTER COLUMN id SET DEFAULT nextval('public.production_batch_stage_logs_id_seq'::regclass);


--
-- Name: production_batches id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.production_batches ALTER COLUMN id SET DEFAULT nextval('public.production_batches_id_seq'::regclass);


--
-- Name: production_formula_items id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.production_formula_items ALTER COLUMN id SET DEFAULT nextval('public.production_formula_items_id_seq'::regclass);


--
-- Name: production_formula_stages id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.production_formula_stages ALTER COLUMN id SET DEFAULT nextval('public.production_formula_stages_id_seq'::regclass);


--
-- Name: production_formulas id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.production_formulas ALTER COLUMN id SET DEFAULT nextval('public.production_formulas_id_seq'::regclass);


--
-- Name: production_lines id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.production_lines ALTER COLUMN id SET DEFAULT nextval('public.production_lines_id_seq'::regclass);


--
-- Name: products id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.products ALTER COLUMN id SET DEFAULT nextval('public.products_id_seq'::regclass);


--
-- Name: profiles id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.profiles ALTER COLUMN id SET DEFAULT nextval('public.profiles_id_seq'::regclass);


--
-- Name: project_attachments id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_attachments ALTER COLUMN id SET DEFAULT nextval('public.project_attachments_id_seq'::regclass);


--
-- Name: project_component_activity_events id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_component_activity_events ALTER COLUMN id SET DEFAULT nextval('public.project_component_activity_events_id_seq'::regclass);


--
-- Name: project_component_attachments id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_component_attachments ALTER COLUMN id SET DEFAULT nextval('public.project_component_attachments_id_seq'::regclass);


--
-- Name: project_component_item_ledger id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_component_item_ledger ALTER COLUMN id SET DEFAULT nextval('public.project_component_item_ledger_id_seq'::regclass);


--
-- Name: project_component_items id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_component_items ALTER COLUMN id SET DEFAULT nextval('public.project_component_items_id_seq'::regclass);


--
-- Name: project_component_tasks id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_component_tasks ALTER COLUMN id SET DEFAULT nextval('public.project_component_tasks_id_seq'::regclass);


--
-- Name: project_components id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_components ALTER COLUMN id SET DEFAULT nextval('public.project_components_id_seq'::regclass);


--
-- Name: project_events id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_events ALTER COLUMN id SET DEFAULT nextval('public.project_events_id_seq'::regclass);


--
-- Name: project_members id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_members ALTER COLUMN id SET DEFAULT nextval('public.project_members_id_seq'::regclass);


--
-- Name: projects id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.projects ALTER COLUMN id SET DEFAULT nextval('public.projects_id_seq'::regclass);


--
-- Name: purchase_order_approvers id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.purchase_order_approvers ALTER COLUMN id SET DEFAULT nextval('public.purchase_order_approvers_id_seq'::regclass);


--
-- Name: purchase_order_events id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.purchase_order_events ALTER COLUMN id SET DEFAULT nextval('public.purchase_order_events_id_seq'::regclass);


--
-- Name: purchase_order_items id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.purchase_order_items ALTER COLUMN id SET DEFAULT nextval('public.purchase_order_items_id_seq'::regclass);


--
-- Name: purchase_orders id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.purchase_orders ALTER COLUMN id SET DEFAULT nextval('public.purchase_orders_id_seq'::regclass);


--
-- Name: refresh_tokens id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.refresh_tokens ALTER COLUMN id SET DEFAULT nextval('public.refresh_tokens_id_seq'::regclass);


--
-- Name: sales_deliveries id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sales_deliveries ALTER COLUMN id SET DEFAULT nextval('public.sales_deliveries_id_seq'::regclass);


--
-- Name: sales_delivery_items id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sales_delivery_items ALTER COLUMN id SET DEFAULT nextval('public.sales_delivery_items_id_seq'::regclass);


--
-- Name: sales_order_items id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sales_order_items ALTER COLUMN id SET DEFAULT nextval('public.sales_order_items_id_seq'::regclass);


--
-- Name: sales_orders id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sales_orders ALTER COLUMN id SET DEFAULT nextval('public.sales_orders_id_seq'::regclass);


--
-- Name: statuses id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.statuses ALTER COLUMN id SET DEFAULT nextval('public.statuses_id_seq'::regclass);


--
-- Name: subscription_plans id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.subscription_plans ALTER COLUMN id SET DEFAULT nextval('public.subscription_plans_id_seq'::regclass);


--
-- Name: transfer_order_approvers id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transfer_order_approvers ALTER COLUMN id SET DEFAULT nextval('public.transfer_order_approvers_id_seq'::regclass);


--
-- Name: transfer_order_events id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transfer_order_events ALTER COLUMN id SET DEFAULT nextval('public.transfer_order_events_id_seq'::regclass);


--
-- Name: transfer_order_items id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transfer_order_items ALTER COLUMN id SET DEFAULT nextval('public.transfer_order_items_id_seq'::regclass);


--
-- Name: transfer_orders id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transfer_orders ALTER COLUMN id SET DEFAULT nextval('public.transfer_orders_id_seq'::regclass);


--
-- Name: waitlist_signups id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.waitlist_signups ALTER COLUMN id SET DEFAULT nextval('public.waitlist_signups_id_seq'::regclass);


--
-- Name: work_order_approvers id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_order_approvers ALTER COLUMN id SET DEFAULT nextval('public.work_order_approvers_id_seq'::regclass);


--
-- Name: work_order_events id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_order_events ALTER COLUMN id SET DEFAULT nextval('public.work_order_events_id_seq'::regclass);


--
-- Name: work_order_items id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_order_items ALTER COLUMN id SET DEFAULT nextval('public.work_order_items_id_seq'::regclass);


--
-- Name: work_order_template_approvers id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_order_template_approvers ALTER COLUMN id SET DEFAULT nextval('public.work_order_template_approvers_id_seq'::regclass);


--
-- Name: work_order_template_items id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_order_template_items ALTER COLUMN id SET DEFAULT nextval('public.work_order_template_items_id_seq'::regclass);


--
-- Name: work_order_templates id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_order_templates ALTER COLUMN id SET DEFAULT nextval('public.work_order_templates_id_seq'::regclass);


--
-- Name: work_order_types id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_order_types ALTER COLUMN id SET DEFAULT nextval('public.work_order_types_id_seq'::regclass);


--
-- Name: work_orders id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_orders ALTER COLUMN id SET DEFAULT nextval('public.work_orders_id_seq'::regclass);


--
-- Name: workspace_audit_logs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.workspace_audit_logs ALTER COLUMN id SET DEFAULT nextval('public.workspace_audit_logs_id_seq'::regclass);


--
-- Name: workspace_invitations id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.workspace_invitations ALTER COLUMN id SET DEFAULT nextval('public.workspace_invitations_id_seq'::regclass);


--
-- Name: workspace_members id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.workspace_members ALTER COLUMN id SET DEFAULT nextval('public.workspace_members_id_seq'::regclass);


--
-- Name: workspaces id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.workspaces ALTER COLUMN id SET DEFAULT nextval('public.workspaces_id_seq'::regclass);


--
-- Name: access_control access_control_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.access_control
    ADD CONSTRAINT access_control_pkey PRIMARY KEY (id);


--
-- Name: account_invoices account_invoices_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.account_invoices
    ADD CONSTRAINT account_invoices_pkey PRIMARY KEY (id);


--
-- Name: account_tag_assignments account_tag_assignments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.account_tag_assignments
    ADD CONSTRAINT account_tag_assignments_pkey PRIMARY KEY (id);


--
-- Name: account_tags account_tags_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.account_tags
    ADD CONSTRAINT account_tags_pkey PRIMARY KEY (id);


--
-- Name: accounts accounts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.accounts
    ADD CONSTRAINT accounts_pkey PRIMARY KEY (id);


--
-- Name: app_settings app_settings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.app_settings
    ADD CONSTRAINT app_settings_pkey PRIMARY KEY (id);


--
-- Name: attachments attachments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.attachments
    ADD CONSTRAINT attachments_pkey PRIMARY KEY (id);


--
-- Name: delivery_methods delivery_methods_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.delivery_methods
    ADD CONSTRAINT delivery_methods_pkey PRIMARY KEY (id);


--
-- Name: departments departments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.departments
    ADD CONSTRAINT departments_pkey PRIMARY KEY (id);


--
-- Name: discussions discussions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.discussions
    ADD CONSTRAINT discussions_pkey PRIMARY KEY (id);


--
-- Name: expense_order_approvers expense_order_approvers_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.expense_order_approvers
    ADD CONSTRAINT expense_order_approvers_pkey PRIMARY KEY (id);


--
-- Name: expense_order_events expense_order_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.expense_order_events
    ADD CONSTRAINT expense_order_events_pkey PRIMARY KEY (id);


--
-- Name: expense_order_items expense_order_items_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.expense_order_items
    ADD CONSTRAINT expense_order_items_pkey PRIMARY KEY (id);


--
-- Name: expense_orders expense_orders_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.expense_orders
    ADD CONSTRAINT expense_orders_pkey PRIMARY KEY (id);


--
-- Name: factories factories_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.factories
    ADD CONSTRAINT factories_pkey PRIMARY KEY (id);


--
-- Name: factory_sections factory_sections_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.factory_sections
    ADD CONSTRAINT factory_sections_pkey PRIMARY KEY (id);


--
-- Name: financial_audit_logs financial_audit_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.financial_audit_logs
    ADD CONSTRAINT financial_audit_logs_pkey PRIMARY KEY (id);


--
-- Name: inventory_ledger inventory_ledger_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.inventory_ledger
    ADD CONSTRAINT inventory_ledger_pkey PRIMARY KEY (id);


--
-- Name: inventory inventory_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.inventory
    ADD CONSTRAINT inventory_pkey PRIMARY KEY (id);


--
-- Name: invoice_events invoice_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invoice_events
    ADD CONSTRAINT invoice_events_pkey PRIMARY KEY (id);


--
-- Name: invoice_items invoice_items_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invoice_items
    ADD CONSTRAINT invoice_items_pkey PRIMARY KEY (id);


--
-- Name: invoice_payments invoice_payments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invoice_payments
    ADD CONSTRAINT invoice_payments_pkey PRIMARY KEY (id);


--
-- Name: invoice_status_tracker invoice_status_tracker_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invoice_status_tracker
    ADD CONSTRAINT invoice_status_tracker_pkey PRIMARY KEY (id);


--
-- Name: item_tag_assignments item_tag_assignments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.item_tag_assignments
    ADD CONSTRAINT item_tag_assignments_pkey PRIMARY KEY (id);


--
-- Name: item_tags item_tags_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.item_tags
    ADD CONSTRAINT item_tags_pkey PRIMARY KEY (id);


--
-- Name: items items_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.items
    ADD CONSTRAINT items_pkey PRIMARY KEY (id);


--
-- Name: machine_activity_events machine_activity_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.machine_activity_events
    ADD CONSTRAINT machine_activity_events_pkey PRIMARY KEY (id);


--
-- Name: machine_item_ledger machine_item_ledger_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.machine_item_ledger
    ADD CONSTRAINT machine_item_ledger_pkey PRIMARY KEY (id);


--
-- Name: machine_items machine_items_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.machine_items
    ADD CONSTRAINT machine_items_pkey PRIMARY KEY (id);


--
-- Name: machine_maintenance_logs machine_maintenance_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.machine_maintenance_logs
    ADD CONSTRAINT machine_maintenance_logs_pkey PRIMARY KEY (id);


--
-- Name: machine_section_assignments machine_section_assignments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.machine_section_assignments
    ADD CONSTRAINT machine_section_assignments_pkey PRIMARY KEY (id);


--
-- Name: machines machines_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.machines
    ADD CONSTRAINT machines_pkey PRIMARY KEY (id);


--
-- Name: miscellaneous_project_costs miscellaneous_project_costs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.miscellaneous_project_costs
    ADD CONSTRAINT miscellaneous_project_costs_pkey PRIMARY KEY (id);


--
-- Name: notifications notifications_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notifications
    ADD CONSTRAINT notifications_pkey PRIMARY KEY (id);


--
-- Name: order_template_items order_template_items_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.order_template_items
    ADD CONSTRAINT order_template_items_pkey PRIMARY KEY (id);


--
-- Name: order_templates order_templates_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.order_templates
    ADD CONSTRAINT order_templates_pkey PRIMARY KEY (id);


--
-- Name: order_workflows order_workflows_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.order_workflows
    ADD CONSTRAINT order_workflows_pkey PRIMARY KEY (id);


--
-- Name: payment_transaction_events payment_transaction_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payment_transaction_events
    ADD CONSTRAINT payment_transaction_events_pkey PRIMARY KEY (id);


--
-- Name: payment_transactions payment_transactions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payment_transactions
    ADD CONSTRAINT payment_transactions_pkey PRIMARY KEY (id);


--
-- Name: payment_transactions payment_transactions_tran_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payment_transactions
    ADD CONSTRAINT payment_transactions_tran_id_key UNIQUE (tran_id);


--
-- Name: po_receive_event_items po_receive_event_items_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.po_receive_event_items
    ADD CONSTRAINT po_receive_event_items_pkey PRIMARY KEY (id);


--
-- Name: po_receive_events po_receive_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.po_receive_events
    ADD CONSTRAINT po_receive_events_pkey PRIMARY KEY (id);


--
-- Name: product_ledger product_ledger_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.product_ledger
    ADD CONSTRAINT product_ledger_pkey PRIMARY KEY (id);


--
-- Name: production_batch_items production_batch_items_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.production_batch_items
    ADD CONSTRAINT production_batch_items_pkey PRIMARY KEY (id);


--
-- Name: production_batch_stage_logs production_batch_stage_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.production_batch_stage_logs
    ADD CONSTRAINT production_batch_stage_logs_pkey PRIMARY KEY (id);


--
-- Name: production_batches production_batches_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.production_batches
    ADD CONSTRAINT production_batches_pkey PRIMARY KEY (id);


--
-- Name: production_formula_items production_formula_items_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.production_formula_items
    ADD CONSTRAINT production_formula_items_pkey PRIMARY KEY (id);


--
-- Name: production_formula_stages production_formula_stages_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.production_formula_stages
    ADD CONSTRAINT production_formula_stages_pkey PRIMARY KEY (id);


--
-- Name: production_formulas production_formulas_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.production_formulas
    ADD CONSTRAINT production_formulas_pkey PRIMARY KEY (id);


--
-- Name: production_lines production_lines_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.production_lines
    ADD CONSTRAINT production_lines_pkey PRIMARY KEY (id);


--
-- Name: products products_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.products
    ADD CONSTRAINT products_pkey PRIMARY KEY (id);


--
-- Name: profiles profiles_email_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.profiles
    ADD CONSTRAINT profiles_email_key UNIQUE (email);


--
-- Name: profiles profiles_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.profiles
    ADD CONSTRAINT profiles_pkey PRIMARY KEY (id);


--
-- Name: profiles profiles_user_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.profiles
    ADD CONSTRAINT profiles_user_id_key UNIQUE (user_id);


--
-- Name: project_attachments project_attachments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_attachments
    ADD CONSTRAINT project_attachments_pkey PRIMARY KEY (id);


--
-- Name: project_component_activity_events project_component_activity_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_component_activity_events
    ADD CONSTRAINT project_component_activity_events_pkey PRIMARY KEY (id);


--
-- Name: project_component_attachments project_component_attachments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_component_attachments
    ADD CONSTRAINT project_component_attachments_pkey PRIMARY KEY (id);


--
-- Name: project_component_item_ledger project_component_item_ledger_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_component_item_ledger
    ADD CONSTRAINT project_component_item_ledger_pkey PRIMARY KEY (id);


--
-- Name: project_component_items project_component_items_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_component_items
    ADD CONSTRAINT project_component_items_pkey PRIMARY KEY (id);


--
-- Name: project_component_tasks project_component_tasks_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_component_tasks
    ADD CONSTRAINT project_component_tasks_pkey PRIMARY KEY (id);


--
-- Name: project_components project_components_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_components
    ADD CONSTRAINT project_components_pkey PRIMARY KEY (id);


--
-- Name: project_events project_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_events
    ADD CONSTRAINT project_events_pkey PRIMARY KEY (id);


--
-- Name: project_members project_members_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_members
    ADD CONSTRAINT project_members_pkey PRIMARY KEY (id);


--
-- Name: projects projects_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.projects
    ADD CONSTRAINT projects_pkey PRIMARY KEY (id);


--
-- Name: purchase_order_approvers purchase_order_approvers_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.purchase_order_approvers
    ADD CONSTRAINT purchase_order_approvers_pkey PRIMARY KEY (id);


--
-- Name: purchase_order_events purchase_order_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.purchase_order_events
    ADD CONSTRAINT purchase_order_events_pkey PRIMARY KEY (id);


--
-- Name: purchase_order_items purchase_order_items_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.purchase_order_items
    ADD CONSTRAINT purchase_order_items_pkey PRIMARY KEY (id);


--
-- Name: purchase_orders purchase_orders_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.purchase_orders
    ADD CONSTRAINT purchase_orders_pkey PRIMARY KEY (id);


--
-- Name: refresh_tokens refresh_tokens_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.refresh_tokens
    ADD CONSTRAINT refresh_tokens_pkey PRIMARY KEY (id);


--
-- Name: sales_deliveries sales_deliveries_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sales_deliveries
    ADD CONSTRAINT sales_deliveries_pkey PRIMARY KEY (id);


--
-- Name: sales_delivery_items sales_delivery_items_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sales_delivery_items
    ADD CONSTRAINT sales_delivery_items_pkey PRIMARY KEY (id);


--
-- Name: sales_order_items sales_order_items_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sales_order_items
    ADD CONSTRAINT sales_order_items_pkey PRIMARY KEY (id);


--
-- Name: sales_orders sales_orders_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sales_orders
    ADD CONSTRAINT sales_orders_pkey PRIMARY KEY (id);


--
-- Name: statuses statuses_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.statuses
    ADD CONSTRAINT statuses_pkey PRIMARY KEY (id);


--
-- Name: subscription_plans subscription_plans_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.subscription_plans
    ADD CONSTRAINT subscription_plans_pkey PRIMARY KEY (id);


--
-- Name: transfer_order_approvers transfer_order_approvers_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transfer_order_approvers
    ADD CONSTRAINT transfer_order_approvers_pkey PRIMARY KEY (id);


--
-- Name: transfer_order_events transfer_order_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transfer_order_events
    ADD CONSTRAINT transfer_order_events_pkey PRIMARY KEY (id);


--
-- Name: transfer_order_items transfer_order_items_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transfer_order_items
    ADD CONSTRAINT transfer_order_items_pkey PRIMARY KEY (id);


--
-- Name: transfer_orders transfer_orders_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transfer_orders
    ADD CONSTRAINT transfer_orders_pkey PRIMARY KEY (id);


--
-- Name: account_tag_assignments uq_account_tag; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.account_tag_assignments
    ADD CONSTRAINT uq_account_tag UNIQUE (account_id, tag_id);


--
-- Name: production_batches uq_batch_workspace_number; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.production_batches
    ADD CONSTRAINT uq_batch_workspace_number UNIQUE (workspace_id, batch_number);


--
-- Name: expense_order_approvers uq_eo_approver_eo_user; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.expense_order_approvers
    ADD CONSTRAINT uq_eo_approver_eo_user UNIQUE (expense_order_id, user_id);


--
-- Name: expense_orders uq_eo_workspace_number; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.expense_orders
    ADD CONSTRAINT uq_eo_workspace_number UNIQUE (workspace_id, expense_number);


--
-- Name: production_formula_stages uq_formula_stage_order; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.production_formula_stages
    ADD CONSTRAINT uq_formula_stage_order UNIQUE (formula_id, stage_order);


--
-- Name: inventory uq_inventory_workspace_item_type_factory; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.inventory
    ADD CONSTRAINT uq_inventory_workspace_item_type_factory UNIQUE (workspace_id, item_id, inventory_type, factory_id);


--
-- Name: item_tag_assignments uq_item_tag; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.item_tag_assignments
    ADD CONSTRAINT uq_item_tag UNIQUE (item_id, tag_id);


--
-- Name: machine_section_assignments uq_machine_section_assignment_machine; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.machine_section_assignments
    ADD CONSTRAINT uq_machine_section_assignment_machine UNIQUE (machine_id);


--
-- Name: order_workflows uq_order_workflows_workspace_type; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.order_workflows
    ADD CONSTRAINT uq_order_workflows_workspace_type UNIQUE (workspace_id, type);


--
-- Name: purchase_order_approvers uq_po_approver_po_user; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.purchase_order_approvers
    ADD CONSTRAINT uq_po_approver_po_user UNIQUE (purchase_order_id, user_id);


--
-- Name: purchase_orders uq_po_workspace_number; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.purchase_orders
    ADD CONSTRAINT uq_po_workspace_number UNIQUE (workspace_id, po_number);


--
-- Name: products uq_product_workspace_item_factory_available; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.products
    ADD CONSTRAINT uq_product_workspace_item_factory_available UNIQUE (workspace_id, item_id, factory_id, is_available_for_sale);


--
-- Name: project_members uq_project_member_project_user; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_members
    ADD CONSTRAINT uq_project_member_project_user UNIQUE (project_id, user_id);


--
-- Name: transfer_order_approvers uq_to_approver_to_user; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transfer_order_approvers
    ADD CONSTRAINT uq_to_approver_to_user UNIQUE (transfer_order_id, user_id);


--
-- Name: work_order_approvers uq_wo_approver_wo_user; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_order_approvers
    ADD CONSTRAINT uq_wo_approver_wo_user UNIQUE (work_order_id, user_id);


--
-- Name: work_order_template_approvers uq_wo_template_approver; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_order_template_approvers
    ADD CONSTRAINT uq_wo_template_approver UNIQUE (work_order_template_id, user_id);


--
-- Name: work_order_types uq_wo_type_workspace_name; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_order_types
    ADD CONSTRAINT uq_wo_type_workspace_name UNIQUE (workspace_id, name);


--
-- Name: work_orders uq_wo_workspace_number; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_orders
    ADD CONSTRAINT uq_wo_workspace_number UNIQUE (workspace_id, work_order_number);


--
-- Name: workspace_members uq_workspace_user; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.workspace_members
    ADD CONSTRAINT uq_workspace_user UNIQUE (workspace_id, user_id);


--
-- Name: waitlist_signups waitlist_signups_email_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.waitlist_signups
    ADD CONSTRAINT waitlist_signups_email_key UNIQUE (email);


--
-- Name: waitlist_signups waitlist_signups_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.waitlist_signups
    ADD CONSTRAINT waitlist_signups_pkey PRIMARY KEY (id);


--
-- Name: work_order_approvers work_order_approvers_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_order_approvers
    ADD CONSTRAINT work_order_approvers_pkey PRIMARY KEY (id);


--
-- Name: work_order_events work_order_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_order_events
    ADD CONSTRAINT work_order_events_pkey PRIMARY KEY (id);


--
-- Name: work_order_items work_order_items_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_order_items
    ADD CONSTRAINT work_order_items_pkey PRIMARY KEY (id);


--
-- Name: work_order_template_approvers work_order_template_approvers_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_order_template_approvers
    ADD CONSTRAINT work_order_template_approvers_pkey PRIMARY KEY (id);


--
-- Name: work_order_template_items work_order_template_items_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_order_template_items
    ADD CONSTRAINT work_order_template_items_pkey PRIMARY KEY (id);


--
-- Name: work_order_templates work_order_templates_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_order_templates
    ADD CONSTRAINT work_order_templates_pkey PRIMARY KEY (id);


--
-- Name: work_order_types work_order_types_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_order_types
    ADD CONSTRAINT work_order_types_pkey PRIMARY KEY (id);


--
-- Name: work_orders work_orders_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_orders
    ADD CONSTRAINT work_orders_pkey PRIMARY KEY (id);


--
-- Name: workspace_audit_logs workspace_audit_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.workspace_audit_logs
    ADD CONSTRAINT workspace_audit_logs_pkey PRIMARY KEY (id);


--
-- Name: workspace_invitations workspace_invitations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.workspace_invitations
    ADD CONSTRAINT workspace_invitations_pkey PRIMARY KEY (id);


--
-- Name: workspace_members workspace_members_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.workspace_members
    ADD CONSTRAINT workspace_members_pkey PRIMARY KEY (id);


--
-- Name: workspaces workspaces_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.workspaces
    ADD CONSTRAINT workspaces_pkey PRIMARY KEY (id);


--
-- Name: ix_access_control_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_access_control_id ON public.access_control USING btree (id);


--
-- Name: ix_access_control_workspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_access_control_workspace_id ON public.access_control USING btree (workspace_id);


--
-- Name: ix_account_invoices_account_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_account_invoices_account_id ON public.account_invoices USING btree (account_id);


--
-- Name: ix_account_invoices_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_account_invoices_id ON public.account_invoices USING btree (id);


--
-- Name: ix_account_invoices_invoice_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_account_invoices_invoice_status ON public.account_invoices USING btree (invoice_status);


--
-- Name: ix_account_invoices_invoice_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_account_invoices_invoice_type ON public.account_invoices USING btree (invoice_type);


--
-- Name: ix_account_invoices_order_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_account_invoices_order_id ON public.account_invoices USING btree (order_id);


--
-- Name: ix_account_invoices_payment_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_account_invoices_payment_status ON public.account_invoices USING btree (payment_status);


--
-- Name: ix_account_invoices_workspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_account_invoices_workspace_id ON public.account_invoices USING btree (workspace_id);


--
-- Name: ix_account_tag_assignments_account_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_account_tag_assignments_account_id ON public.account_tag_assignments USING btree (account_id);


--
-- Name: ix_account_tag_assignments_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_account_tag_assignments_id ON public.account_tag_assignments USING btree (id);


--
-- Name: ix_account_tag_assignments_tag_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_account_tag_assignments_tag_id ON public.account_tag_assignments USING btree (tag_id);


--
-- Name: ix_account_tag_assignments_workspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_account_tag_assignments_workspace_id ON public.account_tag_assignments USING btree (workspace_id);


--
-- Name: ix_account_tags_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_account_tags_id ON public.account_tags USING btree (id);


--
-- Name: ix_account_tags_workspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_account_tags_workspace_id ON public.account_tags USING btree (workspace_id);


--
-- Name: ix_accounts_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_accounts_id ON public.accounts USING btree (id);


--
-- Name: ix_accounts_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_accounts_name ON public.accounts USING btree (name);


--
-- Name: ix_accounts_workspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_accounts_workspace_id ON public.accounts USING btree (workspace_id);


--
-- Name: ix_app_settings_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_app_settings_id ON public.app_settings USING btree (id);


--
-- Name: ix_app_settings_workspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_app_settings_workspace_id ON public.app_settings USING btree (workspace_id);


--
-- Name: ix_attachments_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_attachments_id ON public.attachments USING btree (id);


--
-- Name: ix_attachments_workspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_attachments_workspace_id ON public.attachments USING btree (workspace_id);


--
-- Name: ix_delivery_methods_workspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_delivery_methods_workspace_id ON public.delivery_methods USING btree (workspace_id);


--
-- Name: ix_departments_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_departments_id ON public.departments USING btree (id);


--
-- Name: ix_departments_workspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_departments_workspace_id ON public.departments USING btree (workspace_id);


--
-- Name: ix_discussions_entity; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_discussions_entity ON public.discussions USING btree (workspace_id, entity_type, entity_id);


--
-- Name: ix_discussions_parent_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_discussions_parent_id ON public.discussions USING btree (parent_id);


--
-- Name: ix_discussions_workspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_discussions_workspace_id ON public.discussions USING btree (workspace_id);


--
-- Name: ix_expense_order_approvers_expense_order_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_expense_order_approvers_expense_order_id ON public.expense_order_approvers USING btree (expense_order_id);


--
-- Name: ix_expense_order_approvers_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_expense_order_approvers_user_id ON public.expense_order_approvers USING btree (user_id);


--
-- Name: ix_expense_order_approvers_workspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_expense_order_approvers_workspace_id ON public.expense_order_approvers USING btree (workspace_id);


--
-- Name: ix_expense_order_events_expense_order_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_expense_order_events_expense_order_id ON public.expense_order_events USING btree (expense_order_id);


--
-- Name: ix_expense_order_events_workspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_expense_order_events_workspace_id ON public.expense_order_events USING btree (workspace_id);


--
-- Name: ix_expense_order_items_expense_order_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_expense_order_items_expense_order_id ON public.expense_order_items USING btree (expense_order_id);


--
-- Name: ix_expense_order_items_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_expense_order_items_id ON public.expense_order_items USING btree (id);


--
-- Name: ix_expense_order_items_workspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_expense_order_items_workspace_id ON public.expense_order_items USING btree (workspace_id);


--
-- Name: ix_expense_orders_account_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_expense_orders_account_id ON public.expense_orders USING btree (account_id);


--
-- Name: ix_expense_orders_created_by; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_expense_orders_created_by ON public.expense_orders USING btree (created_by);


--
-- Name: ix_expense_orders_expense_category; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_expense_orders_expense_category ON public.expense_orders USING btree (expense_category);


--
-- Name: ix_expense_orders_expense_number; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_expense_orders_expense_number ON public.expense_orders USING btree (expense_number);


--
-- Name: ix_expense_orders_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_expense_orders_id ON public.expense_orders USING btree (id);


--
-- Name: ix_expense_orders_invoice_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_expense_orders_invoice_id ON public.expense_orders USING btree (invoice_id);


--
-- Name: ix_expense_orders_order_template_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_expense_orders_order_template_id ON public.expense_orders USING btree (order_template_id);


--
-- Name: ix_expense_orders_workspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_expense_orders_workspace_id ON public.expense_orders USING btree (workspace_id);


--
-- Name: ix_factories_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_factories_id ON public.factories USING btree (id);


--
-- Name: ix_factories_workspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_factories_workspace_id ON public.factories USING btree (workspace_id);


--
-- Name: ix_factory_sections_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_factory_sections_id ON public.factory_sections USING btree (id);


--
-- Name: ix_factory_sections_workspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_factory_sections_workspace_id ON public.factory_sections USING btree (workspace_id);


--
-- Name: ix_financial_audit_logs_action_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_financial_audit_logs_action_type ON public.financial_audit_logs USING btree (action_type);


--
-- Name: ix_financial_audit_logs_entity_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_financial_audit_logs_entity_id ON public.financial_audit_logs USING btree (entity_id);


--
-- Name: ix_financial_audit_logs_entity_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_financial_audit_logs_entity_type ON public.financial_audit_logs USING btree (entity_type);


--
-- Name: ix_financial_audit_logs_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_financial_audit_logs_id ON public.financial_audit_logs USING btree (id);


--
-- Name: ix_financial_audit_logs_performed_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_financial_audit_logs_performed_at ON public.financial_audit_logs USING btree (performed_at);


--
-- Name: ix_financial_audit_logs_related_entity_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_financial_audit_logs_related_entity_id ON public.financial_audit_logs USING btree (related_entity_id);


--
-- Name: ix_financial_audit_logs_workspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_financial_audit_logs_workspace_id ON public.financial_audit_logs USING btree (workspace_id);


--
-- Name: ix_inventory_factory_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_inventory_factory_id ON public.inventory USING btree (factory_id);


--
-- Name: ix_inventory_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_inventory_id ON public.inventory USING btree (id);


--
-- Name: ix_inventory_inventory_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_inventory_inventory_type ON public.inventory USING btree (inventory_type);


--
-- Name: ix_inventory_item_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_inventory_item_id ON public.inventory USING btree (item_id);


--
-- Name: ix_inventory_ledger_factory_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_inventory_ledger_factory_id ON public.inventory_ledger USING btree (factory_id);


--
-- Name: ix_inventory_ledger_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_inventory_ledger_id ON public.inventory_ledger USING btree (id);


--
-- Name: ix_inventory_ledger_inventory_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_inventory_ledger_inventory_type ON public.inventory_ledger USING btree (inventory_type);


--
-- Name: ix_inventory_ledger_item_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_inventory_ledger_item_id ON public.inventory_ledger USING btree (item_id);


--
-- Name: ix_inventory_ledger_performed_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_inventory_ledger_performed_at ON public.inventory_ledger USING btree (performed_at);


--
-- Name: ix_inventory_ledger_performed_by; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_inventory_ledger_performed_by ON public.inventory_ledger USING btree (performed_by);


--
-- Name: ix_inventory_ledger_source_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_inventory_ledger_source_type ON public.inventory_ledger USING btree (source_type);


--
-- Name: ix_inventory_ledger_transaction_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_inventory_ledger_transaction_type ON public.inventory_ledger USING btree (transaction_type);


--
-- Name: ix_inventory_ledger_workspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_inventory_ledger_workspace_id ON public.inventory_ledger USING btree (workspace_id);


--
-- Name: ix_inventory_workspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_inventory_workspace_id ON public.inventory USING btree (workspace_id);


--
-- Name: ix_invoice_events_invoice_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_invoice_events_invoice_id ON public.invoice_events USING btree (invoice_id);


--
-- Name: ix_invoice_events_workspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_invoice_events_workspace_id ON public.invoice_events USING btree (workspace_id);


--
-- Name: ix_invoice_items_invoice_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_invoice_items_invoice_id ON public.invoice_items USING btree (invoice_id);


--
-- Name: ix_invoice_items_workspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_invoice_items_workspace_id ON public.invoice_items USING btree (workspace_id);


--
-- Name: ix_invoice_payments_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_invoice_payments_id ON public.invoice_payments USING btree (id);


--
-- Name: ix_invoice_payments_invoice_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_invoice_payments_invoice_id ON public.invoice_payments USING btree (invoice_id);


--
-- Name: ix_invoice_payments_payment_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_invoice_payments_payment_date ON public.invoice_payments USING btree (payment_date);


--
-- Name: ix_invoice_payments_workspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_invoice_payments_workspace_id ON public.invoice_payments USING btree (workspace_id);


--
-- Name: ix_invoice_status_tracker_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_invoice_status_tracker_id ON public.invoice_status_tracker USING btree (id);


--
-- Name: ix_invoice_status_tracker_invoice_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_invoice_status_tracker_invoice_id ON public.invoice_status_tracker USING btree (invoice_id);


--
-- Name: ix_invoice_status_tracker_workspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_invoice_status_tracker_workspace_id ON public.invoice_status_tracker USING btree (workspace_id);


--
-- Name: ix_item_tag_assignments_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_item_tag_assignments_id ON public.item_tag_assignments USING btree (id);


--
-- Name: ix_item_tag_assignments_item_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_item_tag_assignments_item_id ON public.item_tag_assignments USING btree (item_id);


--
-- Name: ix_item_tag_assignments_tag_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_item_tag_assignments_tag_id ON public.item_tag_assignments USING btree (tag_id);


--
-- Name: ix_item_tag_assignments_workspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_item_tag_assignments_workspace_id ON public.item_tag_assignments USING btree (workspace_id);


--
-- Name: ix_item_tags_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_item_tags_id ON public.item_tags USING btree (id);


--
-- Name: ix_item_tags_workspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_item_tags_workspace_id ON public.item_tags USING btree (workspace_id);


--
-- Name: ix_items_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_items_id ON public.items USING btree (id);


--
-- Name: ix_items_name_normalized_trgm; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_items_name_normalized_trgm ON public.items USING gin (name_normalized public.gin_trgm_ops);


--
-- Name: ix_items_workspace_active; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_items_workspace_active ON public.items USING btree (workspace_id, is_active);


--
-- Name: ix_items_workspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_items_workspace_id ON public.items USING btree (workspace_id);


--
-- Name: ix_machine_activity_events_machine_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_machine_activity_events_machine_id ON public.machine_activity_events USING btree (machine_id);


--
-- Name: ix_machine_activity_events_workspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_machine_activity_events_workspace_id ON public.machine_activity_events USING btree (workspace_id);


--
-- Name: ix_machine_item_ledger_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_machine_item_ledger_id ON public.machine_item_ledger USING btree (id);


--
-- Name: ix_machine_item_ledger_invoice_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_machine_item_ledger_invoice_id ON public.machine_item_ledger USING btree (invoice_id);


--
-- Name: ix_machine_item_ledger_item_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_machine_item_ledger_item_id ON public.machine_item_ledger USING btree (item_id);


--
-- Name: ix_machine_item_ledger_machine_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_machine_item_ledger_machine_id ON public.machine_item_ledger USING btree (machine_id);


--
-- Name: ix_machine_item_ledger_order_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_machine_item_ledger_order_id ON public.machine_item_ledger USING btree (order_id);


--
-- Name: ix_machine_item_ledger_performed_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_machine_item_ledger_performed_at ON public.machine_item_ledger USING btree (performed_at);


--
-- Name: ix_machine_item_ledger_performed_by; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_machine_item_ledger_performed_by ON public.machine_item_ledger USING btree (performed_by);


--
-- Name: ix_machine_item_ledger_source_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_machine_item_ledger_source_type ON public.machine_item_ledger USING btree (source_type);


--
-- Name: ix_machine_item_ledger_transaction_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_machine_item_ledger_transaction_type ON public.machine_item_ledger USING btree (transaction_type);


--
-- Name: ix_machine_item_ledger_workspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_machine_item_ledger_workspace_id ON public.machine_item_ledger USING btree (workspace_id);


--
-- Name: ix_machine_items_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_machine_items_id ON public.machine_items USING btree (id);


--
-- Name: ix_machine_items_item_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_machine_items_item_id ON public.machine_items USING btree (item_id);


--
-- Name: ix_machine_items_machine_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_machine_items_machine_id ON public.machine_items USING btree (machine_id);


--
-- Name: ix_machine_items_workspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_machine_items_workspace_id ON public.machine_items USING btree (workspace_id);


--
-- Name: ix_machine_maintenance_logs_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_machine_maintenance_logs_id ON public.machine_maintenance_logs USING btree (id);


--
-- Name: ix_machine_maintenance_logs_machine_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_machine_maintenance_logs_machine_id ON public.machine_maintenance_logs USING btree (machine_id);


--
-- Name: ix_machine_maintenance_logs_workspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_machine_maintenance_logs_workspace_id ON public.machine_maintenance_logs USING btree (workspace_id);


--
-- Name: ix_machine_section_assignments_factory_section_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_machine_section_assignments_factory_section_id ON public.machine_section_assignments USING btree (factory_section_id);


--
-- Name: ix_machine_section_assignments_machine_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_machine_section_assignments_machine_id ON public.machine_section_assignments USING btree (machine_id);


--
-- Name: ix_machine_section_assignments_workspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_machine_section_assignments_workspace_id ON public.machine_section_assignments USING btree (workspace_id);


--
-- Name: ix_machines_factory_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_machines_factory_id ON public.machines USING btree (factory_id);


--
-- Name: ix_machines_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_machines_id ON public.machines USING btree (id);


--
-- Name: ix_machines_workspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_machines_workspace_id ON public.machines USING btree (workspace_id);


--
-- Name: ix_miscellaneous_project_costs_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_miscellaneous_project_costs_id ON public.miscellaneous_project_costs USING btree (id);


--
-- Name: ix_miscellaneous_project_costs_workspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_miscellaneous_project_costs_workspace_id ON public.miscellaneous_project_costs USING btree (workspace_id);


--
-- Name: ix_notifications_recipient_unread; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_notifications_recipient_unread ON public.notifications USING btree (workspace_id, recipient_user_id, is_read);


--
-- Name: ix_notifications_workspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_notifications_workspace_id ON public.notifications USING btree (workspace_id);


--
-- Name: ix_order_template_items_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_order_template_items_id ON public.order_template_items USING btree (id);


--
-- Name: ix_order_template_items_order_template_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_order_template_items_order_template_id ON public.order_template_items USING btree (order_template_id);


--
-- Name: ix_order_template_items_workspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_order_template_items_workspace_id ON public.order_template_items USING btree (workspace_id);


--
-- Name: ix_order_templates_account_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_order_templates_account_id ON public.order_templates USING btree (account_id);


--
-- Name: ix_order_templates_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_order_templates_id ON public.order_templates USING btree (id);


--
-- Name: ix_order_templates_workspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_order_templates_workspace_id ON public.order_templates USING btree (workspace_id);


--
-- Name: ix_order_workflows_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_order_workflows_id ON public.order_workflows USING btree (id);


--
-- Name: ix_order_workflows_workspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_order_workflows_workspace_id ON public.order_workflows USING btree (workspace_id);


--
-- Name: ix_payment_transaction_events_payment_transaction_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_payment_transaction_events_payment_transaction_id ON public.payment_transaction_events USING btree (payment_transaction_id);


--
-- Name: ix_payment_transaction_events_workspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_payment_transaction_events_workspace_id ON public.payment_transaction_events USING btree (workspace_id);


--
-- Name: ix_payment_transactions_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_payment_transactions_status ON public.payment_transactions USING btree (status);


--
-- Name: ix_payment_transactions_tran_id; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_payment_transactions_tran_id ON public.payment_transactions USING btree (tran_id);


--
-- Name: ix_payment_transactions_val_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_payment_transactions_val_id ON public.payment_transactions USING btree (val_id);


--
-- Name: ix_payment_transactions_workspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_payment_transactions_workspace_id ON public.payment_transactions USING btree (workspace_id);


--
-- Name: ix_po_receive_event_items_event_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_po_receive_event_items_event_id ON public.po_receive_event_items USING btree (receive_event_id);


--
-- Name: ix_po_receive_events_po_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_po_receive_events_po_id ON public.po_receive_events USING btree (purchase_order_id);


--
-- Name: ix_po_receive_events_workspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_po_receive_events_workspace_id ON public.po_receive_events USING btree (workspace_id);


--
-- Name: ix_product_ledger_factory_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_product_ledger_factory_id ON public.product_ledger USING btree (factory_id);


--
-- Name: ix_product_ledger_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_product_ledger_id ON public.product_ledger USING btree (id);


--
-- Name: ix_product_ledger_item_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_product_ledger_item_id ON public.product_ledger USING btree (item_id);


--
-- Name: ix_product_ledger_performed_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_product_ledger_performed_at ON public.product_ledger USING btree (performed_at);


--
-- Name: ix_product_ledger_performed_by; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_product_ledger_performed_by ON public.product_ledger USING btree (performed_by);


--
-- Name: ix_product_ledger_source_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_product_ledger_source_type ON public.product_ledger USING btree (source_type);


--
-- Name: ix_product_ledger_transaction_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_product_ledger_transaction_type ON public.product_ledger USING btree (transaction_type);


--
-- Name: ix_product_ledger_workspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_product_ledger_workspace_id ON public.product_ledger USING btree (workspace_id);


--
-- Name: ix_production_batch_items_batch_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_production_batch_items_batch_id ON public.production_batch_items USING btree (batch_id);


--
-- Name: ix_production_batch_items_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_production_batch_items_id ON public.production_batch_items USING btree (id);


--
-- Name: ix_production_batch_items_item_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_production_batch_items_item_id ON public.production_batch_items USING btree (item_id);


--
-- Name: ix_production_batch_items_item_role; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_production_batch_items_item_role ON public.production_batch_items USING btree (item_role);


--
-- Name: ix_production_batch_items_workspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_production_batch_items_workspace_id ON public.production_batch_items USING btree (workspace_id);


--
-- Name: ix_production_batch_stage_logs_batch_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_production_batch_stage_logs_batch_id ON public.production_batch_stage_logs USING btree (batch_id);


--
-- Name: ix_production_batch_stage_logs_workspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_production_batch_stage_logs_workspace_id ON public.production_batch_stage_logs USING btree (workspace_id);


--
-- Name: ix_production_batches_batch_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_production_batches_batch_date ON public.production_batches USING btree (batch_date);


--
-- Name: ix_production_batches_batch_number; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_production_batches_batch_number ON public.production_batches USING btree (batch_number);


--
-- Name: ix_production_batches_formula_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_production_batches_formula_id ON public.production_batches USING btree (formula_id);


--
-- Name: ix_production_batches_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_production_batches_id ON public.production_batches USING btree (id);


--
-- Name: ix_production_batches_production_line_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_production_batches_production_line_id ON public.production_batches USING btree (production_line_id);


--
-- Name: ix_production_batches_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_production_batches_status ON public.production_batches USING btree (status);


--
-- Name: ix_production_batches_workspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_production_batches_workspace_id ON public.production_batches USING btree (workspace_id);


--
-- Name: ix_production_formula_items_formula_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_production_formula_items_formula_id ON public.production_formula_items USING btree (formula_id);


--
-- Name: ix_production_formula_items_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_production_formula_items_id ON public.production_formula_items USING btree (id);


--
-- Name: ix_production_formula_items_item_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_production_formula_items_item_id ON public.production_formula_items USING btree (item_id);


--
-- Name: ix_production_formula_items_item_role; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_production_formula_items_item_role ON public.production_formula_items USING btree (item_role);


--
-- Name: ix_production_formula_items_workspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_production_formula_items_workspace_id ON public.production_formula_items USING btree (workspace_id);


--
-- Name: ix_production_formula_stages_formula_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_production_formula_stages_formula_id ON public.production_formula_stages USING btree (formula_id);


--
-- Name: ix_production_formula_stages_workspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_production_formula_stages_workspace_id ON public.production_formula_stages USING btree (workspace_id);


--
-- Name: ix_production_formulas_formula_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_production_formulas_formula_code ON public.production_formulas USING btree (formula_code);


--
-- Name: ix_production_formulas_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_production_formulas_id ON public.production_formulas USING btree (id);


--
-- Name: ix_production_formulas_workspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_production_formulas_workspace_id ON public.production_formulas USING btree (workspace_id);


--
-- Name: ix_production_lines_factory_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_production_lines_factory_id ON public.production_lines USING btree (factory_id);


--
-- Name: ix_production_lines_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_production_lines_id ON public.production_lines USING btree (id);


--
-- Name: ix_production_lines_machine_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_production_lines_machine_id ON public.production_lines USING btree (machine_id);


--
-- Name: ix_production_lines_workspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_production_lines_workspace_id ON public.production_lines USING btree (workspace_id);


--
-- Name: ix_products_factory_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_products_factory_id ON public.products USING btree (factory_id);


--
-- Name: ix_products_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_products_id ON public.products USING btree (id);


--
-- Name: ix_products_is_available_for_sale; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_products_is_available_for_sale ON public.products USING btree (is_available_for_sale);


--
-- Name: ix_products_item_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_products_item_id ON public.products USING btree (item_id);


--
-- Name: ix_products_workspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_products_workspace_id ON public.products USING btree (workspace_id);


--
-- Name: ix_profiles_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_profiles_id ON public.profiles USING btree (id);


--
-- Name: ix_project_attachments_attachment_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_project_attachments_attachment_id ON public.project_attachments USING btree (attachment_id);


--
-- Name: ix_project_attachments_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_project_attachments_id ON public.project_attachments USING btree (id);


--
-- Name: ix_project_attachments_project_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_project_attachments_project_id ON public.project_attachments USING btree (project_id);


--
-- Name: ix_project_attachments_workspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_project_attachments_workspace_id ON public.project_attachments USING btree (workspace_id);


--
-- Name: ix_project_component_activity_events_project_component_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_project_component_activity_events_project_component_id ON public.project_component_activity_events USING btree (project_component_id);


--
-- Name: ix_project_component_activity_events_workspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_project_component_activity_events_workspace_id ON public.project_component_activity_events USING btree (workspace_id);


--
-- Name: ix_project_component_attachments_attachment_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_project_component_attachments_attachment_id ON public.project_component_attachments USING btree (attachment_id);


--
-- Name: ix_project_component_attachments_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_project_component_attachments_id ON public.project_component_attachments USING btree (id);


--
-- Name: ix_project_component_attachments_project_component_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_project_component_attachments_project_component_id ON public.project_component_attachments USING btree (project_component_id);


--
-- Name: ix_project_component_attachments_workspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_project_component_attachments_workspace_id ON public.project_component_attachments USING btree (workspace_id);


--
-- Name: ix_project_component_item_ledger_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_project_component_item_ledger_id ON public.project_component_item_ledger USING btree (id);


--
-- Name: ix_project_component_item_ledger_invoice_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_project_component_item_ledger_invoice_id ON public.project_component_item_ledger USING btree (invoice_id);


--
-- Name: ix_project_component_item_ledger_item_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_project_component_item_ledger_item_id ON public.project_component_item_ledger USING btree (item_id);


--
-- Name: ix_project_component_item_ledger_order_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_project_component_item_ledger_order_id ON public.project_component_item_ledger USING btree (order_id);


--
-- Name: ix_project_component_item_ledger_performed_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_project_component_item_ledger_performed_at ON public.project_component_item_ledger USING btree (performed_at);


--
-- Name: ix_project_component_item_ledger_performed_by; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_project_component_item_ledger_performed_by ON public.project_component_item_ledger USING btree (performed_by);


--
-- Name: ix_project_component_item_ledger_project_component_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_project_component_item_ledger_project_component_id ON public.project_component_item_ledger USING btree (project_component_id);


--
-- Name: ix_project_component_item_ledger_source_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_project_component_item_ledger_source_type ON public.project_component_item_ledger USING btree (source_type);


--
-- Name: ix_project_component_item_ledger_transaction_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_project_component_item_ledger_transaction_type ON public.project_component_item_ledger USING btree (transaction_type);


--
-- Name: ix_project_component_item_ledger_workspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_project_component_item_ledger_workspace_id ON public.project_component_item_ledger USING btree (workspace_id);


--
-- Name: ix_project_component_items_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_project_component_items_id ON public.project_component_items USING btree (id);


--
-- Name: ix_project_component_items_item_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_project_component_items_item_id ON public.project_component_items USING btree (item_id);


--
-- Name: ix_project_component_items_project_component_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_project_component_items_project_component_id ON public.project_component_items USING btree (project_component_id);


--
-- Name: ix_project_component_items_workspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_project_component_items_workspace_id ON public.project_component_items USING btree (workspace_id);


--
-- Name: ix_project_component_tasks_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_project_component_tasks_id ON public.project_component_tasks USING btree (id);


--
-- Name: ix_project_component_tasks_workspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_project_component_tasks_workspace_id ON public.project_component_tasks USING btree (workspace_id);


--
-- Name: ix_project_components_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_project_components_id ON public.project_components USING btree (id);


--
-- Name: ix_project_components_workspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_project_components_workspace_id ON public.project_components USING btree (workspace_id);


--
-- Name: ix_project_events_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_project_events_id ON public.project_events USING btree (id);


--
-- Name: ix_project_events_project_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_project_events_project_id ON public.project_events USING btree (project_id);


--
-- Name: ix_project_events_workspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_project_events_workspace_id ON public.project_events USING btree (workspace_id);


--
-- Name: ix_project_members_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_project_members_id ON public.project_members USING btree (id);


--
-- Name: ix_project_members_project_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_project_members_project_id ON public.project_members USING btree (project_id);


--
-- Name: ix_project_members_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_project_members_user_id ON public.project_members USING btree (user_id);


--
-- Name: ix_project_members_workspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_project_members_workspace_id ON public.project_members USING btree (workspace_id);


--
-- Name: ix_projects_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_projects_id ON public.projects USING btree (id);


--
-- Name: ix_projects_workspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_projects_workspace_id ON public.projects USING btree (workspace_id);


--
-- Name: ix_purchase_order_approvers_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_purchase_order_approvers_id ON public.purchase_order_approvers USING btree (id);


--
-- Name: ix_purchase_order_approvers_purchase_order_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_purchase_order_approvers_purchase_order_id ON public.purchase_order_approvers USING btree (purchase_order_id);


--
-- Name: ix_purchase_order_approvers_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_purchase_order_approvers_user_id ON public.purchase_order_approvers USING btree (user_id);


--
-- Name: ix_purchase_order_approvers_workspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_purchase_order_approvers_workspace_id ON public.purchase_order_approvers USING btree (workspace_id);


--
-- Name: ix_purchase_order_events_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_purchase_order_events_id ON public.purchase_order_events USING btree (id);


--
-- Name: ix_purchase_order_events_purchase_order_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_purchase_order_events_purchase_order_id ON public.purchase_order_events USING btree (purchase_order_id);


--
-- Name: ix_purchase_order_events_workspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_purchase_order_events_workspace_id ON public.purchase_order_events USING btree (workspace_id);


--
-- Name: ix_purchase_order_items_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_purchase_order_items_id ON public.purchase_order_items USING btree (id);


--
-- Name: ix_purchase_order_items_item_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_purchase_order_items_item_id ON public.purchase_order_items USING btree (item_id);


--
-- Name: ix_purchase_order_items_purchase_order_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_purchase_order_items_purchase_order_id ON public.purchase_order_items USING btree (purchase_order_id);


--
-- Name: ix_purchase_order_items_workspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_purchase_order_items_workspace_id ON public.purchase_order_items USING btree (workspace_id);


--
-- Name: ix_purchase_orders_account_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_purchase_orders_account_id ON public.purchase_orders USING btree (account_id);


--
-- Name: ix_purchase_orders_created_by; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_purchase_orders_created_by ON public.purchase_orders USING btree (created_by);


--
-- Name: ix_purchase_orders_current_status_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_purchase_orders_current_status_id ON public.purchase_orders USING btree (current_status_id);


--
-- Name: ix_purchase_orders_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_purchase_orders_id ON public.purchase_orders USING btree (id);


--
-- Name: ix_purchase_orders_invoice_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_purchase_orders_invoice_id ON public.purchase_orders USING btree (invoice_id);


--
-- Name: ix_purchase_orders_order_workflow_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_purchase_orders_order_workflow_id ON public.purchase_orders USING btree (order_workflow_id);


--
-- Name: ix_purchase_orders_po_number; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_purchase_orders_po_number ON public.purchase_orders USING btree (po_number);


--
-- Name: ix_purchase_orders_workspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_purchase_orders_workspace_id ON public.purchase_orders USING btree (workspace_id);


--
-- Name: ix_refresh_tokens_active; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_refresh_tokens_active ON public.refresh_tokens USING btree (user_id, revoked_at, expires_at);


--
-- Name: ix_refresh_tokens_expires_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_refresh_tokens_expires_at ON public.refresh_tokens USING btree (expires_at);


--
-- Name: ix_refresh_tokens_family_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_refresh_tokens_family_id ON public.refresh_tokens USING btree (family_id);


--
-- Name: ix_refresh_tokens_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_refresh_tokens_id ON public.refresh_tokens USING btree (id);


--
-- Name: ix_refresh_tokens_token_hash; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_refresh_tokens_token_hash ON public.refresh_tokens USING btree (token_hash);


--
-- Name: ix_refresh_tokens_user_family; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_refresh_tokens_user_family ON public.refresh_tokens USING btree (user_id, family_id);


--
-- Name: ix_refresh_tokens_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_refresh_tokens_user_id ON public.refresh_tokens USING btree (user_id);


--
-- Name: ix_refresh_tokens_workspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_refresh_tokens_workspace_id ON public.refresh_tokens USING btree (workspace_id);


--
-- Name: ix_sales_deliveries_created_by; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_sales_deliveries_created_by ON public.sales_deliveries USING btree (created_by);


--
-- Name: ix_sales_deliveries_delivery_method_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_sales_deliveries_delivery_method_id ON public.sales_deliveries USING btree (delivery_method_id);


--
-- Name: ix_sales_deliveries_delivery_number; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_sales_deliveries_delivery_number ON public.sales_deliveries USING btree (delivery_number);


--
-- Name: ix_sales_deliveries_delivery_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_sales_deliveries_delivery_status ON public.sales_deliveries USING btree (delivery_status);


--
-- Name: ix_sales_deliveries_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_sales_deliveries_id ON public.sales_deliveries USING btree (id);


--
-- Name: ix_sales_deliveries_sales_order_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_sales_deliveries_sales_order_id ON public.sales_deliveries USING btree (sales_order_id);


--
-- Name: ix_sales_deliveries_workspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_sales_deliveries_workspace_id ON public.sales_deliveries USING btree (workspace_id);


--
-- Name: ix_sales_delivery_items_delivery_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_sales_delivery_items_delivery_id ON public.sales_delivery_items USING btree (delivery_id);


--
-- Name: ix_sales_delivery_items_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_sales_delivery_items_id ON public.sales_delivery_items USING btree (id);


--
-- Name: ix_sales_delivery_items_item_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_sales_delivery_items_item_id ON public.sales_delivery_items USING btree (item_id);


--
-- Name: ix_sales_delivery_items_sales_order_item_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_sales_delivery_items_sales_order_item_id ON public.sales_delivery_items USING btree (sales_order_item_id);


--
-- Name: ix_sales_delivery_items_workspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_sales_delivery_items_workspace_id ON public.sales_delivery_items USING btree (workspace_id);


--
-- Name: ix_sales_order_items_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_sales_order_items_id ON public.sales_order_items USING btree (id);


--
-- Name: ix_sales_order_items_item_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_sales_order_items_item_id ON public.sales_order_items USING btree (item_id);


--
-- Name: ix_sales_order_items_sales_order_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_sales_order_items_sales_order_id ON public.sales_order_items USING btree (sales_order_id);


--
-- Name: ix_sales_order_items_workspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_sales_order_items_workspace_id ON public.sales_order_items USING btree (workspace_id);


--
-- Name: ix_sales_orders_account_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_sales_orders_account_id ON public.sales_orders USING btree (account_id);


--
-- Name: ix_sales_orders_created_by; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_sales_orders_created_by ON public.sales_orders USING btree (created_by);


--
-- Name: ix_sales_orders_current_status_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_sales_orders_current_status_id ON public.sales_orders USING btree (current_status_id);


--
-- Name: ix_sales_orders_factory_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_sales_orders_factory_id ON public.sales_orders USING btree (factory_id);


--
-- Name: ix_sales_orders_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_sales_orders_id ON public.sales_orders USING btree (id);


--
-- Name: ix_sales_orders_invoice_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_sales_orders_invoice_id ON public.sales_orders USING btree (invoice_id);


--
-- Name: ix_sales_orders_sales_order_number; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_sales_orders_sales_order_number ON public.sales_orders USING btree (sales_order_number);


--
-- Name: ix_sales_orders_workspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_sales_orders_workspace_id ON public.sales_orders USING btree (workspace_id);


--
-- Name: ix_statuses_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_statuses_id ON public.statuses USING btree (id);


--
-- Name: ix_statuses_workspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_statuses_workspace_id ON public.statuses USING btree (workspace_id);


--
-- Name: ix_subscription_plans_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_subscription_plans_id ON public.subscription_plans USING btree (id);


--
-- Name: ix_subscription_plans_is_active; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_subscription_plans_is_active ON public.subscription_plans USING btree (is_active);


--
-- Name: ix_subscription_plans_name; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_subscription_plans_name ON public.subscription_plans USING btree (name);


--
-- Name: ix_transfer_order_approvers_transfer_order_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_transfer_order_approvers_transfer_order_id ON public.transfer_order_approvers USING btree (transfer_order_id);


--
-- Name: ix_transfer_order_approvers_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_transfer_order_approvers_user_id ON public.transfer_order_approvers USING btree (user_id);


--
-- Name: ix_transfer_order_approvers_workspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_transfer_order_approvers_workspace_id ON public.transfer_order_approvers USING btree (workspace_id);


--
-- Name: ix_transfer_order_events_transfer_order_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_transfer_order_events_transfer_order_id ON public.transfer_order_events USING btree (transfer_order_id);


--
-- Name: ix_transfer_order_events_workspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_transfer_order_events_workspace_id ON public.transfer_order_events USING btree (workspace_id);


--
-- Name: ix_transfer_order_items_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_transfer_order_items_id ON public.transfer_order_items USING btree (id);


--
-- Name: ix_transfer_order_items_item_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_transfer_order_items_item_id ON public.transfer_order_items USING btree (item_id);


--
-- Name: ix_transfer_order_items_transfer_order_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_transfer_order_items_transfer_order_id ON public.transfer_order_items USING btree (transfer_order_id);


--
-- Name: ix_transfer_order_items_workspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_transfer_order_items_workspace_id ON public.transfer_order_items USING btree (workspace_id);


--
-- Name: ix_transfer_orders_created_by; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_transfer_orders_created_by ON public.transfer_orders USING btree (created_by);


--
-- Name: ix_transfer_orders_current_status_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_transfer_orders_current_status_id ON public.transfer_orders USING btree (current_status_id);


--
-- Name: ix_transfer_orders_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_transfer_orders_id ON public.transfer_orders USING btree (id);


--
-- Name: ix_transfer_orders_transfer_number; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_transfer_orders_transfer_number ON public.transfer_orders USING btree (transfer_number);


--
-- Name: ix_transfer_orders_workspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_transfer_orders_workspace_id ON public.transfer_orders USING btree (workspace_id);


--
-- Name: ix_waitlist_signups_email; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_waitlist_signups_email ON public.waitlist_signups USING btree (email);


--
-- Name: ix_waitlist_signups_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_waitlist_signups_id ON public.waitlist_signups USING btree (id);


--
-- Name: ix_work_order_approvers_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_work_order_approvers_user_id ON public.work_order_approvers USING btree (user_id);


--
-- Name: ix_work_order_approvers_work_order_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_work_order_approvers_work_order_id ON public.work_order_approvers USING btree (work_order_id);


--
-- Name: ix_work_order_approvers_workspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_work_order_approvers_workspace_id ON public.work_order_approvers USING btree (workspace_id);


--
-- Name: ix_work_order_events_work_order_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_work_order_events_work_order_id ON public.work_order_events USING btree (work_order_id);


--
-- Name: ix_work_order_events_workspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_work_order_events_workspace_id ON public.work_order_events USING btree (workspace_id);


--
-- Name: ix_work_order_items_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_work_order_items_id ON public.work_order_items USING btree (id);


--
-- Name: ix_work_order_items_item_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_work_order_items_item_id ON public.work_order_items USING btree (item_id);


--
-- Name: ix_work_order_items_replaced_item_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_work_order_items_replaced_item_id ON public.work_order_items USING btree (replaced_item_id);


--
-- Name: ix_work_order_items_work_order_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_work_order_items_work_order_id ON public.work_order_items USING btree (work_order_id);


--
-- Name: ix_work_order_items_workspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_work_order_items_workspace_id ON public.work_order_items USING btree (workspace_id);


--
-- Name: ix_work_order_template_approvers_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_work_order_template_approvers_user_id ON public.work_order_template_approvers USING btree (user_id);


--
-- Name: ix_work_order_template_approvers_work_order_template_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_work_order_template_approvers_work_order_template_id ON public.work_order_template_approvers USING btree (work_order_template_id);


--
-- Name: ix_work_order_template_approvers_workspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_work_order_template_approvers_workspace_id ON public.work_order_template_approvers USING btree (workspace_id);


--
-- Name: ix_work_order_template_items_item_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_work_order_template_items_item_id ON public.work_order_template_items USING btree (item_id);


--
-- Name: ix_work_order_template_items_replaced_item_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_work_order_template_items_replaced_item_id ON public.work_order_template_items USING btree (replaced_item_id);


--
-- Name: ix_work_order_template_items_work_order_template_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_work_order_template_items_work_order_template_id ON public.work_order_template_items USING btree (work_order_template_id);


--
-- Name: ix_work_order_template_items_workspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_work_order_template_items_workspace_id ON public.work_order_template_items USING btree (workspace_id);


--
-- Name: ix_work_order_templates_account_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_work_order_templates_account_id ON public.work_order_templates USING btree (account_id);


--
-- Name: ix_work_order_templates_work_order_type_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_work_order_templates_work_order_type_id ON public.work_order_templates USING btree (work_order_type_id);


--
-- Name: ix_work_order_templates_workspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_work_order_templates_workspace_id ON public.work_order_templates USING btree (workspace_id);


--
-- Name: ix_work_order_types_workspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_work_order_types_workspace_id ON public.work_order_types USING btree (workspace_id);


--
-- Name: ix_work_orders_factory_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_work_orders_factory_id ON public.work_orders USING btree (factory_id);


--
-- Name: ix_work_orders_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_work_orders_id ON public.work_orders USING btree (id);


--
-- Name: ix_work_orders_machine_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_work_orders_machine_id ON public.work_orders USING btree (machine_id);


--
-- Name: ix_work_orders_planned_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_work_orders_planned_date ON public.work_orders USING btree (planned_date);


--
-- Name: ix_work_orders_project_component_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_work_orders_project_component_id ON public.work_orders USING btree (project_component_id);


--
-- Name: ix_work_orders_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_work_orders_status ON public.work_orders USING btree (status);


--
-- Name: ix_work_orders_work_order_number; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_work_orders_work_order_number ON public.work_orders USING btree (work_order_number);


--
-- Name: ix_work_orders_work_order_template_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_work_orders_work_order_template_id ON public.work_orders USING btree (work_order_template_id);


--
-- Name: ix_work_orders_workspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_work_orders_workspace_id ON public.work_orders USING btree (workspace_id);


--
-- Name: ix_workspace_audit_logs_action; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_workspace_audit_logs_action ON public.workspace_audit_logs USING btree (action);


--
-- Name: ix_workspace_audit_logs_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_workspace_audit_logs_created_at ON public.workspace_audit_logs USING btree (created_at);


--
-- Name: ix_workspace_audit_logs_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_workspace_audit_logs_id ON public.workspace_audit_logs USING btree (id);


--
-- Name: ix_workspace_audit_logs_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_workspace_audit_logs_user_id ON public.workspace_audit_logs USING btree (user_id);


--
-- Name: ix_workspace_audit_logs_workspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_workspace_audit_logs_workspace_id ON public.workspace_audit_logs USING btree (workspace_id);


--
-- Name: ix_workspace_invitations_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_workspace_invitations_id ON public.workspace_invitations USING btree (id);


--
-- Name: ix_workspace_invitations_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_workspace_invitations_status ON public.workspace_invitations USING btree (status);


--
-- Name: ix_workspace_invitations_token; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_workspace_invitations_token ON public.workspace_invitations USING btree (token);


--
-- Name: ix_workspace_invitations_workspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_workspace_invitations_workspace_id ON public.workspace_invitations USING btree (workspace_id);


--
-- Name: ix_workspace_members_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_workspace_members_id ON public.workspace_members USING btree (id);


--
-- Name: ix_workspace_members_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_workspace_members_user_id ON public.workspace_members USING btree (user_id);


--
-- Name: ix_workspace_members_workspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_workspace_members_workspace_id ON public.workspace_members USING btree (workspace_id);


--
-- Name: ix_workspaces_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_workspaces_id ON public.workspaces USING btree (id);


--
-- Name: ix_workspaces_owner_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_workspaces_owner_user_id ON public.workspaces USING btree (owner_user_id);


--
-- Name: ix_workspaces_slug; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_workspaces_slug ON public.workspaces USING btree (slug);


--
-- Name: ix_workspaces_subscription_plan_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_workspaces_subscription_plan_id ON public.workspaces USING btree (subscription_plan_id);


--
-- Name: ix_workspaces_subscription_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_workspaces_subscription_status ON public.workspaces USING btree (subscription_status);


--
-- Name: access_control access_control_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.access_control
    ADD CONSTRAINT access_control_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(id) ON DELETE CASCADE;


--
-- Name: account_invoices account_invoices_account_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.account_invoices
    ADD CONSTRAINT account_invoices_account_id_fkey FOREIGN KEY (account_id) REFERENCES public.accounts(id) ON DELETE RESTRICT;


--
-- Name: account_invoices account_invoices_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.account_invoices
    ADD CONSTRAINT account_invoices_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.profiles(id);


--
-- Name: account_invoices account_invoices_updated_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.account_invoices
    ADD CONSTRAINT account_invoices_updated_by_fkey FOREIGN KEY (updated_by) REFERENCES public.profiles(id);


--
-- Name: account_invoices account_invoices_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.account_invoices
    ADD CONSTRAINT account_invoices_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(id) ON DELETE CASCADE;


--
-- Name: account_tag_assignments account_tag_assignments_account_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.account_tag_assignments
    ADD CONSTRAINT account_tag_assignments_account_id_fkey FOREIGN KEY (account_id) REFERENCES public.accounts(id) ON DELETE CASCADE;


--
-- Name: account_tag_assignments account_tag_assignments_assigned_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.account_tag_assignments
    ADD CONSTRAINT account_tag_assignments_assigned_by_fkey FOREIGN KEY (assigned_by) REFERENCES public.profiles(id);


--
-- Name: account_tag_assignments account_tag_assignments_tag_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.account_tag_assignments
    ADD CONSTRAINT account_tag_assignments_tag_id_fkey FOREIGN KEY (tag_id) REFERENCES public.account_tags(id) ON DELETE CASCADE;


--
-- Name: account_tag_assignments account_tag_assignments_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.account_tag_assignments
    ADD CONSTRAINT account_tag_assignments_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(id) ON DELETE CASCADE;


--
-- Name: account_tags account_tags_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.account_tags
    ADD CONSTRAINT account_tags_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.profiles(id);


--
-- Name: account_tags account_tags_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.account_tags
    ADD CONSTRAINT account_tags_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(id) ON DELETE CASCADE;


--
-- Name: accounts accounts_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.accounts
    ADD CONSTRAINT accounts_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.profiles(id);


--
-- Name: accounts accounts_deleted_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.accounts
    ADD CONSTRAINT accounts_deleted_by_fkey FOREIGN KEY (deleted_by) REFERENCES public.profiles(id);


--
-- Name: accounts accounts_updated_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.accounts
    ADD CONSTRAINT accounts_updated_by_fkey FOREIGN KEY (updated_by) REFERENCES public.profiles(id);


--
-- Name: accounts accounts_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.accounts
    ADD CONSTRAINT accounts_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(id) ON DELETE CASCADE;


--
-- Name: app_settings app_settings_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.app_settings
    ADD CONSTRAINT app_settings_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(id) ON DELETE CASCADE;


--
-- Name: attachments attachments_deleted_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.attachments
    ADD CONSTRAINT attachments_deleted_by_fkey FOREIGN KEY (deleted_by) REFERENCES public.profiles(id);


--
-- Name: attachments attachments_uploaded_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.attachments
    ADD CONSTRAINT attachments_uploaded_by_fkey FOREIGN KEY (uploaded_by) REFERENCES public.profiles(id);


--
-- Name: attachments attachments_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.attachments
    ADD CONSTRAINT attachments_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(id) ON DELETE CASCADE;


--
-- Name: delivery_methods delivery_methods_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.delivery_methods
    ADD CONSTRAINT delivery_methods_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.profiles(id);


--
-- Name: delivery_methods delivery_methods_deleted_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.delivery_methods
    ADD CONSTRAINT delivery_methods_deleted_by_fkey FOREIGN KEY (deleted_by) REFERENCES public.profiles(id);


--
-- Name: delivery_methods delivery_methods_updated_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.delivery_methods
    ADD CONSTRAINT delivery_methods_updated_by_fkey FOREIGN KEY (updated_by) REFERENCES public.profiles(id);


--
-- Name: delivery_methods delivery_methods_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.delivery_methods
    ADD CONSTRAINT delivery_methods_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(id) ON DELETE CASCADE;


--
-- Name: departments departments_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.departments
    ADD CONSTRAINT departments_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.profiles(id);


--
-- Name: departments departments_deleted_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.departments
    ADD CONSTRAINT departments_deleted_by_fkey FOREIGN KEY (deleted_by) REFERENCES public.profiles(id);


--
-- Name: departments departments_updated_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.departments
    ADD CONSTRAINT departments_updated_by_fkey FOREIGN KEY (updated_by) REFERENCES public.profiles(id);


--
-- Name: departments departments_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.departments
    ADD CONSTRAINT departments_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(id) ON DELETE CASCADE;


--
-- Name: discussions discussions_parent_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.discussions
    ADD CONSTRAINT discussions_parent_id_fkey FOREIGN KEY (parent_id) REFERENCES public.discussions(id) ON DELETE CASCADE;


--
-- Name: discussions discussions_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.discussions
    ADD CONSTRAINT discussions_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.profiles(id) ON DELETE SET NULL;


--
-- Name: discussions discussions_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.discussions
    ADD CONSTRAINT discussions_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(id) ON DELETE CASCADE;


--
-- Name: expense_order_approvers expense_order_approvers_assigned_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.expense_order_approvers
    ADD CONSTRAINT expense_order_approvers_assigned_by_fkey FOREIGN KEY (assigned_by) REFERENCES public.profiles(id) ON DELETE SET NULL;


--
-- Name: expense_order_approvers expense_order_approvers_expense_order_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.expense_order_approvers
    ADD CONSTRAINT expense_order_approvers_expense_order_id_fkey FOREIGN KEY (expense_order_id) REFERENCES public.expense_orders(id) ON DELETE CASCADE;


--
-- Name: expense_order_approvers expense_order_approvers_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.expense_order_approvers
    ADD CONSTRAINT expense_order_approvers_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.profiles(id) ON DELETE CASCADE;


--
-- Name: expense_order_approvers expense_order_approvers_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.expense_order_approvers
    ADD CONSTRAINT expense_order_approvers_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(id) ON DELETE CASCADE;


--
-- Name: expense_order_events expense_order_events_expense_order_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.expense_order_events
    ADD CONSTRAINT expense_order_events_expense_order_id_fkey FOREIGN KEY (expense_order_id) REFERENCES public.expense_orders(id) ON DELETE CASCADE;


--
-- Name: expense_order_events expense_order_events_performed_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.expense_order_events
    ADD CONSTRAINT expense_order_events_performed_by_fkey FOREIGN KEY (performed_by) REFERENCES public.profiles(id) ON DELETE SET NULL;


--
-- Name: expense_order_events expense_order_events_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.expense_order_events
    ADD CONSTRAINT expense_order_events_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(id) ON DELETE CASCADE;


--
-- Name: expense_order_items expense_order_items_expense_order_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.expense_order_items
    ADD CONSTRAINT expense_order_items_expense_order_id_fkey FOREIGN KEY (expense_order_id) REFERENCES public.expense_orders(id) ON DELETE CASCADE;


--
-- Name: expense_order_items expense_order_items_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.expense_order_items
    ADD CONSTRAINT expense_order_items_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(id) ON DELETE CASCADE;


--
-- Name: expense_orders expense_orders_account_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.expense_orders
    ADD CONSTRAINT expense_orders_account_id_fkey FOREIGN KEY (account_id) REFERENCES public.accounts(id) ON DELETE RESTRICT;


--
-- Name: expense_orders expense_orders_approved_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.expense_orders
    ADD CONSTRAINT expense_orders_approved_by_fkey FOREIGN KEY (approved_by) REFERENCES public.profiles(id) ON DELETE SET NULL;


--
-- Name: expense_orders expense_orders_completed_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.expense_orders
    ADD CONSTRAINT expense_orders_completed_by_fkey FOREIGN KEY (completed_by) REFERENCES public.profiles(id) ON DELETE SET NULL;


--
-- Name: expense_orders expense_orders_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.expense_orders
    ADD CONSTRAINT expense_orders_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.profiles(id) ON DELETE SET NULL;


--
-- Name: expense_orders expense_orders_invoice_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.expense_orders
    ADD CONSTRAINT expense_orders_invoice_id_fkey FOREIGN KEY (invoice_id) REFERENCES public.account_invoices(id) ON DELETE SET NULL;


--
-- Name: expense_orders expense_orders_order_template_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.expense_orders
    ADD CONSTRAINT expense_orders_order_template_id_fkey FOREIGN KEY (order_template_id) REFERENCES public.order_templates(id) ON DELETE SET NULL;


--
-- Name: expense_orders expense_orders_updated_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.expense_orders
    ADD CONSTRAINT expense_orders_updated_by_fkey FOREIGN KEY (updated_by) REFERENCES public.profiles(id) ON DELETE SET NULL;


--
-- Name: expense_orders expense_orders_voided_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.expense_orders
    ADD CONSTRAINT expense_orders_voided_by_fkey FOREIGN KEY (voided_by) REFERENCES public.profiles(id) ON DELETE SET NULL;


--
-- Name: expense_orders expense_orders_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.expense_orders
    ADD CONSTRAINT expense_orders_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(id) ON DELETE CASCADE;


--
-- Name: factories factories_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.factories
    ADD CONSTRAINT factories_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.profiles(id);


--
-- Name: factories factories_deleted_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.factories
    ADD CONSTRAINT factories_deleted_by_fkey FOREIGN KEY (deleted_by) REFERENCES public.profiles(id);


--
-- Name: factories factories_updated_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.factories
    ADD CONSTRAINT factories_updated_by_fkey FOREIGN KEY (updated_by) REFERENCES public.profiles(id);


--
-- Name: factories factories_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.factories
    ADD CONSTRAINT factories_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(id) ON DELETE CASCADE;


--
-- Name: factory_sections factory_sections_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.factory_sections
    ADD CONSTRAINT factory_sections_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.profiles(id);


--
-- Name: factory_sections factory_sections_deleted_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.factory_sections
    ADD CONSTRAINT factory_sections_deleted_by_fkey FOREIGN KEY (deleted_by) REFERENCES public.profiles(id);


--
-- Name: factory_sections factory_sections_factory_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.factory_sections
    ADD CONSTRAINT factory_sections_factory_id_fkey FOREIGN KEY (factory_id) REFERENCES public.factories(id);


--
-- Name: factory_sections factory_sections_updated_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.factory_sections
    ADD CONSTRAINT factory_sections_updated_by_fkey FOREIGN KEY (updated_by) REFERENCES public.profiles(id);


--
-- Name: factory_sections factory_sections_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.factory_sections
    ADD CONSTRAINT factory_sections_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(id) ON DELETE CASCADE;


--
-- Name: financial_audit_logs financial_audit_logs_performed_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.financial_audit_logs
    ADD CONSTRAINT financial_audit_logs_performed_by_fkey FOREIGN KEY (performed_by) REFERENCES public.profiles(id);


--
-- Name: financial_audit_logs financial_audit_logs_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.financial_audit_logs
    ADD CONSTRAINT financial_audit_logs_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(id) ON DELETE CASCADE;


--
-- Name: work_order_templates fk_wo_templates_default_machine; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_order_templates
    ADD CONSTRAINT fk_wo_templates_default_machine FOREIGN KEY (default_machine_id) REFERENCES public.machines(id) ON DELETE SET NULL;


--
-- Name: work_order_templates fk_wo_templates_default_section; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_order_templates
    ADD CONSTRAINT fk_wo_templates_default_section FOREIGN KEY (default_factory_section_id) REFERENCES public.factory_sections(id) ON DELETE SET NULL;


--
-- Name: inventory inventory_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.inventory
    ADD CONSTRAINT inventory_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.profiles(id);


--
-- Name: inventory inventory_deleted_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.inventory
    ADD CONSTRAINT inventory_deleted_by_fkey FOREIGN KEY (deleted_by) REFERENCES public.profiles(id);


--
-- Name: inventory inventory_factory_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.inventory
    ADD CONSTRAINT inventory_factory_id_fkey FOREIGN KEY (factory_id) REFERENCES public.factories(id);


--
-- Name: inventory inventory_item_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.inventory
    ADD CONSTRAINT inventory_item_id_fkey FOREIGN KEY (item_id) REFERENCES public.items(id);


--
-- Name: inventory_ledger inventory_ledger_factory_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.inventory_ledger
    ADD CONSTRAINT inventory_ledger_factory_id_fkey FOREIGN KEY (factory_id) REFERENCES public.factories(id) ON DELETE RESTRICT;


--
-- Name: inventory_ledger inventory_ledger_item_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.inventory_ledger
    ADD CONSTRAINT inventory_ledger_item_id_fkey FOREIGN KEY (item_id) REFERENCES public.items(id) ON DELETE RESTRICT;


--
-- Name: inventory_ledger inventory_ledger_performed_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.inventory_ledger
    ADD CONSTRAINT inventory_ledger_performed_by_fkey FOREIGN KEY (performed_by) REFERENCES public.profiles(id) ON DELETE SET NULL;


--
-- Name: inventory_ledger inventory_ledger_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.inventory_ledger
    ADD CONSTRAINT inventory_ledger_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(id) ON DELETE CASCADE;


--
-- Name: inventory inventory_updated_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.inventory
    ADD CONSTRAINT inventory_updated_by_fkey FOREIGN KEY (updated_by) REFERENCES public.profiles(id);


--
-- Name: inventory inventory_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.inventory
    ADD CONSTRAINT inventory_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(id) ON DELETE CASCADE;


--
-- Name: invoice_events invoice_events_invoice_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invoice_events
    ADD CONSTRAINT invoice_events_invoice_id_fkey FOREIGN KEY (invoice_id) REFERENCES public.account_invoices(id) ON DELETE CASCADE;


--
-- Name: invoice_events invoice_events_performed_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invoice_events
    ADD CONSTRAINT invoice_events_performed_by_fkey FOREIGN KEY (performed_by) REFERENCES public.profiles(id) ON DELETE SET NULL;


--
-- Name: invoice_events invoice_events_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invoice_events
    ADD CONSTRAINT invoice_events_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(id) ON DELETE CASCADE;


--
-- Name: invoice_items invoice_items_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invoice_items
    ADD CONSTRAINT invoice_items_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.profiles(id) ON DELETE SET NULL;


--
-- Name: invoice_items invoice_items_invoice_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invoice_items
    ADD CONSTRAINT invoice_items_invoice_id_fkey FOREIGN KEY (invoice_id) REFERENCES public.account_invoices(id) ON DELETE CASCADE;


--
-- Name: invoice_items invoice_items_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invoice_items
    ADD CONSTRAINT invoice_items_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(id) ON DELETE CASCADE;


--
-- Name: invoice_payments invoice_payments_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invoice_payments
    ADD CONSTRAINT invoice_payments_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.profiles(id);


--
-- Name: invoice_payments invoice_payments_invoice_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invoice_payments
    ADD CONSTRAINT invoice_payments_invoice_id_fkey FOREIGN KEY (invoice_id) REFERENCES public.account_invoices(id) ON DELETE CASCADE;


--
-- Name: invoice_payments invoice_payments_voided_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invoice_payments
    ADD CONSTRAINT invoice_payments_voided_by_fkey FOREIGN KEY (voided_by) REFERENCES public.profiles(id);


--
-- Name: invoice_payments invoice_payments_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invoice_payments
    ADD CONSTRAINT invoice_payments_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(id) ON DELETE CASCADE;


--
-- Name: invoice_status_tracker invoice_status_tracker_changed_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invoice_status_tracker
    ADD CONSTRAINT invoice_status_tracker_changed_by_fkey FOREIGN KEY (changed_by) REFERENCES public.profiles(id);


--
-- Name: invoice_status_tracker invoice_status_tracker_invoice_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invoice_status_tracker
    ADD CONSTRAINT invoice_status_tracker_invoice_id_fkey FOREIGN KEY (invoice_id) REFERENCES public.account_invoices(id) ON DELETE CASCADE;


--
-- Name: invoice_status_tracker invoice_status_tracker_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invoice_status_tracker
    ADD CONSTRAINT invoice_status_tracker_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(id) ON DELETE CASCADE;


--
-- Name: item_tag_assignments item_tag_assignments_assigned_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.item_tag_assignments
    ADD CONSTRAINT item_tag_assignments_assigned_by_fkey FOREIGN KEY (assigned_by) REFERENCES public.profiles(id);


--
-- Name: item_tag_assignments item_tag_assignments_item_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.item_tag_assignments
    ADD CONSTRAINT item_tag_assignments_item_id_fkey FOREIGN KEY (item_id) REFERENCES public.items(id) ON DELETE CASCADE;


--
-- Name: item_tag_assignments item_tag_assignments_tag_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.item_tag_assignments
    ADD CONSTRAINT item_tag_assignments_tag_id_fkey FOREIGN KEY (tag_id) REFERENCES public.item_tags(id) ON DELETE CASCADE;


--
-- Name: item_tag_assignments item_tag_assignments_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.item_tag_assignments
    ADD CONSTRAINT item_tag_assignments_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(id) ON DELETE CASCADE;


--
-- Name: item_tags item_tags_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.item_tags
    ADD CONSTRAINT item_tags_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.profiles(id);


--
-- Name: item_tags item_tags_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.item_tags
    ADD CONSTRAINT item_tags_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(id) ON DELETE CASCADE;


--
-- Name: items items_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.items
    ADD CONSTRAINT items_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.profiles(id);


--
-- Name: items items_updated_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.items
    ADD CONSTRAINT items_updated_by_fkey FOREIGN KEY (updated_by) REFERENCES public.profiles(id);


--
-- Name: items items_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.items
    ADD CONSTRAINT items_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(id) ON DELETE CASCADE;


--
-- Name: machine_activity_events machine_activity_events_machine_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.machine_activity_events
    ADD CONSTRAINT machine_activity_events_machine_id_fkey FOREIGN KEY (machine_id) REFERENCES public.machines(id) ON DELETE CASCADE;


--
-- Name: machine_activity_events machine_activity_events_performed_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.machine_activity_events
    ADD CONSTRAINT machine_activity_events_performed_by_fkey FOREIGN KEY (performed_by) REFERENCES public.profiles(id) ON DELETE SET NULL;


--
-- Name: machine_activity_events machine_activity_events_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.machine_activity_events
    ADD CONSTRAINT machine_activity_events_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(id) ON DELETE CASCADE;


--
-- Name: machine_item_ledger machine_item_ledger_invoice_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.machine_item_ledger
    ADD CONSTRAINT machine_item_ledger_invoice_id_fkey FOREIGN KEY (invoice_id) REFERENCES public.account_invoices(id) ON DELETE SET NULL;


--
-- Name: machine_item_ledger machine_item_ledger_item_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.machine_item_ledger
    ADD CONSTRAINT machine_item_ledger_item_id_fkey FOREIGN KEY (item_id) REFERENCES public.items(id) ON DELETE RESTRICT;


--
-- Name: machine_item_ledger machine_item_ledger_machine_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.machine_item_ledger
    ADD CONSTRAINT machine_item_ledger_machine_id_fkey FOREIGN KEY (machine_id) REFERENCES public.machines(id) ON DELETE RESTRICT;


--
-- Name: machine_item_ledger machine_item_ledger_performed_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.machine_item_ledger
    ADD CONSTRAINT machine_item_ledger_performed_by_fkey FOREIGN KEY (performed_by) REFERENCES public.profiles(id) ON DELETE SET NULL;


--
-- Name: machine_item_ledger machine_item_ledger_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.machine_item_ledger
    ADD CONSTRAINT machine_item_ledger_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(id) ON DELETE CASCADE;


--
-- Name: machine_items machine_items_item_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.machine_items
    ADD CONSTRAINT machine_items_item_id_fkey FOREIGN KEY (item_id) REFERENCES public.items(id);


--
-- Name: machine_items machine_items_machine_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.machine_items
    ADD CONSTRAINT machine_items_machine_id_fkey FOREIGN KEY (machine_id) REFERENCES public.machines(id);


--
-- Name: machine_items machine_items_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.machine_items
    ADD CONSTRAINT machine_items_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(id) ON DELETE CASCADE;


--
-- Name: machine_maintenance_logs machine_maintenance_logs_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.machine_maintenance_logs
    ADD CONSTRAINT machine_maintenance_logs_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.profiles(id);


--
-- Name: machine_maintenance_logs machine_maintenance_logs_deleted_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.machine_maintenance_logs
    ADD CONSTRAINT machine_maintenance_logs_deleted_by_fkey FOREIGN KEY (deleted_by) REFERENCES public.profiles(id);


--
-- Name: machine_maintenance_logs machine_maintenance_logs_machine_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.machine_maintenance_logs
    ADD CONSTRAINT machine_maintenance_logs_machine_id_fkey FOREIGN KEY (machine_id) REFERENCES public.machines(id);


--
-- Name: machine_maintenance_logs machine_maintenance_logs_updated_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.machine_maintenance_logs
    ADD CONSTRAINT machine_maintenance_logs_updated_by_fkey FOREIGN KEY (updated_by) REFERENCES public.profiles(id);


--
-- Name: machine_maintenance_logs machine_maintenance_logs_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.machine_maintenance_logs
    ADD CONSTRAINT machine_maintenance_logs_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(id) ON DELETE CASCADE;


--
-- Name: machine_section_assignments machine_section_assignments_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.machine_section_assignments
    ADD CONSTRAINT machine_section_assignments_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.profiles(id);


--
-- Name: machine_section_assignments machine_section_assignments_factory_section_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.machine_section_assignments
    ADD CONSTRAINT machine_section_assignments_factory_section_id_fkey FOREIGN KEY (factory_section_id) REFERENCES public.factory_sections(id) ON DELETE CASCADE;


--
-- Name: machine_section_assignments machine_section_assignments_machine_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.machine_section_assignments
    ADD CONSTRAINT machine_section_assignments_machine_id_fkey FOREIGN KEY (machine_id) REFERENCES public.machines(id) ON DELETE CASCADE;


--
-- Name: machine_section_assignments machine_section_assignments_updated_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.machine_section_assignments
    ADD CONSTRAINT machine_section_assignments_updated_by_fkey FOREIGN KEY (updated_by) REFERENCES public.profiles(id);


--
-- Name: machine_section_assignments machine_section_assignments_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.machine_section_assignments
    ADD CONSTRAINT machine_section_assignments_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(id) ON DELETE CASCADE;


--
-- Name: machines machines_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.machines
    ADD CONSTRAINT machines_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.profiles(id);


--
-- Name: machines machines_deleted_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.machines
    ADD CONSTRAINT machines_deleted_by_fkey FOREIGN KEY (deleted_by) REFERENCES public.profiles(id);


--
-- Name: machines machines_factory_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.machines
    ADD CONSTRAINT machines_factory_id_fkey FOREIGN KEY (factory_id) REFERENCES public.factories(id);


--
-- Name: machines machines_updated_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.machines
    ADD CONSTRAINT machines_updated_by_fkey FOREIGN KEY (updated_by) REFERENCES public.profiles(id);


--
-- Name: machines machines_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.machines
    ADD CONSTRAINT machines_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(id) ON DELETE CASCADE;


--
-- Name: miscellaneous_project_costs miscellaneous_project_costs_project_component_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.miscellaneous_project_costs
    ADD CONSTRAINT miscellaneous_project_costs_project_component_id_fkey FOREIGN KEY (project_component_id) REFERENCES public.project_components(id);


--
-- Name: miscellaneous_project_costs miscellaneous_project_costs_project_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.miscellaneous_project_costs
    ADD CONSTRAINT miscellaneous_project_costs_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.projects(id);


--
-- Name: miscellaneous_project_costs miscellaneous_project_costs_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.miscellaneous_project_costs
    ADD CONSTRAINT miscellaneous_project_costs_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(id) ON DELETE CASCADE;


--
-- Name: notifications notifications_actor_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notifications
    ADD CONSTRAINT notifications_actor_user_id_fkey FOREIGN KEY (actor_user_id) REFERENCES public.profiles(id) ON DELETE SET NULL;


--
-- Name: notifications notifications_recipient_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notifications
    ADD CONSTRAINT notifications_recipient_user_id_fkey FOREIGN KEY (recipient_user_id) REFERENCES public.profiles(id) ON DELETE CASCADE;


--
-- Name: notifications notifications_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notifications
    ADD CONSTRAINT notifications_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(id) ON DELETE CASCADE;


--
-- Name: order_template_items order_template_items_order_template_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.order_template_items
    ADD CONSTRAINT order_template_items_order_template_id_fkey FOREIGN KEY (order_template_id) REFERENCES public.order_templates(id) ON DELETE CASCADE;


--
-- Name: order_template_items order_template_items_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.order_template_items
    ADD CONSTRAINT order_template_items_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(id) ON DELETE CASCADE;


--
-- Name: order_templates order_templates_account_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.order_templates
    ADD CONSTRAINT order_templates_account_id_fkey FOREIGN KEY (account_id) REFERENCES public.accounts(id) ON DELETE RESTRICT;


--
-- Name: order_templates order_templates_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.order_templates
    ADD CONSTRAINT order_templates_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.profiles(id) ON DELETE SET NULL;


--
-- Name: order_templates order_templates_default_approver_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.order_templates
    ADD CONSTRAINT order_templates_default_approver_id_fkey FOREIGN KEY (default_approver_id) REFERENCES public.profiles(id) ON DELETE SET NULL;


--
-- Name: order_templates order_templates_updated_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.order_templates
    ADD CONSTRAINT order_templates_updated_by_fkey FOREIGN KEY (updated_by) REFERENCES public.profiles(id) ON DELETE SET NULL;


--
-- Name: order_templates order_templates_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.order_templates
    ADD CONSTRAINT order_templates_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(id) ON DELETE CASCADE;


--
-- Name: order_workflows order_workflows_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.order_workflows
    ADD CONSTRAINT order_workflows_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(id) ON DELETE CASCADE;


--
-- Name: payment_transaction_events payment_transaction_events_payment_transaction_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payment_transaction_events
    ADD CONSTRAINT payment_transaction_events_payment_transaction_id_fkey FOREIGN KEY (payment_transaction_id) REFERENCES public.payment_transactions(id) ON DELETE CASCADE;


--
-- Name: payment_transaction_events payment_transaction_events_performed_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payment_transaction_events
    ADD CONSTRAINT payment_transaction_events_performed_by_fkey FOREIGN KEY (performed_by) REFERENCES public.profiles(id) ON DELETE SET NULL;


--
-- Name: payment_transaction_events payment_transaction_events_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payment_transaction_events
    ADD CONSTRAINT payment_transaction_events_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(id) ON DELETE CASCADE;


--
-- Name: payment_transactions payment_transactions_initiated_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payment_transactions
    ADD CONSTRAINT payment_transactions_initiated_by_fkey FOREIGN KEY (initiated_by) REFERENCES public.profiles(id) ON DELETE SET NULL;


--
-- Name: payment_transactions payment_transactions_risk_resolved_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payment_transactions
    ADD CONSTRAINT payment_transactions_risk_resolved_by_fkey FOREIGN KEY (risk_resolved_by) REFERENCES public.profiles(id) ON DELETE SET NULL;


--
-- Name: payment_transactions payment_transactions_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payment_transactions
    ADD CONSTRAINT payment_transactions_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(id) ON DELETE CASCADE;


--
-- Name: po_receive_event_items po_receive_event_items_po_item_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.po_receive_event_items
    ADD CONSTRAINT po_receive_event_items_po_item_id_fkey FOREIGN KEY (po_item_id) REFERENCES public.purchase_order_items(id) ON DELETE CASCADE;


--
-- Name: po_receive_event_items po_receive_event_items_receive_event_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.po_receive_event_items
    ADD CONSTRAINT po_receive_event_items_receive_event_id_fkey FOREIGN KEY (receive_event_id) REFERENCES public.po_receive_events(id) ON DELETE CASCADE;


--
-- Name: po_receive_events po_receive_events_performed_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.po_receive_events
    ADD CONSTRAINT po_receive_events_performed_by_fkey FOREIGN KEY (performed_by) REFERENCES public.profiles(id) ON DELETE SET NULL;


--
-- Name: po_receive_events po_receive_events_purchase_order_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.po_receive_events
    ADD CONSTRAINT po_receive_events_purchase_order_id_fkey FOREIGN KEY (purchase_order_id) REFERENCES public.purchase_orders(id) ON DELETE CASCADE;


--
-- Name: po_receive_events po_receive_events_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.po_receive_events
    ADD CONSTRAINT po_receive_events_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(id) ON DELETE CASCADE;


--
-- Name: product_ledger product_ledger_factory_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.product_ledger
    ADD CONSTRAINT product_ledger_factory_id_fkey FOREIGN KEY (factory_id) REFERENCES public.factories(id) ON DELETE RESTRICT;


--
-- Name: product_ledger product_ledger_item_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.product_ledger
    ADD CONSTRAINT product_ledger_item_id_fkey FOREIGN KEY (item_id) REFERENCES public.items(id) ON DELETE RESTRICT;


--
-- Name: product_ledger product_ledger_performed_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.product_ledger
    ADD CONSTRAINT product_ledger_performed_by_fkey FOREIGN KEY (performed_by) REFERENCES public.profiles(id) ON DELETE SET NULL;


--
-- Name: product_ledger product_ledger_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.product_ledger
    ADD CONSTRAINT product_ledger_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(id) ON DELETE CASCADE;


--
-- Name: production_batch_items production_batch_items_batch_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.production_batch_items
    ADD CONSTRAINT production_batch_items_batch_id_fkey FOREIGN KEY (batch_id) REFERENCES public.production_batches(id) ON DELETE CASCADE;


--
-- Name: production_batch_items production_batch_items_item_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.production_batch_items
    ADD CONSTRAINT production_batch_items_item_id_fkey FOREIGN KEY (item_id) REFERENCES public.items(id) ON DELETE RESTRICT;


--
-- Name: production_batch_items production_batch_items_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.production_batch_items
    ADD CONSTRAINT production_batch_items_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(id) ON DELETE CASCADE;


--
-- Name: production_batch_stage_logs production_batch_stage_logs_batch_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.production_batch_stage_logs
    ADD CONSTRAINT production_batch_stage_logs_batch_id_fkey FOREIGN KEY (batch_id) REFERENCES public.production_batches(id) ON DELETE CASCADE;


--
-- Name: production_batch_stage_logs production_batch_stage_logs_formula_stage_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.production_batch_stage_logs
    ADD CONSTRAINT production_batch_stage_logs_formula_stage_id_fkey FOREIGN KEY (formula_stage_id) REFERENCES public.production_formula_stages(id) ON DELETE SET NULL;


--
-- Name: production_batch_stage_logs production_batch_stage_logs_logged_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.production_batch_stage_logs
    ADD CONSTRAINT production_batch_stage_logs_logged_by_fkey FOREIGN KEY (logged_by) REFERENCES public.profiles(id) ON DELETE SET NULL;


--
-- Name: production_batch_stage_logs production_batch_stage_logs_production_line_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.production_batch_stage_logs
    ADD CONSTRAINT production_batch_stage_logs_production_line_id_fkey FOREIGN KEY (production_line_id) REFERENCES public.production_lines(id) ON DELETE SET NULL;


--
-- Name: production_batch_stage_logs production_batch_stage_logs_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.production_batch_stage_logs
    ADD CONSTRAINT production_batch_stage_logs_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(id) ON DELETE CASCADE;


--
-- Name: production_batches production_batches_completed_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.production_batches
    ADD CONSTRAINT production_batches_completed_by_fkey FOREIGN KEY (completed_by) REFERENCES public.profiles(id) ON DELETE SET NULL;


--
-- Name: production_batches production_batches_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.production_batches
    ADD CONSTRAINT production_batches_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.profiles(id) ON DELETE SET NULL;


--
-- Name: production_batches production_batches_formula_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.production_batches
    ADD CONSTRAINT production_batches_formula_id_fkey FOREIGN KEY (formula_id) REFERENCES public.production_formulas(id) ON DELETE SET NULL;


--
-- Name: production_batches production_batches_production_line_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.production_batches
    ADD CONSTRAINT production_batches_production_line_id_fkey FOREIGN KEY (production_line_id) REFERENCES public.production_lines(id) ON DELETE RESTRICT;


--
-- Name: production_batches production_batches_started_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.production_batches
    ADD CONSTRAINT production_batches_started_by_fkey FOREIGN KEY (started_by) REFERENCES public.profiles(id) ON DELETE SET NULL;


--
-- Name: production_batches production_batches_updated_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.production_batches
    ADD CONSTRAINT production_batches_updated_by_fkey FOREIGN KEY (updated_by) REFERENCES public.profiles(id) ON DELETE SET NULL;


--
-- Name: production_batches production_batches_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.production_batches
    ADD CONSTRAINT production_batches_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(id) ON DELETE CASCADE;


--
-- Name: production_formula_items production_formula_items_formula_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.production_formula_items
    ADD CONSTRAINT production_formula_items_formula_id_fkey FOREIGN KEY (formula_id) REFERENCES public.production_formulas(id) ON DELETE CASCADE;


--
-- Name: production_formula_items production_formula_items_item_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.production_formula_items
    ADD CONSTRAINT production_formula_items_item_id_fkey FOREIGN KEY (item_id) REFERENCES public.items(id) ON DELETE RESTRICT;


--
-- Name: production_formula_items production_formula_items_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.production_formula_items
    ADD CONSTRAINT production_formula_items_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(id) ON DELETE CASCADE;


--
-- Name: production_formula_stages production_formula_stages_expected_output_item_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.production_formula_stages
    ADD CONSTRAINT production_formula_stages_expected_output_item_id_fkey FOREIGN KEY (expected_output_item_id) REFERENCES public.items(id) ON DELETE SET NULL;


--
-- Name: production_formula_stages production_formula_stages_formula_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.production_formula_stages
    ADD CONSTRAINT production_formula_stages_formula_id_fkey FOREIGN KEY (formula_id) REFERENCES public.production_formulas(id) ON DELETE CASCADE;


--
-- Name: production_formula_stages production_formula_stages_machine_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.production_formula_stages
    ADD CONSTRAINT production_formula_stages_machine_id_fkey FOREIGN KEY (machine_id) REFERENCES public.machines(id) ON DELETE SET NULL;


--
-- Name: production_formula_stages production_formula_stages_production_line_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.production_formula_stages
    ADD CONSTRAINT production_formula_stages_production_line_id_fkey FOREIGN KEY (production_line_id) REFERENCES public.production_lines(id) ON DELETE SET NULL;


--
-- Name: production_formula_stages production_formula_stages_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.production_formula_stages
    ADD CONSTRAINT production_formula_stages_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(id) ON DELETE CASCADE;


--
-- Name: production_formulas production_formulas_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.production_formulas
    ADD CONSTRAINT production_formulas_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.profiles(id) ON DELETE SET NULL;


--
-- Name: production_formulas production_formulas_updated_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.production_formulas
    ADD CONSTRAINT production_formulas_updated_by_fkey FOREIGN KEY (updated_by) REFERENCES public.profiles(id) ON DELETE SET NULL;


--
-- Name: production_formulas production_formulas_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.production_formulas
    ADD CONSTRAINT production_formulas_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(id) ON DELETE CASCADE;


--
-- Name: production_lines production_lines_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.production_lines
    ADD CONSTRAINT production_lines_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.profiles(id) ON DELETE SET NULL;


--
-- Name: production_lines production_lines_factory_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.production_lines
    ADD CONSTRAINT production_lines_factory_id_fkey FOREIGN KEY (factory_id) REFERENCES public.factories(id) ON DELETE RESTRICT;


--
-- Name: production_lines production_lines_machine_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.production_lines
    ADD CONSTRAINT production_lines_machine_id_fkey FOREIGN KEY (machine_id) REFERENCES public.machines(id) ON DELETE SET NULL;


--
-- Name: production_lines production_lines_updated_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.production_lines
    ADD CONSTRAINT production_lines_updated_by_fkey FOREIGN KEY (updated_by) REFERENCES public.profiles(id) ON DELETE SET NULL;


--
-- Name: production_lines production_lines_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.production_lines
    ADD CONSTRAINT production_lines_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(id) ON DELETE CASCADE;


--
-- Name: products products_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.products
    ADD CONSTRAINT products_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.profiles(id);


--
-- Name: products products_deleted_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.products
    ADD CONSTRAINT products_deleted_by_fkey FOREIGN KEY (deleted_by) REFERENCES public.profiles(id);


--
-- Name: products products_factory_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.products
    ADD CONSTRAINT products_factory_id_fkey FOREIGN KEY (factory_id) REFERENCES public.factories(id);


--
-- Name: products products_item_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.products
    ADD CONSTRAINT products_item_id_fkey FOREIGN KEY (item_id) REFERENCES public.items(id);


--
-- Name: products products_updated_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.products
    ADD CONSTRAINT products_updated_by_fkey FOREIGN KEY (updated_by) REFERENCES public.profiles(id);


--
-- Name: products products_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.products
    ADD CONSTRAINT products_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(id) ON DELETE CASCADE;


--
-- Name: project_attachments project_attachments_attached_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_attachments
    ADD CONSTRAINT project_attachments_attached_by_fkey FOREIGN KEY (attached_by) REFERENCES public.profiles(id);


--
-- Name: project_attachments project_attachments_attachment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_attachments
    ADD CONSTRAINT project_attachments_attachment_id_fkey FOREIGN KEY (attachment_id) REFERENCES public.attachments(id) ON DELETE CASCADE;


--
-- Name: project_attachments project_attachments_project_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_attachments
    ADD CONSTRAINT project_attachments_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.projects(id) ON DELETE CASCADE;


--
-- Name: project_attachments project_attachments_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_attachments
    ADD CONSTRAINT project_attachments_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(id) ON DELETE CASCADE;


--
-- Name: project_component_activity_events project_component_activity_events_performed_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_component_activity_events
    ADD CONSTRAINT project_component_activity_events_performed_by_fkey FOREIGN KEY (performed_by) REFERENCES public.profiles(id) ON DELETE SET NULL;


--
-- Name: project_component_activity_events project_component_activity_events_project_component_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_component_activity_events
    ADD CONSTRAINT project_component_activity_events_project_component_id_fkey FOREIGN KEY (project_component_id) REFERENCES public.project_components(id) ON DELETE CASCADE;


--
-- Name: project_component_activity_events project_component_activity_events_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_component_activity_events
    ADD CONSTRAINT project_component_activity_events_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(id) ON DELETE CASCADE;


--
-- Name: project_component_attachments project_component_attachments_attached_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_component_attachments
    ADD CONSTRAINT project_component_attachments_attached_by_fkey FOREIGN KEY (attached_by) REFERENCES public.profiles(id);


--
-- Name: project_component_attachments project_component_attachments_attachment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_component_attachments
    ADD CONSTRAINT project_component_attachments_attachment_id_fkey FOREIGN KEY (attachment_id) REFERENCES public.attachments(id) ON DELETE CASCADE;


--
-- Name: project_component_attachments project_component_attachments_project_component_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_component_attachments
    ADD CONSTRAINT project_component_attachments_project_component_id_fkey FOREIGN KEY (project_component_id) REFERENCES public.project_components(id) ON DELETE CASCADE;


--
-- Name: project_component_attachments project_component_attachments_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_component_attachments
    ADD CONSTRAINT project_component_attachments_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(id) ON DELETE CASCADE;


--
-- Name: project_component_item_ledger project_component_item_ledger_invoice_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_component_item_ledger
    ADD CONSTRAINT project_component_item_ledger_invoice_id_fkey FOREIGN KEY (invoice_id) REFERENCES public.account_invoices(id) ON DELETE SET NULL;


--
-- Name: project_component_item_ledger project_component_item_ledger_item_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_component_item_ledger
    ADD CONSTRAINT project_component_item_ledger_item_id_fkey FOREIGN KEY (item_id) REFERENCES public.items(id) ON DELETE RESTRICT;


--
-- Name: project_component_item_ledger project_component_item_ledger_performed_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_component_item_ledger
    ADD CONSTRAINT project_component_item_ledger_performed_by_fkey FOREIGN KEY (performed_by) REFERENCES public.profiles(id) ON DELETE SET NULL;


--
-- Name: project_component_item_ledger project_component_item_ledger_project_component_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_component_item_ledger
    ADD CONSTRAINT project_component_item_ledger_project_component_id_fkey FOREIGN KEY (project_component_id) REFERENCES public.project_components(id) ON DELETE RESTRICT;


--
-- Name: project_component_item_ledger project_component_item_ledger_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_component_item_ledger
    ADD CONSTRAINT project_component_item_ledger_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(id) ON DELETE CASCADE;


--
-- Name: project_component_items project_component_items_item_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_component_items
    ADD CONSTRAINT project_component_items_item_id_fkey FOREIGN KEY (item_id) REFERENCES public.items(id);


--
-- Name: project_component_items project_component_items_project_component_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_component_items
    ADD CONSTRAINT project_component_items_project_component_id_fkey FOREIGN KEY (project_component_id) REFERENCES public.project_components(id);


--
-- Name: project_component_items project_component_items_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_component_items
    ADD CONSTRAINT project_component_items_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(id) ON DELETE CASCADE;


--
-- Name: project_component_tasks project_component_tasks_project_component_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_component_tasks
    ADD CONSTRAINT project_component_tasks_project_component_id_fkey FOREIGN KEY (project_component_id) REFERENCES public.project_components(id);


--
-- Name: project_component_tasks project_component_tasks_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_component_tasks
    ADD CONSTRAINT project_component_tasks_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(id) ON DELETE CASCADE;


--
-- Name: project_components project_components_project_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_components
    ADD CONSTRAINT project_components_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.projects(id);


--
-- Name: project_components project_components_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_components
    ADD CONSTRAINT project_components_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(id) ON DELETE CASCADE;


--
-- Name: project_events project_events_performed_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_events
    ADD CONSTRAINT project_events_performed_by_fkey FOREIGN KEY (performed_by) REFERENCES public.profiles(id) ON DELETE SET NULL;


--
-- Name: project_events project_events_project_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_events
    ADD CONSTRAINT project_events_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.projects(id) ON DELETE CASCADE;


--
-- Name: project_events project_events_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_events
    ADD CONSTRAINT project_events_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(id) ON DELETE CASCADE;


--
-- Name: project_members project_members_assigned_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_members
    ADD CONSTRAINT project_members_assigned_by_fkey FOREIGN KEY (assigned_by) REFERENCES public.profiles(id) ON DELETE SET NULL;


--
-- Name: project_members project_members_project_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_members
    ADD CONSTRAINT project_members_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.projects(id) ON DELETE CASCADE;


--
-- Name: project_members project_members_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_members
    ADD CONSTRAINT project_members_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.profiles(id) ON DELETE CASCADE;


--
-- Name: project_members project_members_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_members
    ADD CONSTRAINT project_members_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(id) ON DELETE CASCADE;


--
-- Name: projects projects_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.projects
    ADD CONSTRAINT projects_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.profiles(id);


--
-- Name: projects projects_deleted_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.projects
    ADD CONSTRAINT projects_deleted_by_fkey FOREIGN KEY (deleted_by) REFERENCES public.profiles(id);


--
-- Name: projects projects_factory_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.projects
    ADD CONSTRAINT projects_factory_id_fkey FOREIGN KEY (factory_id) REFERENCES public.factories(id);


--
-- Name: projects projects_updated_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.projects
    ADD CONSTRAINT projects_updated_by_fkey FOREIGN KEY (updated_by) REFERENCES public.profiles(id);


--
-- Name: projects projects_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.projects
    ADD CONSTRAINT projects_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(id) ON DELETE CASCADE;


--
-- Name: purchase_order_approvers purchase_order_approvers_assigned_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.purchase_order_approvers
    ADD CONSTRAINT purchase_order_approvers_assigned_by_fkey FOREIGN KEY (assigned_by) REFERENCES public.profiles(id) ON DELETE SET NULL;


--
-- Name: purchase_order_approvers purchase_order_approvers_purchase_order_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.purchase_order_approvers
    ADD CONSTRAINT purchase_order_approvers_purchase_order_id_fkey FOREIGN KEY (purchase_order_id) REFERENCES public.purchase_orders(id) ON DELETE CASCADE;


--
-- Name: purchase_order_approvers purchase_order_approvers_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.purchase_order_approvers
    ADD CONSTRAINT purchase_order_approvers_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.profiles(id) ON DELETE CASCADE;


--
-- Name: purchase_order_approvers purchase_order_approvers_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.purchase_order_approvers
    ADD CONSTRAINT purchase_order_approvers_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(id) ON DELETE CASCADE;


--
-- Name: purchase_order_events purchase_order_events_performed_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.purchase_order_events
    ADD CONSTRAINT purchase_order_events_performed_by_fkey FOREIGN KEY (performed_by) REFERENCES public.profiles(id) ON DELETE SET NULL;


--
-- Name: purchase_order_events purchase_order_events_purchase_order_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.purchase_order_events
    ADD CONSTRAINT purchase_order_events_purchase_order_id_fkey FOREIGN KEY (purchase_order_id) REFERENCES public.purchase_orders(id) ON DELETE CASCADE;


--
-- Name: purchase_order_events purchase_order_events_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.purchase_order_events
    ADD CONSTRAINT purchase_order_events_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(id) ON DELETE CASCADE;


--
-- Name: purchase_order_items purchase_order_items_item_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.purchase_order_items
    ADD CONSTRAINT purchase_order_items_item_id_fkey FOREIGN KEY (item_id) REFERENCES public.items(id) ON DELETE RESTRICT;


--
-- Name: purchase_order_items purchase_order_items_purchase_order_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.purchase_order_items
    ADD CONSTRAINT purchase_order_items_purchase_order_id_fkey FOREIGN KEY (purchase_order_id) REFERENCES public.purchase_orders(id) ON DELETE CASCADE;


--
-- Name: purchase_order_items purchase_order_items_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.purchase_order_items
    ADD CONSTRAINT purchase_order_items_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(id) ON DELETE CASCADE;


--
-- Name: purchase_orders purchase_orders_account_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.purchase_orders
    ADD CONSTRAINT purchase_orders_account_id_fkey FOREIGN KEY (account_id) REFERENCES public.accounts(id) ON DELETE RESTRICT;


--
-- Name: purchase_orders purchase_orders_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.purchase_orders
    ADD CONSTRAINT purchase_orders_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.profiles(id) ON DELETE SET NULL;


--
-- Name: purchase_orders purchase_orders_current_status_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.purchase_orders
    ADD CONSTRAINT purchase_orders_current_status_id_fkey FOREIGN KEY (current_status_id) REFERENCES public.statuses(id) ON DELETE RESTRICT;


--
-- Name: purchase_orders purchase_orders_invoice_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.purchase_orders
    ADD CONSTRAINT purchase_orders_invoice_id_fkey FOREIGN KEY (invoice_id) REFERENCES public.account_invoices(id) ON DELETE SET NULL;


--
-- Name: purchase_orders purchase_orders_order_workflow_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.purchase_orders
    ADD CONSTRAINT purchase_orders_order_workflow_id_fkey FOREIGN KEY (order_workflow_id) REFERENCES public.order_workflows(id) ON DELETE RESTRICT;


--
-- Name: purchase_orders purchase_orders_updated_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.purchase_orders
    ADD CONSTRAINT purchase_orders_updated_by_fkey FOREIGN KEY (updated_by) REFERENCES public.profiles(id) ON DELETE SET NULL;


--
-- Name: purchase_orders purchase_orders_voided_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.purchase_orders
    ADD CONSTRAINT purchase_orders_voided_by_fkey FOREIGN KEY (voided_by) REFERENCES public.profiles(id) ON DELETE SET NULL;


--
-- Name: purchase_orders purchase_orders_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.purchase_orders
    ADD CONSTRAINT purchase_orders_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(id) ON DELETE CASCADE;


--
-- Name: refresh_tokens refresh_tokens_replaced_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.refresh_tokens
    ADD CONSTRAINT refresh_tokens_replaced_by_id_fkey FOREIGN KEY (replaced_by_id) REFERENCES public.refresh_tokens(id) ON DELETE SET NULL;


--
-- Name: refresh_tokens refresh_tokens_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.refresh_tokens
    ADD CONSTRAINT refresh_tokens_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.profiles(id) ON DELETE CASCADE;


--
-- Name: refresh_tokens refresh_tokens_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.refresh_tokens
    ADD CONSTRAINT refresh_tokens_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(id) ON DELETE CASCADE;


--
-- Name: sales_deliveries sales_deliveries_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sales_deliveries
    ADD CONSTRAINT sales_deliveries_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.profiles(id) ON DELETE SET NULL;


--
-- Name: sales_deliveries sales_deliveries_delivery_method_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sales_deliveries
    ADD CONSTRAINT sales_deliveries_delivery_method_id_fkey FOREIGN KEY (delivery_method_id) REFERENCES public.delivery_methods(id) ON DELETE SET NULL;


--
-- Name: sales_deliveries sales_deliveries_sales_order_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sales_deliveries
    ADD CONSTRAINT sales_deliveries_sales_order_id_fkey FOREIGN KEY (sales_order_id) REFERENCES public.sales_orders(id) ON DELETE CASCADE;


--
-- Name: sales_deliveries sales_deliveries_updated_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sales_deliveries
    ADD CONSTRAINT sales_deliveries_updated_by_fkey FOREIGN KEY (updated_by) REFERENCES public.profiles(id) ON DELETE SET NULL;


--
-- Name: sales_deliveries sales_deliveries_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sales_deliveries
    ADD CONSTRAINT sales_deliveries_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(id) ON DELETE CASCADE;


--
-- Name: sales_delivery_items sales_delivery_items_delivery_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sales_delivery_items
    ADD CONSTRAINT sales_delivery_items_delivery_id_fkey FOREIGN KEY (delivery_id) REFERENCES public.sales_deliveries(id) ON DELETE CASCADE;


--
-- Name: sales_delivery_items sales_delivery_items_item_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sales_delivery_items
    ADD CONSTRAINT sales_delivery_items_item_id_fkey FOREIGN KEY (item_id) REFERENCES public.items(id) ON DELETE RESTRICT;


--
-- Name: sales_delivery_items sales_delivery_items_sales_order_item_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sales_delivery_items
    ADD CONSTRAINT sales_delivery_items_sales_order_item_id_fkey FOREIGN KEY (sales_order_item_id) REFERENCES public.sales_order_items(id) ON DELETE RESTRICT;


--
-- Name: sales_delivery_items sales_delivery_items_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sales_delivery_items
    ADD CONSTRAINT sales_delivery_items_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(id) ON DELETE CASCADE;


--
-- Name: sales_order_items sales_order_items_item_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sales_order_items
    ADD CONSTRAINT sales_order_items_item_id_fkey FOREIGN KEY (item_id) REFERENCES public.items(id) ON DELETE RESTRICT;


--
-- Name: sales_order_items sales_order_items_sales_order_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sales_order_items
    ADD CONSTRAINT sales_order_items_sales_order_id_fkey FOREIGN KEY (sales_order_id) REFERENCES public.sales_orders(id) ON DELETE CASCADE;


--
-- Name: sales_order_items sales_order_items_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sales_order_items
    ADD CONSTRAINT sales_order_items_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(id) ON DELETE CASCADE;


--
-- Name: sales_orders sales_orders_account_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sales_orders
    ADD CONSTRAINT sales_orders_account_id_fkey FOREIGN KEY (account_id) REFERENCES public.accounts(id) ON DELETE RESTRICT;


--
-- Name: sales_orders sales_orders_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sales_orders
    ADD CONSTRAINT sales_orders_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.profiles(id) ON DELETE SET NULL;


--
-- Name: sales_orders sales_orders_current_status_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sales_orders
    ADD CONSTRAINT sales_orders_current_status_id_fkey FOREIGN KEY (current_status_id) REFERENCES public.statuses(id) ON DELETE RESTRICT;


--
-- Name: sales_orders sales_orders_factory_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sales_orders
    ADD CONSTRAINT sales_orders_factory_id_fkey FOREIGN KEY (factory_id) REFERENCES public.factories(id) ON DELETE RESTRICT;


--
-- Name: sales_orders sales_orders_invoice_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sales_orders
    ADD CONSTRAINT sales_orders_invoice_id_fkey FOREIGN KEY (invoice_id) REFERENCES public.account_invoices(id) ON DELETE SET NULL;


--
-- Name: sales_orders sales_orders_updated_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sales_orders
    ADD CONSTRAINT sales_orders_updated_by_fkey FOREIGN KEY (updated_by) REFERENCES public.profiles(id) ON DELETE SET NULL;


--
-- Name: sales_orders sales_orders_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sales_orders
    ADD CONSTRAINT sales_orders_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(id) ON DELETE CASCADE;


--
-- Name: statuses statuses_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.statuses
    ADD CONSTRAINT statuses_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(id) ON DELETE CASCADE;


--
-- Name: transfer_order_approvers transfer_order_approvers_assigned_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transfer_order_approvers
    ADD CONSTRAINT transfer_order_approvers_assigned_by_fkey FOREIGN KEY (assigned_by) REFERENCES public.profiles(id) ON DELETE SET NULL;


--
-- Name: transfer_order_approvers transfer_order_approvers_transfer_order_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transfer_order_approvers
    ADD CONSTRAINT transfer_order_approvers_transfer_order_id_fkey FOREIGN KEY (transfer_order_id) REFERENCES public.transfer_orders(id) ON DELETE CASCADE;


--
-- Name: transfer_order_approvers transfer_order_approvers_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transfer_order_approvers
    ADD CONSTRAINT transfer_order_approvers_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.profiles(id) ON DELETE CASCADE;


--
-- Name: transfer_order_approvers transfer_order_approvers_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transfer_order_approvers
    ADD CONSTRAINT transfer_order_approvers_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(id) ON DELETE CASCADE;


--
-- Name: transfer_order_events transfer_order_events_performed_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transfer_order_events
    ADD CONSTRAINT transfer_order_events_performed_by_fkey FOREIGN KEY (performed_by) REFERENCES public.profiles(id) ON DELETE SET NULL;


--
-- Name: transfer_order_events transfer_order_events_transfer_order_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transfer_order_events
    ADD CONSTRAINT transfer_order_events_transfer_order_id_fkey FOREIGN KEY (transfer_order_id) REFERENCES public.transfer_orders(id) ON DELETE CASCADE;


--
-- Name: transfer_order_events transfer_order_events_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transfer_order_events
    ADD CONSTRAINT transfer_order_events_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(id) ON DELETE CASCADE;


--
-- Name: transfer_order_items transfer_order_items_approved_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transfer_order_items
    ADD CONSTRAINT transfer_order_items_approved_by_fkey FOREIGN KEY (approved_by) REFERENCES public.profiles(id) ON DELETE SET NULL;


--
-- Name: transfer_order_items transfer_order_items_item_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transfer_order_items
    ADD CONSTRAINT transfer_order_items_item_id_fkey FOREIGN KEY (item_id) REFERENCES public.items(id) ON DELETE RESTRICT;


--
-- Name: transfer_order_items transfer_order_items_transfer_order_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transfer_order_items
    ADD CONSTRAINT transfer_order_items_transfer_order_id_fkey FOREIGN KEY (transfer_order_id) REFERENCES public.transfer_orders(id) ON DELETE CASCADE;


--
-- Name: transfer_order_items transfer_order_items_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transfer_order_items
    ADD CONSTRAINT transfer_order_items_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(id) ON DELETE CASCADE;


--
-- Name: transfer_orders transfer_orders_completed_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transfer_orders
    ADD CONSTRAINT transfer_orders_completed_by_fkey FOREIGN KEY (completed_by) REFERENCES public.profiles(id) ON DELETE SET NULL;


--
-- Name: transfer_orders transfer_orders_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transfer_orders
    ADD CONSTRAINT transfer_orders_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.profiles(id) ON DELETE SET NULL;


--
-- Name: transfer_orders transfer_orders_current_status_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transfer_orders
    ADD CONSTRAINT transfer_orders_current_status_id_fkey FOREIGN KEY (current_status_id) REFERENCES public.statuses(id) ON DELETE RESTRICT;


--
-- Name: transfer_orders transfer_orders_updated_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transfer_orders
    ADD CONSTRAINT transfer_orders_updated_by_fkey FOREIGN KEY (updated_by) REFERENCES public.profiles(id) ON DELETE SET NULL;


--
-- Name: transfer_orders transfer_orders_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transfer_orders
    ADD CONSTRAINT transfer_orders_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(id) ON DELETE CASCADE;


--
-- Name: work_order_approvers work_order_approvers_assigned_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_order_approvers
    ADD CONSTRAINT work_order_approvers_assigned_by_fkey FOREIGN KEY (assigned_by) REFERENCES public.profiles(id) ON DELETE SET NULL;


--
-- Name: work_order_approvers work_order_approvers_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_order_approvers
    ADD CONSTRAINT work_order_approvers_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.profiles(id) ON DELETE CASCADE;


--
-- Name: work_order_approvers work_order_approvers_work_order_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_order_approvers
    ADD CONSTRAINT work_order_approvers_work_order_id_fkey FOREIGN KEY (work_order_id) REFERENCES public.work_orders(id) ON DELETE CASCADE;


--
-- Name: work_order_approvers work_order_approvers_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_order_approvers
    ADD CONSTRAINT work_order_approvers_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(id) ON DELETE CASCADE;


--
-- Name: work_order_events work_order_events_performed_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_order_events
    ADD CONSTRAINT work_order_events_performed_by_fkey FOREIGN KEY (performed_by) REFERENCES public.profiles(id) ON DELETE SET NULL;


--
-- Name: work_order_events work_order_events_work_order_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_order_events
    ADD CONSTRAINT work_order_events_work_order_id_fkey FOREIGN KEY (work_order_id) REFERENCES public.work_orders(id) ON DELETE CASCADE;


--
-- Name: work_order_events work_order_events_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_order_events
    ADD CONSTRAINT work_order_events_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(id) ON DELETE CASCADE;


--
-- Name: work_order_items work_order_items_consumed_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_order_items
    ADD CONSTRAINT work_order_items_consumed_by_fkey FOREIGN KEY (consumed_by) REFERENCES public.profiles(id) ON DELETE SET NULL;


--
-- Name: work_order_items work_order_items_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_order_items
    ADD CONSTRAINT work_order_items_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.profiles(id);


--
-- Name: work_order_items work_order_items_deleted_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_order_items
    ADD CONSTRAINT work_order_items_deleted_by_fkey FOREIGN KEY (deleted_by) REFERENCES public.profiles(id);


--
-- Name: work_order_items work_order_items_item_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_order_items
    ADD CONSTRAINT work_order_items_item_id_fkey FOREIGN KEY (item_id) REFERENCES public.items(id);


--
-- Name: work_order_items work_order_items_replaced_item_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_order_items
    ADD CONSTRAINT work_order_items_replaced_item_id_fkey FOREIGN KEY (replaced_item_id) REFERENCES public.items(id);


--
-- Name: work_order_items work_order_items_updated_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_order_items
    ADD CONSTRAINT work_order_items_updated_by_fkey FOREIGN KEY (updated_by) REFERENCES public.profiles(id) ON DELETE SET NULL;


--
-- Name: work_order_items work_order_items_work_order_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_order_items
    ADD CONSTRAINT work_order_items_work_order_id_fkey FOREIGN KEY (work_order_id) REFERENCES public.work_orders(id) ON DELETE CASCADE;


--
-- Name: work_order_items work_order_items_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_order_items
    ADD CONSTRAINT work_order_items_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(id) ON DELETE CASCADE;


--
-- Name: work_order_template_approvers work_order_template_approvers_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_order_template_approvers
    ADD CONSTRAINT work_order_template_approvers_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.profiles(id) ON DELETE CASCADE;


--
-- Name: work_order_template_approvers work_order_template_approvers_work_order_template_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_order_template_approvers
    ADD CONSTRAINT work_order_template_approvers_work_order_template_id_fkey FOREIGN KEY (work_order_template_id) REFERENCES public.work_order_templates(id) ON DELETE CASCADE;


--
-- Name: work_order_template_approvers work_order_template_approvers_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_order_template_approvers
    ADD CONSTRAINT work_order_template_approvers_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(id) ON DELETE CASCADE;


--
-- Name: work_order_template_items work_order_template_items_item_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_order_template_items
    ADD CONSTRAINT work_order_template_items_item_id_fkey FOREIGN KEY (item_id) REFERENCES public.items(id);


--
-- Name: work_order_template_items work_order_template_items_replaced_item_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_order_template_items
    ADD CONSTRAINT work_order_template_items_replaced_item_id_fkey FOREIGN KEY (replaced_item_id) REFERENCES public.items(id);


--
-- Name: work_order_template_items work_order_template_items_work_order_template_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_order_template_items
    ADD CONSTRAINT work_order_template_items_work_order_template_id_fkey FOREIGN KEY (work_order_template_id) REFERENCES public.work_order_templates(id) ON DELETE CASCADE;


--
-- Name: work_order_template_items work_order_template_items_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_order_template_items
    ADD CONSTRAINT work_order_template_items_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(id) ON DELETE CASCADE;


--
-- Name: work_order_templates work_order_templates_account_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_order_templates
    ADD CONSTRAINT work_order_templates_account_id_fkey FOREIGN KEY (account_id) REFERENCES public.accounts(id) ON DELETE RESTRICT;


--
-- Name: work_order_templates work_order_templates_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_order_templates
    ADD CONSTRAINT work_order_templates_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.profiles(id) ON DELETE SET NULL;


--
-- Name: work_order_templates work_order_templates_updated_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_order_templates
    ADD CONSTRAINT work_order_templates_updated_by_fkey FOREIGN KEY (updated_by) REFERENCES public.profiles(id) ON DELETE SET NULL;


--
-- Name: work_order_templates work_order_templates_work_order_type_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_order_templates
    ADD CONSTRAINT work_order_templates_work_order_type_id_fkey FOREIGN KEY (work_order_type_id) REFERENCES public.work_order_types(id) ON DELETE RESTRICT;


--
-- Name: work_order_templates work_order_templates_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_order_templates
    ADD CONSTRAINT work_order_templates_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(id) ON DELETE CASCADE;


--
-- Name: work_order_types work_order_types_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_order_types
    ADD CONSTRAINT work_order_types_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.profiles(id) ON DELETE SET NULL;


--
-- Name: work_order_types work_order_types_deleted_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_order_types
    ADD CONSTRAINT work_order_types_deleted_by_fkey FOREIGN KEY (deleted_by) REFERENCES public.profiles(id) ON DELETE SET NULL;


--
-- Name: work_order_types work_order_types_updated_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_order_types
    ADD CONSTRAINT work_order_types_updated_by_fkey FOREIGN KEY (updated_by) REFERENCES public.profiles(id) ON DELETE SET NULL;


--
-- Name: work_order_types work_order_types_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_order_types
    ADD CONSTRAINT work_order_types_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(id) ON DELETE CASCADE;


--
-- Name: work_orders work_orders_account_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_orders
    ADD CONSTRAINT work_orders_account_id_fkey FOREIGN KEY (account_id) REFERENCES public.accounts(id) ON DELETE RESTRICT;


--
-- Name: work_orders work_orders_approved_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_orders
    ADD CONSTRAINT work_orders_approved_by_fkey FOREIGN KEY (approved_by) REFERENCES public.profiles(id) ON DELETE SET NULL;


--
-- Name: work_orders work_orders_completed_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_orders
    ADD CONSTRAINT work_orders_completed_by_fkey FOREIGN KEY (completed_by) REFERENCES public.profiles(id) ON DELETE SET NULL;


--
-- Name: work_orders work_orders_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_orders
    ADD CONSTRAINT work_orders_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.profiles(id);


--
-- Name: work_orders work_orders_deleted_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_orders
    ADD CONSTRAINT work_orders_deleted_by_fkey FOREIGN KEY (deleted_by) REFERENCES public.profiles(id);


--
-- Name: work_orders work_orders_factory_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_orders
    ADD CONSTRAINT work_orders_factory_id_fkey FOREIGN KEY (factory_id) REFERENCES public.factories(id);


--
-- Name: work_orders work_orders_invoice_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_orders
    ADD CONSTRAINT work_orders_invoice_id_fkey FOREIGN KEY (invoice_id) REFERENCES public.account_invoices(id) ON DELETE SET NULL;


--
-- Name: work_orders work_orders_machine_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_orders
    ADD CONSTRAINT work_orders_machine_id_fkey FOREIGN KEY (machine_id) REFERENCES public.machines(id);


--
-- Name: work_orders work_orders_project_component_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_orders
    ADD CONSTRAINT work_orders_project_component_id_fkey FOREIGN KEY (project_component_id) REFERENCES public.project_components(id);


--
-- Name: work_orders work_orders_started_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_orders
    ADD CONSTRAINT work_orders_started_by_fkey FOREIGN KEY (started_by) REFERENCES public.profiles(id) ON DELETE SET NULL;


--
-- Name: work_orders work_orders_updated_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_orders
    ADD CONSTRAINT work_orders_updated_by_fkey FOREIGN KEY (updated_by) REFERENCES public.profiles(id);


--
-- Name: work_orders work_orders_voided_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_orders
    ADD CONSTRAINT work_orders_voided_by_fkey FOREIGN KEY (voided_by) REFERENCES public.profiles(id) ON DELETE SET NULL;


--
-- Name: work_orders work_orders_work_order_template_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_orders
    ADD CONSTRAINT work_orders_work_order_template_id_fkey FOREIGN KEY (work_order_template_id) REFERENCES public.work_order_templates(id) ON DELETE SET NULL;


--
-- Name: work_orders work_orders_work_order_type_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_orders
    ADD CONSTRAINT work_orders_work_order_type_id_fkey FOREIGN KEY (work_order_type_id) REFERENCES public.work_order_types(id) ON DELETE RESTRICT;


--
-- Name: work_orders work_orders_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_orders
    ADD CONSTRAINT work_orders_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(id) ON DELETE CASCADE;


--
-- Name: workspace_audit_logs workspace_audit_logs_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.workspace_audit_logs
    ADD CONSTRAINT workspace_audit_logs_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.profiles(id) ON DELETE SET NULL;


--
-- Name: workspace_audit_logs workspace_audit_logs_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.workspace_audit_logs
    ADD CONSTRAINT workspace_audit_logs_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(id) ON DELETE CASCADE;


--
-- Name: workspace_invitations workspace_invitations_accepted_by_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.workspace_invitations
    ADD CONSTRAINT workspace_invitations_accepted_by_user_id_fkey FOREIGN KEY (accepted_by_user_id) REFERENCES public.profiles(id) ON DELETE SET NULL;


--
-- Name: workspace_invitations workspace_invitations_invited_by_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.workspace_invitations
    ADD CONSTRAINT workspace_invitations_invited_by_user_id_fkey FOREIGN KEY (invited_by_user_id) REFERENCES public.profiles(id) ON DELETE SET NULL;


--
-- Name: workspace_invitations workspace_invitations_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.workspace_invitations
    ADD CONSTRAINT workspace_invitations_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(id) ON DELETE CASCADE;


--
-- Name: workspace_members workspace_members_invited_by_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.workspace_members
    ADD CONSTRAINT workspace_members_invited_by_user_id_fkey FOREIGN KEY (invited_by_user_id) REFERENCES public.profiles(id) ON DELETE SET NULL;


--
-- Name: workspace_members workspace_members_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.workspace_members
    ADD CONSTRAINT workspace_members_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.profiles(id) ON DELETE CASCADE;


--
-- Name: workspace_members workspace_members_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.workspace_members
    ADD CONSTRAINT workspace_members_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(id) ON DELETE CASCADE;


--
-- Name: workspaces workspaces_created_by_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.workspaces
    ADD CONSTRAINT workspaces_created_by_user_id_fkey FOREIGN KEY (created_by_user_id) REFERENCES public.profiles(id) ON DELETE SET NULL;


--
-- Name: workspaces workspaces_owner_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.workspaces
    ADD CONSTRAINT workspaces_owner_user_id_fkey FOREIGN KEY (owner_user_id) REFERENCES public.profiles(id) ON DELETE SET NULL;


--
-- Name: workspaces workspaces_subscription_plan_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.workspaces
    ADD CONSTRAINT workspaces_subscription_plan_id_fkey FOREIGN KEY (subscription_plan_id) REFERENCES public.subscription_plans(id);


--
-- PostgreSQL database dump complete
--



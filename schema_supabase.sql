-- =========================================================
-- NeuroGuía Premium
-- schema_supabase.sql
-- Esquema base para PostgreSQL / Supabase
-- =========================================================

-- Recomendado:
-- 1. Ejecutar este script en una base vacía o controlada
-- 2. Revisar políticas RLS después de crear las tablas
-- 3. Ajustar auth / multiusuario según tu despliegue final

-- =========================================================
-- EXTENSIONES
-- =========================================================
create extension if not exists "pgcrypto";

-- =========================================================
-- TABLA: app_meta
-- =========================================================
create table if not exists public.app_meta (
    meta_key text primary key,
    meta_value jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

-- =========================================================
-- TABLA: families
-- =========================================================
create table if not exists public.families (
    family_id uuid primary key default gen_random_uuid(),
    unit_type text not null default 'individual',
    caregiver_alias text,
    context_notes text,
    support_network text,
    environmental_factors text,
    global_history text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),

    constraint chk_families_unit_type
        check (unit_type in ('individual', 'family'))
);

create index if not exists idx_families_unit_type
    on public.families (unit_type);

create index if not exists idx_families_updated_at
    on public.families (updated_at desc);

-- =========================================================
-- TABLA: profiles
-- =========================================================
create table if not exists public.profiles (
    profile_id uuid primary key default gen_random_uuid(),
    family_id uuid references public.families(family_id) on delete cascade,

    alias text,
    age integer,
    role text,

    conditions jsonb not null default '[]'::jsonb,
    strengths jsonb not null default '[]'::jsonb,
    triggers jsonb not null default '[]'::jsonb,
    early_signs jsonb not null default '[]'::jsonb,
    helpful_strategies jsonb not null default '[]'::jsonb,
    harmful_strategies jsonb not null default '[]'::jsonb,
    sensory_needs jsonb not null default '[]'::jsonb,
    emotional_needs jsonb not null default '[]'::jsonb,

    autonomy_level text,
    sleep_profile text,
    school_profile text,
    executive_profile text,
    evolution_notes text,

    is_active boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),

    constraint chk_profiles_age
        check (age is null or (age >= 0 and age <= 120))
);

create index if not exists idx_profiles_family_id
    on public.profiles (family_id);

create index if not exists idx_profiles_is_active
    on public.profiles (is_active);

create index if not exists idx_profiles_updated_at
    on public.profiles (updated_at desc);

create index if not exists idx_profiles_conditions_gin
    on public.profiles using gin (conditions);

-- =========================================================
-- TABLA: ng_case_memory
-- =========================================================
create table if not exists public.ng_case_memory (
    case_id uuid primary key default gen_random_uuid(),
    family_id uuid references public.families(family_id) on delete set null,
    profile_id uuid references public.profiles(profile_id) on delete set null,

    unit_type text not null default 'individual',

    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),

    raw_input text,
    normalized_summary text,

    detected_category text,
    detected_stage text,
    primary_state text,
    secondary_states jsonb not null default '[]'::jsonb,

    emotional_intensity double precision,
    caregiver_capacity double precision,
    sensory_overload_risk double precision,
    executive_block_risk double precision,
    meltdown_risk double precision,
    shutdown_risk double precision,
    burnout_risk double precision,
    sleep_disruption_risk double precision,

    suggested_strategy text,
    suggested_microaction text,
    suggested_routine_type text,
    response_mode text,

    user_feedback text,
    observed_result text,
    usefulness_score double precision,
    applied_successfully boolean not null default false,

    helps_patterns jsonb not null default '[]'::jsonb,
    worsens_patterns jsonb not null default '[]'::jsonb,
    followup_needed boolean not null default false,
    tags jsonb not null default '[]'::jsonb
);

create index if not exists idx_ng_case_memory_family_id
    on public.ng_case_memory (family_id);

create index if not exists idx_ng_case_memory_profile_id
    on public.ng_case_memory (profile_id);

create index if not exists idx_ng_case_memory_primary_state
    on public.ng_case_memory (primary_state);

create index if not exists idx_ng_case_memory_detected_category
    on public.ng_case_memory (detected_category);

create index if not exists idx_ng_case_memory_detected_stage
    on public.ng_case_memory (detected_stage);

create index if not exists idx_ng_case_memory_created_at
    on public.ng_case_memory (created_at desc);

create index if not exists idx_ng_case_memory_tags_gin
    on public.ng_case_memory using gin (tags);

create index if not exists idx_ng_case_memory_secondary_states_gin
    on public.ng_case_memory using gin (secondary_states);

-- =========================================================
-- TABLA: learned_patterns
-- =========================================================
create table if not exists public.learned_patterns (
    pattern_id uuid primary key default gen_random_uuid(),
    family_id uuid references public.families(family_id) on delete set null,
    profile_id uuid references public.profiles(profile_id) on delete set null,

    context_key text not null,
    helps jsonb not null default '[]'::jsonb,
    worsens jsonb not null default '[]'::jsonb,

    confidence_level double precision not null default 0.20,
    usage_count integer not null default 0,

    last_seen timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists idx_learned_patterns_profile_id
    on public.learned_patterns (profile_id);

create index if not exists idx_learned_patterns_family_id
    on public.learned_patterns (family_id);

create index if not exists idx_learned_patterns_context_key
    on public.learned_patterns (context_key);

create index if not exists idx_learned_patterns_confidence
    on public.learned_patterns (confidence_level desc, updated_at desc);

create index if not exists idx_learned_patterns_helps_gin
    on public.learned_patterns using gin (helps);

create index if not exists idx_learned_patterns_worsens_gin
    on public.learned_patterns using gin (worsens);

-- Evita duplicados exactos por contexto y ámbito
create unique index if not exists uq_learned_patterns_scope_context
    on public.learned_patterns (
        coalesce(profile_id::text, 'no_profile'),
        coalesce(family_id::text, 'no_family'),
        context_key
    );

-- =========================================================
-- TABLA: response_memory
-- =========================================================
create table if not exists public.response_memory (
    response_id uuid primary key default gen_random_uuid(),
    family_id uuid references public.families(family_id) on delete set null,
    profile_id uuid references public.profiles(profile_id) on delete set null,

    detected_intent text,
    detected_category text,
    primary_state text,
    conversation_stage text,

    complexity_signature text,
    conditions_signature jsonb not null default '[]'::jsonb,

    response_text text not null,
    response_structure_json jsonb not null default '{}'::jsonb,

    source_type text not null default 'system',
    confidence_score double precision,
    usefulness_score double precision,

    approved_for_reuse boolean not null default false,
    usage_count integer not null default 0,
    success_count integer not null default 0,
    failure_count integer not null default 0,

    avoid_rules jsonb not null default '[]'::jsonb,
    must_include jsonb not null default '[]'::jsonb,
    supporting_patterns jsonb not null default '[]'::jsonb,
    tags jsonb not null default '[]'::jsonb,

    llm_prompt_version text,
    origin_case_id uuid references public.ng_case_memory(case_id) on delete set null,
    notes text,

    is_active boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),

    constraint chk_response_memory_source_type
        check (source_type in ('system', 'llm_fallback', 'human_curated'))
);

create index if not exists idx_response_memory_family_id
    on public.response_memory (family_id);

create index if not exists idx_response_memory_profile_id
    on public.response_memory (profile_id);

create index if not exists idx_response_memory_detected_intent
    on public.response_memory (detected_intent);

create index if not exists idx_response_memory_detected_category
    on public.response_memory (detected_category);

create index if not exists idx_response_memory_primary_state
    on public.response_memory (primary_state);

create index if not exists idx_response_memory_conversation_stage
    on public.response_memory (conversation_stage);

create index if not exists idx_response_memory_complexity_signature
    on public.response_memory (complexity_signature);

create index if not exists idx_response_memory_active_reuse
    on public.response_memory (is_active, approved_for_reuse, updated_at desc);

create index if not exists idx_response_memory_tags_gin
    on public.response_memory using gin (tags);

create index if not exists idx_response_memory_conditions_gin
    on public.response_memory using gin (conditions_signature);

-- =========================================================
-- TABLA: user_context_memory
-- =========================================================
create table if not exists public.user_context_memory (
    scope_key text primary key,
    scope_type text not null default 'session',
    family_id uuid references public.families(family_id) on delete set null,
    profile_id uuid references public.profiles(profile_id) on delete set null,
    session_scope_id text,
    inferred_user_role text,
    role_confidence double precision,
    role_source text,
    conversation_preferences_json jsonb not null default '{}'::jsonb,
    recurrent_topics_json jsonb not null default '[]'::jsonb,
    recurrent_signals_json jsonb not null default '[]'::jsonb,
    helpful_strategies_json jsonb not null default '[]'::jsonb,
    helpful_routines_json jsonb not null default '[]'::jsonb,
    last_useful_domain text,
    last_useful_phase text,
    summary_snapshot_json jsonb not null default '{}'::jsonb,
    source_case_id uuid references public.ng_case_memory(case_id) on delete set null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),

    constraint chk_user_context_scope_type
        check (scope_type in ('profile', 'family', 'session'))
);

create index if not exists idx_user_context_memory_profile_id
    on public.user_context_memory (profile_id);

create index if not exists idx_user_context_memory_family_id
    on public.user_context_memory (family_id);

create index if not exists idx_user_context_memory_session_scope
    on public.user_context_memory (session_scope_id);

create index if not exists idx_user_context_memory_updated_at
    on public.user_context_memory (updated_at desc);

-- =========================================================
-- TABLA: conversation_curation
-- =========================================================
create table if not exists public.conversation_curation (
    curation_id text primary key,
    dedupe_key text not null,
    scope_key text,
    scope_type text,
    family_id uuid references public.families(family_id) on delete set null,
    profile_id uuid references public.profiles(profile_id) on delete set null,
    session_scope_id text,
    source_case_id uuid references public.ng_case_memory(case_id) on delete set null,

    review_status text not null default 'revisar',
    candidate_targets_json jsonb not null default '[]'::jsonb,
    review_notes text,

    input_summary_json jsonb not null default '{}'::jsonb,
    detected_category text,
    detected_intent text,
    primary_state text,
    secondary_states_json jsonb not null default '[]'::jsonb,
    conversation_domain text,
    conversation_phase text,
    speaker_role text,
    signal_summary_json jsonb not null default '{}'::jsonb,

    response_text text not null,
    response_structure_json jsonb not null default '{}'::jsonb,
    response_mode text,
    generation_source text,
    provider text,
    model text,
    used_stub_fallback boolean not null default false,
    fallback_reason text,
    llm_enabled boolean not null default false,
    llm_quality_score double precision,
    llm_approved boolean not null default false,
    metadata_json jsonb not null default '{}'::jsonb,

    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),

    constraint chk_conversation_curation_review_status
        check (review_status in ('util', 'neutral', 'revisar'))
);

create unique index if not exists uq_conversation_curation_dedupe_key
    on public.conversation_curation (dedupe_key);

create index if not exists idx_conversation_curation_profile_id
    on public.conversation_curation (profile_id);

create index if not exists idx_conversation_curation_family_id
    on public.conversation_curation (family_id);

create index if not exists idx_conversation_curation_review_status
    on public.conversation_curation (review_status, created_at desc);

create index if not exists idx_conversation_curation_detected_category
    on public.conversation_curation (detected_category);

create index if not exists idx_conversation_curation_generation_source
    on public.conversation_curation (generation_source);

-- =========================================================
-- TABLA: routines
-- =========================================================
create table if not exists public.routines (
    routine_id uuid primary key default gen_random_uuid(),
    family_id uuid references public.families(family_id) on delete set null,
    profile_id uuid references public.profiles(profile_id) on delete set null,

    routine_type text not null,
    routine_name text not null,
    goal text,

    steps jsonb not null default '[]'::jsonb,
    short_version jsonb not null default '[]'::jsonb,
    adjustments jsonb not null default '[]'::jsonb,
    indicators jsonb not null default '[]'::jsonb,

    followup_question text,
    source_case_id uuid references public.ng_case_memory(case_id) on delete set null,

    is_active boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists idx_routines_family_id
    on public.routines (family_id);

create index if not exists idx_routines_profile_id
    on public.routines (profile_id);

create index if not exists idx_routines_type
    on public.routines (routine_type);

create index if not exists idx_routines_active
    on public.routines (is_active, updated_at desc);

-- =========================================================
-- TRIGGER GENERICO updated_at
-- =========================================================
create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

drop trigger if exists trg_app_meta_set_updated_at on public.app_meta;
create trigger trg_app_meta_set_updated_at
before update on public.app_meta
for each row execute function public.set_updated_at();

drop trigger if exists trg_families_set_updated_at on public.families;
create trigger trg_families_set_updated_at
before update on public.families
for each row execute function public.set_updated_at();

drop trigger if exists trg_profiles_set_updated_at on public.profiles;
create trigger trg_profiles_set_updated_at
before update on public.profiles
for each row execute function public.set_updated_at();

drop trigger if exists trg_ng_case_memory_set_updated_at on public.ng_case_memory;
create trigger trg_ng_case_memory_set_updated_at
before update on public.ng_case_memory
for each row execute function public.set_updated_at();

drop trigger if exists trg_learned_patterns_set_updated_at on public.learned_patterns;
create trigger trg_learned_patterns_set_updated_at
before update on public.learned_patterns
for each row execute function public.set_updated_at();

drop trigger if exists trg_response_memory_set_updated_at on public.response_memory;
create trigger trg_response_memory_set_updated_at
before update on public.response_memory
for each row execute function public.set_updated_at();

drop trigger if exists trg_user_context_memory_set_updated_at on public.user_context_memory;
create trigger trg_user_context_memory_set_updated_at
before update on public.user_context_memory
for each row execute function public.set_updated_at();

drop trigger if exists trg_conversation_curation_set_updated_at on public.conversation_curation;
create trigger trg_conversation_curation_set_updated_at
before update on public.conversation_curation
for each row execute function public.set_updated_at();

drop trigger if exists trg_routines_set_updated_at on public.routines;
create trigger trg_routines_set_updated_at
before update on public.routines
for each row execute function public.set_updated_at();

-- =========================================================
-- VISTAS ÚTILES PARA ANÁLISIS
-- =========================================================
create or replace view public.v_case_summary as
select
    c.case_id,
    c.family_id,
    c.profile_id,
    c.unit_type,
    c.created_at,
    c.detected_category,
    c.detected_stage,
    c.primary_state,
    c.emotional_intensity,
    c.caregiver_capacity,
    c.suggested_strategy,
    c.suggested_microaction,
    c.suggested_routine_type,
    c.response_mode,
    c.usefulness_score,
    c.applied_successfully,
    c.followup_needed
from public.ng_case_memory c;

create or replace view public.v_response_memory_summary as
select
    r.response_id,
    r.family_id,
    r.profile_id,
    r.detected_intent,
    r.detected_category,
    r.primary_state,
    r.conversation_stage,
    r.source_type,
    r.confidence_score,
    r.usefulness_score,
    r.approved_for_reuse,
    r.usage_count,
    r.success_count,
    r.failure_count,
    r.is_active,
    r.created_at,
    r.updated_at
from public.response_memory r;

-- =========================================================
-- RLS (DESACTIVADA POR DEFECTO)
-- =========================================================
-- Actívala cuando definas tu estrategia de auth.
-- Ejemplo:
-- alter table public.families enable row level security;
-- alter table public.profiles enable row level security;
-- alter table public.ng_case_memory enable row level security;
-- alter table public.learned_patterns enable row level security;
-- alter table public.response_memory enable row level security;
-- alter table public.routines enable row level security;

-- =========================================================
-- DATOS MÍNIMOS DE APP_META
-- =========================================================
insert into public.app_meta (meta_key, meta_value)
values
    ('schema_version', jsonb_build_object('version', '1.0.0', 'name', 'neuroguia_premium_supabase')),
    ('created_by', jsonb_build_object('system', 'ChatGPT', 'project', 'NeuroGuía Premium'))
on conflict (meta_key) do nothing;
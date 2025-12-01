-- ======================================================
-- Enable required extensions
-- ======================================================
create extension IF not exists "uuid-ossp";

create extension IF not exists "pgcrypto";

create extension IF not exists "vector";

-- ======================================================
-- users table
-- ======================================================
create table if not exists users (
  uuid uuid primary key default gen_random_uuid (),
  email text unique not null,
  name text,
  status text default 'pending'::text,
  init_phase text,
  init_progress integer default 0,
  created_at timestamptz default now()
);

-- ======================================================
-- emails table
-- ======================================================
-- Stores Gmail messages per user. Composite key (id, user_id)
create table if not exists emails (
  id text not null,
  user_id uuid not null references users (uuid) on delete CASCADE,
  thread_id text,
  body text,
  subject text,
  from_user text,
  to_user text,
  cc text,
  bcc text,
  date timestamptz,
  primary key (id, user_id)
);

create index IF not exists emails_user_date_idx on emails (user_id, date);

create index IF not exists emails_user_thread_idx on emails (user_id, thread_id);

-- ======================================================
-- schedules table
-- ======================================================
create table if not exists schedules (
  id text not null,
  user_id uuid not null references users (uuid) on delete CASCADE,
  summary text,
  description text,
  location text,
  start_time timestamptz,
  end_time timestamptz,
  -- Best-practice metadata (Google Calendar returns these)
  creator_email text, -- NEW
  organizer_email text, -- NEW
  html_link text, -- NEW
  updated timestamptz, -- NEW
  primary key (id, user_id)
);

create index IF not exists schedules_user_start_idx on schedules (user_id, start_time);

-- ======================================================
-- files table
-- ======================================================
create table if not exists files (
  id text not null,
  user_id uuid not null references users (uuid) on delete CASCADE,
  owner_email text,
  owner_name text,
  path text, -- Full resolved path: /A/B/C.pdf
  name text,
  mime_type text,
  size bigint,
  modified_time timestamptz,
  parents text[], -- NEW: Drive folder IDs (real structure, stable)
  summary text,
  metadata jsonb, -- Additional metadata from Google Drive API
  primary key (id, user_id)
);

create index IF not exists files_user_modified_idx on files (user_id, modified_time);

create index IF not exists files_user_parents_idx on files using GIN (parents);

-- ======================================================
-- embeddings table
-- ======================================================
create table if not exists embeddings (
  id text not null,
  user_id uuid not null references users (uuid) on delete CASCADE,
  type text not null,
  vector vector (1536) not null,
  updated_at timestamptz default now(),
  email_id text,
  schedule_id text,
  file_id text,
  primary key (id, user_id, type),
  foreign KEY (user_id, email_id) references emails (user_id, id) on delete CASCADE,
  foreign KEY (user_id, schedule_id) references schedules (user_id, id) on delete CASCADE,
  foreign KEY (user_id, file_id) references files (user_id, id) on delete CASCADE
);

create index IF not exists embeddings_user_type_idx on embeddings (user_id, type);

create index IF not exists embeddings_updated_idx on embeddings (updated_at);

create index IF not exists embeddings_email_fk_idx on embeddings (user_id, email_id);

create index IF not exists embeddings_schedule_fk_idx on embeddings (user_id, schedule_id);

create index IF not exists embeddings_file_fk_idx on embeddings (user_id, file_id);

create index IF not exists embeddings_vector_hnsw_idx on embeddings using hnsw (vector vector_cosine_ops);

create or replace function public.match_email_embeddings (
  _user_id uuid,
  _query_embedding vector (1536),
  _type text default 'email_context',
  _match_threshold float4 default 0.2,
  _match_count int default 10
) returns table (email_id text, type text, similarity float4) language sql stable as $$
  select
    e.email_id,
    e.type,
    1 - (e.vector <=> _query_embedding) as similarity
  from public.embeddings e
  where e.user_id = _user_id
    and e.type = _type
    and 1 - (e.vector <=> _query_embedding) >= _match_threshold
  order by e.vector <=> _query_embedding -- smaller distance = more similar
  limit _match_count;
$$;

create or replace function public.match_schedule_embeddings (
  _user_id uuid,
  _query_embedding vector (1536),
  _type text default 'schedule_context',
  _match_threshold float4 default 0.2,
  _match_count int default 10
) returns table (schedule_id text, type text, similarity float4) language sql stable as $$
  select
    e.schedule_id,
    e.type,
    1 - (e.vector <=> _query_embedding) as similarity
  from public.embeddings e
  where e.user_id = _user_id
    and e.type = _type
    and 1 - (e.vector <=> _query_embedding) >= _match_threshold
  order by e.vector <=> _query_embedding
  limit _match_count;
$$;

create or replace function public.match_file_embeddings (
  _user_id uuid,
  _query_embedding vector (1536),
  _type text default 'file_context',
  _match_threshold float4 default 0.2,
  _match_count int default 10
) returns table (file_id text, type text, similarity float4) language sql stable as $$
  select
    e.file_id,
    e.type,
    1 - (e.vector <=> _query_embedding) as similarity
  from public.embeddings e
  where e.user_id = _user_id
    and e.type = _type
    and 1 - (e.vector <=> _query_embedding) >= _match_threshold
  order by e.vector <=> _query_embedding
  limit _match_count;
$$;

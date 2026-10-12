-- ════════════════════════════════════════════════════════════════════════
--  Legal AI Hub — database schema (replaces migration.sql + role_system_setup.sql)
--
--  Safe to run more than once and safe on an existing database:
--    * no DROP TABLE — existing data is kept
--    * old permissive policies are dropped and replaced
--    * new users always start as 'Student'; only Admins can change roles
--
--  Run in Supabase → SQL Editor. Then promote your admin once:
--    update public.profiles set role = 'Admin' where email = 'you@example.com';
-- ════════════════════════════════════════════════════════════════════════

-- ─── Tables ─────────────────────────────────────────────────────────────

create table if not exists public.profiles (
    id         uuid primary key default gen_random_uuid(),
    user_id    uuid not null unique references auth.users(id) on delete cascade,
    email      text not null,
    role       text not null default 'Student' check (role in ('Student', 'Lawyer', 'Judge', 'Admin')),
    created_at timestamptz default now()
);

create table if not exists public.case_predictions (
    id                      bigint generated always as identity primary key,
    user_id                 uuid default auth.uid() references auth.users(id) on delete cascade,
    user_email              text not null,
    filename                text not null,
    predicted_jurisdiction  text,
    jurisdiction_confidence numeric,
    predicted_outcome       text,
    outcome_confidence      numeric,
    created_at              timestamptz not null default now()
);

create table if not exists public.cases_vault (
    id                      uuid primary key default gen_random_uuid(),
    user_id                 uuid default auth.uid() references auth.users(id) on delete cascade,
    citation                text,
    title                   text not null,
    summary                 text,
    key_issues              text,
    ratio_decidendi         text,
    relevant_sections_ipc   text,
    relevant_sections_bns   text,
    full_text_path          text,
    user_email              text not null,
    case_category           text default 'General',
    court_level             text default 'Not Specified',
    predicted_jurisdiction  text,
    predicted_outcome       text,
    jurisdiction_confidence double precision,
    outcome_confidence      double precision,
    created_at              timestamptz default now()
);

create table if not exists public.student_queries (
    id              uuid primary key default gen_random_uuid(),
    user_id         uuid default auth.uid() references auth.users(id) on delete cascade,
    user_email      text not null,
    query_text      text not null,
    ai_response     text,
    related_case_id uuid references public.cases_vault(id) on delete set null,
    created_at      timestamptz default now()
);

create table if not exists public.statutory_bridge (
    id                 uuid primary key default gen_random_uuid(),
    ipc_section        text not null unique,
    bns_equivalent     text not null,
    change_description text,
    landmark_precedent text,
    created_at         timestamptz default now()
);

-- "current_role" is a reserved word in PostgreSQL, so it must stay quoted.
create table if not exists public.role_requests (
    id             uuid primary key default gen_random_uuid(),
    user_id        uuid not null references auth.users(id) on delete cascade,
    user_email     text not null,
    "current_role" text not null default 'Student' check ("current_role" in ('Student', 'Lawyer', 'Judge', 'Admin')),
    requested_role text not null check (requested_role in ('Lawyer', 'Judge', 'Admin')),
    status         text not null default 'pending' check (status in ('pending', 'approved', 'rejected')),
    requested_at   timestamptz not null default now(),
    reviewed_at    timestamptz,
    reviewed_by    text
);

-- Upgrade path for databases created by the old scripts: add owner columns.
alter table public.case_predictions add column if not exists user_id uuid default auth.uid() references auth.users(id) on delete cascade;
alter table public.cases_vault      add column if not exists user_id uuid default auth.uid() references auth.users(id) on delete cascade;
alter table public.student_queries  add column if not exists user_id uuid default auth.uid() references auth.users(id) on delete cascade;

-- Back-fill owners of existing rows from their email.
update public.case_predictions t set user_id = p.user_id from public.profiles p where t.user_id is null and lower(t.user_email) = lower(p.email);
update public.cases_vault      t set user_id = p.user_id from public.profiles p where t.user_id is null and lower(t.user_email) = lower(p.email);
update public.student_queries  t set user_id = p.user_id from public.profiles p where t.user_id is null and lower(t.user_email) = lower(p.email);

-- ─── Helper functions (security definer avoids RLS recursion on profiles) ──

create or replace function public.current_app_role()
returns text language sql security definer stable set search_path = public as $$
    select role from public.profiles where user_id = auth.uid();
$$;

create or replace function public.is_admin()
returns boolean language sql security definer stable set search_path = public as $$
    select coalesce(public.current_app_role() = 'Admin', false);
$$;

create or replace function public.is_reviewer()   -- Admin or Judge: may read everyone's records
returns boolean language sql security definer stable set search_path = public as $$
    select coalesce(public.current_app_role() in ('Admin', 'Judge'), false);
$$;

-- ─── New-user trigger: ALWAYS Student (sign-up metadata is ignored) ─────

create or replace function public.handle_new_user()
returns trigger language plpgsql security definer set search_path = public as $$
begin
    insert into public.profiles (user_id, email, role)
    values (new.id, new.email, 'Student')
    on conflict (user_id) do nothing;
    return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
    after insert on auth.users
    for each row execute function public.handle_new_user();

-- ─── Role-change guard: only Admins (or the SQL editor) can change a role ──

create or replace function public.check_role_update()
returns trigger language plpgsql security definer set search_path = public as $$
begin
    if new.role is distinct from old.role and auth.uid() is not null and not public.is_admin() then
        raise exception 'Unauthorized: only administrators can modify user roles.';
    end if;
    return new;
end;
$$;

drop trigger if exists trg_protect_profile_role on public.profiles;
create trigger trg_protect_profile_role
    before update on public.profiles
    for each row execute function public.check_role_update();

-- ─── Row-level security ─────────────────────────────────────────────────

alter table public.profiles         enable row level security;
alter table public.case_predictions enable row level security;
alter table public.cases_vault      enable row level security;
alter table public.student_queries  enable row level security;
alter table public.statutory_bridge enable row level security;
alter table public.role_requests    enable row level security;

-- Remove every policy created by the old scripts (they allowed anyone to read/insert).
do $$
declare r record;
begin
    for r in select policyname, tablename from pg_policies
             where schemaname = 'public'
               and tablename in ('profiles','case_predictions','cases_vault','student_queries','statutory_bridge','role_requests')
    loop
        execute format('drop policy if exists %I on public.%I', r.policyname, r.tablename);
    end loop;
end $$;

-- profiles: read own (Admins read all); no direct inserts (trigger creates rows); Admins update.
create policy profiles_select on public.profiles for select to authenticated
    using (user_id = auth.uid() or public.is_admin());
create policy profiles_admin_update on public.profiles for update to authenticated
    using (public.is_admin()) with check (public.is_admin());

-- case_predictions / cases_vault / student_queries: owner reads and writes own rows;
-- Admins and Judges read everything.
create policy case_predictions_select on public.case_predictions for select to authenticated
    using (user_id = auth.uid() or public.is_reviewer());
create policy case_predictions_insert on public.case_predictions for insert to authenticated
    with check (user_id = auth.uid());

create policy cases_vault_select on public.cases_vault for select to authenticated
    using (user_id = auth.uid() or public.is_reviewer());
create policy cases_vault_insert on public.cases_vault for insert to authenticated
    with check (user_id = auth.uid());
create policy cases_vault_update on public.cases_vault for update to authenticated
    using (user_id = auth.uid() or public.is_admin()) with check (user_id = auth.uid() or public.is_admin());
create policy cases_vault_delete on public.cases_vault for delete to authenticated
    using (user_id = auth.uid() or public.is_admin());

create policy student_queries_select on public.student_queries for select to authenticated
    using (user_id = auth.uid() or public.is_admin());
create policy student_queries_insert on public.student_queries for insert to authenticated
    with check (user_id = auth.uid());

-- statutory_bridge: public reference data; only Admins change it.
create policy statutory_bridge_select on public.statutory_bridge for select using (true);
create policy statutory_bridge_admin_write on public.statutory_bridge for all to authenticated
    using (public.is_admin()) with check (public.is_admin());

-- role_requests: users create and read their own pending requests; Admins review.
create policy role_requests_insert on public.role_requests for insert to authenticated
    with check (user_id = auth.uid() and status = 'pending' and reviewed_at is null and reviewed_by is null);
create policy role_requests_select on public.role_requests for select to authenticated
    using (user_id = auth.uid() or public.is_admin());
create policy role_requests_admin_update on public.role_requests for update to authenticated
    using (public.is_admin()) with check (public.is_admin());

-- ─── Indexes ────────────────────────────────────────────────────────────

create index if not exists idx_case_predictions_user_id   on public.case_predictions(user_id);
create index if not exists idx_case_predictions_email     on public.case_predictions(user_email);
create index if not exists idx_cases_vault_user_id        on public.cases_vault(user_id);
create index if not exists idx_cases_vault_category       on public.cases_vault(case_category);
create index if not exists idx_student_queries_user_id    on public.student_queries(user_id);
create index if not exists idx_role_requests_user_id      on public.role_requests(user_id);
create index if not exists idx_role_requests_status       on public.role_requests(status);
create index if not exists idx_role_requests_requested_at on public.role_requests(requested_at desc);

-- Back-fill profiles for users who signed up before the trigger existed.
insert into public.profiles (user_id, email, role)
select u.id, u.email, 'Student' from auth.users u
on conflict (user_id) do nothing;

notify pgrst, 'reload schema';

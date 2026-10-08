-- =============================================================================
-- ROLE SYSTEM DATABASE SETUP (IDEMPOTENT & RE-RUNNABLE)
-- Safe setup for public.profiles and public.role_requests in Supabase
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. PUBLIC.PROFILES TABLE
-- -----------------------------------------------------------------------------
create table if not exists public.profiles (
    user_id uuid primary key references auth.users(id) on delete cascade,
    email text,
    role text not null default 'Student' check (role in ('Student', 'Lawyer', 'Judge', 'Admin')),
    created_at timestamptz default now()
);

-- Index for fast email lookups
create index if not exists idx_profiles_email on public.profiles(email);

-- -----------------------------------------------------------------------------
-- 2. PUBLIC.ROLE_REQUESTS TABLE
-- -----------------------------------------------------------------------------
create table if not exists public.role_requests (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    user_email text,
    "current_role" text,
    requested_role text not null check (requested_role in ('Student', 'Lawyer', 'Judge', 'Admin')),
    status text not null default 'pending' check (status in ('pending', 'approved', 'rejected')),
    requested_at timestamptz not null default now(),
    created_at timestamptz not null default now(),
    reviewed_at timestamptz,
    reviewed_by text
);

-- Indexes for role_requests queries in app.py
create index if not exists idx_role_requests_user_id on public.role_requests(user_id);
create index if not exists idx_role_requests_status on public.role_requests(status);
create index if not exists idx_role_requests_requested_at on public.role_requests(requested_at desc);

-- -----------------------------------------------------------------------------
-- 3. HELPER FUNCTIONS & TRIGGERS
-- -----------------------------------------------------------------------------

-- Helper function to check if the caller has Admin privileges
create or replace function public.is_admin()
returns boolean
language sql
security definer
stable
set search_path = public
as $$
    select coalesce(
        (select role = 'Admin' from public.profiles where user_id = auth.uid()),
        false
    );
$$;

-- BEFORE UPDATE guard trigger: allow when auth.uid() is null (SQL editor / service_role)
-- or the caller is an Admin; block all other callers.
create or replace function public.check_role_update()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
    if new.role is distinct from old.role and auth.uid() is not null and not public.is_admin() then
        raise exception 'Unauthorized: Only administrators can modify user roles.';
    end if;
    return new;
end;
$$;

drop trigger if exists trg_protect_profile_role on public.profiles;
create trigger trg_protect_profile_role
before update on public.profiles
for each row
execute function public.check_role_update();

-- Automatic profile creation on auth.users insert: strictly defaults to 'Student'
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
    insert into public.profiles (user_id, email, role, created_at)
    values (new.id, new.email, 'Student', now())
    on conflict (user_id) do nothing;
    return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
after insert on auth.users
for each row
execute function public.handle_new_user();

-- -----------------------------------------------------------------------------
-- 4. ROW LEVEL SECURITY (RLS) FOR PROFILES
-- -----------------------------------------------------------------------------
alter table public.profiles enable row level security;

-- Users can select their own profile
drop policy if exists "Users can select own profile" on public.profiles;
create policy "Users can select own profile"
on public.profiles
for select
to authenticated
using (auth.uid() = user_id);

-- Admins can select all profiles
drop policy if exists "Admins can select all profiles" on public.profiles;
create policy "Admins can select all profiles"
on public.profiles
for select
to authenticated
using (public.is_admin());

-- Admins can update all profiles (non-admins have no update policy)
drop policy if exists "Admins can update all profiles" on public.profiles;
create policy "Admins can update all profiles"
on public.profiles
for update
to authenticated
using (public.is_admin())
with check (public.is_admin());

-- -----------------------------------------------------------------------------
-- 5. ROW LEVEL SECURITY (RLS) FOR ROLE_REQUESTS
-- -----------------------------------------------------------------------------
alter table public.role_requests enable row level security;

-- Users can insert only their own requests with initial pending status
drop policy if exists "Users can insert own role requests" on public.role_requests;
create policy "Users can insert own role requests"
on public.role_requests
for insert
to authenticated
with check (
    auth.uid() = user_id
    and status = 'pending'
    and reviewed_at is null
    and reviewed_by is null
);

-- Users can select only their own requests
drop policy if exists "Users can select own role requests" on public.role_requests;
create policy "Users can select own role requests"
on public.role_requests
for select
to authenticated
using (auth.uid() = user_id);

-- Admins can select all requests
drop policy if exists "Admins can select all role requests" on public.role_requests;
create policy "Admins can select all role requests"
on public.role_requests
for select
to authenticated
using (public.is_admin());

-- Admins can update all requests
drop policy if exists "Admins can update all role requests" on public.role_requests;
create policy "Admins can update all role requests"
on public.role_requests
for update
to authenticated
using (public.is_admin())
with check (public.is_admin());

-- -----------------------------------------------------------------------------
-- 6. BACKFILL EXISTING USERS
-- -----------------------------------------------------------------------------
insert into public.profiles (user_id, email, role, created_at)
select
    u.id as user_id,
    u.email,
    case
        when u.raw_user_meta_data->>'role' in ('Student', 'Lawyer', 'Judge')
        then u.raw_user_meta_data->>'role'
        else 'Student'
    end as role,
    coalesce(u.created_at, now()) as created_at
from auth.users u
on conflict (user_id) do nothing;

-- Explicitly assign Admin role to designated admin accounts
update public.profiles
set role = 'Admin'
where email in ('admin@legalai.in', 'admin1@legalcase.com');

-- -----------------------------------------------------------------------------
-- 7. VERIFICATION SELECT
-- -----------------------------------------------------------------------------
select email, role from public.profiles order by email;

-- -----------------------------------------------------------------------------
-- 8. RELOAD SCHEMA
-- -----------------------------------------------------------------------------
notify pgrst, 'reload schema';

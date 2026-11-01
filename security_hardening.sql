-- ═══════════════════════════════════════════════════════════════════════
--  Legal AI Hub — security hardening (OWASP Top 10 review, Oct 2026)
--
--  Safe to run more than once. It only ADDS rules; it never deletes data.
--  Already applied to the "Ai Legal Hub" Supabase project on 30 Oct 2026.
--  The same rules are included in schema.sql for fresh installs.
-- ═══════════════════════════════════════════════════════════════════════

-- ─── A01 / A03: role upgrade requests ──────────────────────────────────
-- Before: a signed-in user could write ANY text into current_role (shown on the Admin page)
-- and ANY email into user_email (so an Admin could see "approve victim@x" while the role
-- change actually went to the attacker's own account).

alter table public.role_requests drop constraint if exists role_requests_current_role_check;
alter table public.role_requests add constraint role_requests_current_role_check
    check ("current_role" is null or "current_role" in ('Student', 'Lawyer', 'Judge', 'Admin'));

drop policy if exists "Users can insert own role requests" on public.role_requests;
drop policy if exists role_requests_insert on public.role_requests;
create policy role_requests_insert on public.role_requests for insert to authenticated
    with check (
        user_id = auth.uid()
        and lower(user_email) = lower(auth.jwt() ->> 'email')
        and status = 'pending'
        and reviewed_at is null
        and reviewed_by is null
    );

-- One open request per user (stops request spamming of the Admin queue).
create unique index if not exists uq_role_requests_one_pending
    on public.role_requests(user_id) where status = 'pending';

-- ─── A04: limit stored chatbot text ────────────────────────────────────
alter table public.student_queries drop constraint if exists student_queries_length_check;
alter table public.student_queries add constraint student_queries_length_check
    check (char_length(coalesce(query_text, '')) <= 2000 and char_length(coalesce(ai_response, '')) <= 8000);

-- ─── A01 / A05: SECURITY DEFINER functions are not public API ──────────
-- Supabase exposes every public function at /rest/v1/rpc/<name>. Trigger functions must not
-- be callable at all; the two role helpers are needed by RLS policies for signed-in users only.
revoke execute on function public.handle_new_user()   from public, anon, authenticated;
revoke execute on function public.check_role_update() from public, anon, authenticated;

do $$
declare f text;
begin
    foreach f in array array['is_admin', 'current_user_role', 'current_app_role', 'is_reviewer'] loop
        if exists (select 1 from pg_proc p join pg_namespace n on n.oid = p.pronamespace
                   where n.nspname = 'public' and p.proname = f) then
            execute format('revoke execute on function public.%I() from public, anon', f);
            execute format('grant execute on function public.%I() to authenticated', f);
        end if;
    end loop;
end $$;

notify pgrst, 'reload schema';

-- =====================================================
-- Legal Research & Prediction Hub
-- Database Migration Script
-- Run this in the Supabase SQL Editor (supabase.com > SQL)
-- =====================================================
-- =====================================================

DROP TABLE IF EXISTS case_predictions CASCADE;
DROP TABLE IF EXISTS cases_vault CASCADE;
DROP TABLE IF EXISTS student_queries CASCADE;
DROP TABLE IF EXISTS statutory_bridge CASCADE;

-- 1. Case Predictions — Stores AI classification and outcome predictions for user history
CREATE TABLE IF NOT EXISTS case_predictions (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_email TEXT NOT NULL,
    filename TEXT NOT NULL,
    predicted_jurisdiction TEXT,
    jurisdiction_confidence NUMERIC,
    predicted_outcome TEXT,
    outcome_confidence NUMERIC,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 2. Cases Vault — Stores analyzed legal cases for research
CREATE TABLE IF NOT EXISTS cases_vault (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    citation TEXT,
    title TEXT NOT NULL,
    summary TEXT,
    key_issues TEXT,
    ratio_decidendi TEXT,
    relevant_sections_ipc TEXT,
    relevant_sections_bns TEXT,
    full_text_path TEXT,
    user_email TEXT NOT NULL,
    case_category TEXT DEFAULT 'General',
    court_level TEXT DEFAULT 'Not Specified',
    predicted_jurisdiction TEXT,
    predicted_outcome TEXT,
    jurisdiction_confidence FLOAT,
    outcome_confidence FLOAT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Student Queries — Doubt Solver conversation history
CREATE TABLE IF NOT EXISTS student_queries (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_email TEXT NOT NULL,
    query_text TEXT NOT NULL,
    ai_response TEXT,
    related_case_id UUID REFERENCES cases_vault(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. Statutory Bridge — IPC to BNS mapping with context
CREATE TABLE IF NOT EXISTS statutory_bridge (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    ipc_section TEXT NOT NULL,
    bns_equivalent TEXT NOT NULL,
    change_description TEXT DEFAULT 'Updated under Bharatiya Nyaya Sanhita (BNS) framework.',
    landmark_precedent TEXT DEFAULT 'Refer to latest Supreme Court guidelines.',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(ipc_section)
);

-- 5. Profiles — Role-Based Access Control
DROP TABLE IF EXISTS profiles CASCADE;
CREATE TABLE IF NOT EXISTS profiles (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'Student' CHECK (role IN ('Student', 'Lawyer', 'Judge', 'Admin')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id),
    UNIQUE(email)
);

-- Auto-create profile on new user signup
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.profiles (user_id, email, role)
    VALUES (
        NEW.id,
        NEW.email,
        COALESCE(NEW.raw_user_meta_data->>'role', 'Student')
    )
    ON CONFLICT (user_id) DO UPDATE
    SET role = COALESCE(EXCLUDED.role, public.profiles.role),
        email = EXCLUDED.email;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- =====================================================
-- Row Level Security
-- =====================================================

ALTER TABLE case_predictions ENABLE ROW LEVEL SECURITY;
ALTER TABLE cases_vault ENABLE ROW LEVEL SECURITY;
ALTER TABLE student_queries ENABLE ROW LEVEL SECURITY;
ALTER TABLE statutory_bridge ENABLE ROW LEVEL SECURITY;
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;

-- Profiles Policies
DROP POLICY IF EXISTS "profiles_public_read" ON profiles;
CREATE POLICY "profiles_public_read" ON profiles FOR SELECT USING (true);

DROP POLICY IF EXISTS "profiles_public_insert" ON profiles;
CREATE POLICY "profiles_public_insert" ON profiles FOR INSERT WITH CHECK (true);

-- Profiles UPDATE Policies (Split: Self-Update vs Admin-Update)
DROP POLICY IF EXISTS "profiles_public_update" ON profiles;
DROP POLICY IF EXISTS "profiles_update" ON profiles;
DROP POLICY IF EXISTS "profiles_update_policy" ON profiles;
DROP POLICY IF EXISTS "profiles_admin_update_policy" ON profiles;
DROP POLICY IF EXISTS "profiles_self_update_policy" ON profiles;

-- 1. Self-update policy: allows users to update their own profile row
CREATE POLICY "profiles_self_update_policy" ON public.profiles
    FOR UPDATE
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

-- 2. Admin update policy: allows Admins to update any user's profile
CREATE POLICY "profiles_admin_update_policy" ON public.profiles
    FOR UPDATE
    USING (
        EXISTS (
            SELECT 1 FROM public.profiles p 
            WHERE p.user_id = auth.uid() AND p.role = 'Admin'
        )
    );

-- 3. Database Trigger: Hard-stops any non-admin from modifying the role column
CREATE OR REPLACE FUNCTION public.protect_profile_role()
RETURNS TRIGGER AS $$
BEGIN
    -- Only evaluate if role is actually being changed
    IF NEW.role IS DISTINCT FROM OLD.role THEN
        -- Allow internal Supabase service-role or postgres superuser
        IF (current_user IN ('postgres', 'supabase_admin')) 
           OR (COALESCE(auth.jwt() ->> 'role', '') = 'service_role') THEN
            RETURN NEW;
        END IF;

        -- Allow if the requester is verified as an Admin in profiles
        IF EXISTS (
            SELECT 1 FROM public.profiles 
            WHERE user_id = auth.uid() AND role = 'Admin'
        ) THEN
            RETURN NEW;
        END IF;

        -- Explicitly block any non-admin from updating the role column
        RAISE EXCEPTION 'Access Denied: Only administrators are permitted to modify the role column.';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS trg_protect_profile_role ON public.profiles;
CREATE TRIGGER trg_protect_profile_role
    BEFORE UPDATE ON public.profiles
    FOR EACH ROW
    EXECUTE FUNCTION public.protect_profile_role();

-- Case Predictions Policies
DROP POLICY IF EXISTS "case_predictions_read" ON case_predictions;
CREATE POLICY "case_predictions_read" ON case_predictions FOR SELECT USING (true);

DROP POLICY IF EXISTS "case_predictions_insert" ON case_predictions;
CREATE POLICY "case_predictions_insert" ON case_predictions FOR INSERT WITH CHECK (true);

-- Cases Vault Policies
DROP POLICY IF EXISTS "cases_vault_public_read" ON cases_vault;
CREATE POLICY "cases_vault_public_read" ON cases_vault FOR SELECT USING (true);

DROP POLICY IF EXISTS "cases_vault_auth_insert" ON cases_vault;
CREATE POLICY "cases_vault_auth_insert" ON cases_vault FOR INSERT WITH CHECK (true);

DROP POLICY IF EXISTS "cases_vault_auth_update" ON cases_vault;
CREATE POLICY "cases_vault_auth_update" ON cases_vault FOR UPDATE USING (true);

-- Student Queries Policies
DROP POLICY IF EXISTS "student_queries_read" ON student_queries;
CREATE POLICY "student_queries_read" ON student_queries FOR SELECT USING (true);

DROP POLICY IF EXISTS "student_queries_insert" ON student_queries;
CREATE POLICY "student_queries_insert" ON student_queries FOR INSERT WITH CHECK (true);

-- Statutory Bridge Policies
DROP POLICY IF EXISTS "statutory_bridge_read" ON statutory_bridge;
CREATE POLICY "statutory_bridge_read" ON statutory_bridge FOR SELECT USING (true);

DROP POLICY IF EXISTS "statutory_bridge_insert" ON statutory_bridge;
CREATE POLICY "statutory_bridge_insert" ON statutory_bridge FOR INSERT WITH CHECK (true);

DROP POLICY IF EXISTS "statutory_bridge_update" ON statutory_bridge;
CREATE POLICY "statutory_bridge_update" ON statutory_bridge FOR UPDATE USING (true);

-- 6. Role Requests — Stores user elevation requests to Lawyer, Judge, or Admin
CREATE TABLE IF NOT EXISTS public.role_requests (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    user_email TEXT NOT NULL,
    current_role TEXT NOT NULL DEFAULT 'Student' CHECK (current_role IN ('Student', 'Lawyer', 'Judge', 'Admin')),
    requested_role TEXT NOT NULL CHECK (requested_role IN ('Lawyer', 'Judge', 'Admin')),
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
    requested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reviewed_at TIMESTAMPTZ,
    reviewed_by TEXT
);

ALTER TABLE public.role_requests ENABLE ROW LEVEL SECURITY;

-- Role Requests Policies
DROP POLICY IF EXISTS "role_requests_select_policy" ON public.role_requests;
CREATE POLICY "role_requests_select_policy" ON public.role_requests
    FOR SELECT
    USING (
        auth.uid() = user_id 
        OR EXISTS (
            SELECT 1 FROM profiles 
            WHERE profiles.user_id = auth.uid() AND profiles.role = 'Admin'
        )
    );

DROP POLICY IF EXISTS "role_requests_insert_policy" ON public.role_requests;
CREATE POLICY "role_requests_insert_policy" ON public.role_requests
    FOR INSERT
    WITH CHECK (
        auth.uid() = user_id 
        AND status = 'pending'
    );

DROP POLICY IF EXISTS "role_requests_admin_update_policy" ON public.role_requests;
CREATE POLICY "role_requests_admin_update_policy" ON public.role_requests
    FOR UPDATE
    USING (
        EXISTS (
            SELECT 1 FROM profiles 
            WHERE profiles.user_id = auth.uid() AND profiles.role = 'Admin'
        )
    );

-- =====================================================
-- Performance Indexes
-- =====================================================

CREATE INDEX IF NOT EXISTS idx_case_predictions_user ON case_predictions(user_email);
CREATE INDEX IF NOT EXISTS idx_cases_vault_category ON cases_vault(case_category);
CREATE INDEX IF NOT EXISTS idx_cases_vault_court ON cases_vault(court_level);
CREATE INDEX IF NOT EXISTS idx_cases_vault_user_email ON cases_vault(user_email);
CREATE INDEX IF NOT EXISTS idx_student_queries_user ON student_queries(user_email);
CREATE INDEX IF NOT EXISTS idx_statutory_bridge_ipc ON statutory_bridge(ipc_section);
CREATE INDEX IF NOT EXISTS idx_role_requests_user_id ON role_requests(user_id);
CREATE INDEX IF NOT EXISTS idx_role_requests_status ON role_requests(status);
CREATE INDEX IF NOT EXISTS idx_role_requests_requested_at ON role_requests(requested_at DESC);

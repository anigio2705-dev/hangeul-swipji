-- DESIGN PREVIEW ONLY — not applied, not a generated/verified migration.
-- Use an EMPTY DISPOSABLE Supabase project. Never run on the existing Work 2 DB.
-- A future adapter must implement the transactional state machine described in
-- SUPABASE-INTEGRATION.md. These tables alone do not implement those services.
begin;
do $$ begin
  if current_setting('hs3.allow_preview_install', true) is distinct from 'isolated-test-only' then
    raise exception 'Preview blocked: use an isolated project and explicitly SET hs3.allow_preview_install = isolated-test-only';
  end if;
end $$;

create schema hs3;
revoke all on schema hs3 from public, anon, authenticated;
alter default privileges in schema hs3 revoke all on tables from public, anon, authenticated;
alter default privileges in schema hs3 revoke all on sequences from public, anon, authenticated;
alter default privileges in schema hs3 revoke all on functions from public, anon, authenticated;
-- Requires an administrator to enable btree_gist in a DISPOSABLE project first.
-- We intentionally do not install extensions or change any public objects here.
set local search_path = hs3, extensions, pg_catalog;

create table hs3.profiles (
  user_id uuid primary key references auth.users(id),
  nickname text not null check (char_length(nickname) between 2 and 40),
  participant_role text not null check (participant_role in ('learner','partner','teacher')),
  adult_attested_at timestamptz not null,
  languages text[] not null default '{}', timezone text not null default 'UTC',
  created_at timestamptz not null default now()
);
create table hs3.providers (
  user_id uuid primary key references hs3.profiles(user_id),
  verification_status text not null default 'pending' check (verification_status in ('pending','approved','suspended','rejected')),
  qualifications text not null default '', specialty text not null default '',
  level text not null, price_minor bigint not null check (price_minor >= 0),
  currency text not null default 'KRW' check (currency = 'KRW'),
  verified_by uuid references auth.users(id), verified_at timestamptz,
  verification_reason text,
  check (verification_status <> 'approved' or (verified_by is not null and verified_at is not null and length(verification_reason)>0))
);
create table hs3.units (
  unit_id text not null, version integer not null check (version > 0),
  title text not null, level text not null,
  duration_minutes integer not null check (duration_minutes between 5 and 180),
  learner_material jsonb not null, teacher_material jsonb not null,
  content_sha256 text not null check (content_sha256 ~ '^[0-9a-f]{64}$'),
  primary key(unit_id,version)
);
create table hs3.availability (
  id uuid primary key default gen_random_uuid(),
  provider_id uuid not null references hs3.providers(user_id),
  starts_at timestamptz not null, ends_at timestamptz not null,
  closed boolean not null default false, check (ends_at>starts_at),
  exclude using gist (provider_id with =, tstzrange(starts_at,ends_at,'[)') with &&) where (not closed)
);
create table hs3.bookings (
  id uuid primary key default gen_random_uuid(),
  learner_id uuid not null references hs3.profiles(user_id),
  provider_id uuid not null references hs3.providers(user_id),
  availability_id uuid not null references hs3.availability(id),
  unit_id text not null, unit_version integer not null,
  foreign key(unit_id,unit_version) references hs3.units(unit_id,version),
  -- Immutable unit/material and commercial snapshot, not mutable catalog lookup.
  material_snapshot jsonb not null,
  starts_at timestamptz not null, ends_at timestamptz not null,
  price_minor bigint not null check(price_minor>=0),
  currency text not null default 'KRW' check(currency='KRW'),
  commission_bps integer not null check(commission_bps between 0 and 10000),
  referral_bps integer not null check(referral_bps between 0 and 10000),
  check(referral_bps<=commission_bps),
  policy_version text not null,
  state text not null default 'reserved' check(state in ('reserved','test_paid','in_progress','completion_pending','completed','disputed','cancelled','refunded')),
  mode text not null default 'test' check(mode='test'),
  private_room_id uuid not null default gen_random_uuid() unique,
  created_at timestamptz not null default now(),
  check(learner_id<>provider_id), check(ends_at>starts_at)
);
create unique index hs3_one_active_booking_per_slot on hs3.bookings(availability_id)
  where state not in ('cancelled','refunded');
create index on hs3.bookings(learner_id);
create index on hs3.bookings(provider_id);
-- Adapter must insert BOTH learner/provider claims in the SAME booking transaction.
create table hs3.participant_claims (
  booking_id uuid not null references hs3.bookings(id),
  user_id uuid not null references hs3.profiles(user_id),
  starts_at timestamptz not null, ends_at timestamptz not null,
  active boolean not null default true,
  primary key(booking_id,user_id), check(ends_at>starts_at),
  exclude using gist(user_id with =, tstzrange(starts_at,ends_at,'[)') with &&) where(active)
);
create table hs3.attendance (
  booking_id uuid not null references hs3.bookings(id),
  user_id uuid not null references hs3.profiles(user_id),
  verified_seconds integer not null default 0 check(verified_seconds>=0),
  confirmed_at timestamptz, evidence_reference text,
  primary key(booking_id,user_id)
);
create table hs3.payments (
  id uuid primary key default gen_random_uuid(), booking_id uuid not null references hs3.bookings(id),
  provider_event_id text not null unique,
  operation text not null check(operation in ('test_authorize','test_capture','test_refund')),
  amount_minor bigint not null check(amount_minor>=0), currency text not null check(currency='KRW'),
  mode text not null default 'test' check(mode='test'),
  created_at timestamptz not null default now()
);
create table hs3.referrals (
  referred_id uuid primary key references hs3.profiles(user_id),
  referrer_id uuid not null references hs3.profiles(user_id),
  created_at timestamptz not null default now(),
  check(referrer_id<>referred_id)
);
create table hs3.settlements (
  booking_id uuid primary key references hs3.bookings(id),
  provider_minor bigint not null check(provider_minor>=0),
  platform_minor bigint not null check(platform_minor>=0),
  referral_minor bigint not null default 0 check(referral_minor>=0),
  status text not null check(status in ('test_pending','test_recorded','test_reversed')),
  mode text not null default 'test' check(mode='test'),
  created_at timestamptz not null default now()
);
create table hs3.ledger (
  id uuid primary key default gen_random_uuid(), booking_id uuid not null references hs3.bookings(id),
  beneficiary_id uuid references hs3.profiles(user_id),
  event_key text not null unique, account text not null,
  amount_minor bigint not null, currency text not null check(currency='KRW'),
  mode text not null default 'test' check(mode='test'),
  reverses_id uuid unique references hs3.ledger(id),
  created_at timestamptz not null default now()
);
create table hs3.assignments (
  booking_id uuid not null references hs3.bookings(id),
  learner_id uuid not null references hs3.profiles(user_id),
  submission text not null default '', feedback text not null default '',
  progress jsonb not null default '{}', updated_at timestamptz not null default now(),
  primary key(booking_id,learner_id)
);
create table hs3.disputes (
  id uuid primary key default gen_random_uuid(), booking_id uuid not null references hs3.bookings(id),
  reporter_id uuid not null references hs3.profiles(user_id),
  category text not null, evidence text not null,
  status text not null default 'open' check(status in ('open','investigating','resolved','appealed')),
  decision text, reason text, resolved_by uuid references auth.users(id),
  created_at timestamptz not null default now()
);
create table hs3.reviews (
  booking_id uuid not null references hs3.bookings(id), author_id uuid not null references hs3.profiles(user_id),
  rating integer not null check(rating between 1 and 5), body text not null,
  moderation_status text not null default 'pending' check(moderation_status in ('pending','published','hidden')),
  primary key(booking_id,author_id)
);
create table hs3.audit (
  id bigint generated always as identity primary key,
  actor_id uuid references auth.users(id), action text not null,
  entity_type text not null, entity_id text not null,
  reason text not null, detail jsonb not null default '{}',
  created_at timestamptz not null default now()
);

-- RLS in the private schema is defense in depth. No client grants are added.
do $$ declare t record; begin
  for t in select tablename from pg_tables where schemaname='hs3' loop
    execute format('alter table hs3.%I enable row level security',t.tablename);
    execute format('revoke all on hs3.%I from public, anon, authenticated',t.tablename);
  end loop;
end $$;
revoke all on all sequences in schema hs3 from public, anon, authenticated;
create policy own_profile_read on hs3.profiles for select to authenticated
  using(user_id=(select auth.uid()));
create policy own_provider_read on hs3.providers for select to authenticated
  using(user_id=(select auth.uid()));
create policy own_booking_read on hs3.bookings for select to authenticated
  using(learner_id=(select auth.uid()) or provider_id=(select auth.uid()));
create policy own_claim_read on hs3.participant_claims for select to authenticated
  using(user_id=(select auth.uid()));
create policy own_attendance_read on hs3.attendance for select to authenticated
  using(user_id=(select auth.uid()));
create policy participant_assignment_read on hs3.assignments for select to authenticated
  using(exists(select 1 from hs3.bookings b where b.id=booking_id
    and (b.learner_id=(select auth.uid()) or b.provider_id=(select auth.uid()))));
create policy own_dispute_read on hs3.disputes for select to authenticated
  using(reporter_id=(select auth.uid()));
create policy own_ledger_read on hs3.ledger for select to authenticated
  using(beneficiary_id=(select auth.uid()));
-- All other tables and all writes are deny-by-default for end users.
-- Server adapter must use a restricted DB role, explicit participant authorization,
-- append-only ledger/audit privileges, and verified provider callbacks.
commit;

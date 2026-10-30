-- 한글쉽지 1·2·3번 통합 시범 서비스. Supabase SQL Editor에서 실행.
create schema if not exists extensions;
create extension if not exists pgcrypto with schema extensions;
create table if not exists public.profiles (
 id uuid primary key references auth.users(id) on delete cascade,
 nickname text not null check (char_length(nickname) between 2 and 40),
 role text not null check (role in ('learner','partner')),
 level text not null default 'beginner' check (level in ('beginner','intermediate','advanced')),
 topic text not null default 'daily' check (topic in ('daily','travel','food','culture')),
 approved boolean not null default false,
 is_online boolean not null default false,
 last_seen timestamptz,
 created_at timestamptz not null default now()
);
create table if not exists public.matches (
 id uuid primary key default gen_random_uuid(),
 learner_id uuid not null references public.profiles(id),
 partner_id uuid not null references public.profiles(id),
 status text not null default 'requested' check (status in ('requested','accepted','rejected','cancelled','finished')),
 room_code text unique,
 created_at timestamptz not null default now(),
 updated_at timestamptz not null default now(),
 check(learner_id<>partner_id)
);
-- Upgrade existing pilot databases so learners can cancel a pending request.
alter table public.matches drop constraint if exists matches_status_check;
alter table public.matches add constraint matches_status_check check (status in ('requested','accepted','rejected','cancelled','finished'));
create unique index if not exists one_open_learner on public.matches(learner_id) where status in ('requested','accepted');
create unique index if not exists one_open_partner on public.matches(partner_id) where status='accepted';
alter table public.profiles enable row level security;
alter table public.matches enable row level security;
-- Clear table and column grants: table UPDATE would override protected columns.
revoke all privileges on public.profiles, public.matches from anon, authenticated;
revoke all privileges (id,nickname,role,level,topic,approved,is_online,last_seen,created_at) on public.profiles from anon, authenticated;
revoke all privileges (id,learner_id,partner_id,status,room_code,created_at,updated_at) on public.matches from anon, authenticated;
grant select,insert on public.profiles to authenticated;
grant update(nickname,role,level,topic) on public.profiles to authenticated;
grant select on public.matches to authenticated;
drop policy if exists "own profile read" on public.profiles;
create policy "own profile read" on public.profiles for select to authenticated using(id=auth.uid());
drop policy if exists "own profile insert" on public.profiles;
create policy "own profile insert" on public.profiles for insert to authenticated with check(id=auth.uid() and approved=false and is_online=false);
drop policy if exists "own profile update" on public.profiles;
create policy "own profile update" on public.profiles for update to authenticated using(id=auth.uid()) with check(id=auth.uid());
-- Protected columns (id, approved, is_online, last_seen, created_at) are not client-updatable.
drop policy if exists "my matches" on public.matches;
create policy "my matches" on public.matches for select to authenticated using(learner_id=auth.uid() or partner_id=auth.uid());
create or replace view public.online_partners with (security_invoker=true) as
select id,nickname,level,topic from public.profiles
where role='partner' and approved=true and is_online=true and last_seen>now()-interval '3 minutes';
-- The view needs a separate select policy; only public, approved partner fields are exposed.
drop policy if exists "public online partners" on public.profiles;
create policy "public online partners" on public.profiles for select to authenticated
using(role='partner' and approved=true and is_online=true and last_seen>now()-interval '3 minutes');
revoke all privileges on public.online_partners from anon, authenticated;
revoke all privileges (id,nickname,level,topic) on public.online_partners from anon, authenticated;
grant select on public.online_partners to authenticated;
create or replace function public.set_availability(want_online boolean) returns void language plpgsql security definer set search_path='' as $$
begin
 update public.profiles set is_online=want_online,last_seen=case when want_online then now() else null end
 where id=auth.uid() and role='partner' and approved=true;
 if not found then raise exception '승인된 파트너만 대기할 수 있습니다'; end if;
end $$;
create or replace function public.request_match(chosen_partner uuid) returns uuid language plpgsql security definer set search_path='' as $$
declare mid uuid;
begin
 if not exists(select 1 from public.profiles where id=auth.uid() and role='learner') then raise exception '학습자 프로필이 필요합니다';end if;
 perform 1 from public.profiles where id=chosen_partner and role='partner' and approved=true and is_online=true and last_seen>now()-interval '3 minutes' for update;
 if not found then raise exception '상대방이 현재 대기 중이지 않습니다';end if;
 insert into public.matches(learner_id,partner_id) values(auth.uid(),chosen_partner) returning id into mid;
 return mid;
end $$;
CREATE OR REPLACE FUNCTION public.respond_match(match_id uuid, approve boolean)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM public.matches
    WHERE id = match_id
      AND partner_id = auth.uid()
      AND status = 'requested'
    FOR UPDATE
  ) THEN
    RAISE EXCEPTION '처리할 요청이 없습니다';
  END IF;

  IF approve THEN
    UPDATE public.matches
    SET status = 'accepted',
        room_code = encode(extensions.gen_random_bytes(18), 'hex'),
        updated_at = now()
    WHERE id = match_id;

    UPDATE public.profiles
    SET is_online = false,
        last_seen = null
    WHERE id = auth.uid();
  ELSE
    UPDATE public.matches
    SET status = 'rejected',
        updated_at = now()
    WHERE id = match_id;
  END IF;
END;
$function$;
create or replace function public.finish_match(match_id uuid) returns void language plpgsql security definer set search_path='' as $$
begin
 update public.matches set status='finished',updated_at=now() where id=match_id and status='accepted' and (learner_id=auth.uid() or partner_id=auth.uid());
 if not found then raise exception '종료할 수업이 없습니다';end if;
end $$;
-- A learner may cancel only their own still-pending request; accepted calls must use finish_match.
create or replace function public.cancel_match(match_id uuid) returns void language plpgsql security definer set search_path='' as $cancel$
begin
 update public.matches set status='cancelled',updated_at=now()
 where id=match_id and learner_id=auth.uid() and status='requested';
 if not found then raise exception '취소할 대화 요청이 없습니다';end if;
end $cancel$;
revoke all on function public.cancel_match(uuid) from public, anon, authenticated;
grant execute on function public.cancel_match(uuid) to authenticated;
revoke all on function public.set_availability(boolean) from public, anon, authenticated;
revoke all on function public.request_match(uuid) from public, anon, authenticated;
revoke all on function public.respond_match(uuid,boolean) from public, anon, authenticated;
revoke all on function public.finish_match(uuid) from public, anon, authenticated;
grant execute on function public.set_availability(boolean),public.request_match(uuid),public.respond_match(uuid,boolean),public.finish_match(uuid) to authenticated;
-- 운영자가 Supabase SQL Editor에서 수동 승인:
-- update public.profiles set approved=true where id='실제-파트너-uuid';
-- NOTE: 화상은 Jitsi 공개 인프라 기반 파일럿. 비밀방/운영 SLA 보장 없음.

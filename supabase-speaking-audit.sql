-- Hangeul Swipji: read-only schema snapshot for comparison with supabase-speaking.sql.
-- Execute through the project owner's SQL Editor / management connection.
-- Reads PostgreSQL metadata only. Does not read auth.users, profiles or matches rows.
-- Does not create, alter, delete, approve accounts, or call matching functions.
begin transaction read only;

select pg_catalog.jsonb_build_object(
  'database_version', pg_catalog.current_setting('server_version'),
  'extensions', (
    select coalesce(pg_catalog.jsonb_agg(pg_catalog.jsonb_build_object(
      'name', e.extname, 'schema', n.nspname, 'version', e.extversion
    ) order by e.extname), '[]'::jsonb)
    from pg_catalog.pg_extension e
    join pg_catalog.pg_namespace n on n.oid = e.extnamespace
    where e.extname = 'pgcrypto'
  ),
  'relations', (
    select coalesce(pg_catalog.jsonb_agg(pg_catalog.jsonb_build_object(
      'name', c.relname, 'kind', c.relkind,
      'row_security', c.relrowsecurity, 'force_row_security', c.relforcerowsecurity,
      'options', c.reloptions, 'acl', c.relacl::text
    ) order by c.relname), '[]'::jsonb)
    from pg_catalog.pg_class c
    join pg_catalog.pg_namespace n on n.oid = c.relnamespace
    where n.nspname = 'public' and c.relname in ('profiles','matches','online_partners')
  ),
  'columns', (
    select coalesce(pg_catalog.jsonb_agg(pg_catalog.to_jsonb(x) order by x.table_name, x.ordinal_position), '[]'::jsonb)
    from (
      select table_name, ordinal_position, column_name, data_type, udt_name,
             is_nullable, column_default, character_maximum_length
      from information_schema.columns
      where table_schema = 'public' and table_name in ('profiles','matches','online_partners')
    ) x
  ),
  'constraints', (
    select coalesce(pg_catalog.jsonb_agg(pg_catalog.jsonb_build_object(
      'table', c.relname, 'name', k.conname, 'definition', pg_catalog.pg_get_constraintdef(k.oid, false)
    ) order by c.relname, k.conname), '[]'::jsonb)
    from pg_catalog.pg_constraint k
    join pg_catalog.pg_class c on c.oid = k.conrelid
    join pg_catalog.pg_namespace n on n.oid = c.relnamespace
    where n.nspname = 'public' and c.relname in ('profiles','matches')
  ),
  'indexes', (
    select coalesce(pg_catalog.jsonb_agg(pg_catalog.to_jsonb(x) order by x.tablename, x.indexname), '[]'::jsonb)
    from (
      select tablename, indexname, indexdef from pg_catalog.pg_indexes
      where schemaname = 'public' and tablename in ('profiles','matches')
    ) x
  ),
  'policies', (
    select coalesce(pg_catalog.jsonb_agg(pg_catalog.to_jsonb(x) order by x.tablename, x.policyname), '[]'::jsonb)
    from (
      select tablename, policyname, permissive, roles, cmd, qual, with_check
      from pg_catalog.pg_policies
      where schemaname = 'public' and tablename in ('profiles','matches')
    ) x
  ),
  'functions', (
    select coalesce(pg_catalog.jsonb_agg(pg_catalog.jsonb_build_object(
      'name', p.proname,
      'arguments', pg_catalog.pg_get_function_identity_arguments(p.oid),
      'security_definer', p.prosecdef, 'config', p.proconfig,
      'owner', pg_catalog.pg_get_userbyid(p.proowner), 'acl', p.proacl::text,
      'definition', pg_catalog.pg_get_functiondef(p.oid)
    ) order by p.proname, p.oid), '[]'::jsonb)
    from pg_catalog.pg_proc p
    join pg_catalog.pg_namespace n on n.oid = p.pronamespace
    where n.nspname = 'public' and p.prokind = 'f'
      and p.proname in ('set_availability','request_match','respond_match','finish_match')
  ),
  'view', (
    select pg_catalog.pg_get_viewdef(c.oid, false)
    from pg_catalog.pg_class c
    join pg_catalog.pg_namespace n on n.oid = c.relnamespace
    where n.nspname = 'public' and c.relname = 'online_partners' and c.relkind = 'v'
  ),
  'table_grants', (
    select coalesce(pg_catalog.jsonb_agg(pg_catalog.to_jsonb(x) order by x.table_name, x.grantee, x.privilege_type), '[]'::jsonb)
    from (
      select grantee, table_name, privilege_type, is_grantable
      from information_schema.table_privileges
      where table_schema = 'public' and table_name in ('profiles','matches','online_partners')
    ) x
  ),
  'column_grants', (
    select coalesce(pg_catalog.jsonb_agg(pg_catalog.to_jsonb(x) order by x.table_name, x.column_name, x.grantee, x.privilege_type), '[]'::jsonb)
    from (
      select grantee, table_name, column_name, privilege_type
      from information_schema.column_privileges
      where table_schema = 'public' and table_name in ('profiles','matches','online_partners')
    ) x
  )
) as speaking_schema_snapshot;

rollback;

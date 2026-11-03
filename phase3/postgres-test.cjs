'use strict';
// Genuine local WASM PostgreSQL; auth fixtures are stubs, NOT hosted Supabase Auth.
const {PGlite}=require('@electric-sql/pglite');
const {btree_gist}=require('@electric-sql/pglite/contrib/btree_gist');
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const checks=[];function pass(n){checks.push(n);console.log('PASS',n);}
(async()=>{const db=new PGlite({extensions:{btree_gist}});try{
 await db.exec("create role anon;create role authenticated;create schema auth;create schema extensions;create extension btree_gist with schema extensions;create table auth.users(id uuid primary key);create function auth.uid() returns uuid language sql stable as $$select nullif(current_setting('request.jwt.claim.sub',true),'')::uuid$$;");
 const preview=fs.readFileSync(path.join(__dirname,'supabase-preview.sql'),'utf8');
 await assert.rejects(db.exec(preview),/Preview blocked/);await db.exec('rollback');pass('preview refuses installation without isolated gate');
 await db.exec("set hs3.allow_preview_install='isolated-test-only'");await db.exec(preview);pass('full proposal SQL installs in isolated PostgreSQL');
 const tables=(await db.query("select tablename,rowsecurity from pg_tables where schemaname='hs3'")).rows;assert.ok(tables.length>=15&&tables.every(t=>t.rowsecurity));pass('RLS enabled on every hs3 table');
 const a='11111111-1111-4111-8111-111111111111',b='22222222-2222-4222-8222-222222222222',t='33333333-3333-4333-8333-333333333333';
 for(const [id,role] of [[a,'learner'],[b,'learner'],[t,'teacher']]){await db.query('insert into auth.users values($1)',[id]);await db.query("insert into hs3.profiles(user_id,nickname,participant_role,adult_attested_at) values($1,$2,$3,now())",[id,'test-'+role,role]);}
 await db.query("insert into hs3.providers(user_id,level,price_minor) values($1,'A1',20000)",[t]);
 await db.exec("set role anon");await assert.rejects(db.query('select * from hs3.profiles'),/permission denied/);await db.exec('reset role');pass('anonymous schema access denied');
 await db.exec("set role authenticated");await assert.rejects(db.query('select * from hs3.profiles'),/permission denied/);await db.exec('reset role');pass('authenticated client denied without explicit grants');
 // Test-only grant activates dormant read policies. It is never applied to any hosted DB.
 await db.exec('grant usage on schema hs3,auth to authenticated;grant select on hs3.profiles,hs3.providers,hs3.bookings,hs3.assignments,hs3.ledger to authenticated');
 await db.exec(`set role authenticated;set request.jwt.claim.sub='${a}'`);assert.equal((await db.query('select * from hs3.profiles')).rows.length,1);assert.equal((await db.query('select user_id from hs3.profiles')).rows[0].user_id,a);await assert.rejects(db.query("update hs3.profiles set participant_role='teacher'"),/permission denied/);await db.exec('reset role');pass('owner RLS reads only self and rejects role escalation');
 await db.exec("insert into hs3.units values('test-unit',1,'Test','A1',30,'{}','{}',repeat('a',64))");
 const slot=(await db.query("insert into hs3.availability(provider_id,starts_at,ends_at) values($1,'2030-01-01T09:00Z','2030-01-01T10:00Z') returning id",[t])).rows[0].id;
 await assert.rejects(db.query("insert into hs3.availability(provider_id,starts_at,ends_at) values($1,'2030-01-01T09:30Z','2030-01-01T10:30Z')",[t]),/exclusion constraint/);pass('provider overlapping availability rejected by GiST');
 const bid=(await db.query("insert into hs3.bookings(learner_id,provider_id,availability_id,unit_id,unit_version,material_snapshot,starts_at,ends_at,price_minor,commission_bps,referral_bps,policy_version) values($1,$2,$3,'test-unit',1,'{}','2030-01-01T09:00Z','2030-01-01T10:00Z',20000,2000,300,'test') returning id",[a,t,slot])).rows[0].id;
 await db.query("insert into hs3.assignments(booking_id,learner_id,submission) values($1,$2,'private homework')",[bid,a]);
 await db.query("insert into hs3.ledger(booking_id,beneficiary_id,event_key,account,amount_minor,currency) values($1,$2,'unique-test-event','test_teacher',16000,'KRW')",[bid,t]);
 await db.exec(`set role authenticated;set request.jwt.claim.sub='${b}'`);assert.equal((await db.query('select * from hs3.bookings')).rows.length,0);assert.equal((await db.query('select * from hs3.assignments')).rows.length,0);assert.equal((await db.query('select * from hs3.ledger')).rows.length,0);await db.exec('reset role');pass('cross-user booking homework and earnings RLS denied');
 await db.exec(`set role authenticated;set request.jwt.claim.sub='${a}'`);assert.equal((await db.query('select * from hs3.bookings')).rows.length,1);assert.equal((await db.query('select * from hs3.assignments')).rows.length,1);await db.exec('reset role');pass('authorized participant reads booking and homework');
 await db.exec(`set role authenticated;set request.jwt.claim.sub='${t}'`);assert.equal((await db.query('select * from hs3.ledger')).rows.length,1);await assert.rejects(db.query("delete from hs3.ledger"),/permission denied/);await assert.rejects(db.query("insert into hs3.ledger(booking_id,event_key,account,amount_minor,currency) values('"+bid+"','evil','test',1,'KRW')"),/permission denied/);await db.exec('reset role');pass('beneficiary reads own ledger but cannot write or delete');
 await db.query("insert into hs3.participant_claims values($1,$2,'2030-01-01T09:00Z','2030-01-01T10:00Z',true)",[bid,a]);
 // Same booking/user PK would mask exclusion; use another user with conflicting provider claim.
 await db.query("insert into hs3.participant_claims values($1,$2,'2030-01-01T09:00Z','2030-01-01T10:00Z',true)",[bid,t]);
 await assert.rejects(db.query("insert into hs3.ledger(booking_id,event_key,account,amount_minor,currency) values($1,'unique-test-event','test',1,'KRW')",[bid]),/unique constraint/);pass('duplicate ledger event rejected');
 const t2='44444444-4444-4444-8444-444444444444';await db.query('insert into auth.users values($1)',[t2]);await db.query("insert into hs3.profiles(user_id,nickname,participant_role,adult_attested_at) values($1,'second-provider','teacher',now())",[t2]);await db.query("insert into hs3.providers(user_id,level,price_minor) values($1,'A1',20000)",[t2]);
 const slot2=(await db.query("insert into hs3.availability(provider_id,starts_at,ends_at) values($1,'2030-01-01T09:30Z','2030-01-01T10:30Z') returning id",[t2])).rows[0].id;
 const bid2=(await db.query("insert into hs3.bookings(learner_id,provider_id,availability_id,unit_id,unit_version,material_snapshot,starts_at,ends_at,price_minor,commission_bps,referral_bps,policy_version) values($1,$2,$3,'test-unit',1,'{}','2030-01-01T09:30Z','2030-01-01T10:30Z',20000,2000,300,'test') returning id",[a,t2,slot2])).rows[0].id;
 await assert.rejects(db.query("insert into hs3.participant_claims values($1,$2,'2030-01-01T09:30Z','2030-01-01T10:30Z',true)",[bid2,a]),/exclusion constraint/);pass('learner overlapping claim rejected across different providers');

 const version=(await db.query('select version()')).rows[0].version;fs.writeFileSync(path.join(__dirname,'postgres-results.json'),JSON.stringify({engine:'PGlite0.5.12 local PostgreSQL WASM',version,checks,hostedSupabaseTested:false,authIdentityFixture:true,productionDatabaseAccessed:false},null,2)+'\n');
 }finally{await db.close();}})().catch(e=>{console.error(e);process.exitCode=1});

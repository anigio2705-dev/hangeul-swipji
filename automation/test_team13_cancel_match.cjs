'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const html = fs.readFileSync(path.join(root, 'speaking-platform.html'), 'utf8');
const sql = fs.readFileSync(path.join(root, 'supabase-speaking.sql'), 'utf8');

assert.match(sql, /status in \('requested','accepted','rejected','cancelled','finished'\)/);
assert.match(sql, /alter table public\.matches add constraint matches_status_check/);
assert.match(sql, /update public\.matches set status='cancelled',updated_at=now\(\)\s+where id=match_id and learner_id=auth\.uid\(\) and status='requested';/);
assert.match(sql, /revoke all on function public\.cancel_match\(uuid\) from public, anon, authenticated;/);
assert.match(sql, /grant execute on function public\.cancel_match\(uuid\) to authenticated;/);
assert.match(sql, /create or replace function public\.request_match/);
assert.match(sql, /create or replace function public\.respond_match/i);
assert.match(sql, /as \$cancel\$[\s\S]*?end \$cancel\$;/);
assert.match(sql, /create or replace function public\.finish_match/);

const match = html.match(/<script type="module">([\s\S]*?)<\/script>/);
assert.ok(match, 'speaking module must exist');
const script = match[1].replace(/import\s*\{createClient\}\s*from\s*['"]https:\/\/esm\.sh\/@supabase\/supabase-js@2['"]\s*;/, '');
assert.doesNotMatch(script, /\bimport\s*\{/);

async function main() {
  const elements = Object.create(null);
  const element = id => elements[id] ||= {
    classList: {toggle() {}}, textContent: '', innerHTML: '', value: '',
    disabled: false, replaceChildren() {}
  };
  let click;
  const calls = [];
  const matches = [{id: 'match-abc', learner_id: 'learner-123',
    partner_id: 'partner-123', status: 'requested'}];
  const db = {
    auth: {
      onAuthStateChange() {},
      async getUser() { return {data: {user: {id: 'learner-123', email: 'student@test.invalid'}}}; }
    },
    from(table) {
      if (table === 'profiles') return {select: () => ({eq: () => ({
        maybeSingle: async () => ({data: {role: 'learner', nickname: 'Student',
          approved: false, is_online: false}})
      })})};
      if (table === 'matches') return {select: () => ({or: () => ({
        in: async () => ({data: matches})
      })})};
      return {select: async () => ({data: []})};
    },
    async rpc(type, args) { calls.push({type, args}); return {error: null}; }
  };
  const document = {
    getElementById: element,
    addEventListener(type, handler) { if (type === 'click') click = handler; },
    createElement() { return {}; }
  };
  const window = {HS_CONFIG: {supabaseUrl: 'https://test.invalid',
    supabaseAnonKey: 'public-test'}};
  new Function('createClient', 'document', 'window', 'location', 'setTimeout',
    'setInterval', 'clearInterval', script)(
    () => db, document, window, {reload() {}}, () => {}, () => 0, () => {});
  const flush = async () => {for (let i = 0; i < 30; i++) await Promise.resolve();};
  await flush();
  assert.match(element('outbox').innerHTML, /data-cancel="match-abc"/);
  click({target: {closest: () => ({dataset: {cancel: 'match-abc'}})}});
  await flush();
  assert.deepEqual(calls[0], {type: 'cancel_match', args: {match_id: 'match-abc'}});
  matches[0].status = 'accepted';
  click({target: {closest: () => ({dataset: {request: 'partner-123'}})}});
  await flush();
  assert.deepEqual(calls[1], {type: 'request_match',
    args: {chosen_partner: 'partner-123'}});
  assert.doesNotMatch(element('outbox').innerHTML, /data-cancel=/,
    'accepted calls must not be cancellable as pending requests');
  console.log('PASS team13: pending cancellation UI/RPC, accepted guard, request flow, SQL authorization');
}
main().catch(e => {console.error(e); process.exitCode = 1;});

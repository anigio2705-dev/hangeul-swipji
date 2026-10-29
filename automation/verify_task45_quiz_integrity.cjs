'use strict';
// Task #45: independent data-integrity audit of the actual seven course quizzes.
// This does NOT certify semantic answer correctness, explanations, scoring UI,
// retry behavior, or real-browser performance.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const COURSES = ['intro', 'beginner1', 'beginner2', 'intermediate1', 'intermediate2', 'advanced1', 'advanced2'];
function extractUnits(html, label) {
  const match = html.match(/(?:^|\n)const units=(\[[^\n]*\]);/);
  assert.ok(match, `${label}: course data not found`);
  const units = JSON.parse(match[1]);
  assert.ok(Array.isArray(units), `${label}: units must be an array`);
  return units;
}
function auditCourse(name, units) {
  assert.equal(units.length, 50, `${name}: expected 50 units`);
  let questions = 0, explanations = 0;
  for (let unit = 0; unit < units.length; unit++) {
    const quiz = units[unit].quiz;
    assert.ok(Array.isArray(quiz) && quiz.length > 0, `${name} unit ${unit + 1}: empty quiz`);
    for (let i = 0; i < quiz.length; i++) {
      const q = quiz[i], label = `${name} unit ${unit + 1} question ${i + 1}`;
      assert.ok(Array.isArray(q) && q.length >= 4, `${label}: invalid question`);
      assert.ok(typeof q[0] === 'string' && q[0].trim(), `${label}: missing Korean question`);
      assert.ok(typeof q[1] === 'string' && q[1].trim(), `${label}: missing English question`);
      assert.ok(Array.isArray(q[2]) && q[2].length >= 2, `${label}: insufficient options`);
      assert.ok(q[2].every(x => typeof x === 'string' && x.trim()), `${label}: blank option`);
      const normalized = q[2].map(x => x.normalize('NFKC').trim().toLocaleLowerCase());
      assert.equal(new Set(normalized).size, normalized.length, `${label}: duplicate options`);
      assert.ok(Number.isInteger(q[3]) && q[3] >= 0 && q[3] < q[2].length,
        `${label}: invalid correct-answer index`);
      if (typeof q[4] === 'string' && q[4].trim()) explanations++;
      questions++;
    }
  }
  return {course: name, units: units.length, questions, explanations};
}
function selfTest() {
  const good = Array.from({length: 50}, () => ({quiz: [['질문?', 'Question?', ['가', '나'], 0]]}));
  assert.equal(auditCourse('fixture', good).questions, 50);
  const badOptions = JSON.parse(JSON.stringify(good));
  badOptions[0].quiz[0][2] = ['가', '가'];
  assert.throws(() => auditCourse('fixture', badOptions), /duplicate options/);
  const badIndex = JSON.parse(JSON.stringify(good));
  badIndex[0].quiz[0][3] = 2;
  assert.throws(() => auditCourse('fixture', badIndex), /invalid correct-answer index/);
  const badUnits = good.slice(1);
  assert.throws(() => auditCourse('fixture', badUnits), /expected 50 units/);
  console.log('PASS #45 negative fixtures: duplicate options, bad index, missing unit');
}
function main() {
  selfTest();
  const root = path.resolve(__dirname, '..');
  const results = COURSES.map(course => {
    const html = fs.readFileSync(path.join(root, course + '.html'), 'utf8');
    return auditCourse(course, extractUnits(html, course));
  });
  const total = results.reduce((a, r) => a + r.questions, 0);
  const explained = results.reduce((a, r) => a + r.explanations, 0);
  assert.equal(total, 1758, 'Quiz question count regression: investigate additions/removals');
  console.log(JSON.stringify({task: 45, courses: 7, units: 350,
    questions: total, duplicate_options: 0, invalid_answer_indices: 0,
    explicit_explanations: explained,
    missing_explanations: total - explained,
    status: 'PARTIAL_DATA_INTEGRITY_ONLY',
    unverified: ['semantic answer correctness', 'explanation quality', 'score calculation UI', 'retry behavior', 'browser and owner approval']}, null, 2));
  if (process.env.GITHUB_STEP_SUMMARY) {
    fs.appendFileSync(process.env.GITHUB_STEP_SUMMARY,
      `Task #45: ${total} questions, duplicate options 0, invalid answer indices 0, explicit explanations ${explained}/${total}. PARTIAL ONLY; do not promote READY or CODE_VERIFIED.\n`);
  }
}
main();

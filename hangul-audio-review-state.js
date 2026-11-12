(function (root, factory) {
  'use strict';
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.HangulAudioReviewState = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  function recordingKey(text, sha256) {
    if (typeof text !== 'string' || !text.trim()) {
      throw new TypeError('A non-empty text is required.');
    }
    if (typeof sha256 !== 'string' || !/^[0-9a-fA-F]{64}$/.test(sha256)) {
      throw new TypeError('A 64-digit hexadecimal SHA-256 is required.');
    }
    return JSON.stringify([text, sha256]);
  }

  function requireRecord(record) {
    if (!record || typeof record !== 'object' || Array.isArray(record)) {
      throw new TypeError('A record is required.');
    }
  }

  function decide(record, decision, reviewer, listenedKey, now) {
    requireRecord(record);
    if (!['pending', 'approved', 'rerecord', 'uncertain'].includes(decision)) {
      throw new TypeError('Invalid decision.');
    }
    const next = Object.assign({}, record, {
      status: decision,
      reviewer: '',
      reviewedAt: ''
    });
    if (decision === 'approved') {
      if (record.kind !== 'human' || typeof reviewer !== 'string' || !reviewer.trim()) {
        throw new TypeError('Approval requires a human recording and a reviewer.');
      }
      if (listenedKey !== recordingKey(record.text, record.sha256)) {
        throw new Error('The current recording must be listened to completely.');
      }
      const timestamp = now === undefined ? new Date() : new Date(now);
      if (!Number.isFinite(timestamp.getTime())) {
        throw new TypeError('Invalid review time.');
      }
      next.reviewer = reviewer.trim();
      next.reviewedAt = timestamp.toISOString();
    }
    return next;
  }

  function replaceCandidate(record, candidate) {
    requireRecord(record);
    if (!candidate || typeof candidate !== 'object' || Array.isArray(candidate) ||
        candidate.kind !== 'human' || typeof candidate.src !== 'string' || !candidate.src.trim()) {
      throw new TypeError('A human recording candidate with a source is required.');
    }
    recordingKey(record.text, candidate.sha256);
    return {
      text: record.text,
      src: candidate.src,
      sha256: candidate.sha256,
      kind: 'human',
      status: 'pending',
      reviewer: '',
      reviewedAt: ''
    };
  }

  return { recordingKey: recordingKey, decide: decide, replaceCandidate: replaceCandidate };
});

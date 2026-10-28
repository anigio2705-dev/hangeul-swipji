/* Team 16: privacy-minimal, consent-gated funnel event helper. No automatic third-party transmission. */
(function (root) {
  "use strict";
  const allow = new Set(["landing_view", "free_learning_start", "signup_complete", "lesson_complete", "speaking_cta_click", "booking_started", "booking_confirmed", "payment_test_success", "payment_live_confirmed", "repeat_purchase_confirmed"]);
  const validCountry = /^(VN|JP|KR|US|OTHER)$/;
  function cleanCampaign(value) { return String(value || "").replace(/[^a-zA-Z0-9_.-]/g, "").slice(0, 80); }
  function makeEvent(type, opts) {
    if (!allow.has(type)) throw new Error("Unknown funnel event");
    const data = opts || {};
    return {event: type, schema_version: 1, at: new Date().toISOString(), country: validCountry.test(data.country) ? data.country : "OTHER", campaign: cleanCampaign(data.campaign), path: String(data.path || "").split("?")[0].slice(0, 160), test: data.test !== false};
  }
  function track(type, opts) {
    if (typeof window === "undefined" || window.hsAnalyticsConsent !== true) return false;
    const event = makeEvent(type, opts);
    // Dispatch locally. Owner-approved analytics transport can subscribe; nothing is sent by default.
    window.dispatchEvent(new CustomEvent("hs:funnel", {detail:event}));
    return true;
  }
  root.HSGrowth = Object.freeze({makeEvent, track, events: Object.freeze(Array.from(allow))});
})(typeof window !== "undefined" ? window : globalThis);

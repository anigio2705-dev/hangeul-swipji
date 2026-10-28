/* Team16 D1: test-only funnel navigation smoke check, no external calls. */
const fs = require("node:fs");
const assert = require("node:assert/strict");
const vm = require("node:vm");
const path = require("node:path");
const root = path.resolve(__dirname, "../..");
const source = fs.readFileSync(path.join(__dirname, "funnel-events.js"), "utf8");
const events = [];
const context = {window: {hsAnalyticsConsent: false, dispatchEvent: e => events.push(e.detail)}, CustomEvent: class {constructor(name, opts){this.type=name;this.detail=opts.detail}}, Date, Set, Object, String, Error};
vm.runInNewContext(source, context);
assert.equal(context.window.HSGrowth.track("landing_view", {country:"VN"}), false);
assert.equal(events.length, 0);
context.window.hsAnalyticsConsent = true;
assert.equal(context.window.HSGrowth.track("speaking_cta_click", {country:"VN",campaign:"promo<script>",path:"/learn?email=private"}), true);
assert.equal(events.length, 1);
assert.equal(events[0].campaign, "promoscript");
assert.equal(events[0].path, "/learn");
assert.equal(events[0].test, true);
assert.throws(()=>context.window.HSGrowth.makeEvent("arbitrary_event"), /Unknown funnel event/);
for (const lang of ["vi","ja"]) {
 const html=fs.readFileSync(path.join(__dirname, "landing-"+lang+".html"), "utf8");
 assert.match(html, /noindex,nofollow/);
 assert.match(html, /\.\.\/\.\.\/learn\.html/);
 assert.match(html, /\.\.\/\.\.\/speaking-platform\.html/);
 assert.match(html, /utm_campaign=/);
}
console.log("PASS: consent, sanitized campaign/path, test-only default, event allowlist, two landing navigation targets");

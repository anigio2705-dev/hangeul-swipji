# TEAM16-EIGHT-LANGUAGE-20261030

**Owner:** Team 16. **Backlog task:** exact 160-item number not yet verified; do not infer one.
**Problem:** Approved eight-language site selection and learning content translation must work without corrupting Hangul glyphs and audio controls.
**Initial approach:** Google Translate whole-page integration and broad `notranslate` exclusions.
**Failure:** Exclusions prevented lesson descriptions from being translated; native selector options could mislead users about supported languages.
**Actual correction:** Restrict `notranslate` to Hangul glyph/audio controls, remove unsupported options, add static regression tests and a dedicated Actions workflow.
**Changed files:** `site-language.js`, `growth/team16/test-site-language.cjs`, `.github/workflows/team16-eight-language.yml`.
**Evidence:** commits `2ea1e70`, `00aa118`, `40078bee`; Team16 CI PASS: https://github.com/anigio2705-dev/hangeul-swipji/actions/runs/40975081169 (staging SHA `44c761253c`).
**Verification level:** TESTED. No independent cross-device browser or test99 deployment claim.
**Reusable lesson:** Translation exclusions should be scoped to content that must stay literal; test both language selector options and page content.
**Cautions:** Machine translation is not professional linguistic QA; Google Translate availability and browser behavior may vary. Never treat a selector label change as proof of full page translation.
**Share with:** Team 12 (learning content), Team 13 (booking labels), Team 15 (independent mobile/browser regression).
**Next:** Cross-team independent validation, integration tests, and test99 SHA evidence before DEPLOYED status.

# Six-team shared knowledge index

This index records verified code and CI evidence. A passing team regression does not imply staging or production deployment.

## Evidence status

- CODE: change committed, behavior not yet independently verified
- TESTED: named CI passed on an exact SHA
- INDEPENDENT: another team or independent audit reproduced success
- INTEGRATED: integration branch passed the required checks
- DEPLOYED: test99 deployment SHA and browser behavior were checked

## Initial cases

- [Team 16: eight-language regression and integration pitfalls](SUCCESS/TEAM16_EIGHT_LANGUAGE_20261030.md)
- [Team 16: translation and staging failure patterns](FAILURE/TEAM16_STAGING_20261030.md)

## Cross-team adoption protocol

Before changing related code, read the matching case, verify its source SHA and test assumptions, then record whether the approach was reused unchanged, adapted, failed, or was inapplicable. Do not claim adoption without code/test evidence. Team 12 owns learning screen semantics, Team 13 owns booking screens, Team 15 independently verifies mobile and integration behavior.

This index is seeded from Team 16 evidence only; other teams' cases must be added after checking their own commit and CI records.

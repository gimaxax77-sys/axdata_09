---
description: 저장소 전체의 과설계 감사 (무엇을 지울 수 있는지)
---
Audit the entire repository for over-engineering only, not correctness. Scan the whole tree, not a diff. One line per finding, ranked biggest cut first: <tag> <what to cut>. <replacement>. [path]. Tags: delete (dead code/speculative feature), stdlib (reinvented standard library), native (dependency doing what the platform does), yagni (abstraction with one implementation), shrink (same logic, fewer lines). End with the net lines and dependencies removable. If nothing to cut: 'Lean already. Ship.'

<!-- Adapted from ponytail (MIT, © 2026 DietrichGebert) https://github.com/DietrichGebert/ponytail -->

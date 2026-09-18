# Changelog

All notable changes to this repository. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions are tagged as [releases](https://github.com/soufian-zaouam/openstack-production-guide/releases).

## [1.1] — 2026-09

### Added

- `series/one-command-one-investigation/`: season 1 of the series, twenty episodes in four parts (the instance from Nova to the guest; the network path; the storage path; the control plane and correlation), each with its investigation memo (`memo/NN-memo.png`), the memo's JSON source and the renderer.
- `incidents/`: six anonymised incident case studies in RCA format: evacuation and fencing on shared storage; kernel upgrade and console recovery; RabbitMQ partition and stopping the APIs; patching with limited capacity; CPU pinning, steal time and live migration; Ceph full OSD and CRUSH weights.
- `errors.md`: index by exact error message, mapping each message to the page that explains it and the first read-only check.
- `methodology/incident-record-template.md` and `methodology/decision-record-template.md`.
- `CHANGELOG.md`, `CITATION.cff`, issue templates (erratum, subject).

### Changed

- `README.md`: rewritten as a map with four entry points (by symptom, by command, by error message, by case); content map; safety labels stated.
- `troubleshooting/` and `methodology/` pages: a *Go deeper* section on each page pointing to the series episodes and incident cases that use its commands.
- `CONTRIBUTING.md`: the three rules (verified and cited commands, no environment data, safety label on every command); conventions for episodes and cases.
- The printable PDF moved out of the repository to the release assets; `pdf/` removed.

## [1.0] — 2026-09-17

### Added

- First release: `README.md`, `LICENSE` (CC BY-SA 4.0), `CONTRIBUTING.md`; `methodology/` (production troubleshooting principles, before you act, changes and rollback, root cause analysis, escalation checklist); `troubleshooting/` (first commands, VM unreachable, VM stuck in BUILD / ERROR, compute, networking, storage, control plane services, RabbitMQ, MariaDB / Galera, Keystone, logs); `reference/` (quick reference by question, upstream documentation); the printable field guide (PDF, 11 pages).

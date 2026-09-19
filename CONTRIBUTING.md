# Contributing

Thank you for helping make this guide more useful to people who operate OpenStack in production.

## What is welcome

- **Corrections**: a command that is wrong, outdated, or behaves differently in a recent release. Open an issue with the *erratum* template, or a pull request with the source that shows the correct behaviour.
- **Context**: the question a command answers, the signal to look for, the release or backend where behaviour differs.
- **Error messages**: an exact message with the page that explains it, for [`errors.md`](errors.md). A message without a page is a reason to write the page.
- **Investigation paths**: a symptom, the order in which you check the layers, and why.
- **Subjects**: a command or a situation for a future episode or case. Open an issue with the *subject* template.
- **Incident cases**: an anonymised production situation in the [incident record format](methodology/incident-record-template.md): the options you had, the decision, what it cost, what you learned.

## What this repository is not

- A dump of every possible command. A command without the question it answers will not be merged.
- A deployment guide, or a place for vendor-specific marketing.
- A place for anything confidential.
- A second copy of the upstream documentation. Link to it; do not paraphrase it.

## Three rules for every contribution

1. **Every command is verified on a primary source and the source is cited.** Official project documentation, release notes, or the source code: a link, in the page's *Sources* section. Behaviour that changed between releases (API microversions, renamed options, removed fields) is stated with the version.
2. **No environment data.** No employer or customer names, real hostnames, real IP addresses, internal architecture details, ticket numbers, or anything covered by an NDA. Use placeholders (`<vm>`, `<compute>`, `<project>`) and documentation addresses (`192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24`). Incident cases are composites, generalised so that no platform or person can be recognised.
3. **Every command carries its safety label.** `READ ONLY`, `STATE CHANGING` or `POTENTIALLY DISRUPTIVE`, in the header block of a series episode or incident case, or as a `[!WARNING]` block in a troubleshooting page:

   ```markdown
   > [!WARNING]
   > **Changes state.** What the command changes, and the precondition.
   ```

   A state-changing command is never presented as a troubleshooting step. When it appears, it comes with its impact, its blast radius, its prerequisites, its rollback, and the conditions under which it must not be run.

## Style

- Say where the command runs: control plane (`openstack` client, API) or compute / network node.
- Say what it proves: the question, and the signal that matters in the output.
- Say what it does *not* tell you. That section is the one readers use most.
- Short sections, the question before the command, no filler, no marketing. Same tone from the README to the last episode.
- File names in kebab-case, without dates; series episodes numbered `NN-<command>.md`; troubleshooting pages named by symptom; incident cases by their short name.
- One H1 per file, containing the words people search for (the exact error message when there is one).

## Series episodes and incident cases

An episode of [One Command, One Investigation](series/one-command-one-investigation/README.md) follows a fixed structure (production situation, the command, what it tells us, what it does not, what it lets us hypothesise, next investigation, investigation chain, production lesson, version notes, sources). Its memo is generated from `memo/NN-memo.json` with `memo/render_memo.py`; edit the JSON, not the image.

An incident case follows the [incident record template](methodology/incident-record-template.md).

## How to contribute

1. Open an issue describing the correction or the addition, with the release and backend if relevant.
2. For changes, fork the repository, create a branch, and open a pull request with a short explanation of *why* the change is correct, and the source.
3. Keep the style above.

By contributing, you agree that your contribution is licensed under the same license as the repository ([CC BY-SA 4.0](LICENSE)).

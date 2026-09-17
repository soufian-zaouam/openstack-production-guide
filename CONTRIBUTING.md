# Contributing

Thank you for helping make this guide more useful to people who operate OpenStack in production.

## What is welcome

- **Corrections**: a command that is wrong, outdated, or behaves differently in a recent release.
- **Context**: the question a command answers, the signal to look for, the release or backend where behaviour differs.
- **Investigation paths**: a symptom, the order in which you check the layers, and why.
- **Field notes**: an anonymised production situation, the options you had, the decision, and what you learned.

## What this repository is not

- A dump of every possible command. A command without the question it answers will not be merged.
- A deployment guide, or a place for vendor-specific marketing.
- A place for anything confidential.

## Rules for every contribution

1. **Keep it generic and anonymised.** No employer or customer names, real hostnames, real IP addresses, internal architecture details, ticket numbers, or anything covered by an NDA. Use placeholders (`<vm>`, `<compute>`, `<project>`) and documentation addresses (`192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24`).
2. **Read-only first.** If a command changes state, add a warning block that says what it changes and what must be true before running it:

   ```markdown
   > [!WARNING]
   > **Changes state.** What the command changes, and the precondition.
   ```

3. **Say where it runs.** Control plane (`openstack` client, API) or compute / network node.
4. **Say what it proves.** For each command: the question, and the signal that matters in the output.
5. **Cite upstream when stating a fact** about OpenStack behaviour, preferably the official project documentation or release notes.
6. **Mention version dependencies** when behaviour changed between releases (API microversions, renamed options, removed features).

## How to contribute

1. Open an issue describing the correction or the addition, with the release and backend if relevant.
2. For changes, fork the repository, create a branch, and open a pull request with a short explanation of *why* the change is correct.
3. Keep the style: short sections, the question before the command, no filler.

By contributing, you agree that your contribution is licensed under the same license as the repository ([CC BY-SA 4.0](LICENSE)).

# Open-source launch checklist

The source, MIT license and community files can be reviewed locally. Publication
is a separate action. This checkout has no public remote URL or established
registry listing; do not invent links, badges or package availability claims.

## Prepared in source

- Root quick start, documentation index, installation and CLI guides.
- Routing, quality, measurement, troubleshooting, architecture and examples.
- MIT license, provenance notice, maintainer contact and governance.
- Contributor guide, conduct policy, support and private security instructions.
- GitHub issue/PR templates, dependency-update configuration and release CI.
- Documentation checks, source-export allowlist and inspected package tooling.

## Before the owner publishes

1. Review the entire staged diff and confirm the maintainer contact is intended
   for public use. Inspect the license and third-party notices.
2. Keep ignored local dependencies, source-input archives, private handoffs,
   native session data, trial logs and quality evidence out of the repository.
3. Run the contributor checks and build a clean source bundle with
   `scripts/prepare_source.py`. Inspect its inventory and checksum.
4. Publish the reviewed Git repository under the intended account. Add the actual
   repository, issue tracker and release URLs to project metadata only afterward.
5. Enable the repository's private vulnerability reporting if desired, alongside
   the email contact already provided. Adding SECURITY.md does not enable it.
6. Configure branch protection or rulesets requiring the actual CI job names
   after observing a successful remote run. Add CODEOWNERS only with a verified
   user/team identifier; no fictional owner is supplied here.
7. Review GitHub Actions and Dependabot permissions/settings. No workflow in this
   source automatically publishes a package or grants repository access.
8. Establish package-name ownership and a release credential/trusted-publishing
   setup before any registry upload. Release only inspected artifacts.

The owner will publish the repository. A local commit is not remote publication.
For supported GitHub settings see
[private vulnerability reporting](https://docs.github.com/en/code-security/how-tos/report-and-fix-vulnerabilities/configure-vulnerability-reporting/configure-for-a-repository)
and [Dependabot options](https://docs.github.com/en/code-security/reference/supply-chain-security/dependabot-options-reference).

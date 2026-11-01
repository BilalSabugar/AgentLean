# Security and data handling

AgentLean's storage, routing decisions and previews run locally and require no
provider credentials. `run --execute` explicitly launches the installed Codex or
Claude CLI, which can send prompts to its provider and perform the requested work
using its existing authentication and permissions. AgentLean does not store prompt
text or change native permission controls. Trial notes and evidence may contain private data; keep logs private
and inspect exports before sharing. Files created for log replacement default to
owner-only POSIX permissions; Windows access follows the directory's ACLs.

`--checks PATH --execute` also runs the explicitly supplied local acceptance
commands as your user, without a shell. Use trusted check definitions. Quality
logs remain on disk; opt-in `--repair-attempts` sends a bounded failure excerpt
to the same native client/provider. Avoid secrets in check output. A changed
manifest blocks success; test-source integrity and subjective output quality
still require review. Timeouts stop the direct check process; scripts that spawn
descendants must manage their cleanup.

The supported environment is a trusted local repository on a local filesystem.
OS locks coordinate AgentLean writers. External editors, hostile concurrent path
changes, and network-filesystem locking/atomicity semantics are outside the
guarantee. Do not run AgentLean with elevated privileges on untrusted workspaces.
Path checks reject resolved destinations outside the target repository and final
symlinks; manifests and recovery journals accept only known managed destinations.

Ordinary failed writes preserve the previous log. Installer recovery data may
contain copies of managed instruction files. Process crashes leave recoverable
journals and harmless persistent lock sidecars. Power-loss durability depends on
the OS and filesystem; keep backups of important experiment data.

## Reporting a vulnerability

Email the private contact in [MAINTAINERS.md](MAINTAINERS.md) with the subject
`AgentLean security report`. Include the affected version, expected impact,
reproduction steps and a minimal sanitized example. Do not post exploitable
details, credentials or private logs in a public issue.

If the published GitHub repository enables private vulnerability reporting, its
Security/Advisories page can provide an additional private channel. That setting
has not been enabled by adding these files. The maintainer should acknowledge,
investigate and coordinate disclosure before public details are shared, but no
fixed response time or confidentiality guarantee is established.

Only the current release is maintained; older versions do not have a separate
security-backport commitment. Update to the current release when reporting a
problem unless doing so prevents reproducing it.

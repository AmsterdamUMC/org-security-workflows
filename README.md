# Organization Security Workflows

Central repository for GitHub security infrastructure at Amsterdam UMC. Provides reusable workflows, pre-commit hooks, and shared configuration for preventing accidental data leaks in research repositories.

This repository is the **single source of truth** for security rules enforced across the organization.

## Repository Structure

```
org-security-workflows/
├── .github/
│   └── workflows/
│       ├── check-forbidden-filetypes.yml    # Reusable workflow for filetype scanning
│       ├── check-gitleaks.yml               # Reusable workflow for secrets detection
│       └── check-personal-info.yml          # Reusable workflow for PII scanning
├── actions/
│   ├── filetype-check/
│   │   └── action.yml                       # Composite action for filetype detection
│   ├── gitleaks-check/
│   │   └── action.yml                       # Composite action for secrets detection
│   └── personal-info-check/
│       └── action.yml                       # Composite action for PII detection
├── pre-commit-check/
│   ├── check-filetypes.sh                   # Pre-commit hook for filetypes
│   └── check-personal-info.sh               # Pre-commit hook for PII
├── pre-push-check/
│   ├── check-filetypes-prepush.sh           # Pre-push hook for filetypes
│   └── check-personal-info-prepush.sh       # Pre-push hook for PII
├── personal-info-lists/
│   ├── common-dutch-firstnames.txt          # Dutch first name database
│   ├── common-dutch-surnames.txt            # Dutch surname database
│   └── common-dutch-streetnames.txt         # Dutch street name database
├── central-gitignore.txt                    # Forbidden file patterns
├── gitleaks.toml                            # Secrets detection rules
├── .pre-commit-hooks.yaml                   # Hook definitions for pre-commit framework
├── LICENSE
└── README.md
```

## Security Architecture

This repository provides security checks that run at multiple layers:

| Layer | Location | Trigger | Can Be Bypassed? |
|-------|----------|---------|------------------|
| Pre-commit hooks | Developer machine | `git commit` | Yes (`--no-verify`) |
| Pre-push hooks | Developer machine | `git push` | Yes (`--no-verify`) |
| GitHub Actions | GitHub servers | Push, PR | No |

The hooks and workflows reference centralized configuration files in this repository, ensuring consistent rules across all Amsterdam UMC projects.

```
Developer Machine                              GitHub
──────────────────────────────────────────────────────────────

git add ──> .gitignore ──> blocked silently

git commit ──> pre-commit hooks ──> blocked with message
               (filetypes, PII)

git push ──> pre-push hooks ──> blocked with message
             (filetypes, PII)

                    │
                    │ (if local checks pass or are bypassed)
                    ▼

              GitHub Actions ──> blocked, PR fails, alert sent
              (filetypes, PII, secrets)
```

## Security Checks

The system performs three primary security checks:

| Check | What It Detects | Hook | Workflow |
|-------|-----------------|------|----------|
| Forbidden filetypes | Data files, medical imaging, databases | Yes | Yes |
| Personal information | Dutch names, addresses, patient IDs | Yes | Yes |
| Secrets | API keys, tokens, passwords, private keys | No | Yes |

Secrets detection runs only as a GitHub Action (not in local hooks) because gitleaks requires additional tooling that may not be available on all developer machines.

## Forbidden File Types

### The Central Gitignore

The `central-gitignore.txt` file defines which file types are blocked:

```gitignore
# BEGIN FORBIDDEN
*.csv
*.xlsx
*.json
!package.json         # Exception: allowed
!package-lock.json    # Exception: allowed
# END FORBIDDEN

# Everything below is convenience-only (not enforced)
.DS_Store
__pycache__/
```

**Only patterns between `# BEGIN FORBIDDEN` and `# END FORBIDDEN`** are enforced by hooks and workflows. Patterns outside this block are helpful `.gitignore` suggestions that won't block commits.

### Blocked Categories

**Data files**
`.csv`, `.tsv`, `.xlsx`, `.xls`, `.ods`, `.sav`, `.dta`, `.RData`, `.rds`, `.sas7bdat`, `.feather`, `.parquet`, `.pickle`, `.h5`, `.hdf5`, `.sqlite`, `.db`

**Medical and research data**
`.nii`, `.nii.gz`, `.dcm` (DICOM), `.edf`, `.bdf`, `.eeg`, `.vhdr` (biosignals), `.fastq`, `.bam`, `.vcf`, `.bed` (genomics)

**Credentials**
`.env`, `.pem`, `.key`, `.p12`, `.pfx`

**Archives** (may contain data)
`.zip`, `.tar.gz`, `.rar`, `.7z`

### Exceptions

Some patterns have exceptions for common safe files:

| Blocked | Exceptions |
|---------|------------|
| `*.json` | `package.json`, `package-lock.json`, `tsconfig.json`, `composer.json`, `appsettings.json` |
| `*.xml` | `pom.xml`, `web.xml`, `*.csproj`, `*.fsproj`, `*.vbproj` |
| `.env` | (no exceptions) |

See `central-gitignore.txt` for the complete list.

## Personal Information Detection

The PII scanner detects patterns common in Dutch healthcare research.

### What Gets Detected

**Dutch names**
- First names from `personal-info-lists/common-dutch-firstnames.txt`
- Surnames from `personal-info-lists/common-dutch-surnames.txt`
- Combinations suggesting full names

**Dutch addresses**
- Street names from `personal-info-lists/common-dutch-streetnames.txt`
- House number patterns
- Postal codes (1234 AB format)
- City names

**Identifiers**
- Patient IDs (7-digit MRN patterns)
- BSN (Burgerservicenummer) with checksum validation
- Medical record number formats

### Reducing False Positives

The PII detection is tuned for medical research contexts. Common Dutch words that happen to match name patterns are excluded. If you encounter false positives, please report them so we can refine the detection rules.

## Secrets Detection

Secrets scanning uses gitleaks with a custom configuration (`gitleaks.toml`).

### What Gets Detected

**Cloud provider credentials**
AWS access keys, Azure credentials, GCP service account keys

**API keys and tokens**
GitHub tokens, Slack tokens, Stripe keys, SendGrid keys, OAuth tokens, JWT tokens

**Database credentials**
Connection strings, database passwords

**Private keys**
SSH private keys, PEM files, PKCS12 certificates

**Generic secrets**
High-entropy strings that may be passwords or tokens

### Configuration

The `gitleaks.toml` file defines detection rules and allowlists. It includes rules for common secret patterns and excludes known safe patterns like example placeholders.

## Usage

### Using the Reusable Workflows

To add security checks to a repository, create a workflow file:

```yaml
# .github/workflows/security-check.yml
name: Security Check

on:
  push:
    branches: [main, master]
  pull_request:
    branches: [main, master]

jobs:
  filetype-check:
    uses: AmsterdamUMC/org-security-workflows/.github/workflows/check-forbidden-filetypes.yml@main

  personal-info-check:
    uses: AmsterdamUMC/org-security-workflows/.github/workflows/check-personal-info.yml@main

  secrets-check:
    uses: AmsterdamUMC/org-security-workflows/.github/workflows/check-gitleaks.yml@main
```

For stability, replace `@main` with a specific version tag (e.g., `@v0.2.21`).

### Using the Pre-Commit Hooks

Add to your repository's `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/AmsterdamUMC/org-security-workflows
    rev: v0.2.21
    hooks:
      - id: check-forbidden-filetypes
        stages: [pre-commit]
      - id: check-forbidden-filetypes-prepush
        stages: [pre-push]
      - id: check-personal-info
        stages: [pre-commit]
      - id: check-personal-info-prepush
        stages: [pre-push]

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-added-large-files
        args: ['--maxkb=100']
      - id: check-merge-conflict
```

Install the hooks:

```bash
pip install pre-commit
pre-commit install
pre-commit install --hook-type pre-push
```

## What Happens When a File Is Blocked

### Pre-commit Hook

```
===============================================================
  ERROR: Forbidden file types detected!
===============================================================

The following files match forbidden data patterns:

  X data/patients.csv

These file types are blocked to prevent accidental data leaks.

If this is a false positive, contact your data steward.
To bypass (NOT recommended): git commit --no-verify
```

### GitHub Action

The workflow fails with a red X and annotates the problematic files. Pull requests cannot be merged until the violation is resolved.

When a violation is detected:
1. The workflow fails
2. A security alert is sent to the `security-telemetry` repository
3. An issue may be created for tracking
4. The security team is notified

## Telemetry Integration

When GitHub Actions detect violations, they send telemetry to the `security-telemetry` repository via repository dispatch:

```json
{
  "event_type": "security_alert",
  "client_payload": {
    "repository": "AmsterdamUMC/example-repo",
    "status": "fail",
    "actor": "username",
    "sha": "abc123...",
    "ref": "refs/heads/main",
    "timestamp": "2024-01-15T10:30:00Z",
    "run_id": "12345678",
    "blocked_files": ["data.csv", "secrets.env"]
  }
}
```

This enables centralized monitoring and alerting across all organization repositories.

## Remediation

### If Sensitive Data Was Committed

If the repository is public, immediately make it private and contact your data steward.

To remove files from Git history:

```bash
# Install git-filter-repo (recommended over filter-branch)
pip install git-filter-repo

# Remove a specific file from all history
git filter-repo --path data/patients.csv --invert-paths

# Force push (coordinate with collaborators first)
git push --force --all
```

See [GitHub's guide on removing sensitive data](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository) for detailed instructions.

### Reporting Security Incidents

If sensitive data may have been exposed:

1. Do not open a public GitHub issue
2. Contact [b.vandervelde@amsterdamumc.nl](mailto:b.vandervelde@amsterdamumc.nl) immediately
3. Include: repository name, what was exposed, when it was committed

## Troubleshooting

### Pre-commit hook not running

```bash
pre-commit install
pre-commit install --hook-type pre-push
```

### Hook using outdated rules

```bash
pre-commit clean
pre-commit autoupdate
pre-commit install
pre-commit install --hook-type pre-push
```

### Need to bypass (use with caution)

```bash
git commit --no-verify
git push --no-verify
```

Bypassing local hooks does not bypass GitHub Actions. Violations will still be caught on push.

### Testing the hooks

```bash
# Create a test file
echo "test" > test.csv

# Try to add it (should be blocked by .gitignore if using template)
git add test.csv

# Force add to bypass .gitignore
git add -f test.csv

# Try to commit (should be blocked by pre-commit)
git commit -m "test"

# Clean up
git reset HEAD test.csv
rm test.csv
```

### Windows / GitHub Desktop

Pre-commit hooks require a Unix-like shell. On Windows:

1. Install Git Bash from https://gitforwindows.org/
2. In GitHub Desktop: File > Options > Git > Shell > select "Git Bash"

Alternatively, use Git Bash or WSL directly for committing.

## Updating Security Rules

### Forbidden Patterns

Edit `central-gitignore.txt` and commit. Changes take effect:
- Immediately for new workflow runs
- On next `pre-commit autoupdate` for local hooks

### PII Detection

Update files in `personal-info-lists/` to add or remove name patterns.

### Secrets Detection

Edit `gitleaks.toml` to modify detection rules or allowlists.

### Versioning

When making changes:
1. Update the relevant configuration files
2. Test thoroughly in a non-production repository
3. Create a new version tag (e.g., `v0.2.22`)
4. Update documentation to reference the new version

Repositories using `@main` receive changes immediately. Repositories pinned to a version tag must update their `.pre-commit-config.yaml` to receive changes.

## Related Repositories

| Repository | Purpose |
|------------|---------|
| `org-security-workflows` | Security rules and hooks (this repo) |
| `org-security-scanner` | Organization-wide scanning for violations |
| `security-telemetry` | Central alerting and logging |
| `repo-template-secure` | Template for new research repositories |

## License

MIT License - See [LICENSE](LICENSE)

## Support

**Technical issues:** [b.vandervelde@amsterdamumc.nl](mailto:b.vandervelde@amsterdamumc.nl)
**False positives:** Open an issue in this repository
**Security incidents:** See Remediation section above
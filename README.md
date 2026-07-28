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
│   ├── check-filetypes.py                   # Pre-commit hook for filetypes
│   ├── check-filetypes.sh                   # Legacy bash version
│   ├── check-personal-info.py               # Pre-commit hook for PII
│   └── check-personal-info.sh               # Legacy bash version
├── pre-push-check/
│   ├── check-filetypes-prepush.py           # Pre-push hook for filetypes
│   ├── check-filetypes-prepush.sh           # Legacy bash version
│   ├── check-personal-info-prepush.py       # Pre-push hook for PII
│   └── check-personal-info-prepush.sh       # Legacy bash version
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
────────────────────────────────────────────────────────────────

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
| Personal information | Dutch names, addresses, patient IDs, BSN | Yes | Yes |
| Secrets | API keys, tokens, passwords, private keys | No | Yes |

Secrets detection runs only as a GitHub Action (not in local hooks) because gitleaks requires additional tooling that may not be available on all developer machines.

## Forbidden File Types

### The Central Gitignore

The `central-gitignore.txt` file defines which file types are blocked:

```gitignore
# BEGIN FORBIDDEN
*.csv
*.xlsx
!package.json         # Exception: allowed
!package-lock.json    # Exception: allowed
# END FORBIDDEN

# Everything below is convenience-only (not enforced)
.DS_Store
__pycache__/
```

**Only patterns between `# BEGIN FORBIDDEN` and `# END FORBIDDEN`** are enforced by hooks and workflows. Patterns outside this block are helpful `.gitignore` suggestions that won't block commits.

### Blocked Categories

**Tabular data**
`.csv`, `.tsv`, `.xlsx`, `.xls`, `.sav`, `.dta`, `.feather`, `.parquet`

**Statistical/scientific data formats**
`.RData`, `.rds`, `.mat`, `.pk1`, `.npz`, `.npy`, `.fig`

**Databases**
`.sqlite`, `.db`

**Medical imaging & biosignals**
`.nii`, `.nii.gz`, `.dcm` (DICOM), `.edf`, `.bdf`, `.eeg`, `.vhdr`, `.vmrk`

**Genomics & bioinformatics**
`.fastq`, `.fastq.gz`, `.fasta`, `.fasta.gz`, `.fna`, `.bam`, `.sam`, `.vcf`, `.gtf`, `.gff`, `.bed`, `.wig`, `.bigWig`

**Audio/video data**
`.mp4`, `.avi`, `.mov`, `.mkv`, `.webm`, `.wav`, `.flac`

**Archives** (may contain data)
`.zip`, `.tar.gz`, `.7z`, `.rar`

**Credentials & secrets**
`.env`, `.env.*`, `.key`, `.pem`, `.pfx`, `.crt`

See `central-gitignore.txt` for the complete and current list.

## Personal Information Detection

The PII scanner detects patterns common in Dutch healthcare research.

### What Gets Detected

**Dutch names**
- First names from `personal-info-lists/common-dutch-firstnames.txt`
- Surnames from `personal-info-lists/common-dutch-surnames.txt`
- Combinations suggesting full names (e.g., first name followed by capitalized word)

**Dutch addresses**
- Street names from `personal-info-lists/common-dutch-streetnames.txt`
- Any word with Dutch street suffixes (straat, laan, weg, plein, gracht, etc.) followed by a house number
- Postal code patterns

**Identifiers**
- Patient IDs (7-digit patterns)
- BSN (Burgerservicenummer) - validated using the 11-proof (elfproef) checksum to reduce false positives

### Reducing False Positives

The PII detection is tuned for medical research contexts:
- Markdown files (`.md`) are excluded to allow documentation with example names
- Street suffix patterns filter out false positive name matches
- BSN detection uses checksum validation (only ~1 in 11 random 9-digit numbers pass)

If you encounter false positives, please report them so we can refine the detection rules.

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
      # Python versions (recommended)
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
3. The security team is notified

## Telemetry

When GitHub Actions detect violations, they send telemetry to the `security-telemetry` repository via repository dispatch. This enables centralized monitoring and alerting across all organization repositories.

### Privacy

**Telemetry never includes sensitive content.** Only metadata is sent:

| Check | What's Sent | What's NOT Sent |
|-------|-------------|-----------------|
| Filetypes | Filenames that were blocked | File contents |
| Personal info | Violation types (e.g., "bsn", "fullname") | Actual names, BSN numbers, addresses |
| Secrets | File locations and rule IDs | Actual secret values |

Example telemetry payload:

```json
{
  "event_type": "personal_info_violation",
  "client_payload": {
    "repository": "AmsterdamUMC/example-repo",
    "status": "fail",
    "actor": "username",
    "sha": "abc123...",
    "ref": "refs/heads/main",
    "timestamp": "2024-01-15T10:30:00Z",
    "run_id": "12345678",
    "violation_types": ["bsn", "fullname_firstname", "address_known"]
  }
}
```

## Remediation

### If a Commit Is Blocked

Review the error message to identify which files or patterns triggered the block. Common solutions:

1. **Remove the file** if it contains actual sensitive data
2. **Add to `.gitignore`** to prevent future accidents
3. **Contact your data steward** if you believe it's a false positive

### If Sensitive Data Was Committed

If the repository is public, immediately make it private and contact your data steward.

<a name="secrets-remediation"></a>
### Secrets Remediation

If secrets were detected:

1. **Rotate the secret immediately** - assume it's compromised
2. **Remove from Git history** using the steps below
3. **Update any systems** using the old secret

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

Pre-commit hooks require Python 3. On Windows:

1. Ensure Python 3 is installed and in your PATH
2. Install Git Bash from https://gitforwindows.org/
3. In GitHub Desktop: File > Options > Git > Shell > select "Git Bash"

The Python-based hooks handle Windows path and encoding differences automatically.

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
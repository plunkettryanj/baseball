# Secrets Management Setup — age + SOPS (Windows / Git Bash)

Reference notes for setting up encrypted secrets in this repo. Covers installation, key generation, and encrypting/decrypting `secrets.yaml`. Written from a Windows + Git Bash + VSCode environment.

---

## Why this exists

ClickHouse credentials need to live in the repo so both local dev and CI can read them, but plaintext credentials should never be committed — even to a private repo. **SOPS** (Secrets OPerationS) encrypts the *values* in a YAML file while keeping the structure readable, so the encrypted file is safe to commit and diff. **age** is the encryption backend SOPS uses here — a simpler modern alternative to GPG.

The pattern:
- A **public key** encrypts. Safe to commit, share, paste anywhere.
- A **private key** decrypts. Never committed — stays local, and later gets pasted into GitHub Actions as a repo secret so CI can decrypt at runtime.

---

## 1. Install `age`

No Scoop/Chocolatey required — manual binary install works fine.

1. Download the Windows zip from https://github.com/FiloSottile/age/releases
2. Extract it — yields `age.exe`, `age-keygen.exe`, and a few plugin binaries
3. Move the extracted folder somewhere permanent, e.g. `C:\Users\<you>\age`
4. Add that folder to **User PATH**:
   - Start menu → search "Environment Variables" → "Edit the system environment variables" → "Environment Variables"
   - Under **User variables**, select `Path` → Edit → New → paste the folder path → OK through all dialogs
5. **Fully restart Git Bash** (and VSCode, if using its integrated terminal — closing just the terminal tab isn't enough; PATH is inherited at process start)
6. Confirm:
   ```bash
   age-keygen --version
   ```

### Windows-specific gotchas encountered
- Renaming a downloaded `.exe` while File Explorer has "hide file extensions" enabled silently produces a double extension (e.g. `sops.exe.exe`). Check the actual filename with `ls` in Git Bash, not Explorer's display name.
- PATH changes don't propagate to already-open terminals — always fully close and reopen the app, not just the terminal pane.
- If a command is "not found" right after confirming the file is in a PATH folder, try `hash -r` to clear Bash's command lookup cache before troubleshooting further.

---

## 2. Generate the age keypair

```bash
age-keygen -o key.txt
```

Output looks like:
```
Public key: ageXXXsample_public_key
```

- `key.txt` contains **both keys** — treat it as the private key file. Never commit it.
- The public key line printed to stdout is safe to copy anywhere (`.sops.yaml`, docs, chat).
- You'll see a `warning: writing secret key to a world-readable file` on Windows — NTFS permissions don't map cleanly to the `chmod` model. Run `chmod 600 key.txt` anyway as good practice; know it may not fully restrict access the way it would on Linux. Fine for local dev secrets; don't reuse this key for anything higher-stakes without tightening actual NTFS ACLs.

**Immediately after generating:** add `key.txt` to `.gitignore` before doing anything else, so there's no window where it could get staged accidentally.

---

## 3. Install SOPS

The GitHub releases page lists platform binaries without file extensions in some cases — look for the one ending in **`.amd64.exe`** (e.g. `sops-v3.13.3.amd64.exe`), not the `.rpm`/`.deb` (Linux packages) or bare `darwin`/`linux.amd64` (Mac/Linux, no extension) files.

1. Download from https://github.com/getsops/sops/releases
2. Rename to `sops.exe` — **verify the actual filename in Git Bash (`ls`) after renaming**, since Explorer may hide the real extension and produce `sops.exe.exe`
3. Move it into the same folder already on PATH (next to `age.exe`)
4. Restart Git Bash
5. Confirm:
   ```bash
   sops --version
   ```

If Windows SmartScreen flags a freshly downloaded unsigned `.exe`: right-click the file in Explorer → Properties → check "Unblock" near the bottom → Apply.

---

## 4. Create `.sops.yaml`

In the repo root — tells SOPS which public key to encrypt for, and which files the rule applies to:

```yaml
creation_rules:
  - path_regex: secrets\.yaml$
    age: ageXXXsample_public_key
```

Safe to commit — contains only the public key.

---

## 5. Create `secrets.yaml` (plaintext, local only)

In the repo root:

```yaml
clickhouse:
  user: app_user
  password: placeholder_password
  host: localhost
  port: 9000
```

Add to `.gitignore` immediately:
```
key.txt
secrets.yaml
```

---

## 6. Encrypt

```bash
cd ~/VSC/baseball   # repo root
sops -e secrets.yaml > secrets.enc.yaml
```

`secrets.enc.yaml` will have the YAML structure intact (`clickhouse:`, `user:`, etc.) but values replaced with ciphertext, plus a `sops:` metadata block appended (key fingerprint, timestamp, MAC). **This is the file you commit.**

---

## 7. Decrypt (verify round-trip before trusting it)

SOPS needs to find the **private key** to decrypt — it checks several default locations and env vars, and won't find a key sitting in an arbitrary repo folder unless told where to look.

Point it at your key file:
```bash
export SOPS_AGE_KEY_FILE="$HOME/VSC/baseball/key.txt"
```

Then:
```bash
sops -d secrets.enc.yaml
```

Should print the original plaintext values.

**This `export` only lasts the current terminal session.** Make it persistent so every new Git Bash session has it set (needed later for dbt's `profiles.yml`, which pulls credentials from the decrypted secrets in Phase 4 of the rollout):

```bash
echo 'export SOPS_AGE_KEY_FILE="$HOME/VSC/baseball/key.txt"' >> ~/.bashrc
```

---

## 8. Commit the encrypted artifacts

```bash
git add .sops.yaml secrets.enc.yaml .gitignore
git commit -m "Add SOPS-encrypted ClickHouse secrets"
```

**Never** `git add secrets.yaml` or `git add key.txt` — both should be gitignored by this point. Double check with:
```bash
git status
```
before committing, to confirm neither shows up as staged or untracked-but-about-to-be-added.

---

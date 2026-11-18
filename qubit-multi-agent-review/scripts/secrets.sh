# Sourced by the other scripts after they set WT (the worktree); the profile is looked up there.
# SECRET_FILES: the files that hold real secrets, by name or glob in any folder, from the profile
# (../../_profiles/README.md). Without a matching profile, profile.py prints its broad fallback set; when profile.py
# itself fails, the same set is used here (kept equal to FALLBACK_SECRETS in profile.py), so the list is never empty.
# Every other env file holds dummies and is reviewed like code.
SECRETS_SH_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
SECRET_FILES=()
while IFS= read -r s; do
  [ -n "$s" ] && SECRET_FILES+=("$s")
done < <(cd "${WT:-.}" 2>/dev/null && python3 "$SECRETS_SH_DIR/../../_profiles/profile.py" secret-files 2>/dev/null)
if [ ${#SECRET_FILES[@]} -eq 0 ]; then
  SECRET_FILES=('.env' '.env.*' '*.env' '*.env.j2' '.envrc' '.netrc' '.npmrc' '*.pem' '*.key' '*.p12' '*.pfx'
                'id_rsa*' 'id_ed25519*' 'credentials.json' 'secrets.*')
fi
# inflator patterns, expanded as "${INFL[@]}": the lockfile, plus one glob per secret file ("**/" also matches the root);
# add generated and vendored paths as more elements, e.g. ':(exclude)dist/**'
INFL=(':(exclude)pnpm-lock*.yaml')
for s in "${SECRET_FILES[@]}"; do INFL+=(":(exclude,glob)**/$s"); done

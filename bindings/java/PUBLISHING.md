# Publishing the JVM bindings to Maven Central

The JVM artifacts — `dev.disarm:disarm` (Java, fat JAR with bundled native libs) and
`dev.disarm:disarm-kotlin` — publish to **Maven Central via the Sonatype Central Portal**
(`central.sonatype.com`). [`publish-java.yml`](../../.github/workflows/publish-java.yml)
runs the actual upload on a **GitHub release** (or manual `workflow_dispatch`); pushes to
`main` only *validate* against the in-repo core (the #374 drift gate).

This is the **one-time setup** that must be in place before the first publish.

## groupId — `dev.disarm`

The Central Portal verifies a namespace by domain ownership: `dev.disarm` is proven by a
DNS TXT record on **`disarm.dev`** (which we control). We deliberately do **not** use
`com.disarm` — that would require owning `disarm.com`. The Java *package* stays
`com.disarm` (package ≠ groupId; the native-lib resource path `/com/disarm/native/…`
follows the package, not the coordinates).

## 1. Register + verify the namespace

1. Create a Central Portal account at <https://central.sonatype.com> (sign in with GitHub).
2. **Namespaces → Add Namespace → `dev.disarm`.** The portal shows a verification key.
3. Add it as a TXT record on `disarm.dev` (Cloudflare zone `39fedece29024d5cb020b07ae6bfc995`).
   With the token in `.env` (`CLOUDFLARE_API_TOKEN`):

   ```sh
   set -a; . ./.env; set +a
   curl -s -X POST \
     "https://api.cloudflare.com/client/v4/zones/39fedece29024d5cb020b07ae6bfc995/dns_records" \
     -H "Authorization: Bearer ${CLOUDFLARE_API_TOKEN}" -H "Content-Type: application/json" \
     --data '{"type":"TXT","name":"disarm.dev","content":"<SONATYPE_VERIFICATION_KEY>","ttl":300}'
   ```

4. Back on the portal, click **Verify**. Once verified the TXT record can be removed.

## 2. GPG signing key (Central Portal requires signed artifacts)

```sh
gpg --gen-key                                   # RSA 4096; note the KEYID
gpg --keyserver keys.openpgp.org      --send-keys <KEYID>   # publish the PUBLIC key
gpg --keyserver keyserver.ubuntu.com  --send-keys <KEYID>   # (mirror; Central checks both)
gpg --armor --export-secret-keys <KEYID>        # the PRIVATE key → the secret below
```

## 3. Central Portal user token

Central Portal → **Account → Generate User Token** → yields a username + password pair.

## 4. GitHub Actions secrets

Add all four under **Settings → Secrets and variables → Actions**
(the workflow reads exactly these names):

| Secret | Value |
| --- | --- |
| `MAVEN_GPG_PRIVATE_KEY` | armored private key from step 2 (`-----BEGIN PGP PRIVATE KEY BLOCK-----…`) |
| `MAVEN_GPG_PASSPHRASE` | the key's passphrase |
| `CENTRAL_PORTAL_USERNAME` | user-token username from step 3 |
| `CENTRAL_PORTAL_PASSWORD` | user-token password from step 3 |

## 5. Dry run, then publish

- **Validate** without publishing: `workflow_dispatch` builds + stages + signs (or run the
  Gradle `publishAllPublicationsToStagingRepository` locally with the signing props set).
- **Publish**: a GitHub release (`v0.MINOR.PATCH`) — or a manual `workflow_dispatch` — bundles
  `build/staging-deploy` and POSTs it to the Central Portal with `publishingType=AUTOMATIC`.
  Lockstep with the other registries: the JVM minor tracks the core (see
  [RELEASING.md](../../RELEASING.md)).

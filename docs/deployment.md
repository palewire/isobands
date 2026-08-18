# Documentation deployment

The intended production site path is
`https://palewi.re/docs/isobands/`. The workflow builds the site once, stores
that build as the `release-candidate` artifact, and deploys that artifact only
for a push to `main` when `DOCS_DEPLOY_ENABLED` is `true`. The URL is shown as
plain text here until deployment makes it available, so strict link checking
does not fail against the current 404.

## Human-owned GitHub setup

Create the GitHub Actions environment `docs-production`. Create these
repository-level Actions variables:

- `DOCS_AWS_ROLE_ARN`: the IAM role ARN assumed through GitHub OIDC.
- `DOCS_AWS_REGION`: the S3 bucket's AWS region.
- `DOCS_DEPLOY_ENABLED`: set to `true` to enable production deployment.

The deploy job reads these variables in its job-level condition, before
environment-scoped configuration is safely available. Put these secrets in
the `docs-production` environment:

- `DOCS_AWS_BUCKET`: the destination bucket name.
- `DOCS_AWS_BASE_PATH`: the S3 key prefix for this site, without a leading
  slash. The prefix should contain the generated `index.html`.

The IAM role's web-identity trust policy must require the GitHub OIDC `sub`
claim to equal:

```text
repo:palewire/isobands:environment:docs-production
```

It should also use the standard GitHub OIDC audience
`sts.amazonaws.com`. The workflow uses temporary OIDC credentials; no static
AWS credentials belong in GitHub.

Grant the role only the S3 access required for the configured bucket and
prefix. Replace `<bucket>` and `<base-path>` below with the human-owned
values:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:PutObject", "s3:PutObjectAcl"],
      "Resource": "arn:aws:s3:::<bucket>/<base-path>/*"
    },
    {
      "Effect": "Allow",
      "Action": "s3:ListBucket",
      "Resource": "arn:aws:s3:::<bucket>",
      "Condition": {
        "StringLike": {
          "s3:prefix": ["<base-path>", "<base-path>/*"]
        }
      }
    }
  ]
}
```

`delivery-deploy-action@v1` checks each destination object with `HeadObject`
before uploading it, so `s3:GetObject` and the prefix-scoped
`s3:ListBucket` permission are required. The action does not delete old
objects. Its `public: true` input sends a `public-read` ACL, which requires
`s3:PutObjectAcl` and compatible S3 public-access settings.

## S3 ownership and ACLs

The current action always sends an object ACL: `public-read` when
`public: true` and `private` otherwise. Consequently, a bucket configured with S3
Object Ownership **Bucket owner enforced** rejects this action's uploads with
`AccessControlListNotSupported`; changing `public` to `false` alone does not
remove the ACL request. Keep the workflow's `public: true` only with a bucket
whose ACLs and public-read behavior are deliberately enabled, or update the
deployment action to omit ACLs before adopting bucket-owner-enforced
ownership. That action change is outside this repository's deployment
configuration.

## Cloudflare route

Configure a Cloudflare Worker route for:

```text
palewi.re/docs/isobands/*
```

The Worker should reverse-proxy the path beneath that route to the configured
S3 bucket and `<base-path>` prefix, mapping the trailing-slash root to
`index.html` and preserving the remaining path (for example, `api.html` and
`_static/...`). Keep the canonical trailing-slash URL and ensure the Worker
also handles the no-slash form consistently. The generated links and asset
URLs are relative so they continue to resolve below this prefix.

## Manual verification

After an approved deployment, verify manually through the Cloudflare URL:

1. The index loads at the canonical path
   `https://palewi.re/docs/isobands/`.
2. The API page loads at the canonical path followed by `api.html`.
3. A stylesheet or other `_static/` asset referenced by the index returns
   successfully.
4. The HTML canonical link uses the
   `https://palewi.re/docs/isobands/` base (the Palewire theme adds each
   document's generated `.html` path).
5. The displayed package version matches the intended release.

Do not make Cloudflare propagation or public-URL availability a blocking
workflow check.

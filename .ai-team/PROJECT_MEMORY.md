# Food Rescue project memory

## Stack and delivery

- Django 5.2 monolith with SQLite, Gunicorn, Nginx, and GitHub Actions SSH deployment.
- `master` is the current local development branch. Production changes require review; no deployment is performed from local validation work.

## Verified architecture decisions

- Customer, Market, Authentication, and Shop layouts load only their required stylesheet layers through Django template inheritance.
- Production static assets use `ManifestStaticFilesStorage`; templates use `{% static %}` without manual query-string versions.
- CI clears its isolated `STATIC_ROOT`, runs `collectstatic`, verifies the manifest, and then runs Django tests.
- Production deploy and rollback collect without `--clear` so older hashed files remain available during the rollback/cache window.
- The Nginx static cache example under `ops/nginx/` is documentation only and must be reviewed against the effective server config before application.

## Current verified milestone

- CSS/static/cache refactor is locally verified: Django checks and 67 tests pass; 147 files are collected and post-processed; 21 required project/admin assets have valid hashed targets.
- Playwright/Chrome checks pass at 320, 375, 390, 430, 768, 1024, and 1440 px for Market, Products, Customer Signup, Password Reset, Shop Login, Store Dashboard, and Store Product pages. No horizontal overflow, failed requests, or console errors were observed; the mobile Customer menu opens correctly.
- Store templates retain both `style.css` and `stores.css` through `{{ block.super }}`.

## Remaining validation

- Effective Nginx cache headers, `nginx -t`, HTTPS asset MIME types, old-hash retention, and deploy/rollback behavior remain to be verified on staging.
- Safari/iOS safe-area and real-device behavior are not yet verified.

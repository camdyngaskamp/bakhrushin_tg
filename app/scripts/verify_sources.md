# Verify RSS URLs

Some theatre websites change RSS endpoints frequently. After seeding, open the `sources` table and fix any RSS URLs that 404.

How:
- Open admin panel (or connect psql) and update `sources.url`
- Prefer official RSS when available; otherwise implement HTML collectors.

Tip:
- If a source doesn't have RSS, set `type=html` and implement a rule in `app/collectors/html.py`.

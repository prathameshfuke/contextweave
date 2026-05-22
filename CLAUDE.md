<!-- CW:START -->
# Project Memory: audit-project

## Relevant Context

**[cli · — · 1 minute ago]**
working on user-authentication feature, Claude worked on this 2 hours ago

**[cli · — · 20 minutes ago]**
working on user-authentication feature, Claude worked on this 2 hours ago

**[cli · — · 2 minutes ago]**
using PostgreSQL not MongoDB — team voted, schema is well-defined

**[cli · — · 20 minutes ago]**
using PostgreSQL not MongoDB — team voted, schema is well-defined

**[hook:SessionStart · claude · 28 seconds ago]**
Session started: auth (agent=claude)

**[hook:SessionStart · claude · 5 minutes ago]**
Session started: auth (agent=claude)

**[cli · — · 8 hours ago]**
switched from SQLite to PostgreSQL for the user sessions table

**[cli · — · 8 hours ago]**
working on implementing OAuth2 flow for Google sign-in

**[hook:SessionStart · gemini · 1 minute ago]**
Session started: auth (agent=gemini)

**[hook:SessionStart · gemini · 19 minutes ago]**
Session started: auth (agent=gemini)

**[hook:SessionEnd · gemini · 48 seconds ago]**
Session completed: completed JWT login flow

**[hook:SessionEnd · gemini · 19 minutes ago]**
Session completed: completed JWT login flow

**[system:consolidate · — · 4 minutes ago]**
Consolidation sweep: merged=0, deleted=0, decayed=0, orphans=0

**[cli · — · 2 minutes ago]**
src/auth/login.ts is the main login handler, src/auth/refresh.ts handles token rotation

**[cli · — · 20 minutes ago]**
src/auth/login.ts is the main login handler, src/auth/refresh.ts handles token rotation

**[cli · — · 8 hours ago]**
decided to use JWT for authentication with 24h expiry and refresh token rotation

**[cli · — · 2 minutes ago]**
decided to use JWT for auth, not cookie sessions, because we need stateless mobile API

**[cli · — · 21 minutes ago]**
decided to use JWT for auth, not cookie sessions, because we need stateless mobile API

**[cli · — · 2 minutes ago]**
refresh token rotation is the next task, pattern is in src/lib/jwt.ts

**[cli · — · 20 minutes ago]**
refresh token rotation is the next task, pattern is in src/lib/jwt.ts


---
## Handoff from gemini — 36s ago
**Feature:** auth
**Next step:** implement refresh token rotation in src/auth/refresh.ts
**Summary:** completed JWT login flow
<!-- CW:END -->

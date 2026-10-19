# RBAC / Permission Matrix — v1

Two roles exist in v1 (matches existing schema: `users.role IN ('user', 'admin')`). No intermediate roles (e.g. content-editor-only) planned yet.

| Action | User (self) | Admin |
|---|---|---|
| View published tours | ✅ | ✅ |
| View/edit own profile | ✅ | ✅ (own) |
| Purchase a tour | ✅ | ✅ (own account, no special discount implied) |
| Download a purchased tour | ✅ (own purchases only) | — |
| Start/resume a walk session | ✅ (own, unconsumed license) | — |
| Like/comment on a tour (post-completion) | ✅ (own) | ✅ (own) |
| Create/edit a tour | ❌ | ✅ |
| Publish/unpublish a tour | ❌ | ✅ |
| Upload stop audio/GPS data | ❌ | ✅ |
| View any user's purchase history | ❌ | ✅ |
| Issue a refund | ❌ | ✅ |
| Reset a stuck session (support action) | ❌ | ✅ |
| View aggregate analytics (which tours sell, completion rates) | ❌ | ✅ |
| Moderate/delete a comment | ❌ (own comment only — delete own) | ✅ (any) |

**Notes:**
- All admin-only endpoints must check `role = 'admin'` server-side — never trust a client-side role flag.
- No "moderator" or "content-only" role exists yet; if the team grows and non-technical people need to publish tours without full admin/refund access, that's a v2 role split, not v1.
- Device/session management (binding, invalidation) is system-enforced, not role-gated — it applies identically to every user account including admins' own personal accounts.

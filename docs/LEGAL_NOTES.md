# Legal notes (not legal advice)

The privacy policy, terms and refund policy are not written yet and need a lawyer's review.

## Privacy policy
- Do not copy another company's policy: it is copyrighted and describes their data, not ours.
- Start from an open template, e.g. the Basecamp policies (https://github.com/basecamp/policies, CC BY 4.0, keep the attribution), or a generator, then adapt.
- Describe what NoB really does: email and name; GPS only while a walk is running; payments via Razorpay; opt-in analytics and marketing; data export and account deletion (built: `GET /me/export`, `DELETE /me`); a grievance email.
- India's DPDP Rules 2025: notice-and-consent duties from 13 May 2027, 90-day grievance response, parental consent for children (source: https://www.scconline.com/blog/post/2025/11/14/meity-notified-digital-personal-data-protection-rules-2025/). Lawyer to confirm.

## What the backend already supports
`accepted_terms` at signup (stored with `TERMS_VERSION`), marketing and analytics opt-ins, export, delete.

## Still needed from the business
Legal entity, policy text, grievance mailbox, Razorpay KYC. See the founder checklist in Notion.

# Authentication handoff — 2026-10-06

Arjun Mehta, Riya Sharma, and Sana Iqbal attended the Atlas Payments authentication handoff.

Arjun Mehta is the authentication and OAuth2 subject-matter expert. The team confirmed that the Identity Gateway validates OAuth2 access tokens; the Payments API receives the validated identity and must not validate tokens a second time.

This confirmed boundary replaces the earlier unapproved proposal to validate access tokens inside the Payments API. The Payments API depends on the Identity Gateway for authenticated requests.

Riya Sharma will document the gateway-to-payment identity claims and review the handoff with Arjun before enabling the integration.

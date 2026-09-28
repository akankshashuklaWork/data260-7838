# AI use disclosure

1. The assistant helped scaffold the measurement harness. I remain responsible for selecting the rental-housing domain, checking the assignment requirements, configuring MySQL, running the application, capturing screenshots, and validating the reported results.
2. One item independently verified: the session cookie contains only the opaque token; user data is looked up from the server-side `sessions` table.
3. I verified this by inspecting the `Set-Cookie` response and querying the session row after login.
4. I kept the cookie HTTP-only and stored `user_id`, timestamps, and expiry only in MySQL, so the browser cannot directly read or modify user data.

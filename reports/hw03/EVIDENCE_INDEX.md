# HW3 Part 1 Evidence Index

| File | Requirement demonstrated |
| --- | --- |
| `screenshots/01_home_page.png` | Public `/` route |
| `screenshots/02_login_page.png` | Public `/login` route and Bootstrap login form |
| `screenshots/03_invalid_credentials.png` | Invalid credentials rejected with a visible Bootstrap alert |
| `screenshots/04_dashboard.png` | Authenticated `/dashboard` route |
| `screenshots/05_logout_home.png` | `/logout` ends the session and redirects to home |
| `screenshots/06_dashboard_after_logout.png` | Logged-out browser cannot open `/dashboard` |
| `screenshots/07_expired_session.png` | Idle-expired session cannot open `/dashboard` |
| `screenshots/08_templates_directory.png` | Separate Jinja template files |
| `screenshots/09_set_cookie_header.png` | Login response cookie has Secure, HttpOnly, and SameSite |
| `screenshots/10_replay_after_logout.png` | A cookie copied before logout is rejected |
| `screenshots/11_idle_timeout_proof.png` | Idle timeout rejection shown with curl |
| `raw/session_evidence.txt` | Text copy of the cookie, replay, and idle timeout evidence |
| `screenshots/12_*.png` to `22_*.png` | Part 2 and test command output |

The signed cookie value is hidden in all evidence. The idle timeout demo used a separate copy of
the app with a 3 second timeout; the application default is 900 seconds.

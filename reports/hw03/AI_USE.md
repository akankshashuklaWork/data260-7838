# AI Use Disclosure

## 1. What did I use an AI assistant for, and what did I do myself?

I used OpenAI Codex to help me understand the Homework 3 requirements, explain
terminal commands, suggest a structure for the authentication and retrieval
code, troubleshoot dependency errors, review saved experiment artifacts, and
organize the report in beginner-friendly language.

I ran the commands on my own computer, selected and downloaded the five public
government PDFs, checked their sources, created and reviewed the five evaluation
questions, inspected the retrieval output, tested the application, and decided
what evidence to include in the submission. I also reviewed all AI-assisted code
and writing before keeping it.

## 2. What AI-produced output was wrong or unsuitable?

An earlier AI-assisted version of the logout code redirected the user to
`/login?logged_out=true`. That behavior was unsuitable because the Homework 3
instructions specifically require logout to destroy the session and redirect to
the home page.

## 3. How did I detect or verify the problem?

I compared the implementation with the assignment requirement, which says that
logout must redirect to home. I then inspected the redirect returned by the
logout route and used the authentication test to check the `Location` header.
This showed that the redirect destination did not match the requirement.

## 4. What did I change, and why does it work now?

I changed the logout route in `auth.py` to return
`RedirectResponse(url="/", status_code=303)`. The route still clears the
session before redirecting. I also changed the test so that it expects `/`, then
reran the authentication checks; all 18 checks passed. This works because the
old session can no longer be reused and the user arrives at the public home page,
where the Login link is available.

## Additional note about Part 2

The Part 2 comparison does not use a large language model to write answers or
grade results. It uses the public `sentence-transformers/all-MiniLM-L6-v2`
embedding model for retrieval. The program calculates the metrics, and an
independent NumPy cosine-similarity check verifies the stored similarity scores.


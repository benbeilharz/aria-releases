# ARIA New Releases

Generates a browsable HTML page of ARIA new release data from PDF reports.

## Usage

```bash
python3 generate_releases.py
```

This scans `~/IHGT/Research/ARIA/` for PDFs (including year subfolders like `2025/`), parses them, and writes `index.html` to this directory.

Open `index.html` locally or push to GitHub Pages to deploy.

## Dependencies

```bash
pip install pdfplumber
```

`pdfplumber` will also be auto-installed the first time the script runs if it's missing.

## Auto-regenerate on push

A pre-push git hook regenerates `index.html` automatically before each push. Run this once to activate it:

```bash
git config core.hooksPath .githooks
```

If the hook finds that `index.html` changed, it will abort the push and ask you to commit the update first.

## Configuration

Edit the variables at the top of `generate_releases.py`:

| Variable | Default | Description |
|---|---|---|
| `PDF_DIR` | `~/IHGT/Research/ARIA` | Folder containing ARIA PDFs |
| `FIREBASE_API_KEY` | — | Firebase web app API key |
| `FIREBASE_AUTH_DOMAIN` | — | Firebase auth domain (`<project-id>.firebaseapp.com`) |
| `FIREBASE_PROJECT_ID` | — | Firebase project ID |
| `ALLOWED_EMAIL` | `ben.beilharz@gmail.com` | Only this Google account can sign in |
| `EXCLUDED_ARTISTS` | The Wiggles, etc. | Artists to filter from output |

## Listened tracking (Firebase)

"Listened" state is synced across devices via Firebase Auth (Google sign-in) + Firestore, keyed per user so it isn't tied to one browser.

Setup, in the [Firebase console](https://console.firebase.google.com):

1. Create a project (free Spark plan).
2. **Authentication → Sign-in method** → enable **Google**.
3. **Firestore Database** → create a database, then set the rules to:

   ```
   rules_version = '2';
   service cloud.firestore {
     match /databases/{database}/documents {
       match /users/{userId}/listened/{key} {
         allow read, write: if request.auth != null
           && request.auth.uid == userId
           && request.auth.token.email == 'ben.beilharz@gmail.com';
       }
     }
   }
   ```

4. **Project settings → General → Your apps** → add a web app, copy `apiKey`, `authDomain`, `projectId` into `generate_releases.py`, then regenerate.

The site is on public GitHub Pages, so `ALLOWED_EMAIL` and the matching Firestore rule keep anyone but that account from reading or writing listened data — sign-in with any other Google account is rejected client-side and blocked server-side by the rule above.

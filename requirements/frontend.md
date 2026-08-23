# RecoverIQ frontend requirements

The frontend is reproducible through `apps/web/package-lock.json`. Install it with `npm ci`; do not translate these packages into `requirements.txt`, which is only for Python tooling.

## Runtime and package manager

| Technology | Tested version | Requirement source |
|---|---:|---|
| Node.js | 24.19.0 | Local release-validation runtime |
| npm | 11.17.0 | Local release-validation runtime |
| Next.js | 16.3.2 | `package.json` and `package-lock.json` |
| React / React DOM | 19.2.8 | `package-lock.json` |
| TypeScript | 5.9.3 | `package-lock.json` |
| ESLint | 9.39.5 | `package-lock.json` |

Use Node.js 24 LTS with npm 11 for the documented path. The exact transitive dependency graph is locked in `apps/web/package-lock.json`.

## UI, styles, graphics, and motion

| Package or approach | Locked version | Purpose |
|---|---:|---|
| Tailwind CSS | 4.3.3 | Token-driven responsive styling |
| @tailwindcss/postcss | 4.3.3 | Tailwind/PostCSS build integration |
| @base-ui/react | 1.7.0 | Accessible UI primitives |
| shadcn | 4.19.0 | Component tooling/conventions |
| lucide-react | 1.33.0 | Interface icons |
| class-variance-authority | 0.7.1 | Component variants |
| clsx | 2.1.1 | Conditional class composition |
| tailwind-merge | 3.6.0 | Safe Tailwind class merging |
| tw-animate-css | 1.4.0 | Utility animation support |

RecoverIQ uses first-party responsive SVG/CSS charts and CSS transitions/keyframes; it does not require a separate charting or JavaScript animation runtime.

## Install and verify

```powershell
Set-Location apps/web
npm ci
npm run lint
npm run typecheck
npm run build
```

`npm ci` intentionally fails when `package.json` and `package-lock.json` disagree, which protects release reproducibility.

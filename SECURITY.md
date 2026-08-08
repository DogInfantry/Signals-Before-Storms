# Security policy

## What this project is, in security terms

Signals-Before-Storms is a research repository. It has **no server, no database, no accounts and no
user data**. It reads public market prices from Yahoo Finance, writes files to disk, and publishes
three static sites from committed JSON. There is nothing to log into and nothing to breach.

That said, it is a public Apache-2.0 repository with three live deployments and one workflow that
writes to `main` unattended, so it should say where to send a report.

## Supported versions

`main` only. This is research code rather than a released library, so fixes land on the default
branch and are not backported to tags.

| Version | Supported |
|---|---|
| `main` | Yes |
| Tagged releases (`v1.x`) | No, snapshots for citation only |

## Reporting a vulnerability

Use GitHub's private reporting, not a public issue:

**[Report a security vulnerability](https://github.com/DogInfantry/Signals-Before-Storms/security/advisories/new)**

Include what you did, what happened, and which file or workflow it touches. Expect an
acknowledgement within roughly a week; this is a solo project, not a staffed one.

Please do not open a public issue for something exploitable until it is fixed.

## In scope

- Anything that lets a third party push to this repository or alter what the three sites serve.
- Supply-chain problems in the declared dependency tree (`hmmlearn`, `cvxpy`, `yfinance`,
  `curl_cffi`, `numpy`, `pandas`, `scipy`, `scikit-learn`, `pydantic`, `pyyaml`, and the Next.js
  tree under `ledger/`). Dependabot watches all three ecosystems, so a known CVE should already be
  opening a pull request; say so if it is not.
- Anything in `.github/workflows/monitor.yml`. It is the only automation here that runs unattended
  with `contents: write`, so it is the highest-value target in the repo. It uses the default
  `GITHUB_TOKEN` and holds no secrets, it commits exactly two JSON payloads, and it refuses to
  publish behind the guards in `tools/check_monitor_payload.py`. A way around those guards is a
  legitimate report.
- Code execution reachable from untrusted input, for example a crafted vendor response that the
  parsing in `src/regime_shift/data.py` mishandles.

## Not in scope

These are not vulnerabilities, and saying so here keeps the channel usable:

- **The strategy losing money.** That is the published result. The README says plainly that the
  regime overlay does not beat a 60/40 benchmark on risk-adjusted return.
- **Disagreement with a number, a method or a modelling choice.** That is an issue or a pull
  request, and it is welcome as one.
- **A vendor outage or a bad print from Yahoo Finance.** Handled as a data-quality problem, guarded
  by `data.drop_return_outliers` and by the staleness check in the monitor workflow.
- **Findings from an automated scanner with no demonstrated impact on this repository.**

## No financial advice

Nothing here is investment advice, and nothing in it should be traded on. See the disclaimer at the
end of the README.

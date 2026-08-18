# Contributing

1. Fork the repository and create a focused branch from the current default branch.
2. Make the smallest change that solves the problem and include tests when behavior changes.
3. Run the project checks:

   ```bash
   python3 -m unittest discover -s tests -v
   uv build
   uvx twine check dist/*
   ```

4. Open a pull request with a clear summary, test output, privacy review, and release impact.

## Privacy

Never commit or attach transcripts, reductions, findings, or other confidential material to an
issue or pull request. Use a synthetic minimal reproduction instead.

## Pull requests

Keep each pull request focused, explain the user-visible effect, and update public documentation
when the interface changes. A maintainer may request a smaller reproduction, additional tests, or
privacy clarification before merging.

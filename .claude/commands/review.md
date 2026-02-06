Review the current code changes or specified file for issues: $ARGUMENTS

Instructions:
1. If a file is specified, read it. Otherwise check `git diff` for recent changes
2. Check for:
   - Logic bugs and off-by-one errors
   - Missing type hints
   - ruff/mypy violations
   - Code duplication
   - Functions doing too many things
   - Missing error handling at boundaries
3. Run `ruff check` and `mypy` on the file
4. Provide a concise summary of findings with line references
5. Suggest fixes for anything critical

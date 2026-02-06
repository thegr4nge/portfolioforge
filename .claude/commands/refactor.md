Analyse code for refactoring opportunities: $ARGUMENTS

Instructions:
1. Read the target file or module
2. Identify refactoring opportunities:
   - Functions doing more than one thing
   - Code duplication (within file and across files)
   - Long methods (>30 lines)
   - Deep nesting (>3 levels)
   - Missing abstractions or unclear naming
   - Type hint gaps
   - Dead code
3. For each opportunity, assess:
   - **Impact:** How much does this improve readability/maintainability?
   - **Risk:** Could this break existing behaviour?
   - **Effort:** Quick fix or significant restructure?
4. Prioritise: high impact + low risk first
5. Propose concrete changes with before/after examples
6. Run ruff, mypy, and tests after any changes to verify nothing broke
7. Do NOT refactor things that are fine — only flag genuine problems

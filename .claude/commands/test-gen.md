Generate comprehensive tests for: $ARGUMENTS

Instructions:
1. Read the target file to understand all functions and classes
2. Identify testable logic (avoid testing terminal rendering/ANSI output)
3. Generate pytest tests covering:
   - Happy path for each public function
   - Edge cases (empty inputs, boundary values, zero/negative numbers)
   - Error conditions
4. Use pytest fixtures for shared setup
5. Place tests in tests/test_<module_name>.py
6. Run the tests to verify they pass
7. Report coverage gaps if any

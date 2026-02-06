def greet(name: str) -> str:
    """Return a greeting message."""
    return f"Hello, {name}!"


def add_numbers(a: int, b: int) -> int:
    result = a + b
    return result


# Test it
message = greet("World")
print(message)

# Intentional error - hover over this
x: int = "not an integer"

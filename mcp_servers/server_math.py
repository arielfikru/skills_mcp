"""
MCP Server: Math Operations
A simple FastMCP server that provides mathematical tools.
Transport: stdio
"""

from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    name="math",
    instructions="Server for mathematical operations. Provides add, multiply, and fibonacci tools.",
)


@mcp.tool()
def add(a: float, b: float) -> float:
    """Add two numbers together.

    Args:
        a: First number
        b: Second number

    Returns:
        The sum of a and b
    """
    return a + b


@mcp.tool()
def multiply(a: float, b: float) -> float:
    """Multiply two numbers together.

    Args:
        a: First number
        b: Second number

    Returns:
        The product of a and b
    """
    return a * b


@mcp.tool()
def fibonacci(n: int) -> str:
    """Calculate the nth Fibonacci number and return the sequence up to that point.

    Args:
        n: The position in the Fibonacci sequence (1-indexed, max 50)

    Returns:
        A string showing the Fibonacci sequence and the nth number
    """
    if n < 1:
        return "Error: n must be >= 1"
    if n > 50:
        return "Error: n must be <= 50 (to prevent excessive computation)"

    fib = [0, 1]
    for i in range(2, n):
        fib.append(fib[-1] + fib[-2])

    sequence = fib[:n]
    return f"Fibonacci({n}) = {sequence[-1]}\nSequence: {', '.join(str(x) for x in sequence)}"


@mcp.tool()
def is_prime(number: int) -> str:
    """Check if a number is prime.

    Args:
        number: The number to check

    Returns:
        Whether the number is prime and its factors if not
    """
    if number < 2:
        return f"{number} is not prime (must be >= 2)"

    factors = []
    for i in range(2, int(number**0.5) + 1):
        if number % i == 0:
            factors.append(i)
            factors.append(number // i)

    if factors:
        factors = sorted(set(factors))
        return f"{number} is NOT prime. Factors: {', '.join(str(f) for f in factors)}"
    else:
        return f"{number} IS prime"


if __name__ == "__main__":
    mcp.run(transport="stdio")

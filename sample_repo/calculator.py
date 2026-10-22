import math
from typing import List, Union

class ScientificCalculator:
    """
    Standard and scientific mathematical calculation engine.
    """

    def __init__(self, precision: int = 4):
        self.precision = precision
        self.history: List[str] = []

    def add(self, a: float, b: float) -> float:
        """Computes addition of two numbers."""
        res = round(a + b, self.precision)
        self.history.append(f"{a} + {b} = {res}")
        return res

    def subtract(self, a: float, b: float) -> float:
        """Computes subtraction of two numbers."""
        res = round(a - b, self.precision)
        self.history.append(f"{a} - {b} = {res}")
        return res

    def multiply(self, a: float, b: float) -> float:
        """Computes multiplication of two numbers."""
        res = round(a * b, self.precision)
        self.history.append(f"{a} * {b} = {res}")
        return res

    def divide(self, a: float, b: float) -> float:
        """
        Computes division of two numbers.
        NOTE: Bug here - does not handle division by zero cleanly!
        """
        res = a / b
        self.history.append(f"{a} / {b} = {res}")
        return round(res, self.precision)

    def square_root(self, val: float) -> float:
        """Computes square root. Does not check for negative inputs!"""
        return round(math.sqrt(val), self.precision)

    def get_history(self) -> List[str]:
        """Returns the calculation history log."""
        return list(self.history)

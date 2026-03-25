def add(a, b):
    """返回两个数的和。
    
    Args:
        a: 第一个数
        b: 第二个数
    
    Returns:
        两个数的和
    """
    return a + b


def subtract(a, b):
    """返回两个数的差。
    
    Args:
        a: 被减数
        b: 减数
    
    Returns:
        两个数的差 (a - b)
    """
    return a - b


def multiply(a, b):
    """返回两个数的乘积。
    
    Args:
        a: 第一个数
        b: 第二个数
    
    Returns:
        两个数的乘积 (a * b)
    """
    return a * b


def divide(a, b):
    """返回两个数的商。
    
    Args:
        a: 被除数
        b: 除数
    
    Returns:
        两个数的商 (a / b)
    
    Raises:
        ZeroDivisionError: 当除数为0时抛出
    """
    return a / b
import warnings
import functools


def deprecated(reason: str):
    """Decorator to mark a method or function as deprecated.

    Emits a DeprecationWarning with the qualified name and reason whenever
    the decorated callable is invoked.

    Usage:
        @deprecated("Replaced by generate_playlist_plan.")
        def old_method(self, ...): ...
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            warnings.warn(
                f"{func.__qualname__} is deprecated and will be removed: {reason}",
                DeprecationWarning,
                stacklevel=2,
            )
            return func(*args, **kwargs)
        return wrapper
    return decorator

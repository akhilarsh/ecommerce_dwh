"""
Utility decorators for automatic logging and monitoring.
"""

import functools
import time
from typing import Any, Callable
from src.utils.logger import get_logger


def log_execution(func: Callable) -> Callable:
    """
    Decorator to automatically log function execution.
    
    Logs:
    - Function entry with arguments
    - Function completion with result
    - Execution time
    - Any exceptions raised
    
    Usage:
        @log_execution
        def my_function(arg1, arg2):
            return result
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        logger = get_logger(func.__module__)
        func_name = func.__name__
        
        # Log entry
        args_repr = [repr(a) for a in args[:3]]  # First 3 args only
        kwargs_repr = [f"{k}={v!r}" for k, v in list(kwargs.items())[:3]]
        signature = ", ".join(args_repr + kwargs_repr)
        if len(args) > 3 or len(kwargs) > 3:
            signature += ", ..."
        
        logger.info(f"▶ Executing: {func_name}({signature})")
        
        start_time = time.time()
        
        try:
            result = func(*args, **kwargs)
            elapsed = time.time() - start_time
            
            # Log completion
            result_repr = repr(result) if result is not None else "None"
            if len(result_repr) > 100:
                result_repr = result_repr[:97] + "..."
            
            logger.info(f"✓ Completed: {func_name} -> {result_repr} ({elapsed:.3f}s)")
            return result
            
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"✗ Failed: {func_name} - {type(e).__name__}: {str(e)} ({elapsed:.3f}s)")
            raise
    
    return wrapper


def log_method(func: Callable) -> Callable:
    """
    Decorator to automatically log method execution (for class methods).
    
    Similar to log_execution but handles 'self' parameter appropriately.
    
    Usage:
        class MyClass:
            @log_method
            def my_method(self, arg1):
                return result
    """
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs) -> Any:
        logger = get_logger(self.__class__.__module__)
        class_name = self.__class__.__name__
        func_name = func.__name__
        
        # Log entry (skip 'self' in args representation)
        args_repr = [repr(a) for a in args[:3]]
        kwargs_repr = [f"{k}={v!r}" for k, v in list(kwargs.items())[:3]]
        signature = ", ".join(args_repr + kwargs_repr)
        if len(args) > 3 or len(kwargs) > 3:
            signature += ", ..."
        
        logger.info(f"▶ Executing: {class_name}.{func_name}({signature})")
        
        start_time = time.time()
        
        try:
            result = func(self, *args, **kwargs)
            elapsed = time.time() - start_time
            
            # Log completion
            result_repr = repr(result) if result is not None else "None"
            if len(result_repr) > 100:
                result_repr = result_repr[:97] + "..."
            
            logger.info(f"✓ Completed: {class_name}.{func_name} ({elapsed:.3f}s)")
            return result
            
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"✗ Failed: {class_name}.{func_name} - {type(e).__name__}: {str(e)} ({elapsed:.3f}s)")
            raise
    
    return wrapper


def log_sql_execution(func: Callable) -> Callable:
    """
    Decorator specifically for SQL execution methods.
    
    Logs SQL queries being executed (truncated for readability).
    
    Usage:
        @log_sql_execution
        def execute_query(self, sql):
            # execute sql
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        logger = get_logger(func.__module__)
        func_name = func.__name__
        
        # Try to extract SQL from args/kwargs
        sql = None
        if len(args) > 1 and isinstance(args[1], str):
            sql = args[1]
        elif 'query' in kwargs:
            sql = kwargs['query']
        elif 'sql' in kwargs:
            sql = kwargs['sql']
        
        if sql:
            # Truncate and clean SQL for logging
            sql_clean = " ".join(sql.split())  # Remove extra whitespace
            if len(sql_clean) > 200:
                sql_clean = sql_clean[:197] + "..."
            logger.info(f"▶ SQL: {sql_clean}")
        else:
            logger.info(f"▶ Executing: {func_name}")
        
        start_time = time.time()
        
        try:
            result = func(*args, **kwargs)
            elapsed = time.time() - start_time
            
            # Log row count if result is a list
            if isinstance(result, list):
                logger.info(f"✓ SQL completed: {len(result)} rows returned ({elapsed:.3f}s)")
            else:
                logger.info(f"✓ SQL completed ({elapsed:.3f}s)")
            
            return result
            
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"✗ SQL failed: {type(e).__name__}: {str(e)} ({elapsed:.3f}s)")
            raise
    
    return wrapper

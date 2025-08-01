import ast
import json
import os
import pickle
import uuid
from typing import (TYPE_CHECKING, Any, Callable, Dict, Iterable, List,
                    Optional, Tuple, Type, Union)

import numpy as np
import torch
from pydantic import ValidationError

from .. import core, core_ext
from ..models import CustomConstraint, LengthConstraint, LLMDataModel
from ..prompts import Prompt
from ..utils import CustomUserWarning
from .measures import calculate_frechet_distance, calculate_mmd

if TYPE_CHECKING:
    from ..symbol import Expression, Symbol


class Primitive:
    # DO NOT use by default neuro-symbolic iterations for mixins to avoid unwanted side effects
    __semantic__ = False
    # disable the entire NeSy engine access
    __disable_nesy_engine__ = False
    # disable None shortcut
    __disable_none_shortcut__ = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # by default, disable shortcut matches and neuro-symbolic iterations
        self.__semantic__ = self.__semantic__ or Primitive.__semantic__
        self.__disable_nesy_engine__ = self.__disable_nesy_engine__ or Primitive.__disable_nesy_engine__
        self.__disable_none_shortcut__ = self.__disable_none_shortcut__ or Primitive.__disable_none_shortcut__

    @staticmethod
    def _is_iterable(value):
        return isinstance(value, (list, tuple, set, dict, bytes, bytearray, range, torch.Tensor, np.ndarray))


class OperatorPrimitives(Primitive):
    def __try_type_specific_func(self, other, func, op: str = None):
        if not isinstance(other, self._symbol_type):
            other = self._to_type(other)
        # None shortcut
        if not self.__disable_none_shortcut__:
            if  self.value is None or other.value is None:
                CustomUserWarning(f"unsupported {self._symbol_type.__class__} value operand type(s) for {op}: '{type(self.value)}' and '{type(other.value)}'", raise_with=TypeError)
        # try type specific function
        try:
            # try type specific function
            value = func(self, other)
            if value is NotImplemented:
                operation = '' if op is None else op
                CustomUserWarning(f"unsupported {self._symbol_type.__class__} value operand type(s) for {operation}: '{type(self.value)}' and '{type(other.value)}'", raise_with=TypeError)
            return value
        except Exception as ex:
            self._metadata._error = ex
            pass
        return None

    def __throw_error_on_nesy_engine_call(self, func):
        '''
        This function raises an error if the neuro-symbolic engine is disabled.
        '''
        if self.__disable_nesy_engine__:
            CustomUserWarning(f"unsupported {self.__class__} value operand type(s) for {func.__name__}: '{type(self.value)}'", raise_with=TypeError)

    def __bool__(self) -> bool:
        '''
        Get the boolean value of the Symbol.
        If the Symbol's value is of type 'bool', the method returns the boolean value, otherwise it returns False.

        Returns:
            bool: The boolean value of the Symbol.
        '''
        val = False
        if isinstance(self.value, bool):
            val = self.value
        elif self.value is not None:
            val = True if self.value else False

        return val

    '''
    This mixin contains functions that perform arithmetic operations on symbols or symbol values.
    The functions in this mixin are bound to the 'neurosymbolic' engine for evaluation.
    '''
    def __contains__(self, other: Any) -> bool:
        '''
        Check if a Symbol object is present in another Symbol object.
        By default, if 'other' is not a Symbol, it's casted to a Symbol object.

        Args:
            other (Any): The object to check for containment.

        Returns:
            bool: True if the current Symbol contains the 'other' Symbol, otherwise False.
        '''
        result = self.__try_type_specific_func(other, lambda self, other: other.value in self.value, op='in')

        if not self.__semantic__ and not getattr(other, '__semantic__', False):
            return result

        self.__throw_error_on_nesy_engine_call(self.__contains__)

        @core.contains()
        def _func(_, other) -> bool:
            pass

        return self._to_type(_func(self, other))

    def __eq__(self, other: Any) -> bool:
        '''
        Check if the current Symbol is equal to another Symbol.
        By default, if 'other' is not a Symbol, it's casted to a Symbol object.

        Args:
            other (Any): The object to check for equality.

        Returns:
            bool: True if the current Symbol is equal to the 'other' Symbol, otherwise False.
        '''
        if self is other:
            return True

        result = self.__try_type_specific_func(other, lambda self, other: self.value == other.value, op='==')

        if not self.__semantic__ and not getattr(other, '__semantic__', False):
            return self._to_type(result)

        self.__throw_error_on_nesy_engine_call(self.__eq__)

        @core.equals()
        def _func(_, other) -> bool:
            pass

        return self._to_type(_func(self, other))

    def __ne__(self, other: Any) -> bool:
        '''
        This method checks if a Symbol object is not equal to another Symbol by using the __eq__ method.
        By default, if 'other' is not a Symbol, it's casted to a Symbol object.

        Args:
            other (Any): The object to check for inequality.

        Returns:
            bool: True if the current Symbol is not equal to the 'other' Symbol, otherwise False.
        '''
        result = self.__try_type_specific_func(other, lambda self, other:  self.value != other.value, op='!=')

        if not self.__semantic__ and not getattr(other, '__semantic__', False):
            return result

        return not self.__eq__(other)

    def __gt__(self, other: Any) -> bool:
        '''
        This method checks if a Symbol object is greater than another Symbol using the @core.compare() decorator with the '>' operator.
        By default, if 'other' is not a Symbol, it's casted to a Symbol object.

        Args:
            other (Any): The object to compare.

        Returns:
            bool: True if the current Symbol is greater than the 'other' Symbol, otherwise False.
        '''
        result = self.__try_type_specific_func(other, lambda self, other: self.value > other.value, op='>')

        if not self.__semantic__ and not getattr(other, '__semantic__', False):
            return self._to_type(result)

        self.__throw_error_on_nesy_engine_call(self.__gt__)

        @core.compare(operator='>')
        def _func(_, other) -> bool:
            pass

        return self._to_type(_func(self, other))

    def __lt__(self, other: Any) -> bool:
        '''
        This method checks if a Symbol object is less than another Symbol using the @core.compare() decorator with the '<' operator.
        By default, if 'other' is not a Symbol, it's casted to a Symbol object.

        Args:
            other (Any): The object to compare.

        Returns:
            bool: True if the current Symbol is less than the 'other' Symbol, otherwise False.
        '''
        result = self.__try_type_specific_func(other, lambda self, other: self.value < other.value, op='<')

        if not self.__semantic__ and not getattr(other, '__semantic__', False):
            return self._to_type(result)

        self.__throw_error_on_nesy_engine_call(self.__lt__)

        @core.compare(operator='<')
        def _func(_, other) -> bool:
            pass

        return self._to_type(_func(self, other))

    def __le__(self, other) -> bool:
        '''
        This method checks if a Symbol object is less than or equal to another Symbol using the @core.compare() decorator with the '<=' operator.
        By default, if 'other' is not a Symbol, it's casted to a Symbol object.

        Args:
            other (Any): The object to compare.

        Returns:
            bool: True if the current Symbol is less than or equal to the 'other' Symbol, otherwise False.
        '''
        result = self.__try_type_specific_func(other, lambda self, other: self.value <= other.value, op='<=')

        if not self.__semantic__ and not getattr(other, '__semantic__', False):
            return self._to_type(result)

        self.__throw_error_on_nesy_engine_call(self.__le__)

        @core.compare(operator='<=')
        def _func(_, other) -> bool:
            pass

        return self._to_type(_func(self, other))

    def __ge__(self, other) -> bool:
        '''
        This method checks if a Symbol object is greater than or equal to another Symbol using the @core.compare() decorator with the '>=' operator.
        By default, if 'other' is not a Symbol, it's casted to a Symbol object.

        Args:
            other (Any): The object to compare.

        Returns:
            bool: True if the current Symbol is greater than or equal to the 'other' Symbol, otherwise False.
        '''
        result = self.__try_type_specific_func(other, lambda self, other: self.value >= other.value, op='>=')

        if not self.__semantic__ and not getattr(other, '__semantic__', False):
            return self._to_type(result)

        self.__throw_error_on_nesy_engine_call(self.__ge__)

        @core.compare(operator='>=')
        def _func(_, other) -> bool:
            pass

        return self._to_type(_func(self, other))

    def __neg__(self) -> 'Symbol':
        '''
        Return the negated value of the Symbol.
        The method uses the @core.negate decorator to compute the negation of the Symbol value.

        Returns:
            Symbol: The negated value of the Symbol.
        '''
        result = self.__try_type_specific_func(False, lambda self, _: -self.value, op='-')

        if not self.__semantic__:
            return self._to_type(result)

        self.__throw_error_on_nesy_engine_call(self.__neg__)

        @core.negate()
        def _func(_):
            pass

        return self._to_type(_func(self))

    def __invert__(self) -> 'Symbol':
        '''
        Return the inverted value of the Symbol (logical NOT).
        The method uses the @core.invert decorator to compute the inversion of the Symbol value.
        This allows using the ~ operator for semantic inversion.

        Returns:
            Symbol: The negated value of the Symbol.
        '''
        if isinstance(self.value, bool):
            return self._to_type(not self.value)

        result = self.__try_type_specific_func(False, lambda self, _: ~self.value, op='~')

        if not self.__semantic__:
            return self._to_type(result)

        self.__throw_error_on_nesy_engine_call(self.__invert__)

        @core.invert()
        def _func(_):
            pass

        return self._to_type(_func(self))

    def __lshift__(self, other: Any) -> 'Symbol':
        '''
        Add new information to the Symbol.
        The method uses the @core.include decorator to incorporate information into the Symbol.

        Args:
            information (Any): The information to include in the Symbol.

        Returns:
            Symbol: The Symbol with the new information included.
        '''
        result = self.__try_type_specific_func(other, lambda self, other: self.value << other.value, op='<<')

        if not self.__semantic__ and not getattr(other, '__semantic__', False):
            return self._to_type(result)

        self.__throw_error_on_nesy_engine_call(self.__lshift__)

        @core.include()
        def _func(_, information: str):
            pass

        return self._to_type(_func(self, other))

    def __rlshift__(self, other: Any) -> 'Symbol':
        '''
        Add new information to the Symbol.
        The method uses the @core.include decorator to incorporate information into the Symbol.

        Args:
            information (Any): The information to include in the Symbol.

        Returns:
            Symbol: The Symbol with the new information included.
        '''
        result = self.__try_type_specific_func(other, lambda self, other: other.value << self.value, op='<<')

        if not self.__semantic__ and not getattr(other, '__semantic__', False):
            return self._to_type(result)

        self.__throw_error_on_nesy_engine_call(self.__rlshift__)

        @core.include()
        def _func(_, information: str):
            pass

        return self._to_type(_func(self, other))

    def __ilshift__(self, other: Any) -> 'Symbol':
        '''
        Add new information to the Symbol.
        The method uses the @core.include decorator to incorporate information into the Symbol.

        Args:
            information (Any): The information to include in the Symbol.

        Returns:
            Symbol: The Symbol with the new information included.
        '''
        result = self.__try_type_specific_func(other, lambda self, other: self.value << other.value, op='<<=')

        if not self.__semantic__ and not getattr(other, '__semantic__', False):
            self._value = result
            return self

        self.__throw_error_on_nesy_engine_call(self.__ilshift__)

        @core.include()
        def _func(_, information: str):
            pass
        self._value = _func(self, other)

        return self

    def __rshift__(self, other: Any) -> 'Symbol':
        '''
        Add new information to the Symbol.
        The method uses the @core.include decorator to incorporate information into the Symbol.

        Args:
            information (Any): The information to include in the Symbol.

        Returns:
            Symbol: The Symbol with the new information included.
        '''
        result = self.__try_type_specific_func(other, lambda self, other: self.value >> other.value, op='>>')

        if not self.__semantic__ and not getattr(other, '__semantic__', False):
            return self._to_type(result)

        self.__throw_error_on_nesy_engine_call(self.__rshift__)

        @core.include()
        def _func(_, information: str):
            pass

        return self._to_type(_func(self, other))

    def __rrshift__(self, other: Any) -> 'Symbol':
        '''
        Add new information to the Symbol.
        The method uses the @core.include decorator to incorporate information into the Symbol.

        Args:
            information (Any): The information to include in the Symbol.

        Returns:
            Symbol: The Symbol with the new information included.
        '''
        result = self.__try_type_specific_func(other, lambda self, other: other.value >> self.value, op='>>')

        if not self.__semantic__ and not getattr(other, '__semantic__', False):
            return self._to_type(result)

        self.__throw_error_on_nesy_engine_call(self.__rrshift__)

        @core.include()
        def _func(_, information: str):
            pass

        return self._to_type(_func(self, other))

    def __irshift__(self, other: Any) -> 'Symbol':
        '''
        Add new information to the Symbol.
        The method uses the @core.include decorator to incorporate information into the Symbol.

        Args:
            information (Any): The information to include in the Symbol.

        Returns:
            Symbol: The Symbol with the new information included.
        '''
        result = self.__try_type_specific_func(other, lambda self, other: self.value >> other.value, op='>>=')

        if not self.__semantic__ and not getattr(other, '__semantic__', False):
            self._value = result
            return self

        self.__throw_error_on_nesy_engine_call(self.__irshift__)

        @core.include()
        def _func(_, information: str):
            pass
        self._value = _func(self, other)

        return self

    def __add__(self, other: Any) -> 'Symbol':
        '''
        Combine the Symbol with another value.
        By default, if 'other' is not a Symbol, it's casted to a Symbol object.
        The method uses the @core.combine decorator to merge the Symbol and the other value.

        Args:
            other: The value to combine with the Symbol.

        Returns:
            Symbol: The Symbol combined with the other value.
        '''
        result = self.__try_type_specific_func(other, lambda self, other: self.value + other.value, op='+')

        if not self.__semantic__ and not getattr(other, '__semantic__', False):
            return self._to_type(result)

        self.__throw_error_on_nesy_engine_call(self.__add__)

        @core.combine()
        def _func(_, a: str, b: str):
            pass

        return self._to_type(_func(self, other))

    def __radd__(self, other) -> 'Symbol':
        '''
        Combine another value with the Symbol.
        By default, if 'other' is not a Symbol, it's casted to a Symbol object.
        The method uses the @core.combine decorator to merge the other value and the Symbol.

        Args:
            other (Any): The value to combine with the Symbol.

        Returns:
            Symbol: The other value combined with the Symbol.
        '''
        result = self.__try_type_specific_func(other, lambda self, other: other.value + self.value, op='+')

        if not self.__semantic__ and not getattr(other, '__semantic__', False):
            return self._to_type(result)

        self.__throw_error_on_nesy_engine_call(self.__radd__)

        @core.combine()
        def _func(_, a: str, b: str):
            pass

        return self._to_type(_func(other, self))

    def __iadd__(self, other: Any) -> 'Symbol':
        '''
        This method adds another value to the Symbol and updates its value with the result.
        By default, if 'other' is not a Symbol, it's casted to a Symbol object.

        Args:
            other (Any): The value to add to the Symbol.

        Returns:
            Symbol: The updated Symbol with the added value.
        '''
        result = self.__try_type_specific_func(other, lambda self, other: self.value + other.value, op='+=')

        if not self.__semantic__ and not getattr(other, '__semantic__', False):
            self._value = result
            return self
        other = self._to_type(other)
        self._value = self.__add__(other)

        return self

    def __sub__(self, other: Any) -> 'Symbol':
        '''
        Replace occurrences of a value with another value in the Symbol.
        By default, if 'other' is not a Symbol, it's casted to a Symbol object.
        The method uses the @core.replace decorator to replace occurrences of the other value with an empty string in the Symbol.

        Args:
            other (Any): The value to replace in the Symbol.

        Returns:
            Symbol: The Symbol with occurrences of the other value replaced with an empty string.
        '''
        result = self.__try_type_specific_func(other, lambda self, other: self.value - other.value, op='-')

        if not self.__semantic__ and not getattr(other, '__semantic__', False):
            return self._to_type(result)

        self.__throw_error_on_nesy_engine_call(self.__sub__)

        @core.replace()
        def _func(_, text: str, replace: str, value: str):
            pass

        return self._to_type(_func(self, other, ''))

    def __rsub__(self, other: Any) -> 'Symbol':
        '''
        Subtracts the symbol value from another one and removes the substrings that match the symbol value.
        By default, if 'other' is not a Symbol, it's casted to a Symbol object.
        Using the core.replace decorator, this function creates a _func method to remove matching substrings.

        Args:
            other (Any): The string to subtract the symbol value from.

        Returns:
            Symbol: A new symbol with the result of the subtraction.
        '''
        result = self.__try_type_specific_func(other, lambda self, other: other.value - self.value, op='-')

        if not self.__semantic__ and not getattr(other, '__semantic__', False):
            return self._to_type(result)

        self.__throw_error_on_nesy_engine_call(self.__rsub__)

        @core.replace()
        def _func(_, text: str, replace: str, value: str):
            pass
        other = self._to_type(other)

        return self._to_type(_func(other, self, ''))

    def __isub__(self, other: Any) -> 'Symbol':
        '''
        In-place subtraction of the symbol value by the other symbol value.
        By default, if 'other' is not a Symbol, it's casted to a Symbol object.

        Args:
            other (Any): The symbol to subtract from the current symbol.

        Returns:
            Symbol: The current symbol with the updated value.
        '''
        result = self.__try_type_specific_func(other, lambda self, other: self.value - other.value, op='-=')

        if not self.__semantic__ and not getattr(other, '__semantic__', False):
            self._value = result
            return self
        val = self.__sub__(other)
        self._value = val.value

        return self

    def __and__(self, other: Any) -> Any:
        '''
        Performs a logical AND operation between the symbol value and another.
        By default, if 'other' is not a Symbol, it's casted to a Symbol object.
        Uses the core.logic decorator with operator='and' to create a _func method for the AND operation.

        Args:
            other (Any): The string to perform the AND operation with the symbol value.

        Returns:
            Symbol: A new symbol with the result of the AND operation.
        '''
        result = self.__try_type_specific_func(other, lambda self, other: self.value & other.value, op='&')

        if not self.__semantic__ and not getattr(other, '__semantic__', False):
            return self._to_type(result)

        self.__throw_error_on_nesy_engine_call(self.__and__)

        @core.logic(operator='and')
        def _func(_, a: str, b: str):
            pass

        return self._to_type(_func(self, other))

    def __rand__(self, other: Any) -> Any:
        '''
        Performs a logical AND operation between the symbol value and another.
        By default, if 'other' is not a Symbol, it's casted to a Symbol object.
        Uses the core.logic decorator with operator='and' to create a _func method for the AND operation.

        Args:
            other (Any): The string to perform the AND operation with the symbol value.

        Returns:
            Symbol: A new symbol with the result of the AND operation.
        '''
        result = self.__try_type_specific_func(other, lambda self, other:  other.value & self.value, op='&')

        if not self.__semantic__ and not getattr(other, '__semantic__', False):
            return self._to_type(result)

        self.__throw_error_on_nesy_engine_call(self.__rand__)

        @core.logic(operator='and')
        def _func(_, a: str, b: str):
            pass
        other = self._to_type(other)

        return self._to_type(_func(other, self))

    def __iand__(self, other: Any) -> Any:
        '''
        Performs a logical AND operation between the symbol value and another.
        By default, if 'other' is not a Symbol, it's casted to a Symbol object.
        Uses the core.logic decorator with operator='and' to create a _func method for the AND operation.

        Args:
            other (Any): The string to perform the AND operation with the symbol value.

        Returns:
            Symbol: A new symbol with the result of the AND operation.
        '''
        result = self.__try_type_specific_func(other, lambda self, other: self.value & other.value, op='&=')

        if not self.__semantic__ and not getattr(other, '__semantic__', False):
            self._value = result
            return self

        self.__throw_error_on_nesy_engine_call(self.__iand__)

        @core.logic(operator='and')
        def _func(_, a: str, b: str):
            pass
        self._value = _func(self, other)

        return self

    def __or__(self, other: Any) -> Any:
        '''
        Performs a logical OR operation between the symbol value and another.
        By default, if 'other' is not a Symbol, it's casted to a Symbol object.
        Uses the core.logic decorator with operator='or' to create a _func method for the OR operation.

        Args:
            other (Any): The string to perform the OR operation with the symbol value.

        Returns:
            Symbol: A new symbol with the result of the OR operation.
        '''
        # exclude the evaluation for the Aggregator class
        from ..collect.stats import Aggregator
        if isinstance(other, Aggregator):
            return NotImplemented

        result = self.__try_type_specific_func(other, lambda self, other: self.value | other.value, op='|')

        if not self.__semantic__ and not getattr(other, '__semantic__', False):
            return self._to_type(result)

        self.__throw_error_on_nesy_engine_call(self.__or__)

        @core.logic(operator='or')
        def _func(_, a: str, b: str):
            pass

        return self._to_type(_func(self, other))

    def __ror__(self, other: Any) -> 'Symbol':
        '''
        Performs a logical OR operation between the symbol value and another.
        By default, if 'other' is not a Symbol, it's casted to a Symbol object.

        Args:
            other (Any): The object to concatenate.

        Returns:
            Symbol: A new Symbol object with the concatenated value.
        '''
        # exclude the evaluation for the Aggregator class
        from ..collect.stats import Aggregator
        if isinstance(other, Aggregator):
            return NotImplemented

        result = self.__try_type_specific_func(other, lambda self, other: self.value | other.value, op='|')

        if not self.__semantic__ and not getattr(other, '__semantic__', False):
            return self._to_type(result)

        self.__throw_error_on_nesy_engine_call(self.__ror__)

        @core.logic(operator='or')
        def _func(a: str, b: str):
            pass
        other = self._to_type(other)

        return self._to_type(_func(other, self))

    def __ior__(self, other: Any) -> 'Symbol':
        '''
        Performs a logical OR operation between the symbol value and another.
        By default, if 'other' is not a Symbol, it's casted to a Symbol object.

        Args:
            other (Any): The object to concatenate.

        Returns:
            Symbol: A new Symbol object with the concatenated value.
        '''
        # exclude the evaluation for the Aggregator class
        from ..collect.stats import Aggregator
        if isinstance(other, Aggregator):
            return NotImplemented

        result = self.__try_type_specific_func(other, lambda self, other: self.value | other.value, op='|=')

        if not self.__semantic__ and not getattr(other, '__semantic__', False):
            self._value = result
            return self
        result = self._to_type(str(self) + str(other))

        self.__throw_error_on_nesy_engine_call(self.__ior__)

        @core.logic(operator='or')
        def _func(_, a: str, b: str):
            pass
        self._value = _func(self, other)

        return self

    def __xor__(self, other: Any) -> Any:
        '''
        Performs a logical XOR operation between the symbol value and another.
        By default, if 'other' is not a Symbol, it's casted to a Symbol object.
        Uses the core.logic decorator with operator='xor' to create a _func method for the XOR operation.

        Args:
            other (Any): The string to perform the XOR operation with the symbol value.

        Returns:
            Symbol: A new symbol with the result of the XOR operation.
        '''
        result = self.__try_type_specific_func(other, lambda self, other: self.value ^ other.value, op='^')

        if not self.__semantic__ and not getattr(other, '__semantic__', False):
            return self._to_type(result)

        self.__throw_error_on_nesy_engine_call(self.__xor__)

        @core.logic(operator='xor')
        def _func(_, a: str, b: str):
            pass

        return self._to_type(_func(self, other))

    def __rxor__(self, other: Any) -> 'Symbol':
        '''
        Performs a logical XOR operation between the symbol value and another.
        By default, if 'other' is not a Symbol, it's casted to a Symbol object.
        Uses the core.logic decorator with operator='xor' to create a _func method for the XOR operation.

        Args:
            other (Any): The string to perform the XOR operation with the symbol value.

        Returns:
            Symbol: A new symbol with the result of the XOR operation.
        '''
        result = self.__try_type_specific_func(other, lambda self, other: other.value ^ self.value, op='^')

        if not self.__semantic__ and not getattr(other, '__semantic__', False):
            return self._to_type(result)

        self.__throw_error_on_nesy_engine_call(self.__rxor__)

        @core.logic(operator='xor')
        def _func(_, a: str, b: str):
            pass

        return self._to_type(_func(other, self))

    def __ixor__(self, other: Any) -> 'Symbol':
        '''
        Performs a logical XOR operation between the symbol value and another.
        By default, if 'other' is not a Symbol, it's casted to a Symbol object.
        Uses the core.logic decorator with operator='xor' to create a _func method for the XOR operation.

        Args:
            other (Any): The string to perform the XOR operation with the symbol value.

        Returns:
            Symbol: A new symbol with the result of the XOR operation.
        '''
        result = self.__try_type_specific_func(other, lambda self, other: self.value ^ other.value, op='^=')

        if not self.__semantic__ and not getattr(other, '__semantic__', False):
            self._value = result
            return self

        self.__throw_error_on_nesy_engine_call(self.__ixor__)

        @core.logic(operator='xor')
        def _func(_, a: str, b: str):
            pass
        self._value = _func(self, other)

        return self

    def __matmul__(self, other: Any) -> 'Symbol':
        '''
        This method concatenates the string representation of two Symbol objects and returns a new Symbol with the concatenated result.
        By default, if 'other' is not a Symbol, it's casted to a Symbol object.

        Args:
            other (Any): The object to concatenate.

        Returns:
            Symbol: A new Symbol object with the concatenated value.
        '''
        if isinstance(self.value, str) and isinstance(other, str) or \
            isinstance(self.value, str) and isinstance(other, self._symbol_type) and isinstance(other.value, str):
            other = self._to_type(other)
            return self._to_type(f'{self.value}{other.value}')
        CustomUserWarning(f'This method is only supported for string concatenation! Got {type(self.value)} and {type(other)} instead.', raise_with=TypeError)

    def __rmatmul__(self, other: Any) -> 'Symbol':
        '''
        This method concatenates the string representation of two Symbol objects in a reversed order and returns a new Symbol with the concatenated result.
        By default, if 'other' is not a Symbol, it's casted to a Symbol object.

        Args:
            other (Any): The object to concatenate.

        Returns:
            Symbol: A new Symbol object with the concatenated value.
        '''
        result = self.__try_type_specific_func(other, lambda self, other:  self._to_type(self.value).__matmul__(other), op='@')

        return self._to_type(result)

    def __imatmul__(self, other: Any) -> 'Symbol':
        '''
        This method concatenates the string representation of two Symbol objects and assigns the concatenated result to the value of the current Symbol object.
        By default, if 'other' is not a Symbol, it's casted to a Symbol object.

        Args:
            other (Any): The object to concatenate.

        Returns:
            Symbol: The current Symbol object with the concatenated value.
        '''
        result = self.__try_type_specific_func(other, lambda self, other: self._to_type(self.value).__matmul__(other), op='@=')
        self._value = result

        return self

    def __truediv__(self, other: Any) -> 'Symbol':
        '''
        Divides the symbol value by another, splitting the symbol value by the other value.
        The string representation of the other value is used to split the symbol value.

        Args:
            other (Any): The string to split the symbol value by.

        Returns:
            Symbol: A new symbol with the result of the division.
        '''
        result = self.__try_type_specific_func(other, lambda self, other: self.value / other.value, op='/')
        if result is not None:
            return self._to_type(result)

        return self._to_type(str(self).split(str(other)))

    def __rtruediv__(self, other: Any) -> 'Symbol':
        '''
        Divides the symbol value by another, splitting the symbol value by the other value.
        The string representation of the other value is used to split the symbol value.

        Args:
            other (Any): The string to split the symbol value by.

        Returns:
            Symbol: A new symbol with the result of the division.
        '''
        result = self.__try_type_specific_func(other, lambda self, other: other.value / self.value, op='/')
        if result is not None:
            return self._to_type(result)

        CustomUserWarning('Division operation not supported semantically! Might change in the future.', raise_with=NotImplementedError)


    def __itruediv__(self, other: Any) -> 'Symbol':
        '''
        Divides the symbol value by another, splitting the symbol value by the other value.
        The string representation of the other value is used to split the symbol value.

        Args:
            other (Any): The string to split the symbol value by.

        Returns:
            Symbol: A new symbol with the result of the division.
        '''
        result = self.__try_type_specific_func(other, lambda self, other: self.value / other.value, op='/=')
        if result is not None:
            self._value = result
            return self

        CustomUserWarning('Division operation not supported semantically! Might change in the future.', raise_with=NotImplementedError)


    def __floordiv__(self, other: Any) -> 'Symbol':
        '''
        Floor divides the symbol value by another, splitting the symbol value by the other value.
        The string representation of the other value is used to split the symbol value.

        Args:
            other (Any): The string to split the symbol value by.

        Returns:
            Symbol: A new symbol with the result of the division.
        '''
        result = self.__try_type_specific_func(other, lambda self, other: self.value // other.value, op='//')
        if result is not None:
            return self._to_type(result)

        CustomUserWarning('Floor division operation not supported semantically! Might change in the future.', raise_with=NotImplementedError)

    def __rfloordiv__(self, other: Any) -> 'Symbol':
        '''
        Floor divides the symbol value by another, splitting the symbol value by the other value.
        The string representation of the other value is used to split the symbol value.

        Args:
            other (Any): The string to split the symbol value by.

        Returns:
            Symbol: A new symbol with the result of the division.
        '''
        result = self.__try_type_specific_func(other, lambda self, other: other.value // self.value, op='//')
        if result is not None:
            return self._to_type(result)

        CustomUserWarning('Floor division operation not supported semantically! Might change in the future.', raise_with=NotImplementedError)

    def __ifloordiv__(self, other: Any) -> 'Symbol':
        '''
        Floor divides the symbol value by another, splitting the symbol value by the other value.
        The string representation of the other value is used to split the symbol value.

        Args:
            other (Any): The string to split the symbol value by.

        Returns:
            Symbol: A new symbol with the result of the division.
        '''
        result = self.__try_type_specific_func(other, lambda self, other: self.value // other.value, op='//=')
        if result is not None:
            self._value = result
            return self

        CustomUserWarning('Floor division operation not supported semantically! Might change in the future.', raise_with=NotImplementedError)

    def __pow__(self, other: Any) -> 'Symbol':
        '''
        Power operation on symbol value by another, splitting the symbol value by the other value.
        The string representation of the other value is used to split the symbol value.

        Args:
            other (Any): The string to split the symbol value by.

        Returns:
            Symbol: A new symbol with the result of the division.
        '''
        result = self.__try_type_specific_func(other, lambda self, other: self.value ** other.value, op='**')
        if result is not None:
            return self._to_type(result)

        CustomUserWarning('Power operation not supported semantically! Might change in the future.', raise_with=NotImplementedError)


    def __rpow__(self, other: Any) -> 'Symbol':
        '''
        Power operation on symbol value by another, splitting the symbol value by the other value.
        The string representation of the other value is used to split the symbol value.

        Args:
            other (Any): The string to split the symbol value by.

        Returns:
            Symbol: A new symbol with the result of the division.
        '''
        result = self.__try_type_specific_func(other, lambda self, other: other.value ** self.value, op='**')
        if result is not None:
            return self._to_type(result)

        CustomUserWarning('Power operation not supported semantically! Might change in the future.', raise_with=NotImplementedError)

    def __ipow__(self, other: Any) -> 'Symbol':
        '''
        Power operation on symbol value by another, splitting the symbol value by the other value.
        The string representation of the other value is used to split the symbol value.

        Args:
            other (Any): The string to split the symbol value by.

        Returns:
            Symbol: A new symbol with the result of the division.
        '''
        result = self.__try_type_specific_func(other, lambda self, other: self.value ** other.value, op='**=')
        if result is not None:
            self._value = result
            return self

        CustomUserWarning('Power operation not supported semantically! Might change in the future.', raise_with=NotImplementedError)

    def __mod__(self, other: Any) -> 'Symbol':
        '''
        Modulo operation on symbol value by another, splitting the symbol value by the other value.
        The string representation of the other value is used to split the symbol value.

        Args:
            other (Any): The string to split the symbol value by.

        Returns:
            Symbol: A new symbol with the result of the division.
        '''
        result = self.__try_type_specific_func(other, lambda self, other: self.value % other.value, op='%')
        if result is not None:
            return self._to_type(result)

        CustomUserWarning('Modulo operation not supported semantically! Might change in the future.', raise_with=NotImplementedError)

    def __rmod__(self, other: Any) -> 'Symbol':
        '''
        Modulo operation on symbol value by another, splitting the symbol value by the other value.
        The string representation of the other value is used to split the symbol value.

        Args:
            other (Any): The string to split the symbol value by.

        Returns:
            Symbol: A new symbol with the result of the division.
        '''
        result = self.__try_type_specific_func(other, lambda self, other: other.value % self.value, op='%')
        if result is not None:
            return self._to_type(result)

        raise NotImplementedError('Modulo operation not supported! Might change in the future.') from self._metadata._error

    def __imod__(self, other: Any) -> 'Symbol':
        '''
        Modulo operation on symbol value by another, splitting the symbol value by the other value.
        The string representation of the other value is used to split the symbol value.

        Args:
            other (Any): The string to split the symbol value by.

        Returns:
            Symbol: A new symbol with the result of the division.
        '''
        result = self.__try_type_specific_func(other, lambda self, other: self.value % other.value, op='%=')
        if result is not None:
            self._value = result
            return self

        CustomUserWarning('Modulo operation not supported semantically! Might change in the future.', raise_with=NotImplementedError)

    def __mul__(self, other: Any) -> 'Symbol':
        '''
        Multiply operation on symbol value by another, splitting the symbol value by the other value.
        The string representation of the other value is used to split the symbol value.

        Args:
            other (Any): The string to split the symbol value by.

        Returns:
            Symbol: A new symbol with the result of the division.
        '''
        result = self.__try_type_specific_func(other, lambda self, other: self.value * other.value, op='*')
        if result is not None:
            return self._to_type(result)

        CustomUserWarning('Multiply operation not supported semantically! Might change in the future.', raise_with=NotImplementedError)

    def __rmul__(self, other: Any) -> 'Symbol':
        '''
        Multiply operation on symbol value by another, splitting the symbol value by the other value.
        The string representation of the other value is used to split the symbol value.

        Args:
            other (Any): The string to split the symbol value by.

        Returns:
            Symbol: A new symbol with the result of the division.
        '''
        result = self.__try_type_specific_func(other, lambda self, other: other.value * self.value, op='*')
        if result is not None:
            return self._to_type(result)

        CustomUserWarning('Multiply operation not supported semantically! Might change in the future.', raise_with=NotImplementedError)

    def __imul__(self, other: Any) -> 'Symbol':
        '''
        Multiply operation on symbol value by another, splitting the symbol value by the other value.
        The string representation of the other value is used to split the symbol value.

        Args:
            other (Any): The string to split the symbol value by.

        Returns:
            Symbol: A new symbol with the result of the division.
        '''
        result = self.__try_type_specific_func(other, lambda self, other: self.value * other.value, op='*=')
        if result is not None:
            self._value = result
            return self

        CustomUserWarning('Multiply operation not supported semantically! Might change in the future.', raise_with=NotImplementedError)


class CastingPrimitives(Primitive):
    '''
    This mixin contains functionalities related to casting symbols.
    '''
    @property
    def syn(self) -> "Symbol":
        """
        Return a syntactic (non-semantic) view of this Symbol.
        """
        if not getattr(self, "__semantic__", False):
            return self
        return self._to_type(self.value, semantic=False)

    @property
    def sem(self) -> "Symbol":
        """
        Return a semantic view of this Symbol. 
        (Useful after calling `.syn` in a chain.)
        """
        if getattr(self, "__semantic__", False):
            return self
        return self._to_type(self.value, semantic=True)

    def cast(self, as_type: Type) -> Any:
        '''
        Cast the Symbol's value to a specific type.

        Args:
            as_type (Type): The type to cast the Symbol's value to.

        Returns:
            The Symbol's value casted to the specified type.
        '''
        return as_type(self.value)

    def to(self, as_type: Type) -> Any:
        '''
        Cast the Symbol's value to a specific type.

        Args:
            as_type (Type): The type to cast the Symbol's value to.

        Returns:
            The Symbol's value casted to the specified type.
        '''
        return self.cast(as_type)

    def ast(self) -> Any:
        '''
        Converts the string representation of the Symbol's value to an abstract syntax tree using 'ast.literal_eval'.

        Returns:
            The abstract syntax tree representation of the Symbol's value.
        '''
        return ast.literal_eval(str(self.value))

    def str(self) -> str:
        '''
        Get the string representation of the Symbol's value.

        Returns:
            str: The string representation of the Symbol's value.
        '''
        return str(self.value)

    def int(self) -> int:
        '''
        Get the integer representation of the Symbol's value.

        Returns:
            int: The integer representation of the Symbol's value.
        '''
        return int(self.value)

    def float(self) -> float:

        '''
        Get the float representation of the Symbol's value.

        Returns:
            float: The float representation of the Symbol's value.
        '''
        return float(self.value)

    def bool(self) -> bool:
        '''
        Get the boolean representation of the Symbol's value.

        Returns:
            bool: The boolean representation of the Symbol's value.
        '''
        return bool(self.value)


#@TODO: We can do much better than asking the model to generate the entire thing. We can come up with a more structured way, e.g.,
#       using a JSON schema (or contracts) and return only the keys where we need to set/del information.
class IterationPrimitives(Primitive):
    '''
    This mixin contains functions that perform iteration operations on symbols or symbol values.
    The functions in this mixin are bound to the 'neurosymbolic' engine for evaluation.
    '''
    def __getitem__(self, key: Union[str, int, slice]) -> 'Symbol':
        '''
        Get the item of the Symbol value with the specified key or index.
        If the Symbol value is a list, tuple, or numpy array, the key can be an integer or slice.
        If the Symbol value is a dictionary, the key can be a string or an integer.
        If the direct item retrieval fails, the method falls back to using the @core.getitem decorator, which retrieves and returns the item using core functions.

        Args:
            key (Union[str, int, slice]): The key or index for the item in the Symbol value.

        Returns:
            Symbol: The item of the Symbol value with the specified key or index.

        Raises:
            KeyError: If the key or index is not found in the Symbol value.
        '''
        if not self.__semantic__:
            try:
                return self.value[key]
            except Exception:
                CustomUserWarning(f'Key {key} not found in {self.value}', raise_with=Exception)

        @core.getitem()
        def _func(_, index: str):
            pass

        return self._to_type(_func(self, key))

    def __setitem__(self, key: Union[str, int, slice], value: Any) -> None:
        '''
        Set the item of the Symbol value with the specified key or index to the given value.
        If the Symbol value is a list, the key can be an integer or slice.
        If the Symbol value is a dictionary, the key can be a string or an integer.
        If the direct item setting fails, the method falls back to using the @core.setitem decorator, which sets the item using core functions.

        Args:
            key (Union[str, int, slice]): The key or index for the item in the Symbol value.
            value: The value to set the item to.

        Raises:
            KeyError: If the key or index is not found in the Symbol value.
        '''
        from ..post_processors import ASTPostProcessor

        if not isinstance(self.value, (str, dict, list)):
            CustomUserWarning(f'Setting item is not supported for {type(self.value)}. Supported types are str, dict, and list.', raise_with=TypeError)

        if not self.__semantic__:
            try:
                self.value[key] = value
                return
            except Exception:
                CustomUserWarning(f'Key {key} not found in {self.value}', raise_with=Exception)

        @core.setitem()
        def _func(_, index: str, value: str):
            pass

        result = _func(self, key, value)
        try:
            self._value = ASTPostProcessor()(result) # The type of the object that the model changed was a list or a dict
        except Exception:
            self._value = result # It was a string, or something failed (because } wasn't close, etc)

    def __delitem__(self, key: Union[str, int]) -> None:
        '''
        Delete the item of the Symbol value with the specified key or index.
        If the Symbol value is a dictionary, the key can be a string or an integer.
        If the direct item deletion fails, the method falls back to using the @core.delitem decorator, which deletes the item using core functions.

        Args:
            key (Union[str, int]): The key for the item in the Symbol value.

        Raises:
            KeyError: If the key or index is not found in the Symbol value.
        '''
        from ..post_processors import ASTPostProcessor

        if not isinstance(self.value, (str, dict, list)):
            CustomUserWarning(f'Setting item is not supported for {type(self.value)}. Supported types are str, dict, and list.', raise_with=TypeError)

        if not self.__semantic__:
            try:
                del self.value[key]
                return
            except Exception:
                CustomUserWarning(f'Key {key} not found in {self.value}', raise_with=Exception)

        @core.delitem()
        def _func(_, index: str):
            pass

        result = _func(self, key)
        try:
            self._value = ASTPostProcessor()(result) # The type of the object that the model changed was a list or a dict
        except json.JSONDecodeError:
            self._value = result # It was a string, or something failed (because } wasn't close, etc)

#@TODO: Add tests for this class
class ValueHandlingPrimitives(Primitive):
    '''
    This mixin includes functions responsible for handling symbol values - tokenization, type retrieval, value casting, indexing, etc.
    Future functions might include different methods of processing or manipulating the values of symbols, working with metadata of values, etc.
    '''
    @property
    def size(self) -> int:
        '''
        Get the size of the container of the Symbol's value.

        Returns:
            int: The size of the container of the Symbol's value.
        '''
        return len(self.value)

    @property
    def tokens(self) -> int:
        '''
        Tokenize the Symbol's value using the tokenizer method.
        The tokenizer method is bound to the 'neurosymbolic' engine using the @decorator.bind() decorator.

        Returns:
            int: The tokenized value of the Symbol.
        '''
        return self.tokenizer().encode(str(self))

    @core_ext.bind(engine='neurosymbolic', property='tokenizer')
    def tokenizer(self) -> Callable:
        '''
        The tokenizer method.
        This method is bound to the 'neurosymbolic' engine using the @decorator.bind() decorator.

        Returns:
            Callable: The tokenizer.
        '''
        pass

    @property
    def type(self):
        '''
        Get the type of the Symbol.

        Returns:
            type: The type of the Symbol.
        '''
        return type(self)

    @property
    def value_type(self):
        '''
        Get the type of the Symbol's value.

        Returns:
            type: The type of the Symbol's value.
        '''
        return type(self.value)

    def index(self, item: str, **kwargs) -> 'Symbol':
        '''
        Returns the index of a specified item in the symbol value.
        Uses the core.getitem decorator to create a _func method that finds the index of the item.

        Args:
            item (str): The item to find the index of within the symbol value.

        Returns:
            Symbol: A new symbol with the index of the specified item.
        '''
        @core.getitem(**kwargs)
        def _func(_, item: str) -> int:
            pass
        return self._to_type(_func(self, item))


class StringHelperPrimitives(Primitive):
    '''
    This mixin contains functions that provide additional help for symbols or their values.
    '''
    def split(self, delimiter: str, **kwargs) -> 'Symbol':
        '''
        Splits the symbol value by a specified delimiter.
        Uses the core.split decorator to create a _func method that splits the symbol value by the specified delimiter.

        Args:
            delimiter (str): The delimiter to split the symbol value by.

        Returns:
            Symbol: A new symbol with the split value.
        '''
        assert isinstance(delimiter, str), f'delimiter must be a string, got {type(delimiter)}'
        assert isinstance(self.value, str), f'self.value must be a string, got {type(self.value)}'
        return self._to_type([*self.value.split(delimiter)])

    def join(self, delimiter: str = ' ', **kwargs) -> 'Symbol':
        '''
        Joins the symbol value with a specified delimiter.

        Args:
            delimiter (str, optional): The delimiter to join the symbol value with. Defaults to ' '.

        Returns:
            Symbol: A new symbol with the joined str value.
        '''
        assert isinstance(delimiter, str),f'delimiter must be a string, got {type(delimiter)}'
        assert isinstance(self.value, Iterable), f'value must be an iterable, got {type(self.value)}'
        return self._to_type(delimiter.join(self.value))

    def startswith(self, prefix: str, **kwargs) -> bool:
        '''
        Checks if the symbol value starts with a specified prefix.
        Uses the core.startswith decorator to create a _func method that checks if the symbol value starts with the specified prefix.

        Args:
            prefix (str): The prefix to check if the symbol value starts with.

        Returns:
            bool: True if the symbol value starts with the specified prefix, otherwise False.
        '''
        assert isinstance(prefix, str),  f'prefix must be a string, got {type(prefix)}'
        assert isinstance(self.value, str), f'self.value must be a string, got {type(self.value)}'

        if not self.__semantic__:
            return self.value.startswith(prefix)

        @core.startswith()
        def _func(_, prefix: str) -> bool:
            pass

        return _func(self, prefix)

    def endswith(self, suffix: str, **kwargs) -> bool:
        '''
        Checks if the symbol value ends with a specified suffix.
        Uses the core.endswith decorator to create a _func method that checks if the symbol value ends with the specified suffix.

        Args:
            suffix (str): The suffix to check if the symbol value ends with.

        Returns:
            bool: True if the symbol value ends with the specified suffix, otherwise False.
        '''
        assert isinstance(suffix, str),  f'suffix must be a string, got {type(suffix)}'
        assert isinstance(self.value, str), f'self.value must be a string, got {type(self.value)}'

        if not self.__semantic__:
            return self.value.endswith(suffix)

        @core.endswith()
        def _func(_, suffix: str) -> bool:
            pass

        return _func(self, suffix)


class ComparisonPrimitives(Primitive):
    '''
    This mixin is dedicated to functions that perform more complex comparison operations between symbols or symbol values.
    This usually involves additional context, which the builtin overrode (e.g. __eq__) functions lack.
    '''
    def equals(self, string: str, context: str = 'contextually', **kwargs) -> 'Symbol':
        '''
        Checks if the symbol value is equal to another string.
        Uses the core.equals decorator to create a _func method that checks for equality in a specific context.

        Args:
            string (str): The string to compare with the symbol value.
            context (str, optional): The context in which to compare the strings. Defaults to 'contextually'.

        Returns:
            Symbol: A new symbol indicating whether the two strings are equal or not.
        '''
        @core.equals(context=context, **kwargs)
        def _func(_, string: str) -> bool:
            pass

        return self._to_type(_func(self, string))

    def contains(self, element: Any, **kwargs) -> bool:
        '''
        Uses the @core.contains decorator, checks whether the symbol's value contains the element.

        Args:
            element (Any): The element to be checked for containment.
            **kwargs: Additional keyword arguments to pass to the core.contains decorator.

        Returns:
            bool: True if the symbol's value contains the element, False otherwise.
        '''
        @core.contains(**kwargs)
        def _func(_, other) -> bool:
            pass

        return _func(self, element)

    def isinstanceof(self, query: str, **kwargs) -> bool:
        '''
        Check if the current Symbol is an instance of a specific type.

        Args:
            query (str): The type to check if the Symbol is an instance of.
            **kwargs: Any additional kwargs for @core.isinstanceof() decorator.

        Returns:
            bool: True if the current Symbol is an instance of the specified type, otherwise False.
        '''
        @core.isinstanceof()
        def _func(_, query: str, **kwargs) -> bool:
            pass

        return _func(self, query, **kwargs)


class ExpressionHandlingPrimitives(Primitive):
    '''
    This mixin consists of functions that handle symbolic expressions - evaluations, parsing, computation and more.
    Future functionalities in this mixin might include operations to manipulate expressions, more complex evaluation techniques, etc.
    '''
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def init_results(self):
        """Ensures _accumulated_results exists, initializing if needed."""
        if not hasattr(self, '_accumulated_results'):
            self._accumulated_results = []

    def get_results(self) -> List['Symbol']:
        '''
        Retrieves accumulated results from previous interpretations.

        Returns:
            List[Symbol]: List of accumulated results
        '''
        self.init_results()
        return self._accumulated_results

    def clear_results(self):
        '''Clears the accumulated results'''
        self.init_results()
        self._accumulated_results = []

    def interpret(self, prompt: Optional[str] = "Evaluate the symbolic expressions and return only the result:\n", accumulate: bool = False, **kwargs) -> 'Symbol':
        '''
        Evaluates simple symbolic expressions.
        Uses the core.expression decorator to create a _func method that evaluates the given expression.

        Args:
            prompt (Optional[str]): The prompt to evaluate. Defaults to the symbol value.
            accumulate (bool): If True, stores results for later retrieval. Defaults to False.
            **kwargs: Additional keyword arguments for the core.interpret decorator.

        Returns:
            Symbol: A new symbol with the result of the expression evaluation.
        '''
        # Propagate original input
        input_value = getattr(self, '_input', self) if hasattr(self, '_input') else self

        @core.interpret(prompt=prompt, **kwargs)
        def _func(_):
            pass

        result = _func(self)
        result = self._to_type(result)

        if accumulate:
            input_value.init_results()
            input_value._accumulated_results.append(result.value)

        result._input = input_value
        return result


#@TODO: add tests
class ValidationHandlingPrimitives(Primitive):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def print_verbose(self, msg):
        if self.verbose:
            print(msg)

    def prepare_seeds(self, num_seeds: int, **kwargs) -> list[int]:
        seed = kwargs.get("seed") or getattr(self, "seed", 42)
        rng = np.random.default_rng(seed)
        return rng.integers(0, np.iinfo(np.int16).max, size=num_seeds, dtype=np.int16).tolist()

    def simplify_validation_errors(self, error: ValidationError) -> str:
        return "\n".join(
            f"Field '{' -> '.join(str(loc) for loc in err['loc'])}': {err['msg']}. "
            f"Expected type: {err.get('type', 'unknown')}. "
            f"Provided value: {err.get('ctx', {}).get('given', 'unknown')}."
            for err in error.errors()
        )

    def validate_json(self, result: 'Symbol', data_model: "LLMDataModel", retry_count: int,
                     accumulate: bool = False, prompt: Optional[str] = None, **kwargs) -> 'Symbol':
        remedy_seeds = self.prepare_seeds(retry_count, **kwargs)
        json_validation_count = 0

        static_context = """
        [Task]
        You are tasked with fixing a string that is intended to be in **JSON format** but contains errors.
        Your goal is to correct the errors and ensure the JSON string is valid according to a given JSON schema.
        Follow these rules:

        1. Parse the provided string and use the list of validation errors to identify what needs to be fixed.
        2. Correct the identified errors to produce a properly formatted JSON string.
        3. Ensure the corrected JSON complies fully with the provided JSON schema.
        4. Preserve all original keys and values as much as possible. Only modify keys or values if they do not comply with the schema.
        5. Only modify the structure or values if necessary to meet the schema's requirements.
        6. Return the corrected JSON string as the output.

        [Requirements]
        - The output must be a valid, well-formatted JSON string.
        - Do not introduce new data or alter the intent of the original content unless required for schema compliance.
        - Ensure all changes are minimal and strictly necessary to fix the listed errors.
        """

        if prompt:
            result._value = prompt

        self.print_verbose(f"Starting validation process with {retry_count} maximum retries...")

        last_error = ""
        for i in range(retry_count):
            # Convert dictionary to JSON string if needed
            if isinstance(result.value, dict):
                result._value = json.dumps(result.value)
            elif isinstance(result.value, data_model):
                result._value = result.value.model_dump_json()

            # Clean the input string by removing invisible characters and whitespace
            if isinstance(result.value, str):
                result._value = result.value.strip()
                # Remove any non-printable characters except for whitespace
                result._value = ''.join(char for char in result.value
                                      if char.isprintable() or char.isspace())
                # Remove any "json" prefix that might appear
                if result._value.lower().startswith('json'):
                    result._value = result._value[4:].lstrip()

            json_validation_count += 1
            self.print_verbose(f"\nAttempt {json_validation_count}:")
            self.print_verbose(f"Input type: {type(result.value)}")
            self.print_verbose(f"Input value: {result.value}")

            try:
                final_result = data_model.model_validate_json(result.value, strict=True)
                result_symbol = self._to_type(final_result)
                result_symbol.data_model = data_model
                result_symbol.json_validation_count = json_validation_count
                result_symbol._input = self.input_value

                if accumulate:
                    self.input_value._accumulated_results.append(result_symbol.value)
                self.print_verbose(f"✓ Validation successful on attempt {json_validation_count}")

                return result_symbol

            except ValidationError as e:
                error_str = self.simplify_validation_errors(e)
                self.print_verbose(f"Validation errors:\n{error_str}")
                self.print_verbose("Attempting to fix validation errors...\n")

                remedy_prompt = (
                    f"[Original Input]\n```json\n{result.value}\n```\n"
                    f"[Validation Errors]\n{error_str}\n"
                    f"[JSON Schema]\n{data_model.model_json_schema()}\n"
                )

                kwargs.update({
                    'static_context': static_context,
                    'seed': remedy_seeds[i]
                })

                # Run interpret with its own metadata tracking
                result = self.interpret(remedy_prompt, accumulate=False, **kwargs)
                last_error = error_str

                if i < retry_count - 1:
                    self.print_verbose("Attempting to fix validation errors...\n")

        error_msg = f"Failed to retrieve valid JSON: {last_error}"
        self.print_verbose(f"\n✗ Validation failed after {json_validation_count} attempts")
        raise Exception(error_msg)

    def validate(self, prompt: Optional[str] = None, data_model: "LLMDataModel" = None,
                retry_count: int = 5, accumulate: bool = False,
                verbose: bool = False, **kwargs) -> 'Symbol':
        """
        Validates a Symbol against a JSON schema, retrying with interpretation if needed.

        Args:
            data_model (LLMDataModel): The Pydantic model to validate against.
            retry_count (int): Number of retry attempts. Defaults to 5.
            accumulate (bool): Whether to accumulate results.
            verbose (bool): Whether to print detailed validation progress.
            **kwargs: Additional keyword arguments for interpretation.

        Returns:
            Symbol: The validated Symbol
        """
        self.verbose = verbose
        self.input_value = getattr(self, '_input', self) if hasattr(self, '_input') else self

        if accumulate:
            self.input_value.init_results()

        if data_model is None:
            raise ValueError("data_model parameter is required for validation")

        kwargs["response_format"] = {"type": "json_object"}

        return self.validate_json(self, data_model, retry_count, accumulate, prompt, **kwargs)


#@TODO: add tests
class ConstraintHandlingPrimitives(Primitive):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def check_constraints(self, result: Union["LLMDataModel", str], constraints: Union[List[Union["LengthConstraint", "CustomConstraint"]], "LengthConstraint", "CustomConstraint"]):
        constraint_violations = []
        if not isinstance(constraints, list):
            constraints = [constraints]

        for constraint in constraints:
            if isinstance(constraint, LengthConstraint):
                violations = self._check_length_constraint(result, constraint)
                constraint_violations.extend(violations)
            elif isinstance(constraint, CustomConstraint):
                violations = self._check_custom_constraint(result, constraint)
                constraint_violations.extend(violations)

        return constraint_violations

    def _check_custom_constraint(self, result: Union["LLMDataModel", str], constraint: "CustomConstraint") -> List[str]:
        violations = []
        content = result if isinstance(result, str) else result.model_dump_json()

        # Create a validation prompt
        validation_prompt = f"""
        Validate if the following content meets this rule: "{constraint.rule}"

        Content:
        {content}

        Respond with only "PASS" if the content meets the rule, or provide a specific explanation of why it fails.
        """

        validation_result = self.interpret(validation_prompt, temperature=0)
        if "PASS" not in validation_result.value.upper():
            violations.append(f"Custom constraint violation: {constraint.rule} - {validation_result.value}")
            self.print_verbose(f"Failed custom constraint: {constraint.rule}")
        else:
            self.print_verbose(f"[PASS] Content passed custom constraint: {constraint.rule}")

        return violations

    def _check_length_constraint(self, result: Union["LLMDataModel", str], constraint: "LengthConstraint") -> List[str]:
        constraint_violations = []
        if not isinstance(constraint, list):
            constraint = [constraint]

        # Handle plain string input
        if isinstance(result, str):
            for c in constraint:
                if not (c.min_length <= len(result) <= c.max_length):
                    self.print_verbose(
                        f"Text must have between {c.min_length} and {c.max_length} characters, has {len(result)}"
                    )
                    remedy_str = [
                        f"The text must have between {c.min_length} and {c.max_length} characters, but has {len(result)}."
                    ]
                    if len(result) < c.min_length:
                        remedy_str.append(
                            f"Increase the length by at least {c.min_length - len(result)} characters."
                        )
                    elif len(result) > c.max_length:
                        remedy_str.append(
                            f"Decrease the length by at least {len(result) - c.max_length} characters."
                        )
                    constraint_violations.append(" ".join(remedy_str))
                else:
                    self.print_verbose(
                        f"[PASS] Text passed length validation: {len(result)} ({c.min_length} - {c.max_length})"
                    )
        # Handle structured data model
        else:
            # Convert Pydantic model to dict if needed
            result_dict = result.model_dump() if hasattr(result, 'model_dump') else result

            for constraint in constraint:
                # Check if this is an items constraint
                is_items_constraint = constraint.field_name.endswith('.items')
                field_name = constraint.field_name[:-6] if is_items_constraint else constraint.field_name

                # Direct dictionary access for Pydantic models
                if field_name in result_dict:
                    field_value = result_dict[field_name]
                    if isinstance(field_value, str):
                        if not constraint.min_length <= len(field_value) <= constraint.max_length:
                            self.print_verbose(
                                f"Field {field_name} must have between {constraint.min_length} and {constraint.max_length} characters, has {len(field_value)}"
                            )
                            remedy_str = [
                                f"The field {field_name} must have between {constraint.min_length} and {constraint.max_length} characters, but has {len(field_value)}."
                            ]
                            if len(field_value) < constraint.min_length:
                                remedy_str.append(
                                    f"Increase the length of {field_name} by at least {constraint.min_length - len(field_value)} characters."
                                )
                            elif len(field_value) > constraint.max_length:
                                remedy_str.append(
                                    f"Decrease the length of {field_name} by at least {len(field_value) - constraint.max_length} characters."
                                )
                            constraint_violations.append(" ".join(remedy_str))
                        else:
                            self.print_verbose(
                                f"[PASS] Field {field_name} passed length validation: {len(field_value)} ({constraint.min_length} - {constraint.max_length})"
                            )
                    else:
                        field_values = field_value if isinstance(field_value, list) else [field_value]
                        # Handle list fields
                        if is_items_constraint:
                            # Validate each item's string length
                            for idx, item in enumerate(field_values):
                                if not constraint.min_length <= len(str(item)) <= constraint.max_length:
                                    self.print_verbose(
                                        f"Item {idx} in list field {field_name} must have between {constraint.min_length} and {constraint.max_length} characters, has {len(str(item))}"
                                    )
                                    remedy_str = [
                                        f"Item {idx} in list field {field_name} must have between {constraint.min_length} and {constraint.max_length} characters, but has {len(str(item))}."
                                    ]
                                    if len(str(item)) < constraint.min_length:
                                        remedy_str.append(
                                            f"Increase the length of item {idx} by at least {constraint.min_length - len(str(item))} characters."
                                        )
                                    elif len(str(item)) > constraint.max_length:
                                        remedy_str.append(
                                            f"Decrease the length of item {idx} by at least {len(str(item)) - constraint.max_length} characters."
                                        )
                                    constraint_violations.append(" ".join(remedy_str))
                                else:
                                    self.print_verbose(
                                        f"[PASS] Item {idx} in list field {field_name} passed length validation: {len(str(item))} ({constraint.min_length} - {constraint.max_length})"
                                    )
                        else:
                            # Regular list length validation
                            list_length = len(field_values)
                            if not constraint.min_length <= list_length <= constraint.max_length:
                                self.print_verbose(
                                    f"List field {field_name} must have between {constraint.min_length} and {constraint.max_length} items, has {list_length}"
                                )
                                remedy_str = [
                                    f"The list field {field_name} must have between {constraint.min_length} and {constraint.max_length} items, but has {list_length}."
                                ]
                                if list_length < constraint.min_length:
                                    remedy_str.append(
                                        f"Add at least {constraint.min_length - list_length} more items to {field_name}."
                                    )
                                elif list_length > constraint.max_length:
                                    remedy_str.append(
                                        f"Remove at least {list_length - constraint.max_length} items from {field_name}."
                                    )
                                constraint_violations.append(" ".join(remedy_str))
                            else:
                                self.print_verbose(
                                    f"[PASS] List field {field_name} passed length validation: {list_length} items ({constraint.min_length} - {constraint.max_length})"
                                )
                else:
                    raise ValueError(f"Field {field_name} not found in model")

        return constraint_violations

    def wrap_task(self, task: str, result: str, violations: List[str], all_constraints: List[Union["LengthConstraint", "CustomConstraint"]]):
        def format_constraint_description(constraint):
            if isinstance(constraint, LengthConstraint):
                field_desc = f"field '{constraint.field_name}'" if hasattr(constraint, 'field_name') and constraint.field_name else "text"
                return f"The {field_desc} must have between {constraint.min_length} and {constraint.max_length} characters."
            elif isinstance(constraint, CustomConstraint):
                return f"The content must satisfy this rule: \"{constraint.rule}\""
            return str(constraint)

        wrapped_task = [
            "Your task was the following: \n\n" + task + "\n",
            "Your output was the following: \n\n" + result + "\n",
            "You must adhere to ALL of the following constraints:",
        ]

        # Add all constraints first
        for constraint in all_constraints:
            wrapped_task.append("- " + format_constraint_description(constraint))

        # Then add specific violations
        if violations:
            wrapped_task.append("\nThe following constraints were violated:")
            for constraint_violation in violations:
                wrapped_task.append("- " + constraint_violation)
        else:
            wrapped_task.append("\nNo constraints were violated, but you must continue to adhere to all constraints.")

        wrapped_task.append(
            "\nFollow the original task and make sure to adhere to ALL constraints listed above."
        )
        return "\n".join(wrapped_task)

    @classmethod
    def _get(cls, obj, path: str):
        value = obj
        for i, key in enumerate(path.split(".")):
            if isinstance(value, list):
                try:
                    index = int(key)
                    if index < len(value):
                        value = value[index]
                    else:
                        raise ValueError(f"Index {index} out of range in {value}")
                except:
                    values = []
                    for val in value:
                        leaf = cls.get(
                            val, ".".join(path.split(".")[i:])
                        )
                        values.extend(leaf)
                    return values
            # Add handling for Pydantic models
            elif hasattr(value, "model_dump"):
                model_dict = value.model_dump()
                if key in model_dict:
                    value = model_dict[key]
                else:
                    raise ValueError(f"Key {key} not found in {value}")
            elif isinstance(value, dict):
                if key in value:
                    value = value[key]
                else:
                    raise ValueError(f"Key {key} not found in {value}")
            else:
                if hasattr(value, key):
                    value = getattr(value, key)
                else:
                    raise ValueError(f"Key {key} not found in {value}")

        if not isinstance(value, list):
            value = [value]
        return value

    def length_constraint(self, result: 'Symbol',
                          constraints: Union[List[Union["LengthConstraint", "CustomConstraint"]], "LengthConstraint", "CustomConstraint"],
                          retry_count: int = 5, accumulate: bool = False,
                          prompt: Optional[str] = None, *args, **kwargs):

        remedy_seeds = self.prepare_seeds(retry_count, **kwargs)
        constraint_count = 0

        if prompt:
            result._value = prompt

        original_task = self.input_value.value
        last_violation = []

        # Ensure constraints is a list
        all_constraints = constraints if isinstance(constraints, list) else [constraints]

        self.print_verbose(f"Starting constraint process with {retry_count} maximum retries...")

        for i in range(retry_count):
            constraint_count += 1
            self.print_verbose(f"\nAttempt {constraint_count}:")
            self.print_verbose(f"Input type: {type(result.value)}")
            self.print_verbose(f"Input value: {result.value}")

            constraint_violations = self.check_constraints(result.value, all_constraints)
            if len(constraint_violations) > 0:
                self.print_verbose(f"Constraint violations:\n{constraint_violations}")
                self.print_verbose("Attempting to fix constraint violations...\n")

                remedy_task = self.wrap_task(
                    original_task if isinstance(original_task, str) else original_task.model_dump_json(),
                    result.value if isinstance(result.value, str) else result.value.model_dump_json(),
                    constraint_violations,
                    all_constraints  # Pass all constraints
                )
                kwargs.update({'seed': remedy_seeds[i]})

                # Store the original type
                original_type = type(result.value)
                result = self.interpret(remedy_task, accumulate=False, **kwargs)

                # Convert back to original type if needed
                if hasattr(original_type, 'model_validate_json') and isinstance(result.value, str):
                    try:
                        result._value = original_type.model_validate_json(result.value)
                    except ValidationError as e:
                        self.print_verbose(f"Failed to convert back to original type: {e}")
                        raise

                last_violation = constraint_violations

                if i < retry_count - 1:
                    self.print_verbose("Attempting to fix constraint violations...\n")
            else:
                result_symbol = result
                result_symbol.constraint_count = constraint_count
                result_symbol._input = self.input_value

                if accumulate:
                    self.input_value._accumulated_results.append(result_symbol.value)
                self.print_verbose(f"✓ Constraint validation successful on attempt {constraint_count}")

                return result_symbol

        error_msg = f"Failed to enforce constraints: {' | '.join(last_violation)}"
        self.print_verbose(f"\n✗ Constraint validation failed after {constraint_count} attempts")
        raise Exception(error_msg)

    def constrain(self, constraints: Union[List[Union["LengthConstraint", "CustomConstraint"]], "LengthConstraint", "CustomConstraint"],
                  retry_count: int = 5, accumulate: bool = False,
                  verbose: bool = False, *args, **kwargs) -> 'Symbol':
        """
        Constrains a Symbol according to specified constraints, retrying with interpretation if needed.

        Args:
            constraints: Length or custom constraints to enforce.
            retry_count (int): Number of retry attempts. Defaults to 5.
            accumulate (bool): Whether to accumulate results.
            verbose (bool): Whether to print detailed constraint validation progress.
            **kwargs: Additional keyword arguments for interpretation.

        Returns:
            Symbol: The constrained Symbol
        """
        self.verbose = verbose
        self.input_value = getattr(self, '_input', self) if hasattr(self, '_input') else self

        if accumulate:
            self.input_value.init_results()

        result = self.length_constraint(self, constraints, retry_count, accumulate, *args, **kwargs)
        return result


class DataHandlingPrimitives(Primitive):
    '''
    This mixin houses functions that clean, summarize and outline symbols or their values.
    Future implementations in this mixin may include various other cleaning and summarization techniques, error detection/correction in symbols, complex filtering, bulk modifications, or other types of condition-based manipulations on symbols, etc.
    '''
    def clean(self, **kwargs) -> 'Symbol':
        '''
        Cleans the symbol value.
        Uses the core.clean decorator to create a _func method that cleans the symbol value.

        Returns:
            Symbol: A new symbol with the cleaned value.
        '''
        @core.clean(**kwargs)
        def _func(_) -> str:
            pass

        return self._to_type(_func(self))

    def summarize(self, context: Optional[str] = None, **kwargs) -> 'Symbol':
        '''
        Summarizes the symbol value.
        Uses the core.summarize decorator with an optional context to create a _func method that summarizes the symbol value.

        Args:
            context (Optional[str]): The context to be used for summarization. Defaults to None.

        Returns:
            Symbol: A new symbol with the summarized value.
        '''
        @core.summarize(context=context, **kwargs)
        def _func(_) -> str:
            pass

        return self._to_type(_func(self))

    def outline(self, **kwargs) -> 'Symbol':
        '''
        Creates an outline of the symbol value.
        Uses the core.outline decorator to create a _func method that generates an outline of the symbol value.

        Returns:
            Symbol: A new symbol with the outline of the value.
        '''
        @core.outline(**kwargs)
        def _func(_) -> str:
            pass

        return self._to_type(_func(self))

    def filter(self, criteria: str, include: Optional[bool] = False, **kwargs) -> 'Symbol':
        '''
        Filters the symbol value based on a specified criteria.
        Uses the core.filtering decorator with the provided criteria and include flag to create a _func method to filter the symbol value.

        Args:
            criteria (str): The criteria to filter the symbol value by.
            include (Optional[bool]): Whether to include or exclude items based on the criteria. Defaults to False.

        Returns:
            Symbol: A new symbol with the filtered value.
        '''
        @core.filtering(criteria=criteria, include=include, **kwargs)
        def _func(_) -> str:
            pass

        return self._to_type(_func(self))

    def map(self, instruction: str, **kwargs) -> 'Symbol':
        '''
        Applies a semantic transformation instruction to each element in an iterable.
        This method transforms each element based on the provided instruction while preserving
        elements that don't match the transformation criteria.

        Args:
            instruction (str): The semantic instruction to apply to each element
            **kwargs: Additional keyword arguments for the transformation

        Returns:
            Symbol: A Symbol object containing the transformed elements

        Raises:
            AssertionError: If the Symbol's value is not iterable or is an unsupported type
        '''
        try:
            iter(self.value)
        except TypeError:
            CustomUserWarning('Map can only be applied to iterable objects', raise_with=AssertionError)

        @core.map(instruction=instruction, **kwargs)
        def _func(_):
            pass

        return self._to_type(_func(self))

    def modify(self, changes: str, **kwargs) -> 'Symbol':
        '''
        Modifies the symbol value based on the specified changes.
        Uses the core.modify decorator with the provided changes to create a _func method to modify the symbol value.

        Args:
            changes (str): The changes to apply to the symbol value.

        Returns:
            Symbol: A new symbol with the modified value.
        '''
        @core.modify(changes=changes, **kwargs)
        def _func(_) -> str:
            pass

        return self._to_type(_func(self))

    def replace(self, old: str, new: str, **kwargs) -> 'Symbol':
        '''
        Replaces one value in the symbol value with another.
        Uses the core.replace decorator to create a _func method that replaces the values in the symbol value.

        Args:
            old (str): The value to be replaced in the symbol value.
            new (str): The value to replace the existing value with.

        Returns:
            Symbol: A new symbol with the replaced value.
        '''
        @core.replace(**kwargs)
        def _func(_, old: str, new: str):
            pass

        return self._to_type(_func(self, old, new))

    def remove(self, information: str, **kwargs) -> 'Symbol':
        '''
        Removes a specified piece of information from the symbol value.
        Uses the core.replace decorator to create a _func method that removes the specified information.

        Args:
            information (str): The information to remove from the symbol value.

        Returns:
            Symbol: A new symbol with the removed information.
        '''
        @core.replace(**kwargs)
        def _func(_, text: str, replace: str, value: str):
            pass

        return self._to_type(_func(self, information, ''))

    def include(self, information: str, **kwargs) -> 'Symbol':
        '''
        Includes a specified piece of information in the symbol value.
        Uses the core.include decorator to create a _func method that includes the specified information.

        Args:
            information (str): The information to include in the symbol value.

        Returns:
            Symbol: A new symbol with the included information.
        '''
        @core.include(**kwargs)
        def _func(_, information: str):
            pass

        return self._to_type(_func(self, information))

    def combine(self, information: str, **kwargs) -> 'Symbol':
        '''
        Combines the current symbol value with another string.
        Uses the core.combine decorator to create a _func method that combines the symbol value with another string.

        Args:
            information (str): The information to combine with the symbol value.

        Returns:
            Symbol: A new symbol with the combined value.
        '''
        @core.combine(**kwargs)
        def _func(_, a: str, b: str):
            pass

        return self._to_type(_func(self, information))


class UniquenessPrimitives(Primitive):
    '''
    This mixin includes functions that work with unique aspects of symbol values, like extracting unique information or composing new unique symbols.
    Future functionalities might include finding duplicate information, defining levels of uniqueness, etc.
    '''
    def unique(self, keys: Optional[List[str]] = [], **kwargs) -> 'Symbol':
        '''
        Extracts unique information from the symbol value, using provided keys.
        Uses the core.unique decorator with a list of keys to create a _func method that extracts unique data from the symbol value.

        Args:
            keys (Optional[List[str]]): The list of keys to extract unique data. Defaults to [].

        Returns:
            Symbol: A new symbol with the unique information.
        '''
        @core.unique(keys=keys, **kwargs)
        def _func(_) -> str:
            pass

        return self._to_type(_func(self))

    def compose(self, **kwargs) -> 'Symbol':
        '''
        Composes a text based on the symbol value.
        Uses the core.compose decorator to create a _func method that composes a text using the symbol value.

        Returns:
            Symbol: A new symbol with the composed text.
        '''
        @core.compose(**kwargs)
        def _func(_) -> str:
            pass

        return self._to_type(_func(self))


class PatternMatchingPrimitives(Primitive):
    '''
    This mixin houses functions that deal with ranking symbols, extracting details based on patterns, and correcting symbols.
    It will house future functionalities that involve sorting, complex pattern detections, advanced correction techniques etc.
    '''
    def rank(self, measure: Optional[str] = 'alphanumeric', order: Optional[str] = 'desc', **kwargs) -> 'Symbol':
        '''
        Ranks the symbol value based on a measure and a sort order.
        Uses the core.rank decorator with the specified measure and order to create a _func method that ranks the symbol value.

        Args:
            measure (Optional[str]): The measure to rank the symbol value by. Defaults to 'alphanumeric'.
            order (Optional[str]): The sort order for ranking. Defaults to 'desc'.
            **kwargs: Additional keyword arguments to pass to the core.rank decorator.

        Returns:
            Symbol: A new symbol with the ranked value.
        '''
        @core.rank(order=order, **kwargs)
        def _func(_, measure: str) -> str:
            pass

        return self._to_type(_func(self, measure))

    def extract(self, pattern: str, **kwargs) -> 'Symbol':
        '''
        Extracts data from the symbol value based on a pattern.
        Uses the core.extract decorator with the specified pattern to create a _func method that extracts data from the symbol value.

        Args:
            pattern (str): The pattern to use for data extraction.

        Returns:
            Symbol: A new symbol with the extracted data.
        '''
        @core.extract(**kwargs)
        def _func(_, pattern: str) -> str:
            pass

        return self._to_type(_func(self, pattern))

    def correct(self, context: str, exception: Exception, **kwargs) -> 'Symbol':
        '''
        Corrects the symbol value based on a specified context.
        Uses the @core.correct decorator, corrects the value of the symbol based on the given context.

        Args:
            context (str): The context used to correct the value of the symbol.
            exception (Exception): The exception that occurred during processing, which provides context for the correction.
            **kwargs: Additional keyword arguments to pass to the core.correct decorator.

        Returns:
            Symbol: The corrected value as a Symbol.
        '''
        @core.correct(context=context, exception=exception, **kwargs)
        def _func(_) -> str:
            pass

        return self._to_type(_func(self))

    def translate(self, language: Optional[str] = 'English', **kwargs) -> 'Symbol':
        '''
        Translates the symbol value to the specified language.
        Uses the @core.translate decorator to translate the symbol's value to the specified language.

        Args:
            language (Optional[str]): The language to translate the value to. Defaults to 'English'.
            **kwargs: Additional keyword arguments to pass to the core.translate decorator.

        Returns:
            Symbol: The translated value as a Symbol.
        '''
        @core.translate(language=language, **kwargs)
        def _func(_) -> str:
            pass

        return self._to_type(_func(self))

    def choice(self, cases: List[str], default: str, **kwargs) -> 'Symbol':
        '''
        Chooses one of the cases based on the symbol value.
        Uses the @core.case decorator, selects one of the cases based on the symbol's value.

        Args:
            cases (List[str]): The list of possible cases.
            default (str): The default case if none of the cases match the symbol's value.
            **kwargs: Additional keyword arguments to pass to the core.case decorator.

        Returns:
            Symbol: The chosen case as a Symbol.
        '''
        @core.case(enum=cases, default=default, **kwargs)
        def _func(_) -> str:
            pass

        return self._to_type(_func(self))


class QueryHandlingPrimitives(Primitive):
    '''
    This mixin helps in transforming, preparing, and executing queries, and it is designed to be extendable as new ways of handling queries are developed.
    Future methods could potentially include query optimization, enhanced query formatting, multi-level query execution, query error handling, etc.
    '''
    def query(self, context: str, prompt: Optional[str] = None, examples: Optional[List[Prompt]] = None, **kwargs) -> 'Symbol':
        '''
        Queries the symbol value based on a specified context.
        Uses the @core.query decorator, queries based on the context, prompt, and examples.

        Args:
            context (str): The context used for the query.
            prompt (Optional[str]): The prompt for the query. Defaults to None.
            examples (Optional[List[Prompt]]): The examples for the query. Defaults to None.
            **kwargs: Additional keyword arguments to pass to the core.query decorator.

        Returns:
            Symbol: The result of the query as a Symbol.
        '''
        @core.query(context=context, prompt=prompt, examples=examples, **kwargs)
        def _func(_) -> str:
            pass

        return self._to_type(_func(self))

    def convert(self, format: str, **kwargs) -> 'Symbol':
        '''
        Converts the symbol value to the specified format.
        Uses the @core.convert decorator, converts the symbol's value to the specified format.

        Args:
            format (str): The format to convert the value to.
            **kwargs: Additional keyword arguments to pass to the core.convert decorator.

        Returns:
            Symbol: The converted value as a Symbol.
        '''
        @core.convert(format=format, **kwargs)
        def _func(_) -> str:
            pass

        return self._to_type(_func(self))

    def transcribe(self, modify: str, **kwargs) -> 'Symbol':
        '''
        Transcribes the symbol value based on a specified modification.
        Uses the @core.transcribe decorator, modifies the symbol's value based on the modify parameter.

        Args:
            modify (str): The modification to be applied to the value.
            **kwargs: Additional keyword arguments to pass to the core.transcribe decorator.

        Returns:
            Symbol: The modified value as a Symbol.
        '''
        @core.transcribe(modify=modify, **kwargs)
        def _func(_) -> str:
            pass

        return self._to_type(_func(self))


class ExecutionControlPrimitives(Primitive):
    '''
    This mixin represents the core methods for dealing with symbol execution.
    Possible future methods could potentially include async execution, pipeline chaining, execution profiling, improved error handling, version management, embedding more complex execution control structures etc.
    '''
    def analyze(self, exception: Exception, query: Optional[str] = '', **kwargs) -> 'Symbol':
        '''Uses the @core.analyze decorator, analyzes an exception and returns a symbol.

        Args:
            exception (Exception): The exception to be analyzed.
            query (Optional[str]): An additional query to provide context during analysis. Defaults to ''.
            **kwargs: Additional keyword arguments to pass to the core.analyze decorator.

        Returns:
            Symbol: The analyzed result as a Symbol.
        '''
        @core.analyze(exception=exception, query=query, **kwargs)
        def _func(_) -> str:
            pass

        return self._to_type(_func(self))

    def execute(self, **kwargs) -> 'Symbol':
        '''
        Executes the symbol's expression using the @core.execute decorator.

        Args:
            **kwargs: Additional keyword arguments to pass to the core.execute decorator.

        Returns:
            Symbol: The result of the executed expression as a Symbol.
        '''
        @core.execute(**kwargs)
        def _func(_):
            pass

        return _func(self)

    def fexecute(self, **kwargs) -> 'Symbol':
        '''
        Executes the symbol's expression using the fallback execute method (ftry).

        Args:
            **kwargs: Additional keyword arguments to pass to the core.execute decorator.

        Returns:
            Symbol: The result of the executed expression as a Symbol.
        '''
        def _func(sym: 'Symbol', **kargs):
            return sym.execute(**kargs)

        return self.ftry(_func, **kwargs)

    def simulate(self, **kwargs) -> 'Symbol':
        '''
        Uses the @core.simulate decorator, simulates the value of the symbol. Used for hypothesis testing or code simulation.

        Args:
            **kwargs: Additional keyword arguments to pass to the core.simulate decorator.

        Returns:
            Symbol: The simulated value as a Symbol.
        '''
        @core.simulate(**kwargs)
        def _func(_):
            pass

        return self._to_type(_func(self))

    def sufficient(self, query: str, **kwargs) -> 'Symbol':
        '''
        Uses the @core.sufficient decorator and checks if the symbol's value is sufficient based on the query.

        Args:
            query (str): The query to verify if the symbol's value is sufficient.
            **kwargs: Additional keyword arguments to pass to the core.sufficient decorator.

        Returns:
            Symbol: The sufficiency result as a Symbol.
        '''
        @core.sufficient(query=query, **kwargs)
        def _func(_) -> bool:
            pass

        return self._to_type(_func(self))

    def list(self, condition: str, **kwargs) -> 'Symbol':  #@TODO: can't filter directly handle this case?
        '''
        Uses the @core.listing decorator and lists elements based on the condition.

        Args:
            condition (str): The condition to filter the elements in the list.
            **kwargs: Additional keyword arguments to pass to the core.listing decorator.

        Returns:
            Symbol: The filtered list as a Symbol.
        '''
        @core.listing(condition=condition, **kwargs)
        def _func(_) -> list:
            pass

        return self._to_type(_func(self))

    def foreach(self, condition: str, apply: str, **kwargs) -> 'Symbol':
        '''
        Uses the @core.foreach decorator, iterates through the symbol's value, and applies the provided functionality.

        Args:
            condition (str): The condition to filter the elements in the list.
            apply (str): The functionality to be applied to each element in the list.
            **kwargs: Additional keyword arguments to pass to the core.foreach decorator.

        Returns:
            Symbol: The result of the iterative application of the function as a Symbol.
        '''
        @core.foreach(condition=condition, apply=apply, **kwargs)
        def _func(_):
            pass

        return self._to_type(_func(self))

    def stream(self, expr: 'Expression', token_ratio: Optional[float] = 0.6, **kwargs) -> 'Symbol':
        '''
        Streams the Symbol's value through an Expression object.
        This method divides the Symbol's value into chunks and processes each chunk through the given Expression object.
        It is useful for processing large strings in smaller parts.

        Args:
            expr (Expression): The Expression object to evaluate the Symbol's chunks.
            token_ratio (Optional[float]): The ratio between input-output tokens for calculating max_chars. Defaults to 0.6.
            **kwargs: Additional keyword arguments for the given Expression.

        Returns:
            Symbol: A Symbol object containing the evaluated chunks.

        Raises:
            ValueError: If the Expression object exceeds the maximum allowed tokens.
        '''
        @core_ext.bind(engine='neurosymbolic', property='max_context_tokens')
        def _max_tokens(_): pass

        max_ctxt_tokens = int(_max_tokens(self) * token_ratio)
        prev = expr(self, preview=True, **kwargs)
        prev = str(prev)

        if len(prev) > _max_tokens(self):
            n_splits = (len(prev) // max_ctxt_tokens) + 1

            for i in range(n_splits):
                tokens_sliced = self.tokens[i * max_ctxt_tokens: (i + 1) * max_ctxt_tokens]
                r = self._to_type(self.tokenizer().decode(tokens_sliced))

                yield expr(r, **kwargs)

        else:
            yield expr(self, **kwargs)

    def ftry(self, expr: 'Expression', retries: Optional[int] = 1, **kwargs) -> 'Symbol':
        # TODO: find a way to pass on the constraints and behavior from the self.expr to the corrected code
        '''
        Tries to evaluate a Symbol using a given Expression.
        This method evaluates a Symbol using a given Expression.
        If it fails, it retries the evaluation a specified number of times.

        Args:
            expr (Expression): The Expression object to evaluate the Symbol.
            retries (Optional[int]): The number of retries if the evaluation fails. Defaults to 1.
            **kwargs: Additional keyword arguments for the given Expression.

        Returns:
            Symbol: A Symbol object with the evaluated result.

        Raises:
            Exception: If the evaluation fails after all retries.
        '''
        prompt = {'out_msg': ''}

        def output_handler(input_):
            prompt['out_msg'] = input_

        kwargs['output_handler'] = output_handler
        retry_cnt: int = 0
        code = self # original input

        if hasattr(expr, 'prompt'):
            prompt['prompt_instruction'] = expr.prompt

        sym = self # used for getting passed from one iteration to the next
        while True:
            try:
                sym = expr(sym, **kwargs) # run the expression
                retry_cnt = 0

                return sym

            except Exception as e:
                retry_cnt += 1
                if retry_cnt > retries:
                    raise e
                else:
                    # analyze the error
                    payload = f'[ORIGINAL_USER_PROMPT]\n{prompt["prompt_instruction"]}\n\n' if 'prompt_instruction' in prompt else ''
                    payload = payload + f'[ORIGINAL_USER_DATA]\n{code}\n\n[ORIGINAL_GENERATED_OUTPUT]\n{prompt["out_msg"]}'
                    probe   = sym.analyze(query="What is the issue in this expression?", payload=payload, exception=e)
                    # attempt to correct the error
                    payload = f'[ORIGINAL_USER_PROMPT]\n{prompt["prompt_instruction"]}\n\n' if 'prompt_instruction' in prompt else ''
                    payload = payload + f'[ANALYSIS]\n{probe}\n\n'
                    context = f'Try to correct the error of the original user request based on the analysis above: \n [GENERATED_OUTPUT]\n{prompt["out_msg"]}\n\n'
                    constraints = expr.constraints if hasattr(expr, 'constraints') else []

                    if hasattr(expr, 'post_processor'):
                        post_processor = expr.post_processor
                        sym = code.correct(
                            context=context,
                            exception=e,
                            payload=payload,
                            constraints=constraints,
                            post_processor=post_processor
                        )
                    else:
                        sym = code.correct(
                            context=context,
                            exception=e,
                            payload=payload,
                            constraints=constraints
                        )


class DictHandlingPrimitives(Primitive):
    '''
    This mixin hosts functions that deal with dictionary operations on symbol values.
    It can be extended in the future with more advanced dictionary methods and operations.
    '''
    def dict(self, context: str, **kwargs) -> 'Symbol':
        '''
        Maps related content together under a common abstract topic as a dictionary of the Symbol value.
        This method uses the @core.dictionary decorator to apply the given context to the Symbol.
        It is useful for applying additional context to the symbol.

        Args:
            context (str): The context to apply to the Symbol.
            **kwargs: Additional keyword arguments for the @core.dictionary decorator.

        Returns:
            Symbol: A Symbol object with a dictionary applied.
        '''
        @core.dictionary(context=context, **kwargs)
        def _func(_):
            pass

        return self._to_type(_func(self))


class TemplateStylingPrimitives(Primitive):
    '''
    This mixin includes functionalities for stylizing symbols and applying templates.
    Future functionalities might include a variety of new stylizing methods, application of more complex templates, etc.
    '''
    def template(that, template: str, placeholder: Optional[str] = '{{placeholder}}', **kwargs) -> 'Symbol':
        '''
        Applies a template to the Symbol.
        This method uses the @core.template decorator to apply the given template and placeholder to the Symbol.
        It is useful for providing structure to the Symbol's value.

        Args:
            template (str): The template to apply to the Symbol.
            placeholder (Optional[str]): The placeholder in the template to be replaced with the Symbol's value. Defaults to '{{placeholder}}'.
            **kwargs: Additional keyword arguments for the @core.template decorator.

        Returns:
            Symbol: A Symbol object with a template applied.
        '''
        def _func(self):
            res = template.replace(placeholder, str(self))
            return that._to_type(res)

        return _func(that)

    def style(self, description: str, libraries: Optional[List] = [], **kwargs) -> 'Symbol':
        '''
        Applies a style to the Symbol.
        This method uses the @core.style decorator to apply the given style description, libraries, and placeholder to the Symbol.
        It is useful for providing structure and style to the Symbol's value.

        Args:
            description (str): The description of the style to apply.
            libraries (Optional[List]): A list of libraries that may be included in the style. Defaults to an empty list.
            **kwargs: Additional keyword arguments for the @core.style decorator.

        Returns:
            Symbol: A Symbol object with the style applied.
        '''
        @core.style(description=description, libraries=libraries, **kwargs)
        def _func(_):
            pass

        return self._to_type(_func(self))


class DataClusteringPrimitives(Primitive):
    '''
    This mixin contains functionalities that deal with clustering symbol values or generating embeddings.
    New functionalities in this mixin might include different types of clustering and embedding methods, dimensionality reduction techniques, etc.
    '''
    def cluster(self, **kwargs) -> 'Symbol':
        '''
        Creates a cluster from the Symbol's value.
        This method uses the @core.cluster decorator to create a cluster from the Symbol's value.
        It is useful for grouping values in the Symbol.

        Args:
            **kwargs: Additional keyword arguments for the @core.cluster decorator.

        Returns:
            Symbol: A Symbol object with its value clustered.
        '''
        @core.cluster(entries=self.value, **kwargs)
        def _func(_, error=None, stack_trace=None):
            pass

        return self._to_type(_func(self))


class EmbeddingPrimitives(Primitive):
    '''
    This mixin contains functionalities that deal with embedding symbol values.
    New functionalities in this mixin might include different types of embedding methods, similarity and distance measures etc.
    '''
    def embed(self, **kwargs) -> 'Symbol':
        '''
        Generates embeddings for the Symbol's value.
        This method uses the @core.embed decorator to generate embeddings for the Symbol's value.
        If the value is not a list, it is converted to a list.

        Args:
            **kwargs: Additional keyword arguments for the @core.embed decorator.

        Returns:
            Symbol: A Symbol object with its value embedded.
        '''
        value = self.value
        if not isinstance(value, list):
            # must convert to list of str for embedding
            value = [str(value)]
        # ensure that all values are strings
        value = [str(v) for v in value]

        @core.embed(entries=value, **kwargs)
        def _func(_) -> list:
            pass

        return self._to_type(_func(self))

    @property
    def embedding(self) -> np.array:
        '''
        Get the embedding as a numpy array.

        Returns:
            Any: The embedding of the symbol.
        '''
        # if the embedding is not yet computed, compute it
        if self._metadata.embedding is None:
            if ((isinstance(self.value, list) or isinstance(self.value, tuple)) and all([type(x) == int or type(x) == float or type(x) == bool for x in self.value])) \
                or isinstance(self.value, np.ndarray):
                if isinstance(self.value, list) or isinstance(self.value, tuple):
                    assert len(self.value) > 0, 'Cannot compute embedding of empty list'
                    if isinstance(self.value[0], Symbol):
                        # convert each element to numpy array
                        self._metadata.embedding = np.asarray([x.embedding for x in self.value])
                    elif isinstance(self.value[0], str):
                        # embed each string
                        self._metadata.embedding = np.asarray([Symbol(x).embedding for x in self.value])
                    else:
                        # convert to numpy array
                        self._metadata.embedding = np.asarray(self.value)
                else:
                    # convert to numpy array
                    self._metadata.embedding = np.asarray(self.value)
            elif isinstance(self.value, torch.Tensor):
                self._metadata.embedding = self.value.detach().cpu().numpy()
            else:
                # compute the embedding and store as numpy array
                self._metadata.embedding = np.asarray(self.embed().value)
        if isinstance(self._metadata.embedding, list):
            self._metadata.embedding = np.asarray(self._metadata.embedding)
        # return the embedding
        return self._metadata.embedding

    def _ensure_numpy_format(self, x, cast=False):
        # if it is a Symbol, get its value
        if not isinstance(x, np.ndarray) or not isinstance(x, torch.Tensor) or not isinstance(x, list):
            if not isinstance(x, self._symbol_type): #@NOTE: enforce Symbol to avoid circular import
                if not cast:
                    raise TypeError(f'Cannot compute similarity with type {type(x)}')
                x = self._symbol_type(x)
            # evaluate the Symbol as an embedding
            x = x.embedding
        # if it is a list, convert it to numpy
        if isinstance(x, list) or isinstance(x, tuple):
            assert len(x) > 0, 'Cannot compute similarity with empty list'
            x = np.asarray(x)
        # if it is a tensor, convert it to numpy
        elif isinstance(x, torch.Tensor):
            x = x.detach().cpu().numpy()
        return x.squeeze()[:, None]

    def similarity(self, other: Union['Symbol', list, np.ndarray, torch.Tensor], metric: Union['cosine', 'angular-cosine', 'product', 'manhattan', 'euclidean', 'minkowski', 'jaccard'] = 'cosine', eps: float = 1e-8, normalize: Optional[Callable] = None, **kwargs) -> float:
        '''
        Calculates the similarity between two Symbol objects using a specified metric.
        This method compares the values of two Symbol objects and calculates their similarity according to the specified metric.
        It supports the 'cosine' metric, and raises a NotImplementedError for other metrics.

        Args:
            other (Symbol): The other Symbol object to calculate the similarity with.
            metric (Optional[str]): The metric to use for calculating the similarity. Defaults to 'cosine'.
            eps (float): A small value to avoid division by zero.
            normalize (Optional[Callable]): A function to normalize the Symbol's value before calculating the similarity. Defaults to None.
            **kwargs: Additional keyword arguments for the @core.similarity decorator.

        Returns:
            float: The similarity value between the two Symbol objects.

        Raises:
            TypeError: If any of the Symbol objects is not of type np.ndarray or Symbol.
            NotImplementedError: If the given metric is not supported.
        '''
        v = self._ensure_numpy_format(self)
        if isinstance(other, list) or isinstance(other, tuple):
            o = []
            for i in range(len(other)):
                o.append(self._ensure_numpy_format(other[i], cast=True))
            o = np.concatenate(o, axis=1)
        else:
            o = self._ensure_numpy_format(other, cast=True)

        if   metric == 'cosine':
            val     = v.T@o / (np.sqrt(v.T@v) * np.sqrt(o.T@o) + eps)
        elif metric == 'angular-cosine':
            c       = kwargs.get('c', 1)
            val     = 1 - (c * np.arccos((v.T@o / (np.sqrt(v.T@v) * np.sqrt(o.T@o) + eps))) / np.pi)
        elif metric == 'product':
            val     = v.T@o
        elif metric == 'manhattan':
            val     = np.abs(v - o).sum(axis=0, keepdims=True)
        elif metric == 'euclidean':
            val     = np.sqrt(np.sum((v - o)**2, axis=0, keepdims=True))
        elif metric == 'minkowski':
            p       = kwargs.get('p', 3)
            val     = np.sum(np.abs(v - o)**p, axis=0, keepdims=True)**(1/p)
        elif metric == 'jaccard':
            intersection = np.minimum(v, o)
            union = np.maximum(v, o)
            val = np.sum(intersection, axis=0, keepdims=True) / (np.sum(union, axis=0, keepdims=True) + eps)
        else:
            raise NotImplementedError(f"Similarity metric {metric} not implemented. Available metrics: 'cosine', 'angular-cosine', 'product', 'manhattan', 'euclidean', 'minkowski', 'jaccard'")

        # get the similarity value(s)
        shape = val.shape
        if len(shape) >= 2 and min(shape) > 1: val = val.diagonal()
        elif len(shape) >= 1 and shape[0] > 1: val = val
        else:                                  val = val.item()
        if normalize is not None:              val = normalize(val)

        return val

    def distance(self, other: Union['Symbol', list, np.ndarray, torch.Tensor], kernel: Union['gaussian', 'rbf', 'laplacian', 'polynomial', 'sigmoid', 'linear', 'cauchy', 't-distribution', 'inverse-multiquadric', 'cosine', 'angular-cosine', 'frechet', 'mmd'] = 'gaussian',  eps: float = 1e-8, normalize: Optional[Callable] = None, **kwargs) -> float:
        '''
        Calculates the kernel between two Symbol objects.

        Args:
            other (Symbol): The other Symbol object to calculate the kernel with.
            kernel (Optional[str]): The function to use for calculating the kernel. Defaults to 'gaussian'.
            normalize (Optional[Callable]): A function to normalize the Symbol's value before calculating the kernel. Defaults to None.
            **kwargs: Additional keyword arguments for the kernel arguments (e.g. gamma, coef).

        Returns:
            float: The kernel value between the two Symbol objects.

        Raises:
            TypeError: If any of the Symbol objects is not of type np.ndarray or Symbol.
            NotImplementedError: If the given kernel is not supported.
        '''
        v = self._ensure_numpy_format(self)
        if isinstance(other, list) or isinstance(other, tuple):
            o = []
            for i in range(len(other)):
                o.append(self._ensure_numpy_format(other[i], cast=True))
            o = np.concatenate(o, axis=1)
        else:
            o = self._ensure_numpy_format(other, cast=True)

        # compute the kernel value
        if   kernel == 'gaussian':
            gamma   = kwargs.get('gamma', 1)
            val     = np.exp(-gamma * np.sum((v - o)**2, axis=0))
        elif kernel == 'rbf':
            # vectors are expected to be normalized
            bandwidth = kwargs.get('bandwidth', None)
            gamma     = kwargs.get('gamma', 1)
            d         = np.sum((v - o)**2, axis=0)
            if bandwidth is not None:
                val   = 0
                for a in bandwidth:
                    gamma = 1.0 / (2 * a)
                    val  += np.exp(-gamma * d)
            else:
                # if no bandwidth is given, default to the gaussian kernel
                val = np.exp(-gamma * d)
        elif kernel == 'laplacian':
            gamma   = kwargs.get('gamma', 1)
            val     = np.exp(-gamma * np.sum(np.abs(v - o), axis=0))
        elif kernel == 'polynomial':
            gamma   = kwargs.get('gamma', 1)
            degree  = kwargs.get('degree', 3)
            coef    = kwargs.get('coef', 1)
            val     = (gamma * np.sum((v * o), axis=0) + coef)**degree
        elif kernel == 'sigmoid':
            gamma   = kwargs.get('gamma', 1)
            coef    = kwargs.get('coef', 1)
            val     = np.tanh(gamma * np.sum((v * o), axis=0) + coef)
        elif kernel == 'linear':
            val     = np.sum((v * o), axis=0)
        elif kernel == 'cauchy':
            gamma   = kwargs.get('gamma', 1)
            val     = 1 / (1 + np.sum((v - o)**2, axis=0) / gamma)
        elif kernel == 't-distribution':
            gamma   = kwargs.get('gamma', 1)
            degree  = kwargs.get('degree', 1)
            val     = 1 / (1 + (np.sum((v - o)**2, axis=0) / (gamma * degree))**(degree + 1) / 2)
        elif kernel == 'inverse-multiquadric':
            gamma   = kwargs.get('gamma', 1)
            val     = 1 / np.sqrt(np.sum((v - o)**2, axis=0) / gamma**2 + 1)
        elif kernel == 'cosine':
            val     = 1 - (np.sum(v * o, axis=0) / (np.sqrt(np.sum(v**2, axis=0)) * np.sqrt(np.sum(o**2, axis=0)) + eps))
        elif kernel == 'angular-cosine':
            c       = kwargs.get('c', 1)
            val     = c * np.arccos((np.sum(v * o, axis=0) / (np.sqrt(np.sum(v**2, axis=0)) * np.sqrt(np.sum(o**2, axis=0)) + eps))) / np.pi
        elif kernel == 'frechet':
            sigma1  = kwargs.get('sigma1', None)
            sigma2  = kwargs.get('sigma2', None)
            assert sigma1 is not None and sigma2 is not None, 'Frechet distance requires covariance matrices for both inputs'
            v       = v.T
            o       = o.T
            val     = calculate_frechet_distance(v, sigma1, o, sigma2, eps)
        elif kernel == 'mmd':
            v       = v.T
            o       = o.T
            val     = calculate_mmd(v, o, eps=eps)
        else:
            raise NotImplementedError(f"Kernel function {kernel} not implemented. Available functions: 'gaussian'")

        # get the kernel value(s)
        shape = val.shape
        if len(shape) >= 1 and shape[0] > 1: val = val
        else:                                val = val.item()
        if normalize is not None:            val = normalize(val)
        return val

    def zip(self, **kwargs) -> List[Tuple[str, List, Dict]]:
        '''
        Zips the Symbol's value with its embeddings and a query containing the value.
        This method zips the Symbol's value along with its embeddings and a query containing the value.

        Args:
            **kwargs: Additional keyword arguments for the `embed` method.

        Returns:
            List[Tuple[str, List, Dict]]: A list of tuples containing a unique ID, the value's embeddings, and a query containing the value.

        Raises:
            ValueError: If the Symbol's value is not a string or list of strings.
        '''
        if isinstance(self.value, str):
            self._value = [self.value]
        elif isinstance(self.value, list):
            pass
        else:
            raise ValueError(f'Expected id to be a string, got {type(self.value)}')

        embeds = self.embed(**kwargs).value
        idx    = [str(uuid.uuid4()) for _ in range(len(self.value))]
        query  = [{'text': str(self.value[i])} for i in range(len(self.value))]

        # convert embeds to list if it is a tensor or numpy array
        if type(embeds) == np.ndarray:
            embeds = embeds.tolist()
        elif type(embeds) == torch.Tensor:
            embeds = embeds.cpu().numpy().tolist()

        return list(zip(idx, embeds, query))


class IOHandlingPrimitives(Primitive):
    '''
    This mixin contains functionalities related to input/output operations.
    '''
    def input(self, message: str = 'Please add more information', **kwargs) -> 'Symbol':
        '''
        Request user input and return a Symbol containing the user input.

        Args:
            message (str, optional): The message displayed to request the user input. Defaults to 'Please add more information'.
            **kwargs: Additional keyword arguments to be passed to the `@core.userinput` decorator.

        Returns:
            Symbol: The resulting Symbol after receiving the user input.

        Examples:
        --------
        >>> from symai import Symbol
        >>> s = Symbol().input('Please enter your name')
        >>> [output: 'John']

        >>> s = Symbol('I was born in')
        >>> s = s.input('Please enter the year of your birth')
        >>> [output: 'I was born in 1990'] # if Symbol has a <str> value inputs will be concatenated

        # Works identically for the `Expression` class
        '''
        @core.userinput(**kwargs)
        def _func(_, message) -> str:
            pass

        res = _func(self, message)
        condition = self.value is not None and isinstance(self.value, str)

        if hasattr(self, 'sym_return_type'):
            return self.sym_return_type(self.value if condition else '') | res
        return self._to_type(self.value if condition else '') | self._to_type(res)

    def open(self, path: str = None, **kwargs) -> 'Symbol':
        '''
        Open a file and store its content in an Expression object as a string.

        Args:
            path (str): The path to the file that needs to be opened.
            **kwargs: Arbitrary keyword arguments to be used by the core.opening decorator.

        Returns:
            Symbol: An Expression object containing the content of the file as a string value.

        Examples:
        --------
        >>> from symai import Symbol
        >>> s = Symbol().open('file.txt')

        >>> s = Symbol('file.txt')
        >>> s = s.open()

        # Works identically for the `Expression` class
        '''

        path = path if path is not None else self.value
        if path is None:
            raise ValueError('Path is not provided; either provide a path or set the value of the Symbol to the path')

        @core.opening(path=path, **kwargs)
        def _func(_):
            pass

        if hasattr(self, 'sym_return_type'):
            return self.sym_return_type(_func(self))
        return self._to_type(_func(self))


#@TODO: add tests
class IndexingPrimitives(Primitive):
    '''
    This mixin contains functionalities related to indexing symbols locally.
    '''
    def config(self, path: str, index_name: str, **kwargs) -> 'Symbol':
        '''Execute a configuration operation on the index.'''
        @core.index(prompt=path, index_name=index_name, operation='config', **kwargs)
        def _func(_):
            pass
        return _func(self)

    def add(self, doc: list[str], index_name: str, **kwargs) -> 'Symbol':
        '''Add an entry to the existing index.'''
        @core.index(prompt=doc, index_name=index_name, operation='add', **kwargs)
        def _func(_):
            pass
        return _func(self)

    def get(self, query: list[str], index_name: str, **kwargs) -> 'Symbol':
        '''Search the index based on the provided query.'''
        @core.index(prompt=query, index_name=index_name, operation='search', **kwargs)
        def _func(_):
            pass
        return _func(self)


class PersistencePrimitives(Primitive):
    '''
    This mixin contains functionalities related to expanding symbols and saving/loading symbols to/from disk.
    Future functionalities in this mixin might include different ways of serialization and deserialization, or more complex expansion techniques etc.
    '''
    def expand(self, *args, **kwargs) -> str:
        '''
        Expand the current Symbol and create a new sub-component.
        The function writes a self-contained function (with all imports) to solve a specific user problem task.
        This method uses the `@core.expand` decorator with a maximum token limit of 2048, and allows additional keyword
        arguments to be passed to the decorator.

        Args:
            *args: Additional arguments for the `@core.expand` decorator.
            **kwargs: Additional keyword arguments for the `@core.expand` decorator.

        Returns:
            Symbol: The name of the newly created sub-component.
        '''
        @core.expand(**kwargs)
        def _func(_, *args): pass

        _tmp_llm_func = self._to_type(_func(self, *args))
        func_name = str(_tmp_llm_func.extract('function name'))

        def _llm_func(*args, **kwargs):
            res = _tmp_llm_func.fexecute(*args, **kwargs)

            return res['locals'][func_name]()

        setattr(self, func_name, _llm_func)

        return func_name

    def save(self, path: str, replace: Optional[bool] = False, serialize: Optional[bool] = True) -> None:
        '''
        Save the current Symbol to a file.

        Args:
            path (str): The filepath of the saved file.
            replace (Optional[bool]): Whether to replace the file if it already exists. Defaults to False.
            serialize (Optional[bool]): Whether to serialize the object via pickle instead of writing the string. Defaults to True.

        Returns:
            Symbol: The current Symbol.
        '''
        file_path = path

        if not replace:
            cnt = 0
            while os.path.exists(file_path):
                filename, file_extension = os.path.splitext(path)
                file_path = f'{filename}_{cnt}{file_extension}'
                cnt += 1

        if serialize:
            # serialize the object via pickle instead of writing the string
            path_ = str(file_path) + '.pkl' if not str(file_path).endswith('.pkl') else str(file_path)
            with open(path_, 'wb') as f:
                pickle.dump(self, file=f)
        else:
            with open(str(file_path), 'w') as f:
                f.write(str(self))

    def load(self, path: str) -> Any:
        '''
        Load a Symbol from a file.

        Args:
            path (str): The filepath of the saved file.

        Returns:
            Symbol: The loaded Symbol.
        '''
        with open(path, 'rb') as f:
            obj = pickle.load(f)
        return obj


class OutputHandlingPrimitives(Primitive):
    '''
    This mixin include functionalities related to outputting symbols. It can be expanded in the future to include different types of output methods or complex output formatting, etc.
    '''

    def output(self, *args, **kwargs) -> 'Symbol':
        '''
        Output the current Symbol to an output handler.
        This method uses the `@core.output` decorator and allows additional keyword arguments to be passed to the decorator.

        Args:
            *args: Additional arguments for the `@core.output` decorator.
            **kwargs: Additional keyword arguments for the `@core.output` decorator.

        Returns:
            Symbol: The resulting Symbol after the output operation.
        '''
        @core.output(**kwargs)
        def _func(_, *func_args, **func_kwargs):
            return self.value

        return self._to_type(_func(self, self.value, *args))


#@TODO: add tests
class FineTuningPrimitives(Primitive):
    '''
    This mixin contains functionalities related to fine tuning models.
    '''
    def tune(self, operation: str = 'create', **kwargs) -> 'Symbol':
        '''
        Fine tune a base model.

        Args:
            operation (str, optional): The specific operation to be performed. Defaults to 'create'.
            **kwargs: Additional keyword arguments to be passed to the `@core.tune` decorator dependent on the used operation.

        Returns:
            Symbol: The resulting Symbol containing the fine tuned model ID.
        '''
        @core.tune(operation=operation, **kwargs)
        def _func(_, *args, **kwargs) -> str:
            pass
        return self.sym_return_type(_func(self))

    @property
    def data(self) -> torch.Tensor:
        '''
        Get the data as a Pytorch tensor.

        Returns:
            Any: The data of the symbol.
        '''
        # if the data is not yet computed, compute it
        if self._metadata.data is None:
            # compute the data and store as numpy array
            self._metadata.data = self.embedding
        # if the data is a tensor, return it
        if isinstance(self._metadata.data, torch.Tensor):
            # return tensor
            return self._metadata.data
        # if the data is a numpy array, convert it to tensor
        elif isinstance(self._metadata.data, np.ndarray):
            # convert to tensor
            self._metadata.data = torch.from_numpy(self._metadata.data)
            return self._metadata.data
        else:
            raise TypeError(f'Expected data to be a tensor or numpy array, got {type(self._metadata.data)}')

    @data.setter
    def data(self, data: torch.Tensor) -> None:
        '''
        Set the data of the symbol.

        Args:
            data (torch.Tensor): The data to set.
        '''
        self._metadata.data = data

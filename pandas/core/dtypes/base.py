"""
Extend pandas with custom array types.
"""

from functools import lru_cache
from typing import TYPE_CHECKING, Any, List, Optional, Tuple, Type, Union

import numpy as np

from pandas._typing import DtypeObj
from pandas.errors import AbstractMethodError

from pandas.core.dtypes.generic import ABCDataFrame, ABCIndexClass, ABCSeries

if TYPE_CHECKING:
    from pandas.core.arrays import ExtensionArray  # noqa: F401


class ExtensionDtype:
    """
    A custom data type, to be paired with an ExtensionArray.

    .. versionadded:: 0.23.0

    See Also
    --------
    extensions.register_extension_dtype
    extensions.ExtensionArray

    Notes
    -----
    The interface includes the following abstract methods that must
    be implemented by subclasses:

    * type
    * name

    The following attributes and methods influence the behavior of the dtype in
    pandas operations

    * _is_numeric
    * _is_boolean
    * _get_common_dtype

    Optionally one can override construct_array_type for construction
    with the name of this dtype via the Registry. See
    :meth:`extensions.register_extension_dtype`.

    * construct_array_type

    The `na_value` class attribute can be used to set the default NA value
    for this type. :attr:`numpy.nan` is used by default.

    ExtensionDtypes are required to be hashable. The base class provides
    a default implementation, which relies on the ``_metadata`` class
    attribute. ``_metadata`` should be a tuple containing the strings
    that define your data type. For example, with ``PeriodDtype`` that's
    the ``freq`` attribute.

    **If you have a parametrized dtype you should set the ``_metadata``
    class property**.

    Ideally, the attributes in ``_metadata`` will match the
    parameters to your ``ExtensionDtype.__init__`` (if any). If any of
    the attributes in ``_metadata`` don't implement the standard
    ``__eq__`` or ``__hash__``, the default implementations here will not
    work.

    .. versionchanged:: 0.24.0

       Added ``_metadata``, ``__hash__``, and changed the default definition
       of ``__eq__``.

    For interaction with Apache Arrow (pyarrow), a ``__from_arrow__`` method
    can be implemented: this method receives a pyarrow Array or ChunkedArray
    as only argument and is expected to return the appropriate pandas
    ExtensionArray for this dtype and the passed values::

        class ExtensionDtype:

            def __from_arrow__(
                self, array: Union[pyarrow.Array, pyarrow.ChunkedArray]
            ) -> ExtensionArray:
                ...

    This class does not inherit from 'abc.ABCMeta' for performance reasons.
    Methods and properties required by the interface raise
    ``pandas.errors.AbstractMethodError`` and no ``register`` method is
    provided for registering virtual subclasses.
    """

    _metadata: Tuple[str, ...] = ()

    def __str__(self) -> str:
        return self.name

    def __eq__(self, other: Any) -> bool:
        """
        Check whether 'other' is equal to self.

        By default, 'other' is considered equal if either

        * it's a string matching 'self.name'.
        * it's an instance of this type and all of the
          the attributes in ``self._metadata`` are equal between
          `self` and `other`.

        Parameters
        ----------
        other : Any

        Returns
        -------
        bool
        """
        if isinstance(other, str):
            try:
                other = self.construct_from_string(other)
            except TypeError:
                return False
        if isinstance(other, type(self)):
            return all(
                getattr(self, attr) == getattr(other, attr) for attr in self._metadata
            )
        return False

    def __hash__(self) -> int:
        return hash(tuple(getattr(self, attr) for attr in self._metadata))

    def __ne__(self, other: Any) -> bool:
        return not self.__eq__(other)

    @property
    def na_value(self) -> object:
        """
        Default NA value to use for this type.

        This is used in e.g. ExtensionArray.take. This should be the
        user-facing "boxed" version of the NA value, not the physical NA value
        for storage.  e.g. for JSONArray, this is an empty dictionary.
        """
        return np.nan

    @property
    def type(self) -> Type:
        """
        The scalar type for the array, e.g. ``int``

        It's expected ``ExtensionArray[item]`` returns an instance
        of ``ExtensionDtype.type`` for scalar ``item``, assuming
        that value is valid (not NA). NA values do not need to be
        instances of `type`.
        """
        raise AbstractMethodError(self)

    @property
    def kind(self) -> str:
        """
        A character code (one of 'biufcmMOSUV'), default 'O'

        This should match the NumPy dtype used when the array is
        converted to an ndarray, which is probably 'O' for object if
        the extension type cannot be represented as a built-in NumPy
        type.

        See Also
        --------
        numpy.dtype.kind
        """
        return "O"

    @property
    def name(self) -> str:
        """
        A string identifying the data type.

        Will be used for display in, e.g. ``Series.dtype``
        """
        raise AbstractMethodError(self)

    @property
    def names(self) -> Optional[List[str]]:
        """
        Ordered list of field names, or None if there are no fields.

        This is for compatibility with NumPy arrays, and may be removed in the
        future.
        """
        return None

    @classmethod
    def construct_array_type(cls) -> Type["ExtensionArray"]:
        """
        Return the array type associated with this dtype.

        Returns
        -------
        type
        """
        raise NotImplementedError

    @classmethod
    def construct_from_string(cls, string: str):
        r"""
        Construct this type from a string.

        This is useful mainly for data types that accept parameters.
        For example, a period dtype accepts a frequency parameter that
        can be set as ``period[H]`` (where H means hourly frequency).

        By default, in the abstract class, just the name of the type is
        expected. But subclasses can overwrite this method to accept
        parameters.

        Parameters
        ----------
        string : str
            The name of the type, for example ``category``.

        Returns
        -------
        ExtensionDtype
            Instance of the dtype.

        Raises
        ------
        TypeError
            If a class cannot be constructed from this 'string'.

        Examples
        --------
        For extension dtypes with arguments the following may be an
        adequate implementation.

        >>> @classmethod
        ... def construct_from_string(cls, string):
        ...     pattern = re.compile(r"^my_type\[(?P<arg_name>.+)\]$")
        ...     match = pattern.match(string)
        ...     if match:
        ...         return cls(**match.groupdict())
        ...     else:
        ...         raise TypeError(
        ...             f"Cannot construct a '{cls.__name__}' from '{string}'"
        ...         )
        """
        if not isinstance(string, str):
            raise TypeError(
                f"'construct_from_string' expects a string, got {type(string)}"
            )
        # error: Non-overlapping equality check (left operand type: "str", right
        #  operand type: "Callable[[ExtensionDtype], str]")  [comparison-overlap]
        assert isinstance(cls.name, str), (cls, type(cls.name))
        if string != cls.name:
            raise TypeError(f"Cannot construct a '{cls.__name__}' from '{string}'")
        return cls()

    @classmethod
    def is_dtype(cls, dtype: object) -> bool:
        """
        Check if we match 'dtype'.

        Parameters
        ----------
        dtype : object
            The object to check.

        Returns
        -------
        bool

        Notes
        -----
        The default implementation is True if

        1. ``cls.construct_from_string(dtype)`` is an instance
           of ``cls``.
        2. ``dtype`` is an object and is an instance of ``cls``
        3. ``dtype`` has a ``dtype`` attribute, and any of the above
           conditions is true for ``dtype.dtype``.
        """
        dtype = getattr(dtype, "dtype", dtype)
        if isinstance(dtype, str):
            dtype_or_str = dtype
        else:
            dtype_or_str = type(dtype)
        return _caching_is_type(dtype_or_str)

    @classmethod
    @lru_cache(128)
    def _caching_is_type(cls, dtype_or_str):
        """Check if dtype_or_str is a dtype class or string that can build one."""
        if dtype_or_str is None:
            return False

        # use a low level check for str dtypes to avoid the overloaded __isinstance__ logic in dtypes
        arg_type = type(dtype_or_str)
        if type(arg_type) is not type and str in type(dtype_or_str).mro():
            try:
                return cls.construct_from_string(dtype_or_str) is not None
            except TypeError:
                return False
        # now we know we have some dtype class so can use issubclass

        if issubclass(dtype_or_str, (ABCSeries, ABCIndexClass, ABCDataFrame, np.dtype)):
            # https://github.com/pandas-dev/pandas/issues/22960
            # avoid passing data to `construct_from_string`. This could
            # cause a FutureWarning from numpy about failing elementwise
            # comparison from, e.g., comparing DataFrame == 'category'.
            return False

        # this could be fun - need to cache for each class, could be expressed as _cache[cls] = lru_cache(test, cls)
        if issubclass(dtype_or_str, cls):
            return True

        return False

    @property
    def _is_numeric(self) -> bool:
        """
        Whether columns with this dtype should be considered numeric.

        By default ExtensionDtypes are assumed to be non-numeric.
        They'll be excluded from operations that exclude non-numeric
        columns, like (groupby) reductions, plotting, etc.
        """
        return False

    @property
    def _is_boolean(self) -> bool:
        """
        Whether this dtype should be considered boolean.

        By default, ExtensionDtypes are assumed to be non-numeric.
        Setting this to True will affect the behavior of several places,
        e.g.

        * is_bool
        * boolean indexing

        Returns
        -------
        bool
        """
        return False

    def _get_common_dtype(self, dtypes: List[DtypeObj]) -> Optional[DtypeObj]:
        """
        Return the common dtype, if one exists.

        Used in `find_common_type` implementation. This is for example used
        to determine the resulting dtype in a concat operation.

        If no common dtype exists, return None (which gives the other dtypes
        the chance to determine a common dtype). If all dtypes in the list
        return None, then the common dtype will be "object" dtype (this means
        it is never needed to return "object" dtype from this method itself).

        Parameters
        ----------
        dtypes : list of dtypes
            The dtypes for which to determine a common dtype. This is a list
            of np.dtype or ExtensionDtype instances.

        Returns
        -------
        Common dtype (np.dtype or ExtensionDtype) or None
        """
        if len(set(dtypes)) == 1:
            # only itself
            return self
        else:
            return None


def register_extension_dtype(cls: Type[ExtensionDtype]) -> Type[ExtensionDtype]:
    """
    Register an ExtensionType with pandas as class decorator.

    .. versionadded:: 0.24.0

    This enables operations like ``.astype(name)`` for the name
    of the ExtensionDtype.

    Returns
    -------
    callable
        A class decorator.

    Examples
    --------
    >>> from pandas.api.extensions import register_extension_dtype
    >>> from pandas.api.extensions import ExtensionDtype
    >>> @register_extension_dtype
    ... class MyExtensionDtype(ExtensionDtype):
    ...     name = "myextension"
    """
    registry.register(cls)
    return cls


class Registry:
    """
    Registry for dtype inference.

    The registry allows one to map a string repr of a extension
    dtype to an extension dtype. The string alias can be used in several
    places, including

    * Series and Index constructors
    * :meth:`pandas.array`
    * :meth:`pandas.Series.astype`

    Multiple extension types can be registered.
    These are tried in order.
    """

    def __init__(self):
        self.dtypes: List[Type[ExtensionDtype]] = []

    def register(self, dtype: Type[ExtensionDtype]) -> None:
        """
        Parameters
        ----------
        dtype : ExtensionDtype class
        """
        if not issubclass(dtype, ExtensionDtype):
            raise ValueError("can only register pandas extension dtypes")

        self.dtypes.append(dtype)

    def find(
        self, dtype: Union[Type[ExtensionDtype], str]
    ) -> Optional[Type[ExtensionDtype]]:
        """
        Parameters
        ----------
        dtype : Type[ExtensionDtype] or str

        Returns
        -------
        return the first matching dtype, otherwise return None
        """
        if not isinstance(dtype, str):
            dtype_type = dtype
            if not isinstance(dtype, type):
                dtype_type = type(dtype)
            if issubclass(dtype_type, ExtensionDtype):
                return dtype

            return None

        for dtype_type in self.dtypes:
            try:
                return dtype_type.construct_from_string(dtype)
            except TypeError:
                pass

        return None


registry = Registry()

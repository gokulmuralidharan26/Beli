from __future__ import annotations

from typing import Iterable, Protocol

from ..models import Transaction


class TransactionSource(Protocol):
    """The input layer.  Anything that yields Transactions can drive the pipeline.

    To switch to Plaid later, write a PlaidSource with a fetch() that maps Plaid
    transactions to Transaction (using Plaid's own category as `category`) and
    pass it to the pipeline in cli.py.  Nothing else changes.
    """

    def fetch(self) -> Iterable[Transaction]: ...

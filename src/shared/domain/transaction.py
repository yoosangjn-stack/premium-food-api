from abc import ABC, abstractmethod

class TransactionManager(ABC):
    """응용 서비스가 저장 확정/취소를 요청하는 작은 계약."""
    @abstractmethod
    async def commit(self) -> None: ...

    @abstractmethod
    async def rollback(self) -> None: ...

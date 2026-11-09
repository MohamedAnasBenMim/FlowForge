import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from flowforge.database import Base
from flowforge.queue import MemoryExecutionQueue


@pytest.fixture
def session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as database_session:
        yield database_session


@pytest.fixture
def queue():
    return MemoryExecutionQueue()

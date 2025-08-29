from dataclasses import dataclass, field
from typing import Any


@dataclass
class AwsProvider:
    dynamodb: Any
    tables: dict = field(default_factory=dict)

    def get_table(self, name: str):
        if name not in self.tables:
            self.tables[name] = self.dynamodb.Table(name)
        return self.tables[name]

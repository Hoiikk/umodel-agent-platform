"""Read-only MySQL. One pool per storage target. Tests pass runner and never open a socket."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from ..errors import NotConfigured
from ..secret_resolver import SecretResolver
from ..security_guard import SecurityGuard
from .base import FetchPlan

Runner = Callable[[FetchPlan], Awaitable[list[dict[str, Any]]]]


class MysqlExecutor:
    def __init__(self, guard: SecurityGuard, secrets: SecretResolver, runner: Runner | None = None) -> None:
        self._guard = guard
        self._secrets = secrets
        self._runner = runner
        self._pools: dict[tuple[Any, ...], Any] = {}

    async def execute(self, plan: FetchPlan) -> list[dict[str, Any]]:
        self._guard.validate_sql(plan.sql)
        if self._runner is not None:
            return await self._runner(plan)
        target = plan.mysql_target or {}
        if not plan.credential_ref or not target:
            raise NotConfigured("mysql", ["credential_ref", "endpoint"])
        pool = await self._pool(plan, target)
        async with pool.acquire() as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(plan.sql, plan.params)
                fetched = await cursor.fetchall()
                columns = [item[0] for item in cursor.description or ()]
        return [dict(zip(columns, row)) for row in fetched]

    async def _pool(self, plan: FetchPlan, target: dict[str, Any]) -> Any:
        key = (
            target.get("host"),
            int(target.get("port") or 3306),
            target.get("database"),
            target.get("username"),
            plan.credential_ref,
        )
        if key not in self._pools:
            try:
                import aiomysql
            except ImportError as exc:
                raise NotConfigured("mysql driver", ["aiomysql"]) from exc
            password = self._secrets.resolve(plan.credential_ref)
            self._pools[key] = await aiomysql.create_pool(
                host=key[0],
                port=key[1],
                db=key[2],
                user=key[3],
                password=password,
                charset="utf8mb4",
                autocommit=True,
                minsize=1,
                maxsize=4,
            )
        return self._pools[key]

    async def close(self) -> None:
        for pool in self._pools.values():
            pool.close()
        for pool in self._pools.values():
            await pool.wait_closed()

"""
Асинхронный клиент для FreeSWITCH ESL (Event Socket Library).
"""

import asyncio
import logging

logger = logging.getLogger(__name__)


class ESLClient:
    """Асинхронный клиент для подключения к FreeSWITCH ESL."""

    def __init__(self, host: str, port: int, password: str, timeout: float = 10.0):
        self.host = host
        self.port = port
        self.password = password
        self.timeout = timeout
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._authenticated = False

    async def connect(self) -> bool:
        """Устанавливает соединение и авторизуется."""
        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port), timeout=self.timeout
            )
            welcome = await self._read_line()
            if not welcome or "Content-Type: auth/request" not in welcome:
                raise Exception("Invalid ESL greeting")
            await self._send_command(f"auth {self.password}")
            auth_response = await self._read_line()
            if "+OK" not in auth_response:
                raise Exception("Authentication failed")
            self._authenticated = True
            logger.info(
                "ESL client connected and authenticated",
                extra={"host": self.host, "port": self.port},
            )
            return True
        except Exception as e:
            logger.error("ESL connection failed", error=str(e))
            return False

    async def disconnect(self):
        if self._writer:
            self._writer.close()
            await self._writer.wait_closed()
        self._authenticated = False

    async def _send_command(self, cmd: str) -> None:
        if not self._writer:
            raise Exception("Not connected")
        self._writer.write(f"{cmd}\n\n".encode())
        await self._writer.drain()

    async def _read_line(self) -> str:
        line = await self._reader.readline()
        return line.decode().strip()

    async def api(self, command: str) -> str:
        if not self._authenticated:
            raise Exception("Not authenticated")
        await self._send_command(f"api {command}")
        response_lines = []
        while True:
            line = await self._read_line()
            if line == "":
                break
            response_lines.append(line)
        return "\n".join(response_lines)

    async def originate(
        self, destination: str, context: str = "default", extension: str = "s"
    ) -> dict:
        cmd = f"originate {{origination_caller_id_name=MassRecruitHub}}{destination} &playback({extension})"
        response = await self.api(cmd)
        if "+OK" in response:
            parts = response.split()
            call_id = parts[1] if len(parts) > 1 else None
            return {"success": True, "call_id": call_id, "response": response}
        else:
            return {"success": False, "error": response}

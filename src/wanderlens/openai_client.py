from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request
from pathlib import Path

from wanderlens.media import jpeg_data_url
from wanderlens.paths import prompt_path
from wanderlens.semantic import extract_json_object, normalize_semantic


class OpenAICompatibleClient:
    """呼叫本機 vLLM、SGLang、Ollama 或其他 OpenAI 相容服務。"""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        timeout: float,
        max_edge: int,
        send_disable_thinking: bool,
        prompt: str | None = None,
    ) -> None:
        self.base_url = base_url
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.max_edge = max_edge
        self.send_disable_thinking = send_disable_thinking
        self.prompt = prompt if prompt is not None else prompt_path().read_text(encoding="utf-8")

    def describe_image(self, path: Path) -> dict:
        payload = self._post(self._payload(path))
        return normalize_semantic(extract_json_object(message_text(payload)))

    def _payload(self, path: Path) -> dict:
        text = self.prompt.strip()
        if self.send_disable_thinking:
            text = "/no_think\n" + text
        body = {
            "model": self.model,
            "temperature": 0.2,
            "max_tokens": 2048,
            "messages": [
                {
                    "role": "system",
                    "content": "你只輸出一個 JSON 物件，不要加入其他文字。",
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": text},
                        {
                            "type": "image_url",
                            "image_url": {"url": jpeg_data_url(path, self.max_edge)},
                        },
                    ],
                },
            ],
        }
        if self.send_disable_thinking:
            body["chat_template_kwargs"] = {"enable_thinking": False}
        return body

    def _post(self, payload: dict) -> dict:
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            chat_url(self.base_url),
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "ignore")[:500]
            raise RuntimeError(f"模型服務回覆 HTTP {exc.code}：{detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"無法連線到模型服務：{exc.reason}") from exc
        except (TimeoutError, socket.timeout) as exc:
            raise RuntimeError("模型服務逾時。") from exc
        try:
            parsed = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise RuntimeError("模型服務的回應不是 JSON。") from exc
        if not isinstance(parsed, dict):
            raise RuntimeError("模型服務的回應不是 JSON 物件。")
        return parsed


def chat_url(base_url: str) -> str:
    base = base_url.rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    return base + "/chat/completions"


def message_text(payload: dict) -> str:
    choices = payload.get("choices") or []
    if not choices:
        raise ValueError("模型服務的回應沒有 choices。")
    message = choices[0].get("message") or {}
    content = message.get("content")
    if isinstance(content, list):
        content = "\n".join(
            part.get("text", "") for part in content if isinstance(part, dict)
        )
    if not isinstance(content, str) or not content.strip():
        reasoning = message.get("reasoning_content")
        if isinstance(reasoning, str) and reasoning.strip():
            content = reasoning
    if not isinstance(content, str) or not content.strip():
        raise ValueError("模型服務的回應沒有文字內容。")
    return content

from __future__ import annotations

import json
import os
from pathlib import Path

BASE_DIR = Path('/app/nanobot')
CONFIG_PATH = BASE_DIR / 'config.json'
RESOLVED_CONFIG_PATH = BASE_DIR / 'config.resolved.json'
WORKSPACE_PATH = BASE_DIR / 'workspace'


def _env(name: str, default: str | None = None) -> str | None:
    val = os.environ.get(name)
    if val is None or val == '':
        return default
    return val


def _set_path(obj: dict, path: list[str], value: object) -> None:
    cur = obj
    for key in path[:-1]:
        if not isinstance(cur.get(key), dict):
            cur[key] = {}
        cur = cur[key]
    cur[path[-1]] = value


def _load_config() -> dict:
    with CONFIG_PATH.open('r', encoding='utf-8') as f:
        return json.load(f)


def _resolve_config() -> dict:
    cfg = _load_config()

    llm_api_key = _env('LLM_API_KEY')
    llm_api_base = _env('LLM_API_BASE_URL')
    llm_model = _env('LLM_API_MODEL')
    if llm_api_key:
        _set_path(cfg, ['providers', 'custom', 'apiKey'], llm_api_key)
    if llm_api_base:
        _set_path(cfg, ['providers', 'custom', 'apiBase'], llm_api_base)
    if llm_model:
        _set_path(cfg, ['agents', 'defaults', 'model'], llm_model)

    gateway_host = _env('NANOBOT_GATEWAY_CONTAINER_ADDRESS')
    gateway_port = _env('NANOBOT_GATEWAY_CONTAINER_PORT')
    if gateway_host:
        _set_path(cfg, ['gateway', 'host'], gateway_host)
    if gateway_port:
        _set_path(cfg, ['gateway', 'port'], int(gateway_port))

    lms_url = _env('NANOBOT_LMS_BACKEND_URL')
    lms_api_key = _env('NANOBOT_LMS_API_KEY')
    lms_env: dict[str, str] = {}
    if lms_url:
        lms_env['NANOBOT_LMS_BACKEND_URL'] = lms_url
    if lms_api_key:
        lms_env['NANOBOT_LMS_API_KEY'] = lms_api_key
    if lms_env:
        _set_path(cfg, ['tools', 'mcpServers', 'lms', 'env'], lms_env)

    webchat_host = _env('NANOBOT_WEBCHAT_CONTAINER_ADDRESS', '0.0.0.0')
    webchat_port = int(_env('NANOBOT_WEBCHAT_CONTAINER_PORT', '8765'))
    _set_path(cfg, ['channels', 'webchat', 'enabled'], True)
    _set_path(cfg, ['channels', 'webchat', 'host'], webchat_host)
    _set_path(cfg, ['channels', 'webchat', 'port'], webchat_port)
    _set_path(cfg, ['channels', 'webchat', 'allowFrom'], ['*'])

    victorialogs_url = _env('NANOBOT_VICTORIALOGS_URL', 'http://victorialogs:9428')
    victoriatraces_url = _env('NANOBOT_VICTORIATRACES_URL', 'http://victoriatraces:10428')
    _set_path(
        cfg,
        ['tools', 'mcpServers', 'obs'],
        {
            'command': 'python',
            'args': ['-m', 'mcp_obs'],
            'env': {
                'NANOBOT_VICTORIALOGS_URL': victorialogs_url,
                'NANOBOT_VICTORIATRACES_URL': victoriatraces_url,
            },
        },
    )

    relay_url = _env('NANOBOT_UI_RELAY_URL', 'http://127.0.0.1:8766')
    relay_token = _env('NANOBOT_UI_RELAY_TOKEN', _env('NANOBOT_ACCESS_KEY', ''))
    _set_path(
        cfg,
        ['tools', 'mcpServers', 'webchat'],
        {
            'command': 'python',
            'args': ['-m', 'mcp_webchat'],
            'env': {
                'NANOBOT_UI_RELAY_URL': relay_url,
                'NANOBOT_UI_RELAY_TOKEN': relay_token,
            },
        },
    )

    return cfg


def main() -> None:
    cfg = _resolve_config()
    RESOLVED_CONFIG_PATH.write_text(
        json.dumps(cfg, ensure_ascii=False, indent=2) + '\n',
        encoding='utf-8',
    )
    existing_pythonpath = os.environ.get('PYTHONPATH', '')
    os.environ['PYTHONPATH'] = (
        f"{BASE_DIR}:{existing_pythonpath}" if existing_pythonpath else str(BASE_DIR)
    )

    os.execvp(
        'nanobot',
        [
            'nanobot',
            'gateway',
            '--config',
            str(RESOLVED_CONFIG_PATH),
            '--workspace',
            str(WORKSPACE_PATH),
        ],
    )


if __name__ == '__main__':
    main()

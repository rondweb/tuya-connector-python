#!/usr/bin/env python3
"""FastAPI wrapper around the existing TuyaOpenAPI client.

Provides endpoints to:
- list devices (supports multiple ids)
- get device details (single id)
- send commands to one or more devices
- fetch logs for one or more devices

Configuration is read from environment variables:
- `TUYA_API_ENDPOINT`, `TUYA_ACCESS_ID`, `TUYA_ACCESS_KEY`.

Run: `uvicorn example.fastapi_tuya_api:app --reload`
"""
from typing import List, Optional, Dict, Any
import os

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from tuya_connector import TuyaOpenAPI


API_ENDPOINT = os.getenv("TUYA_API_ENDPOINT", "https://openapi.tuyaus.com")
ACCESS_ID = os.getenv("TUYA_ACCESS_ID", "fy7u3kxfsh4x4p5wc9p8")
ACCESS_KEY = os.getenv("TUYA_ACCESS_KEY", "b2542cf2f4234aee8a354e60059b3029")


class CommandItem(BaseModel):
	code: str
	value: Any


class CommandsRequest(BaseModel):
	device_ids: List[str]
	commands: List[CommandItem]


app = FastAPI(title="Tuya Connector FastAPI")


def _init_openapi() -> TuyaOpenAPI:
	openapi = TuyaOpenAPI(API_ENDPOINT, ACCESS_ID, ACCESS_KEY)
	try:
		openapi.connect()
	except Exception:
		# don't fail app startup if connect fails; calls will try to connect on demand
		pass
	return openapi


tuya = _init_openapi()


@app.get("/health")
def health():
	return {"status": "ok"}


@app.get("/devices")
def list_devices(ids: Optional[str] = Query(None, description="Comma separated device ids")):
	"""List devices. If `ids` provided (comma-separated), returns details for those ids.

	If `ids` is not provided calls Tuya Cloud list devices endpoint.
	"""
	try:
		if ids:
			device_ids = [i.strip() for i in ids.split(",") if i.strip()]
			results = {}
			for did in device_ids:
				resp = tuya.get(f"/v1.0/devices/{did}")
				results[did] = resp
			return results

		# fallback: try common list devices endpoint
		resp = tuya.get("/v1.0/iot-03/devices")
		if resp is None:
			raise HTTPException(status_code=502, detail="No response from Tuya API")
		return resp
	except HTTPException:
		raise
	except Exception as exc:
		raise HTTPException(status_code=500, detail=str(exc))


@app.get("/devices/{device_id}")
def get_device(device_id: str):
	"""Get details for a single device id."""
	try:
		resp = tuya.get(f"/v1.0/devices/{device_id}")
		if resp is None:
			raise HTTPException(status_code=502, detail="No response from Tuya API")
		return resp
	except HTTPException:
		raise
	except Exception as exc:
		raise HTTPException(status_code=500, detail=str(exc))


@app.post("/devices/commands")
def send_commands(payload: CommandsRequest):
	"""Send commands to one or more devices.

	The request body should be JSON with `device_ids` and `commands` (list of {code, value}).
	"""
	try:
		commands_payload = {"commands": [c.dict() for c in payload.commands]}
		results = {}
		for did in payload.device_ids:
			resp = tuya.post(f"/v1.0/devices/{did}/commands", commands_payload)
			results[did] = resp
		return results
	except Exception as exc:
		raise HTTPException(status_code=500, detail=str(exc))


@app.get("/devices/logs")
def get_logs(ids: Optional[str] = Query(None, description="Comma separated device ids")):
	"""Fetch logs for one or more devices.

	If `ids` provided, returns a mapping device_id -> logs response.
	"""
	try:
		if not ids:
			raise HTTPException(status_code=400, detail="Query parameter `ids` is required")

		device_ids = [i.strip() for i in ids.split(",") if i.strip()]
		results = {}
		for did in device_ids:
			# Common logs endpoint; if your project uses a different one, adjust here.
			resp = tuya.get(f"/v1.0/devices/{did}/logs")
			results[did] = resp
		return results
	except HTTPException:
		raise
	except Exception as exc:
		raise HTTPException(status_code=500, detail=str(exc))


if __name__ == "__main__":
	# Start with: `uvicorn example.fastapi_tuya_api:app --reload`
	import uvicorn

	uvicorn.run("example.fastapi_tuya_api:app", host="0.0.0.0", port=8000, reload=True)


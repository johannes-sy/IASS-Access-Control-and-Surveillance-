# IASS V1 Hardware API

Base path: `/api/v1/hardware`

## State

- `GET /devices`
- `GET /state`
- `GET /devices/{device_id}`

## Cameras

- `POST /cameras/{camera_id}/move` — `{pan, tilt, speed}`
- `POST /cameras/{camera_id}/track` — `{x, y, frame_width, frame_height}`
- `POST /cameras/{camera_id}/stop`
- `POST /cameras/{camera_id}/home`

## Doors

- `POST /doors/{door_id}/lock` — optional `{duration, reason}`
- `POST /doors/{door_id}/unlock` — optional `{duration, reason}`
- `GET /doors/{door_id}`

## Alarms

- `POST /alarms/{alarm_id}/trigger` — optional `{mode, duration, reason}`
- `POST /alarms/{alarm_id}/clear`
- `GET /alarms/{alarm_id}`

## Access

`POST /access/decide` accepts a semantic RFID/access decision. Credential values are never passed to a physical driver. The request is recorded in the access audit and the selected door is controlled through `HardwareController`.

## Audit

- `GET /commands`
- `GET /events`

All returned command results include success/failure, command ID, correlation ID, requested state and known actual state.

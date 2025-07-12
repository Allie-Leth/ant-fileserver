# API Reference

## Overview

The ANT Fileserver API provides RESTful endpoints for firmware file management. All API requests require authentication via API key.

## Base URL

```
Production: https://api.scopecreep.productions/api/v1/firmware
Staging: https://api-staging.scopecreep.productions/api/v1/firmware
Local: http://localhost:8000/api/v1/firmware
```

## Authentication

All firmware endpoints require API key authentication:

```http
X-API-Key: your-api-key-here
```

Example:
```bash
curl -H "X-API-Key: your-api-key" https://api.scopecreep.productions/api/v1/firmware
```

## Endpoints

### List Firmware Files

Returns a list of all firmware files with metadata.

**Endpoint:** `GET /api/v1/firmware`

**Headers:**
- `X-API-Key`: Required authentication key

**Query Parameters:**
- `prefix` (optional): Filter files by prefix
- `limit` (optional): Maximum number of results (default: 100)
- `offset` (optional): Pagination offset (default: 0)

**Response:**
```json
{
  "firmware": [
    {
      "filename": "device-v1.2.3.bin",
      "version": "1.2.3",
      "device_type": "sensor-module",
      "size": 524288,
      "checksum": "sha256:abcd1234...",
      "uploaded_at": "2024-01-15T10:30:00Z",
      "metadata": {
        "release_notes": "Bug fixes and improvements",
        "min_hardware_version": "2.0"
      }
    }
  ],
  "total": 1,
  "limit": 100,
  "offset": 0
}
```

**Status Codes:**
- `200 OK`: Success
- `401 Unauthorized`: Invalid or missing API key
- `500 Internal Server Error`: Server error

**Example:**
```bash
curl -H "X-API-Key: your-api-key" \
  "https://api.scopecreep.productions/api/v1/firmware?prefix=sensor&limit=10"
```

### Get Firmware Details

Retrieve metadata for a specific firmware file.

**Endpoint:** `GET /api/v1/firmware/<firmware_id>`

**Headers:**
- `X-API-Key`: Required authentication key

**Response:**
```json
{
  "filename": "device-v1.2.3.bin",
  "version": "1.2.3",
  "device_type": "sensor-module",
  "size": 524288,
  "checksum": "sha256:abcd1234...",
  "uploaded_at": "2024-01-15T10:30:00Z",
  "download_url": "/api/v1/firmware/device-v1.2.3.bin/download",
  "metadata": {
    "release_notes": "Bug fixes and improvements",
    "min_hardware_version": "2.0",
    "changelog": "- Fixed connectivity issue\n- Improved battery life"
  }
}
```

**Status Codes:**
- `200 OK`: Success
- `401 Unauthorized`: Invalid or missing API key
- `404 Not Found`: Firmware not found
- `500 Internal Server Error`: Server error

### Download Firmware

Download the actual firmware binary file.

**Endpoint:** `GET /api/v1/firmware/<firmware_id>/download`

**Headers:**
- `X-API-Key`: Required authentication key
- `Range` (optional): Byte range for partial downloads

**Response:**
- Binary firmware file
- Content-Type: `application/octet-stream`
- Content-Disposition: `attachment; filename="device-v1.2.3.bin"`

**Status Codes:**
- `200 OK`: Complete file
- `206 Partial Content`: Partial download (when Range header used)
- `401 Unauthorized`: Invalid or missing API key
- `404 Not Found`: Firmware not found
- `500 Internal Server Error`: Server error

**Example:**
```bash
curl -H "X-API-Key: your-api-key" \
  -o firmware.bin \
  "https://api.scopecreep.productions/api/v1/firmware/device-v1.2.3.bin/download"
```

### Upload Firmware

Upload a new firmware file with metadata.

**Endpoint:** `POST /api/v1/firmware`

**Headers:**
- `X-API-Key`: Required authentication key
- `Content-Type`: `multipart/form-data`

**Form Data:**
- `file`: Binary firmware file (required)
- `version`: Firmware version (required)
- `device_type`: Target device type (required)
- `metadata`: JSON string with additional metadata (optional)

**Request Example:**
```bash
curl -X POST \
  -H "X-API-Key: your-api-key" \
  -F "file=@firmware-v2.0.0.bin" \
  -F "version=2.0.0" \
  -F "device_type=sensor-module" \
  -F 'metadata={"release_notes":"Major update","min_hardware_version":"2.0"}' \
  "https://api.scopecreep.productions/api/v1/firmware"
```

**Response:**
```json
{
  "message": "Firmware uploaded successfully",
  "firmware": {
    "filename": "sensor-module-v2.0.0.bin",
    "version": "2.0.0",
    "device_type": "sensor-module",
    "size": 524288,
    "checksum": "sha256:efgh5678...",
    "uploaded_at": "2024-01-15T11:00:00Z"
  }
}
```

**Status Codes:**
- `201 Created`: Upload successful
- `400 Bad Request`: Invalid input
- `401 Unauthorized`: Invalid or missing API key
- `413 Payload Too Large`: File too large
- `415 Unsupported Media Type`: Invalid file type
- `500 Internal Server Error`: Server error

**Validation Rules:**
- Maximum file size: 100MB (configurable)
- Allowed extensions: `.bin`, `.hex`, `.img`
- Version format: Semantic versioning recommended
- Device type: Alphanumeric with hyphens

### Delete Firmware

Delete a firmware file from storage.

**Endpoint:** `DELETE /api/v1/firmware/<firmware_id>`

**Headers:**
- `X-API-Key`: Required authentication key

**Response:**
```json
{
  "message": "Firmware deleted successfully",
  "filename": "device-v1.2.3.bin"
}
```

**Status Codes:**
- `200 OK`: Deletion successful
- `401 Unauthorized`: Invalid or missing API key
- `404 Not Found`: Firmware not found
- `500 Internal Server Error`: Server error

**Example:**
```bash
curl -X DELETE \
  -H "X-API-Key: your-api-key" \
  "https://api.scopecreep.productions/api/v1/firmware/device-v1.2.3.bin"
```

## Health Check Endpoints

### Liveness Check

Basic health check for Kubernetes liveness probe.

**Endpoint:** `GET /health`

**Response:**
```json
{
  "status": "healthy"
}
```

**Status Codes:**
- `200 OK`: Service is alive

### Readiness Check

Comprehensive readiness check including storage connectivity.

**Endpoint:** `GET /ready`

**Response:**
```json
{
  "status": "ready",
  "checks": {
    "storage": "connected",
    "database": "connected"
  }
}
```

**Status Codes:**
- `200 OK`: Service is ready
- `503 Service Unavailable`: Service not ready

## Error Responses

All error responses follow a consistent format:

```json
{
  "error": "Error message",
  "code": "ERROR_CODE",
  "details": {
    "field": "Additional context"
  }
}
```

### Common Error Codes

| Code | Description |
|------|-------------|
| `UNAUTHORIZED` | Invalid or missing API key |
| `NOT_FOUND` | Resource not found |
| `VALIDATION_ERROR` | Input validation failed |
| `STORAGE_ERROR` | Storage operation failed |
| `SERVER_ERROR` | Internal server error |

## Rate Limiting

API requests are rate-limited per API key:

- **Staging**: 200 requests/minute
- **Production**: 500 requests/minute

Rate limit headers:
```
X-RateLimit-Limit: 500
X-RateLimit-Remaining: 499
X-RateLimit-Reset: 1642257600
```

## Versioning

The API uses URL versioning. Current version: `v1`

Future versions will be available at:
- `/api/v2/firmware`
- `/api/v3/firmware`

## SDKs and Examples

### Python Example

```python
import requests

API_KEY = "your-api-key"
BASE_URL = "https://api.scopecreep.productions/api/v1/firmware"

headers = {"X-API-Key": API_KEY}

# List firmware
response = requests.get(BASE_URL, headers=headers)
firmware_list = response.json()

# Upload firmware
files = {"file": open("firmware.bin", "rb")}
data = {
    "version": "1.0.0",
    "device_type": "sensor",
    "metadata": '{"release_notes": "Initial release"}'
}
response = requests.post(BASE_URL, headers=headers, files=files, data=data)

# Download firmware
response = requests.get(f"{BASE_URL}/firmware-v1.0.0.bin/download", 
                       headers=headers, stream=True)
with open("downloaded.bin", "wb") as f:
    for chunk in response.iter_content(chunk_size=8192):
        f.write(chunk)
```

### JavaScript Example

```javascript
const API_KEY = 'your-api-key';
const BASE_URL = 'https://api.scopecreep.productions/api/v1/firmware';

// List firmware
fetch(BASE_URL, {
  headers: { 'X-API-Key': API_KEY }
})
.then(response => response.json())
.then(data => console.log(data));

// Upload firmware
const formData = new FormData();
formData.append('file', fileInput.files[0]);
formData.append('version', '1.0.0');
formData.append('device_type', 'sensor');

fetch(BASE_URL, {
  method: 'POST',
  headers: { 'X-API-Key': API_KEY },
  body: formData
})
.then(response => response.json())
.then(data => console.log(data));
```

## Best Practices

1. **Security**
   - Store API keys securely
   - Use HTTPS for all requests
   - Rotate API keys regularly

2. **Performance**
   - Use pagination for large lists
   - Implement caching where appropriate
   - Use byte-range requests for large downloads

3. **Error Handling**
   - Implement retry logic for transient errors
   - Handle rate limiting gracefully
   - Log errors for debugging

4. **Versioning**
   - Always specify version in requests
   - Monitor deprecation notices
   - Test with new versions before migration
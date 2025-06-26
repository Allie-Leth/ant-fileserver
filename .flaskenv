FLASK_APP=app:create_app
FLASK_ENV=development          # enables --reload automatically
STORAGE_ENDPOINT=http://localhost:9000
STORAGE_BUCKET=firmware
STORAGE_ACCESS_KEY_ID=minio
STORAGE_SECRET_ACCESS_KEY=minio123
JWT_SECRET_KEY=dev-secret
API_KEY_ROLES={"dev-key":["admin","uploader"]}

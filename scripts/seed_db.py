from pathlib import Path
from dotenv import load_dotenv

# DEV HELPER TOOL
env_file = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(env_file, override=False)


from app import create_app
app = create_app("development")

if __name__ == "__main__":
    app.run(
        hosts="0.0.0.0",
        port=5000,
        debug=True,
        use_reloader=True,
    )